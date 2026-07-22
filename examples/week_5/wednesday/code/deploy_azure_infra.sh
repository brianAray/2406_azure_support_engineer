#!/bin/bash
# ====================================================================================
# Azure Infrastructure Deployment Script
# ====================================================================================
#
# Prerequisites:
#   1. Azure CLI (`az`) installed and authenticated via `az login`.
#   2. Active Azure Subscription selected (`az account set --subscription <ID>`).
#   3. Local execution from the `code/` directory containing Dockerfile & app code.
# ====================================================================================

set -e

# ------------------------------------------------------------------------------------
# Configuration & Variable Initialization
# Unique resource names are generated using $RANDOM to prevent naming collisions.
# ------------------------------------------------------------------------------------
RG_NAME="rg-banking-demo-prod-$RANDOM"
# If you encounter a "location is restricted" error (e.g. for PostgreSQL Flexible Server),
# update LOCATION to 'eastus2', 'westus2', or 'centralus'.
LOCATION="westus2"
VNET_NAME="vnet-banking-prod"
ACR_NAME="acrbankingdemo$RANDOM"
DB_SERVER_NAME="psql-banking-prod-$RANDOM"
APP_SERVICE_PLAN="asp-banking-prod-$RANDOM"
WEBAPP_NAME="app-banking-api-$RANDOM"
LOG_WORKSPACE="law-banking-prod-$RANDOM"
APP_INSIGHTS="appi-banking-prod-$RANDOM"

echo "============================================================"
echo "Starting Banking Microservice Infrastructure Deployment..."
echo "============================================================"

# ------------------------------------------------------------------------------------
# Step 0: Azure AD (Entra ID) App Registration Setup
# Creates an Identity representation in Azure AD to act as the OAuth2 / OIDC resource server.
# The FastAPI app will use this Client ID to validate incoming JWT Access Tokens.
# ------------------------------------------------------------------------------------
echo "0. Setting up Azure AD (Entra ID) Configuration..."
TENANT_ID=$(az account show --query tenantId -o tsv | tr -d '\r')
AAD_APP_NAME="app-banking-ad-$RANDOM"
CLIENT_ID=$(az ad app create --display-name "$AAD_APP_NAME" --query appId -o tsv 2>/dev/null | tr -d '\r' || echo "")

if [ -z "$CLIENT_ID" ]; then
    echo "Notice: Directory permissions restricted for App Registration creation."
    echo "Defaulting Client ID to Azure Resource Manager scope for token validation testing."
    CLIENT_ID="https://management.azure.com"
else
    echo "App Registration created successfully with Client ID: $CLIENT_ID"
fi

# ------------------------------------------------------------------------------------
# Step 1: Resource Group Creation
# Creates a logical container (rg-banking-demo-prod-XXXX) for all Azure resources
# ensuring clean lifecycle management and easy single-command teardown (`az group delete`).
# ------------------------------------------------------------------------------------
echo "1. Creating Azure Resource Group ($RG_NAME in $LOCATION)..."
az group create --name $RG_NAME --location $LOCATION

# ------------------------------------------------------------------------------------
# Step 2: Observability Platform Setup (Log Analytics & Application Insights)
# - Log Analytics Workspace (LAW): Centralized repository for all system logs & telemetry.
# - Application Insights: APM (Application Performance Monitoring) tool collecting
#   distributed traces, request metrics, dependency queries, and Python stack traces.
# ------------------------------------------------------------------------------------
echo "2. Provisioning Observability Platform (Log Analytics & Application Insights)..."
az monitor log-analytics workspace create --resource-group $RG_NAME --workspace-name $LOG_WORKSPACE
LAW_ID=$(az monitor log-analytics workspace show --resource-group $RG_NAME --workspace-name $LOG_WORKSPACE --query id -o tsv | tr -d '\r')

az monitor app-insights component create --app "$APP_INSIGHTS" --location "$LOCATION" --kind web --resource-group "$RG_NAME" --workspace "$LAW_ID"
APPINSIGHTS_CONN_STR=$(az monitor app-insights component show --app "$APP_INSIGHTS" --resource-group "$RG_NAME" --query connectionString -o tsv | tr -d '\r')

# ------------------------------------------------------------------------------------
# Step 3: Virtual Network (VNet) & Dedicated Subnet Provisioning
# Establishes a private isolated network (10.0.0.0/16) with 2 dedicated subnets:
#   - snet-webapp (10.0.2.0/24): Subnet delegated to 'Microsoft.Web/serverFarms' for Web App VNet integration.
#   - snet-db (10.0.3.0/24): Subnet delegated to 'Microsoft.DBforPostgreSQL/flexibleServers' for private DB isolation.
# ------------------------------------------------------------------------------------
echo "3. Creating Virtual Network ($VNET_NAME) and Subnets..."
az network vnet create --resource-group $RG_NAME --name $VNET_NAME --address-prefix 10.0.0.0/16
az network vnet subnet create --resource-group $RG_NAME --vnet-name $VNET_NAME --name snet-webapp --address-prefixes 10.0.2.0/24 --delegations Microsoft.Web/serverFarms
az network vnet subnet create --resource-group $RG_NAME --vnet-name $VNET_NAME --name snet-db --address-prefixes 10.0.3.0/24 --delegations Microsoft.DBforPostgreSQL/flexibleServers

# ------------------------------------------------------------------------------------
# Step 4: Private DNS Zone & PostgreSQL Flexible Server Deployment
# - Private DNS Zone: Provides internal domain name resolution (e.g. xxx.postgres.database.azure.com)
#   linked to our VNet so DB hostnames resolve to internal private IPs (no public internet access).
# - PostgreSQL Flexible Server: Fully managed PostgreSQL database deployed into snet-db.
# - Cost Optimization: Configured with SKU 'Standard_B1ms' (Burstable tier) for lab cost management.
# ------------------------------------------------------------------------------------
echo "4. Setting up Private DNS Zone and Deploying PostgreSQL Flexible Server..."
DNS_ZONE_NAME="bankingdemo-$RANDOM.private.postgres.database.azure.com"
az network private-dns zone create --resource-group $RG_NAME --name $DNS_ZONE_NAME
az network private-dns link vnet create --resource-group $RG_NAME --zone-name $DNS_ZONE_NAME --name vnet-link-db --virtual-network $VNET_NAME --registration-enabled false
DNS_ZONE_ID=$(az network private-dns zone show --resource-group $RG_NAME --name $DNS_ZONE_NAME --query id -o tsv | tr -d '\r')

az postgres flexible-server create --resource-group $RG_NAME --name $DB_SERVER_NAME --location $LOCATION \
    --admin-user postgres --admin-password "SuperSecret123!" \
    --sku-name Standard_B1ms --tier Burstable \
    --vnet $VNET_NAME --subnet snet-db \
    --private-dns-zone "$DNS_ZONE_ID" \
    --yes

# ------------------------------------------------------------------------------------
# Step 5: Azure Container Registry (ACR) & Container Image Build
# - ACR: Private Docker registry to securely host production container images.
# - Remote Build (`az acr build`): Uploads current source directory, builds the Docker image 
#   in the cloud using the Dockerfile, and tags it as `banking-api:latest`.
# ------------------------------------------------------------------------------------
echo "5. Creating Azure Container Registry ($ACR_NAME) and Building Docker Image..."
az acr create --resource-group $RG_NAME --name $ACR_NAME --sku Basic --admin-enabled true
az acr build --registry $ACR_NAME --image banking-api:latest .

# ------------------------------------------------------------------------------------
# Step 6: Azure Web App for Containers Deployment & VNet Integration
# - App Service Plan: Linux B1 tier (cost-efficient single-core container host).
# - Web App: Deploys container image from ACR (acrbankingdemo.azurecr.io/banking-api:latest).
# - VNet Integration: Attaches Web App outbound traffic to `snet-webapp`, allowing direct 
#   private network access to PostgreSQL inside `snet-db`.
# - App Settings: Injects DB credentials, Azure AD Tenant/Client IDs, and App Insights Connection String.
# ------------------------------------------------------------------------------------
echo "6. Deploying Azure Web App for Containers with VNet Integration..."
az appservice plan create --name $APP_SERVICE_PLAN --resource-group $RG_NAME --is-linux --sku B1
az webapp create --resource-group $RG_NAME --plan $APP_SERVICE_PLAN --name $WEBAPP_NAME \
    --deployment-container-image-name $ACR_NAME.azurecr.io/banking-api:latest

echo "Connecting Web App to VNet Subnet (snet-webapp)..."
az webapp vnet-integration add --resource-group $RG_NAME --name $WEBAPP_NAME --vnet $VNET_NAME --subnet snet-webapp

echo "Configuring Environment App Settings (App Insights, Database, Azure AD)..."
az webapp config appsettings set --resource-group $RG_NAME --name $WEBAPP_NAME \
    --settings APPLICATIONINSIGHTS_CONNECTION_STRING=$APPINSIGHTS_CONN_STR \
    DB_HOST=$DB_SERVER_NAME.postgres.database.azure.com \
    DB_NAME=postgres DB_USER=postgres DB_PASSWORD="SuperSecret123!" \
    AZURE_AD_TENANT_ID="$TENANT_ID" \
    AZURE_AD_CLIENT_ID="$CLIENT_ID"

# ------------------------------------------------------------------------------------
# Deployment Completion & Output Summary
# ------------------------------------------------------------------------------------
echo "============================================================"
echo " Deployment Complete!"
echo "============================================================"
echo "Web App Base URL: https://$WEBAPP_NAME.azurewebsites.net"
echo "Health Endpoint:  https://$WEBAPP_NAME.azurewebsites.net/health"
echo ""
echo "=== Azure AD App Registration Details ==="
echo "Tenant ID:     $TENANT_ID"
echo "Client ID:     $CLIENT_ID"
echo ""
echo "=== Generate Access Token Command ==="
echo "TOKEN=\$(az account get-access-token --resource \"$CLIENT_ID\" --query accessToken -o tsv)"
echo ""
echo "=== Test Endpoints with Authorization ==="
echo "# 1. Health Check (Unprotected):"
echo "curl -i https://$WEBAPP_NAME.azurewebsites.net/health"
echo ""
echo "# 2. Get Accounts (Protected - Requires Bearer Token):"
echo "curl -i -H \"Authorization: Bearer \$TOKEN\" https://$WEBAPP_NAME.azurewebsites.net/api/v1/accounts"
echo ""
echo "=== Clean Up Notice ==="
echo "To avoid incurring ongoing Azure charges, delete all resources when finished:"
echo "az group delete --name $RG_NAME --yes --no-wait"
echo "============================================================"


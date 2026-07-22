# Guide

This guide provides a hands-on, step-by-step walkthrough for building, containerizing, deploying, and observing a secure Python FastAPI banking microservice on Azure.

---

## 1. System Architecture & Concepts

The Capstone Banking Application demonstrates an enterprise-grade cloud architecture combining **Identity & Security**, **Serverless Hosting & Containerization**, and **Observability**:

```
[ Client / Browser ] -- 1. HTTPS Request + JWT Token --> [ Azure Web App (FastAPI Container) ]
                                                                   |
                                                      2. Private VNet Query (snet-db)
                                                                   v
                                                  [ Azure DB for PostgreSQL Flexible Server ]

[ Azure Web App ] -- 3. Traces, Metrics & Exceptions --> [ Application Insights / Log Analytics ]
```

### Key Security & Observability Pillars

1. **Identity & JWT:** Endpoints validate JSON Web Tokens (JWT) issued by Microsoft Entra ID (Azure AD).
2. **Role-Based Access Control (RBAC):** Read endpoints (`GET /api/v1/accounts`) require a valid token, while write actions (`POST /api/v1/transfer`) enforce application roles (`Transfer.Execute`).
3. **Network Isolation:** The Web App communicates with PostgreSQL over a private Virtual Network (`vnet-banking-prod`) via delegated subnets (`snet-webapp` and `snet-db`) and Private DNS zones.
4. **Centralized Telemetry:** Native OpenTelemetry integration streams distributed traces, application logs, and HTTP dependency calls directly into Azure Monitor.

---

## 2. Lab Setup: Local Development & Docker Testing

Before deploying to Azure, build and test the microservice locally using Docker and `docker-compose`.

### Step 2.1: Explore the Application Structure

Navigate to the `code/` directory:

```bash
cd code/
```

Key files:

- `app/main.py`: FastAPI routes (`/health`, `/api/v1/accounts`, `/api/v1/transfer`) and OpenTelemetry instrumentation.
- `app/auth.py`: JWT token extraction and decoding logic.
- `Dockerfile`: Multi-stage Docker build installing `psycopg2` system libraries and Python dependencies.
- `docker-compose.yml`: Local orchestrator spinning up the FastAPI API container and a PostgreSQL database container.

### Step 2.2: Launch Local Containers

Start the API and local PostgreSQL database:

```bash
docker-compose up --build
```

### Step 2.3: Verify Local Endpoint Health

In a separate terminal tab, test the health check:

```bash
curl <http://localhost:8000/health>
```

**Expected Response:** `{"status": "healthy"}`

---

## 3. Lab Setup: Cloud Deployment via Azure CLI

Deploy the complete microservice infrastructure and observability platform to Azure using the provided automated script.

### Step 3.1: Log into Azure CLI

Ensure your CLI is authenticated to your target subscription:

```bash
az login
```

### Step 3.2: Execute Deployment Script

Run the automated deployment script:

```bash
bash deploy_azure_infra.sh
```

What the script provisions:

1. **Resource Group** (`rg-banking-demo-prod-<RANDOM>`) in region `westus2`.
2. **Log Analytics Workspace & Application Insights** instance for telemetry.
3. **Virtual Network (`10.0.0.0/16`)** with dedicated subnets for Web App (`snet-webapp`) and PostgreSQL (`snet-db`).
4. **Private DNS Zone** (`bankingdemo-<RANDOM>.private.postgres.database.azure.com`) linked to the VNet.
5. **Azure Database for PostgreSQL Flexible Server** (`Standard_B1ms`).
6. **Azure Container Registry (ACR)** building the container image remotely via `az acr build`.
7. **Azure Web App for Containers** with VNet Integration and Application Insights connection settings.

Make a note of the **Web App URL** printed at the end of the script (e.g., `https://app-banking-api-XXXX.azurewebsites.net`).

---

## 4. Lab Steps: Security & RBAC Verification

Test authentication and authorization against your live cloud microservice.

### Step 4.1: Fetch an Azure Access Token

Run this command in your terminal to generate a test JWT:

```bash
TOKEN=$(az account get-access-token --resource "<https://management.azure.com>" --query accessToken -o tsv | tr -d '\r')
```

### Step 4.2: Test 1 - Unauthorized Access (No Token)

Call the accounts endpoint without an authorization header:

```bash
curl -i https://<YOUR_WEBAPP_NAME>.azurewebsites.net/api/v1/accounts
```

**Expected Output:** `HTTP/1.1 401 Unauthorized` (`detail: Missing or invalid Authorization header`)

### Step 4.3: Test 2 - Authenticated Read Access (Valid Token)

Call the accounts endpoint with your Bearer token:

```bash
curl -i -H "Authorization: Bearer $TOKEN" https://<YOUR_WEBAPP_NAME>.azurewebsites.net/api/v1/accounts
```

**Expected Output:** `HTTP/1.1 200 OK`

```json
{"message":"Accounts retrieved successfully","user":"your_email@domain.com"}
```

### Step 4.4: Test 3 - RBAC Authorization Failure (Missing Role)

Attempt a money transfer endpoint without holding the `Transfer.Execute` role:

```bash
curl -i -X POST -H "Authorization: Bearer $TOKEN" "https://<YOUR_WEBAPP_NAME>.azurewebsites.net/api/v1/transfer?amount=500"
```

**Expected Output:** `HTTP/1.1 403 Forbidden`

```json
{"detail":"User does not have the Transfer.Execute role."}
```

---

## 5. Lab Steps: Observability & Log Analytics Verification

Inspect live application telemetry in the Azure Portal.

1. **Application Insights Map:**
    - Open **Application Insights** (`appi-banking-prod-<RANDOM>`) in the Azure Portal.
    - Navigate to **Investigate -> Application Map**.
    - Observe the visual map showing HTTP traffic flowing from the Web App to the PostgreSQL database dependency.
2. **Transaction Search & Tracing:**
    - Navigate to **Investigate -> Transaction Search**.
    - Click on one of the `401` or `403` HTTP events generated during Step 4.
    - View the End-to-End Transaction Details showing the request headers and Uvicorn execution timeline.
3. **Kusto Log Querying:**
    - Open **Log Analytics Workspace** (`law-banking-prod-<RANDOM>`) -> **Logs**.
    - Run a KCL query to list incoming requests:
        
        ```
        AppRequests
        | project TimeGenerated, Name, Url, ResultCode, DurationMs
        | order by TimeGenerated desc
        ```
        

---

## 6. Reference Troubleshooting Table

| Symptom / Error | Root Cause | Solution |
| --- | --- | --- |
| `HTTP 400 Bad Request` when curling Web App. | Hidden carriage return (`\r`) in the `$TOKEN` variable from Windows/WSL line endings. | Append `| tr -d '\r'` to the token assignment command. |
| `Database connection failed` on `/health`. | Web App VNet integration is still initializing or Postgres DNS link hasn't resolved. | Wait 30 seconds for VNet route propagation and re-test `/health`. |
| `Location is restricted` during Postgres creation. | Selected Azure region has quota limits for PostgreSQL Flexible Server. | Update `LOCATION="eastus2"` or `LOCATION="westus2"` in `deploy_azure_infra.sh`. |

---

## 7. Resource Cleanup (Cost Control)

To prevent ongoing billing charges, delete the resource group immediately after completing your testing:

```bash
RG_NAME=$(az webapp list --query "[?contains(name, 'app-banking-api')].resourceGroup" -o tsv | tr -d '\r')
az group delete --name $RG_NAME --yes --no-wait
```
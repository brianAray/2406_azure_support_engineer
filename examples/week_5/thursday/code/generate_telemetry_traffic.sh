#!/bin/bash
# Telemetry Traffic Generator for Stage 2 Observability Demo
# Usage: ./generate_telemetry_traffic.sh <WEBAPP_URL>
# Example: ./generate_telemetry_traffic.sh https://app-banking-api-2101.azurewebsites.net

set -e

WEBAPP_URL=$1

if [ -z "$WEBAPP_URL" ]; then
    echo "Error: Please provide your Web App URL."
    echo "Usage: ./generate_telemetry_traffic.sh <WEBAPP_URL>"
    exit 1
fi

# Remove trailing slash if present
WEBAPP_URL=${WEBAPP_URL%/}

echo "=========================================================="
echo " Starting Telemetry Traffic Generation against:"
echo " $WEBAPP_URL"
echo "=========================================================="

echo ""
echo "1. Generating Baseline Healthy Traffic (GET /health)..."
for i in {1..5}; do
    curl -s -o /dev/null -w "GET /health -> Status: %{http_code}\n" "$WEBAPP_URL/health"
    sleep 0.5
done

echo ""
echo "2. Generating Security Telemetry (401 Unauthorized - Missing Token)..."
for i in {1..3}; do
    curl -s -o /dev/null -w "GET /api/v1/accounts (No Auth) -> Status: %{http_code}\n" "$WEBAPP_URL/api/v1/accounts"
    sleep 0.5
done

echo ""
echo "3. Fetching Valid Azure AD JWT Token..."
TOKEN=$(az account get-access-token --resource "https://management.azure.com" --query accessToken -o tsv 2>/dev/null | tr -d '\r' || echo "MOCK_DEMO_TOKEN")

echo ""
echo "4. Generating Authenticated Read Traffic (200 OK)..."
for i in {1..5}; do
    curl -s -o /dev/null -w "GET /api/v1/accounts (With Token) -> Status: %{http_code}\n" \
        -H "Authorization: Bearer $TOKEN" "$WEBAPP_URL/api/v1/accounts"
    sleep 0.5
done

echo ""
echo "5. Generating RBAC Failure Telemetry (403 Forbidden - Missing Transfer Role)..."
for i in {1..4}; do
    curl -s -o /dev/null -w "POST /api/v1/transfer (RBAC Failure) -> Status: %{http_code}\n" \
        -X POST -H "Authorization: Bearer $TOKEN" "$WEBAPP_URL/api/v1/transfer?amount=500"
    sleep 0.5
done

echo ""
echo "=========================================================="
echo " Traffic Generation Complete!"
echo " Telemetry is streaming into Application Insights & Log Analytics."
echo " (Note: Ingestion lag into Log Analytics is typically 1-3 minutes)."
echo "=========================================================="

#!/usr/bin/env bash
# Monday: AAD Auth Flow Client Request and JWT Endpoint Validation - RetailBank-Pro
# This script executes JWT authentication test curl cases against a local container or remote Azure VM.

set -euo pipefail

# Configurations
tenantId="00000000-0000-0000-0000-000000000000"
clientId="11111111-1111-1111-1111-111111111111"
clientSecret="mock-retailbank-client-secret-value-77777"
tokenEndpoint="https://login.microsoftonline.com/$tenantId/oauth2/v2.0/token"

# Target resolution
TARGET_HOST="localhost"
LOCAL_MODE=true

if [ $# -ge 1 ] && [ -n "$1" ]; then
    TARGET_HOST="$1"
    LOCAL_MODE=false
    echo "[INFO] Remote testing mode active. Target VM Host: $TARGET_HOST"
else
    echo "[INFO] No remote IP argument provided. Falling back to local container mode."
fi

# Log helper
log_section() {
    echo "======================================================================"
    echo "  $1"
    echo "======================================================================"
}

# 1. Environment Setup
if [ "$LOCAL_MODE" = true ]; then
    log_section "1. VERIFYING DOCKER CONTAINER ENVIRONMENT (LOCAL)"
    if ! command -v docker &>/dev/null; then
        echo "[ERROR] Docker is not installed or not in PATH." >&2
        exit 1
    fi

    echo "[INFO] Building FastAPI Docker image 'retailbank-auth-api'..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    docker build --quiet -t retailbank-auth-api "$SCRIPT_DIR"

    echo "[INFO] Starting container 'auth-api-service'..."
    # Stop existing container if any
    docker rm -f auth-api-service &>/dev/null || true
    docker run -d --name auth-api-service -p 8000:8000 retailbank-auth-api

    # Ensure the container is stopped and removed on exit
    cleanup() {
        echo ""
        log_section "5. TEARDOWN ENVIRONMENT"
        echo "[INFO] Stopping and removing local Docker container 'auth-api-service'..."
        docker stop auth-api-service &>/dev/null || true
        docker rm auth-api-service &>/dev/null || true
        echo "[INFO] Cleanups complete."
    }
    trap cleanup EXIT

    # Wait for server to boot
    echo "[INFO] Booting FastAPI container... waiting 3 seconds"
    sleep 3
else
    log_section "1. VERIFYING REMOTE CONNECTION STATE"
    echo "[INFO] Testing remote transaction endpoint at: http://${TARGET_HOST}:8000"
    
    # Check if VM port 8000 is open before executing tests
    if ! curl -s --connect-timeout 5 "http://${TARGET_HOST}:8000/" &>/dev/null; then
        # FastAPI root path might return 404 but connection succeeds. If curl returns connection refused, it fails.
        local exit_code=$?
        if [ $exit_code -eq 7 ]; then
            echo "[ERROR] Connection refused on http://${TARGET_HOST}:8000. Is uvicorn running on the VM?" >&2
            exit 1
        elif [ $exit_code -eq 28 ]; then
            echo "[ERROR] Connection timed out. Check NSG rules on Azure VM for port 8000." >&2
            exit 1
        fi
    fi
    echo "[INFO] Target VM Host is reachable."

    cleanup() {
        echo ""
        log_section "5. TEARDOWN ENVIRONMENT"
        echo "[INFO] Test suite completed. Remote container left running on VM host."
    }
    trap cleanup EXIT
fi

# 2. Acquire JWT Token
log_section "2. ACQUIRING TOKEN FROM ENTRA ID ENDPOINT"
echo "POST Request: $tokenEndpoint"

simulate_token_request() {
    local scopes=$1
    local roles_claim='["Transaction.Write","Audit.Read"]'
    if [ "$scopes" = "Audit" ]; then
        roles_claim='["Audit.Read"]'
    fi
    
    # Dynamically build the JWT payload JSON and base64-encode it using python
    local payload_json="{\"aud\":\"https://api.retailbank.com\",\"iss\":\"https://sts.windows.net/00000000-0000-0000-0000-000000000000/\",\"iat\":1625375200,\"exp\":1925378800,\"tenantId\":\"00000000-0000-0000-0000-000000000000\",\"roles\":$roles_claim}"
    
    local payload_b64=$(echo -n "$payload_json" | python3 -c "import sys, base64; print(base64.urlsafe_b64encode(sys.stdin.read().strip().encode('utf-8')).decode('utf-8').rstrip('='))" 2>/dev/null || \
                        echo -n "$payload_json" | python -c "import sys, base64; print(base64.urlsafe_b64encode(sys.stdin.read().strip().encode('utf-8')).decode('utf-8').rstrip('='))")
    
    local header_b64="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjEyMyJ9"
    local access_token="${header_b64}.${payload_b64}.mock_signature"
    
    cat << EOF
{
  "token_type": "Bearer",
  "expires_in": 3599,
  "access_token": "$access_token"
}
EOF
}

echo "[INFO] Fetching valid Transaction.Write Bearer token..."
tokenDataValid=$(simulate_token_request "Transaction")
tokenValid=$(echo "$tokenDataValid" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || \
             echo "$tokenDataValid" | python -c "import sys, json; print(json.load(sys.stdin).get('access_token',''))")

echo "[INFO] Fetching unauthorized token (Audit role only)..."
tokenDataInvalid=$(simulate_token_request "Audit")
tokenInvalid=$(echo "$tokenDataInvalid" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || \
               echo "$tokenDataInvalid" | python -c "import sys, json; print(json.load(sys.stdin).get('access_token',''))")

# 3. Perform Transaction Request Tests
log_section "3. VERIFYING ENDPOINT PROTECTION RULES"

transaction_payload='{"id": "TXN-98765-ABC", "amount": 1250.00}'

echo ""
echo "[TEST A] Sending POST transaction request without Authorization header:"
curl -s -w "\nHTTP Response Code: %{http_code}\n" \
    -X POST "http://${TARGET_HOST}:8000/api/transactions" \
    -H "Content-Type: application/json" \
    -d "$transaction_payload"

echo ""
echo "[TEST B] Sending POST transaction request with invalid signature token format:"
curl -s -w "\nHTTP Response Code: %{http_code}\n" \
    -X POST "http://${TARGET_HOST}:8000/api/transactions" \
    -H "Authorization: Bearer bad_token_string_here" \
    -H "Content-Type: application/json" \
    -d "$transaction_payload"

echo ""
echo "[TEST C] Sending POST transaction request with insufficient privileges (Missing Transaction.Write role):"
curl -s -w "\nHTTP Response Code: %{http_code}\n" \
    -X POST "http://${TARGET_HOST}:8000/api/transactions" \
    -H "Authorization: Bearer $tokenInvalid" \
    -H "Content-Type: application/json" \
    -d "$transaction_payload"

echo ""
echo "[TEST D] Sending POST transaction request with valid client credentials token:"
curl -s -w "\nHTTP Response Code: %{http_code}\n" \
    -X POST "http://${TARGET_HOST}:8000/api/transactions" \
    -H "Authorization: Bearer $tokenValid" \
    -H "Content-Type: application/json" \
    -d "$transaction_payload"

log_section "4. DIAGNOSTICS & TELEMETRY COMPLIANCE SUMMARY"
echo "[INFO] Test execution complete. Trainees should verify that:"
echo "  - Test A returns: 401 Unauthorized"
echo "  - Test B returns: 401 Unauthorized"
echo "  - Test C returns: 403 Forbidden"
echo "  - Test D returns: 200 OK with success transaction confirmation"

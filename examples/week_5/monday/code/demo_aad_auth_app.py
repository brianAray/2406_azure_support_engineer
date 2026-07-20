import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import requests
from jwt import PyJWKClient

app = FastAPI(title="RetailBank-Pro Transaction API")

# Configuration
TENANT_ID = os.getenv("TENANT_ID", "00000000-0000-0000-0000-000000000000")
AUDIENCE = os.getenv("AUDIENCE", "https://api.retailbank.com")
# Note: Entra ID v2 tokens usually end with /v2.0, while v1 tokens end with /
ISSUER_URL = os.getenv("ISSUER_URL", f"https://sts.windows.net/{TENANT_ID}/")

# Entra ID OpenID configuration / JWKS endpoint
JWKS_URL = os.getenv("JWKS_URL", f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys")

# PyJWKClient caches the public keys automatically
jwk_client = PyJWKClient(JWKS_URL)

# Built-in FastAPI bearer handler (handles "Bearer <token>" extraction)
security = HTTPBearer()


def verify_entra_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    
    try:
        if TENANT_ID == "00000000-0000-0000-0000-000000000000":
            # Mock / local testing mode: bypass signature verification since there is no real tenant
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True},
                audience=AUDIENCE,
                issuer=ISSUER_URL
            )
        else:
            # Real Entra ID validation: fetch public key from JWKS and verify signature
            signing_key = jwk_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                key=signing_key.key,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=ISSUER_URL,
                options={"verify_exp": True}
            )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 3. Role-Based Access Control (RBAC) check
    roles = payload.get("roles", [])
    if "Transaction.Write" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Role 'Transaction.Write' required."
        )
        
    return payload


@app.post("/api/transactions")
def create_transaction(payload: dict, claims: dict = Depends(verify_entra_token)):
    return {
        "status": "success",
        "message": "Transaction created successfully.",
        "transactionId": payload.get("id"),
        "amount": payload.get("amount"),
        "authorizedByTenant": claims.get("tid")  # Entra ID uses 'tid' for Tenant ID
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
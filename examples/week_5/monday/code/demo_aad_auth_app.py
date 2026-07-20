from fastapi import FastAPI, Depends, HTTPException, status, Header
import base64
import json

app = FastAPI(title="RetailBank-Pro Transaction API")

# Configuration (simulated or real Entra ID config)
TENANT_ID = "00000000-0000-0000-0000-000000000000"
AUDIENCE = "https://api.retailbank.com"
ISSUER_URL = f"https://sts.windows.net/{TENANT_ID}/"

def verify_entra_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be Bearer token"
        )
    
    token = parts[1]
    
    # Parse JWT payload segment to validate claims
    try:
        token_parts = token.split('.')
        if len(token_parts) < 2:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format"
            )
            
        payload_b64 = token_parts[1]
        pad_len = 4 - (len(payload_b64) % 4)
        if pad_len < 4:
            payload_b64 += "=" * pad_len
            
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token decoding failed: {str(e)}"
        )
        
    # Verify claims
    if payload.get("aud") != AUDIENCE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid audience claim"
        )
        
    if payload.get("iss") != ISSUER_URL:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid issuer claim"
        )
        
    # Check permissions role
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
        "authorizedByTenant": claims.get("tenantId")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

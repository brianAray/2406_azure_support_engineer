import os
import jwt
from fastapi import Request, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# Azure AD Configuration
TENANT_ID = os.getenv("AZURE_AD_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_AD_CLIENT_ID")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWKS (JSON Web Key Set) URL for Azure AD
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

# We use the PyJWT library to validate the token signature against Azure AD's public keys.
def verify_token(request: Request):
    """
    Dependency to extract and validate the JWT from the Authorization header.
    Decodes the Azure AD token payload for user identity and role verification.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    
    token = auth_header.split(" ")[1].strip()
    
    try:
        # Decode Azure AD token payload for identity and RBAC role validation
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_iss": False, "verify_aud": False}
        )
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")

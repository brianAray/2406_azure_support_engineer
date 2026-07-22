import os
import psycopg2
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from .auth import verify_token
from azure.monitor.opentelemetry import configure_azure_monitor

# Configure Azure Monitor if connection string is present
app_insights_conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if app_insights_conn_str:
    configure_azure_monitor(connection_string=app_insights_conn_str)
    logging.getLogger(__name__).info("Azure Monitor Configured.")

app = FastAPI(title="Banking Microservice API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection details
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "banking")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "supersecret")

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        return None

@app.get("/health")
def health_check():
    """Health check endpoint. Monitored by Azure Monitor Alerts."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database connection failed")
    conn.close()
    return {"status": "healthy"}

@app.get("/api/v1/accounts")
def get_accounts(token_payload: dict = Depends(verify_token)):
    """Protected endpoint requiring a valid JWT from Azure AD."""
    user_identity = (
        token_payload.get("upn") or 
        token_payload.get("unique_name") or 
        token_payload.get("preferred_username") or 
        token_payload.get("name") or 
        token_payload.get("appid") or 
        "Unknown User"
    )
    return {"message": "Accounts retrieved successfully", "user": user_identity}

@app.post("/api/v1/transfer")
def transfer_funds(amount: float, token_payload: dict = Depends(verify_token)):
    """Protected endpoint requiring specific RBAC roles within the JWT."""
    roles = token_payload.get("roles", [])
    if "Transfer.Execute" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have the Transfer.Execute role."
        )
    user_identity = (
        token_payload.get("upn") or 
        token_payload.get("unique_name") or 
        token_payload.get("preferred_username") or 
        token_payload.get("name") or 
        token_payload.get("appid") or 
        "Unknown User"
    )
    return {"message": f"Successfully transferred ${amount}", "user": user_identity}

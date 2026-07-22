import os
import psycopg2
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from .auth import verify_token
# ====================================================================================
# OBSERVABILITY & DISTRIBUTED TRACING (OpenTelemetry Integration)
# ====================================================================================
# What is OpenTelemetry (OTel)?
#   OpenTelemetry is a vendor-neutral CNCF framework that standardizes how telemetry
#   (Metrics, Logs, and Distributed Traces) is collected and exported from microservices
#   to observability backends like Azure Application Insights and Log Analytics.
#
# Typical Mistake vs. SRE Best Practice:
#   TYPICAL SETUP: Calling only `configure_azure_monitor(connection_string=...)` and 
#   assuming Azure Monitor automatically captures all web routes and database calls.
#
# WHAT MUST BE DONE DIFFERENTLY & WHY:
#   1. configure_azure_monitor(): Initializes global OpenTelemetry providers & Azure exporters.
#   2. FastAPIInstrumentor.instrument_app(app): Explicitly hooks into FastAPI's ASGI 
#      request engine. WITHOUT THIS, incoming HTTP requests do NOT generate server 
#      spans, causing the `AppRequests` table in Log Analytics to remain empty.
#   3. Psycopg2Instrumentor().instrument(): Monkey-patches the `psycopg2` driver to 
#      intercept SQL queries. WITHOUT THIS, database calls fail to produce dependency 
#      spans, causing the `AppDependencies` table to return 0 records.
# ====================================================================================
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

app = FastAPI(title="Banking Microservice API")

# Configure Azure Monitor & explicit OTel instrumentors if connection string is present
app_insights_conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if app_insights_conn_str:
    # Step 1: Initialize Azure Monitor OpenTelemetry Distro Exporters
    configure_azure_monitor(connection_string=app_insights_conn_str)
    
    # Step 2: Instrument FastAPI HTTP Server Spans -> Populates 'AppRequests'
    FastAPIInstrumentor.instrument_app(app)
    
    # Step 3: Instrument Psycopg2 PostgreSQL Client Spans -> Populates 'AppDependencies'
    Psycopg2Instrumentor().instrument()
    
    logging.getLogger(__name__).info("Azure Monitor, FastAPI & Psycopg2 OpenTelemetry Instrumentations Active.")

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

FROM python:3.10-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn "PyJWT[crypto]" requests

# Copy code
COPY demo_aad_auth_app.py .

# Expose FastAPI port
EXPOSE 8000

# Start server
CMD ["python", "-m", "uvicorn", "demo_aad_auth_app:app", "--host", "0.0.0.0", "--port", "8000"]

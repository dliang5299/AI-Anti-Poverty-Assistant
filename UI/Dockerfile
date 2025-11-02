# Dockerfile for BenefitsFlow FastAPI Backend + HTML Frontend
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
# Using minimal requirements for FastAPI + HTML frontend
COPY requirements_ui.txt .
RUN pip install --no-cache-dir -r requirements_ui.txt || pip install --no-cache-dir fastapi uvicorn pydantic httpx requests

# Copy application code
COPY . .

# Expose port 8000 for FastAPI
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "fastapi_backend:app", "--host", "0.0.0.0", "--port", "8000"]

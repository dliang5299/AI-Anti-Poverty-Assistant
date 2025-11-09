# BenefitsFlow Frontend

HTML frontend with FastAPI backend for California benefits navigation. Integrated with RAG system.

## Quick Start

### Local Development (Simplest)
```bash
cd UI
python start_app.py
```
Opens browser at http://localhost:8000 with demo responses.

### With Full RAG System (Docker)
```bash
# From project root - requires API keys (see API_KEYS_SETUP.md)
docker-compose up --build
```
- RAG service: http://localhost:8000
- Frontend: http://localhost:8501

## Documentation

- **`RUN_LOCALLY.md`** - How to run locally for development
- **`API_KEYS_SETUP.md`** - Setting up API keys (current: OpenAI + Pinecone)
- **`AWS_NATIVE_SETUP.md`** - Using 100% AWS services (Bedrock + OpenSearch) - Recommended if you have AWS budget
- **`AWS_SECRETS_MANAGER_SETUP.md`** - Production deployment to EC2 with Secrets Manager

## Architecture

```
Frontend (HTML) → FastAPI Backend → RAG Service
                                      ↓
                              Bedrock + Pinecone + OpenAI
```

- **Frontend**: `benefitsflow_frontend.html` - HTML/CSS/JavaScript
- **Backend**: `fastapi_backend.py` - FastAPI with API endpoints
- **RAG Service**: `app/RAG_service.py` - Vector search + LLM (Deric's code)

## API Endpoints

- `GET /` - Serve HTML frontend
- `POST /api/chat` - Chat with RAG system
- `POST /api/download/checklist` - Download checklist
- `POST /api/download/calendar` - Download calendar (.ics)
- `GET /api/health` - Health check

## Production Deployment

- **`EC2_DEPLOYMENT_GUIDE.md`** - Complete step-by-step guide for two-instance EC2 deployment
- **`AWS_SECRETS_MANAGER_SETUP.md`** - Using AWS Secrets Manager for API keys
- **`AWS_NATIVE_SETUP.md`** - Using 100% AWS services (optional, if migrating from Pinecone)
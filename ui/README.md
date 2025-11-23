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
# From project root - requires API keys configured
docker-compose up --build
```
- RAG service: http://localhost:8000
- Frontend: http://localhost:8501

## Documentation

For deployment and setup details, see the main project documentation.

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

For production deployment instructions, see the main project documentation.
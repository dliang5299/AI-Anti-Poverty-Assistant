# BenefitsFlow Frontend

Professional HTML frontend with FastAPI backend for California benefits navigation.

## Quick Start

### Option 1: Simple Startup (Recommended)
```bash
cd UI
python start_app.py
```
- Opens HTML frontend in browser
- Starts FastAPI backend automatically
- Uses demo responses for testing

### Option 2: Hosted Application
```bash
cd UI
python serve_frontend.py
```
- Serves frontend at http://localhost:8000
- API available at http://localhost:8000/api
- API docs at http://localhost:8000/api/docs

## File Structure

### Core Files
- `benefitsflow_frontend.html` - Main HTML frontend
- `fastapi_backend.py` - FastAPI backend with API endpoints
- `rag_backend.py` - Demo RAG responses (will be replaced by Deric's system)
- `utils.py` - Utility functions

### Startup Scripts
- `start_app.py` - Simple startup script
- `serve_frontend.py` - Hosted application server

### Resources
- `images/` - Logo and UI images
- `requirements.txt` - Python dependencies

### Documentation
- `INTEGRATION_GUIDE_FOR_DERIC.md` - Guide for connecting Deric's RAG system
- `README.md` - This file

## API Endpoints

- `GET /` - Health check
- `POST /chat` - Main chat endpoint
- `POST /download/checklist` - Generate checklist
- `POST /download/calendar` - Generate calendar
- `GET /situations` - Available situation types
- `GET /health` - Health check

## Integration with RAG System

The frontend is ready to connect to Deric's RAG system. See `INTEGRATION_GUIDE_FOR_DERIC.md` for details.

## Dependencies

- FastAPI
- Uvicorn
- Standard Python libraries

## Development

The application uses:
- **Frontend**: HTML/CSS/JavaScript (no framework dependencies)
- **Backend**: FastAPI with Python
- **Architecture**: Clean separation between frontend and backend

## Production Deployment

Ready for deployment to:
- AWS SageMaker
- Docker containers
- Cloud platforms

The architecture is production-ready and scalable.
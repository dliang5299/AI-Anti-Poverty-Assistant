#!/usr/bin/env python3
"""
BenefitsFlow - Properly Hosted Frontend + Backend
Serves the HTML frontend through FastAPI with proper hosting
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from pathlib import Path

# Import your existing backend
from fastapi_backend import app as backend_app
from fastapi_backend import *

# Create main app that serves both frontend and backend
app = FastAPI(
    title="BenefitsFlow",
    description="California Benefits Navigator - Full Application",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the backend API at /api
app.mount("/api", backend_app)

# Get the directory where this file is located
ui_dir = Path(__file__).parent

# Serve static files (images, CSS, etc.) - mount images directory
images_dir = ui_dir / "images"
if images_dir.exists():
    app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")
    print(f"✅ Images mounted at /images from {images_dir}")
else:
    print(f"⚠️ Images directory not found at {images_dir}")

@app.get("/")
async def serve_frontend():
    """Serve the main HTML frontend"""
    html_file = ui_dir / "benefitsflow_frontend.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return {"error": "Frontend file not found"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "BenefitsFlow is running!"}

if __name__ == "__main__":
    # AWS Deployment: UI runs on port 8501 (RAG service uses 8000)
    # Port matches docker-compose.yml and Dockerfile.ui
    ui_port = int(os.getenv("UI_PORT", "8501"))
    rag_url = os.getenv("RAG_SERVICE_URL") or os.getenv("RAG_API_URL") or "http://app:8000"
    print("🚀 [AWS] Starting BenefitsFlow - Hosted Application")
    print(f"🌐 Frontend: http://0.0.0.0:{ui_port}")
    print(f"🔌 Backend API: http://0.0.0.0:{ui_port}/api")
    print(f"📚 API Documentation: http://0.0.0.0:{ui_port}/api/docs")
    print(f"🔗 RAG service expected at: {rag_url}")
    print(f"✅ Application ready for AWS deployment")
    
    uvicorn.run(app, host="0.0.0.0", port=ui_port)

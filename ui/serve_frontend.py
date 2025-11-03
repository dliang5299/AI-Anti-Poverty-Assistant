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

# Serve static files (images, CSS, etc.)
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def serve_frontend():
    """Serve the main HTML frontend"""
    return FileResponse("benefitsflow_frontend.html")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "BenefitsFlow is running!"}

if __name__ == "__main__":
    print("Starting BenefitsFlow - Hosted Application")
    print("Frontend: http://localhost:8000")
    print("Backend API: http://localhost:8000/api")
    print("API Documentation: http://localhost:8000/api/docs")
    print("\nApplication is now properly hosted and ready for use.")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

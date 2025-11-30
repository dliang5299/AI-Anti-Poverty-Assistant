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

# Serve favicon files
@app.get("/favicon.ico")
async def favicon_ico():
    """Serve favicon.ico"""
    favicon_path = ui_dir / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/x-icon")
    from fastapi import HTTPException
    raise HTTPException(status_code=404)

@app.get("/favicon-16x16.png")
async def favicon_16():
    """Serve 16x16 favicon"""
    favicon_path = ui_dir / "favicon-16x16.png"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/png")
    from fastapi import HTTPException
    raise HTTPException(status_code=404)

@app.get("/favicon-32x32.png")
async def favicon_32():
    """Serve 32x32 favicon"""
    favicon_path = ui_dir / "favicon-32x32.png"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/png")
    from fastapi import HTTPException
    raise HTTPException(status_code=404)

@app.get("/apple-touch-icon.png")
async def apple_touch_icon():
    """Serve Apple touch icon"""
    icon_path = ui_dir / "apple-touch-icon.png"
    if icon_path.exists():
        return FileResponse(str(icon_path), media_type="image/png")
    from fastapi import HTTPException
    raise HTTPException(status_code=404)

@app.get("/android-chrome-192x192.png")
async def android_chrome_192():
    """Serve Android Chrome 192x192 icon"""
    icon_path = ui_dir / "android-chrome-192x192.png"
    if icon_path.exists():
        return FileResponse(str(icon_path), media_type="image/png")
    from fastapi import HTTPException
    raise HTTPException(status_code=404)

@app.get("/android-chrome-512x512.png")
async def android_chrome_512():
    """Serve Android Chrome 512x512 icon"""
    icon_path = ui_dir / "android-chrome-512x512.png"
    if icon_path.exists():
        return FileResponse(str(icon_path), media_type="image/png")
    from fastapi import HTTPException
    raise HTTPException(status_code=404)

@app.get("/site.webmanifest")
async def site_webmanifest():
    """Serve site.webmanifest"""
    manifest_path = ui_dir / "site.webmanifest"
    if manifest_path.exists():
        return FileResponse(str(manifest_path), media_type="application/manifest+json")
    from fastapi import HTTPException
    raise HTTPException(status_code=404)

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

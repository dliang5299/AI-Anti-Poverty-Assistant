"""
FastAPI Backend for BenefitsFlow
Handles API requests from the HTML frontend
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import os
import time
from pathlib import Path
from datetime import datetime
import io

# Import your existing modules
from rag_backend import get_rag_response, generate_checklist
from utils import extract_programs_from_conversation, get_quick_replies

# Activity tracking file (for EC2 auto-stop)
ACTIVITY_FILE = Path("/tmp/benefitsflow-last-activity.txt")

# Initialize FastAPI app
app = FastAPI(
    title="BenefitsFlow API",
    description="California Benefits Navigator API",
    version="1.0.0"
)

# Activity tracking middleware - updates timestamp on each HTTP request
class ActivityTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Update activity file on any HTTP request
        try:
            ACTIVITY_FILE.write_text(str(int(time.time())))
        except:
            pass  # Ignore errors if file can't be written (e.g., local development)
        
        response = await call_next(request)
        return response

# Add activity tracking middleware (before CORS)
app.add_middleware(ActivityTrackingMiddleware)

# Add CORS middleware to allow HTML frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class ChatRequest(BaseModel):
    message: str
    situation: str = None
    conversation_history: List[Dict[str, Any]] = []

class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, str]] = []
    programs: List[str] = []

class DownloadRequest(BaseModel):
    situation: str = None
    conversation_history: List[Dict[str, Any]] = []

# Serve static files (images, CSS, etc.)
static_dir = Path(__file__).parent
if (static_dir / "images").exists():
    app.mount("/images", StaticFiles(directory=str(static_dir / "images")), name="images")

# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML frontend"""
    html_file = static_dir / "benefitsflow_frontend.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>BenefitsFlow</h1><p>Frontend file not found</p>")

@app.get("/api")
async def api_root():
    """API root endpoint"""
    return {"message": "BenefitsFlow API is running!", "status": "healthy"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint - handles user messages and returns AI responses
    This will connect to Deric's RAG system when ready
    """
    try:
        # For now, use demo responses
        # TODO: Replace with Deric's RAG system when ready
        response_text, sources, programs = get_rag_response(
            request.message, 
            request.conversation_history, 
            {"situation": request.situation}
        )
        
        return ChatResponse(
            response=response_text,
            sources=sources,
            programs=programs
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

@app.post("/api/download/checklist")
async def download_checklist(request: DownloadRequest):
    """
    Generate and download a personalized checklist as a text file
    """
    try:
        # Generate checklist using your existing logic
        checklist_items = generate_checklist(
            request.conversation_history,
            {"situation": request.situation} if request.situation else {}
        )
        
        # Format checklist items into readable text
        checklist_text = []
        for i, item in enumerate(checklist_items, 1):
            checklist_text.append(f"{i}. {item['title']}")
            checklist_text.append(f"   {item['description']}")
            if item.get('deadline'):
                checklist_text.append(f"   Deadline: {item['deadline']}")
            checklist_text.append("   Action Items:")
            for detail in item.get('details', []):
                checklist_text.append(f"     • {detail}")
            if item.get('link'):
                checklist_text.append(f"   Website: {item['link']}")
            checklist_text.append("")  # Empty line between items
        
        # Build complete text file content
        content = f"""BenefitsFlow Personalized Checklist
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 60}

Your Situation: {request.situation or 'General'}

{'=' * 60}

CHECKLIST ITEMS:
{'=' * 60}

{chr(10).join(checklist_text)}

{'=' * 60}

NEXT STEPS:
{'=' * 60}
1. Review each item above carefully
2. Check eligibility requirements for each program
3. Gather required documents before applying
4. Apply for benefits that match your situation
5. Keep track of application deadlines and follow up

{'=' * 60}

HELPFUL RESOURCES:
{'=' * 60}
• BenefitsCal.com - Apply for CalFresh, Medi-Cal, and more
• EDD.ca.gov - Unemployment Insurance and job services
• DHCS.ca.gov - Health coverage and Medi-Cal information
• 211california.org - Local resources and assistance

{'=' * 60}

Generated by BenefitsFlow - California Benefits Navigator
For questions or assistance, visit: https://benefitscal.com
"""
        
        # Create file in memory as text/plain
        file_content = content.encode('utf-8')
        
        return FileResponse(
            io.BytesIO(file_content),
            media_type='text/plain',
            filename=f'benefits-checklist-{datetime.now().strftime("%Y%m%d")}.txt',
            headers={"Content-Disposition": f'attachment; filename="benefits-checklist-{datetime.now().strftime("%Y%m%d")}.txt"'}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating checklist: {str(e)}")

@app.post("/api/download/calendar")
async def download_calendar(request: DownloadRequest):
    """
    Generate and download a calendar file (.ics)
    """
    try:
        # Generate calendar events based on conversation
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//BenefitsFlow//Benefits Calendar//EN
BEGIN:VEVENT
UID:benefitsflow-1@example.com
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:20250115T090000Z
DTEND:20250115T100000Z
SUMMARY:Apply for CalFresh
DESCRIPTION:Apply for CalFresh food assistance program
LOCATION:Online Application
URL:https://benefitscal.com
END:VEVENT
BEGIN:VEVENT
UID:benefitsflow-2@example.com
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:20250120T090000Z
DTEND:20250120T100000Z
SUMMARY:Apply for Medi-Cal
DESCRIPTION:Apply for Medi-Cal health insurance
LOCATION:Online Application
URL:https://benefitscal.com
END:VEVENT
BEGIN:VEVENT
UID:benefitsflow-3@example.com
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:20250125T090000Z
DTEND:20250125T100000Z
SUMMARY:Check Unemployment Benefits
DESCRIPTION:Review unemployment insurance eligibility
LOCATION:Online Application
URL:https://edd.ca.gov
END:VEVENT
END:VCALENDAR"""
        
        # Create file in memory
        file_content = ics_content.encode('utf-8')
        
        return FileResponse(
            io.BytesIO(file_content),
            media_type='text/calendar',
            filename='benefits-calendar.ics',
            headers={"Content-Disposition": "attachment; filename=benefits-calendar.ics"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating calendar: {str(e)}")

@app.get("/api/situations")
async def get_situations():
    """
    Get available situation types
    """
    return {
        "situations": [
            {"id": "unemployed", "name": "Unemployed", "description": "Looking for work and need immediate assistance"},
            {"id": "family", "name": "Family with Children", "description": "Supporting children and need family benefits"},
            {"id": "senior", "name": "Senior Citizen", "description": "65+ and need healthcare and assistance"},
            {"id": "disability", "name": "Disability", "description": "Living with disability and need support"},
            {"id": "student", "name": "Student", "description": "In school and need educational support"},
            {"id": "immigrant", "name": "New to California", "description": "Recently moved and need to understand benefits"}
        ]
    }

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

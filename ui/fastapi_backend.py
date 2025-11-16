"""
FastAPI Backend for BenefitsFlow
Handles API requests from the HTML frontend
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
import io
import httpx

# Import your existing modules (fallback)
from rag_backend import get_rag_response
from utils import extract_programs_from_conversation, get_quick_replies

# Import UI generators (all logic in UI folder)
from checklist_generator import generate_checklist
from calendar_generator import generate_calendar_events

# Deric's RAG Service URL
# In Docker: use service name "api" (from docker-compose.yml)
# Locally: use "localhost"
# On EC2: use private IP or service name
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8000")

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
    situation: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = []

class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, str]] = []
    programs: List[str] = []

class DownloadRequest(BaseModel):
    situation: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = []
    programs: List[str] = []

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
    Calls Deric's RAG service, with fallback to demo if unavailable
    """
    try:
        # Try to call Deric's RAG service first
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{RAG_SERVICE_URL}/chat",
                    json={
                        "message": request.message,
                        "situation": request.situation,
                        "conversation_history": request.conversation_history
                    }
                )
                response.raise_for_status()
                rag_result = response.json()
                
                return ChatResponse(
                    response=rag_result["response"],
                    sources=rag_result.get("sources", []),
                    programs=rag_result.get("programs", [])
                )
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            # Fallback to demo RAG if Deric's service is unavailable
            print(f"Warning: RAG service unavailable ({RAG_SERVICE_URL}), using fallback: {str(e)}")
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
    Generate and download a personalized checklist as a text file using RAG service
    """
    try:
        # Validate request
        if not isinstance(request.conversation_history, list):
            request.conversation_history = []
        if not isinstance(request.programs, list):
            request.programs = []
        
        # Extract programs from conversation
        all_programs = set()
        if request.programs:
            all_programs.update(request.programs)
        
        for msg in request.conversation_history:
            if msg.get('role') == 'assistant' and msg.get('programs'):
                if isinstance(msg['programs'], list):
                    all_programs.update(msg['programs'])
            content = msg.get('content', '').lower()
            program_keywords = {
                'calfresh': 'CalFresh',
                'medi-cal': 'Medi-Cal',
                'unemployment': 'Unemployment Insurance',
                'calworks': 'CalWORKs',
                'section 8': 'Section 8',
                'covered california': 'Covered California'
            }
            for keyword, program in program_keywords.items():
                if keyword in content:
                    all_programs.add(program)
        
        # Generate checklist using UI generator (uses Deric's RAG service internally)
        checklist_items = []
        try:
            user_context = {
                "situation": request.situation,
                "programs": list(all_programs)
            }
            checklist_items = generate_checklist(request.conversation_history, user_context)
        except Exception as e:
            print(f"Error generating checklist: {e}")
            checklist_items = []
        
        if not checklist_items or len(checklist_items) == 0:
            # Return fallback message if no items generated
            content = f"""BenefitsFlow Personalized Checklist
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 60}

Not enough conversation context to generate a personalized checklist.

Please continue your conversation with the assistant to provide more details about:
• Your specific situation
• Programs you're interested in
• Deadlines or important dates
• Documents you need to gather

Then try downloading your checklist again.
"""
            return Response(
                content=content.encode('utf-8'),
                media_type='text/plain',
                headers={
                    "Content-Disposition": f"attachment; filename=benefits-checklist-{datetime.now().strftime('%Y%m%d')}.txt"
                }
            )
        
        # Format checklist items into readable text
        checklist_text = []
        try:
            for i, item in enumerate(checklist_items, 1):
                if not isinstance(item, dict):
                    continue
                checklist_text.append(f"{i}. {item.get('title', 'Item')}")
                checklist_text.append(f"   {item.get('description', '')}")
                if item.get('deadline'):
                    checklist_text.append(f"   Deadline: {item['deadline']}")
                if item.get('details') and isinstance(item['details'], list):
                    checklist_text.append("   Action Items:")
                    for detail in item['details']:
                        if detail:
                            checklist_text.append(f"     • {detail}")
                if item.get('link'):
                    checklist_text.append(f"   Website: {item['link']}")
                checklist_text.append("")  # Empty line between items
        except Exception as format_error:
            print(f"Error formatting checklist items: {format_error}")
            # Fallback to simple format
            for i, item in enumerate(checklist_items, 1):
                checklist_text.append(f"{i}. {str(item.get('title', 'Item'))}")
        
        # Build complete text file content
        checklist_body = chr(10).join(checklist_text) if checklist_text else "No checklist items generated."
        
        content = f"""BenefitsFlow Personalized Checklist
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 60}

Your Situation: {request.situation or 'General'}

{'=' * 60}

CHECKLIST ITEMS:
{'=' * 60}

{checklist_body}

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
        
        filename = f'benefits-checklist-{datetime.now().strftime("%Y%m%d")}.txt'
        
        return Response(
            content=file_content,
            media_type='text/plain',
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(file_content))
            }
        )
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Checklist download error: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Error generating checklist: {str(e)}")

@app.post("/api/download/calendar")
async def download_calendar(request: DownloadRequest):
    """
    Generate and download a calendar file (.ics) using RAG service
    """
    try:
        # Extract programs from conversation
        all_programs = set()
        if request.programs:
            all_programs.update(request.programs)
        
        for msg in request.conversation_history:
            if msg.get('role') == 'assistant' and msg.get('programs'):
                if isinstance(msg['programs'], list):
                    all_programs.update(msg['programs'])
            content = msg.get('content', '').lower()
            program_keywords = {
                'calfresh': 'CalFresh',
                'medi-cal': 'Medi-Cal',
                'unemployment': 'Unemployment Insurance',
                'calworks': 'CalWORKs',
                'section 8': 'Section 8',
                'covered california': 'Covered California'
            }
            for keyword, program in program_keywords.items():
                if keyword in content:
                    all_programs.add(program)
        
        # Generate calendar events using UI generator (uses Deric's RAG service internally)
        events_data = []
        try:
            user_context = {
                "situation": request.situation,
                "programs": list(all_programs)
            }
            events_data = generate_calendar_events(request.conversation_history, user_context)
        except Exception as e:
            print(f"Error generating calendar events: {e}")
            events_data = []
        
        # Convert events to iCalendar format
        events = []
        event_num = 1
        
        if not events_data:
            # Not enough context - create a single informational event
            base_date = datetime.now() + timedelta(days=1)
            events.append(f"""BEGIN:VEVENT
UID:benefitsflow-context-needed@benefitsflow.com
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{base_date.strftime('%Y%m%dT090000Z')}
DTEND:{base_date.strftime('%Y%m%dT100000Z')}
SUMMARY:Continue Conversation for Personalized Calendar
DESCRIPTION:Not enough context from our conversation to generate personalized calendar events. Please continue chatting with the assistant about your specific situation, programs you're interested in, and any deadlines or important dates. Then try downloading your calendar again.
LOCATION:BenefitsFlow Chat
STATUS:CONFIRMED
END:VEVENT""")
        else:
            # Use RAG-generated events
            for event in events_data:
                try:
                    event_date = datetime.strptime(event['start_date'], "%Y-%m-%d")
                    events.append(f"""BEGIN:VEVENT
UID:benefitsflow-{event_num}@benefitsflow.com
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{event_date.strftime('%Y%m%dT090000Z')}
DTEND:{event_date.strftime('%Y%m%dT100000Z')}
SUMMARY:{event.get('summary', 'Important Date')}
DESCRIPTION:{event.get('description', '')}
LOCATION:Online Application
URL:{event.get('url', '')}
END:VEVENT""")
                    event_num += 1
                except Exception as e:
                    print(f"Error formatting calendar event: {e}")
                    continue
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//BenefitsFlow//Benefits Calendar//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:California Benefits Important Dates
X-WR-CALDESC:Important dates for California benefits programs based on your conversation
X-WR-TIMEZONE:America/Los_Angeles
{chr(10).join(events)}
END:VCALENDAR"""
        
        # Create file in memory
        file_content = ics_content.encode('utf-8')
        
        return Response(
            content=file_content,
            media_type='text/calendar',
            headers={
                "Content-Disposition": "attachment; filename=benefits-calendar.ics",
                "Content-Length": str(len(file_content))
            }
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

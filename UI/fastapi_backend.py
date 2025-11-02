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
        # Validate request
        if not isinstance(request.conversation_history, list):
            request.conversation_history = []
        if not isinstance(request.programs, list):
            request.programs = []
        
        # Validate input and extract programs from conversation
        all_programs = set()
        if request.programs:
            all_programs.update(request.programs)
        
        # Extract programs from conversation history (from assistant messages with programs field)
        for msg in request.conversation_history:
            if msg.get('role') == 'assistant' and msg.get('programs'):
                if isinstance(msg['programs'], list):
                    all_programs.update(msg['programs'])
            # Also check if programs are mentioned in content
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
        
        if not request.conversation_history and not request.situation:
            # Generate a generic checklist if no conversation
            conversation_history = []
            user_context = {"programs": list(all_programs)}
        else:
            conversation_history = request.conversation_history
            user_context = {
                "situation": request.situation,
                "programs": list(all_programs)
            } if request.situation else {"programs": list(all_programs)}
        
        # Generate checklist using your existing logic with programs
        try:
            print(f"Generating checklist with {len(conversation_history)} messages and programs: {list(all_programs)}")
            checklist_items = generate_checklist(conversation_history, user_context)
            print(f"Generated {len(checklist_items)} checklist items")
        except Exception as gen_error:
            import traceback
            print(f"Error in generate_checklist: {str(gen_error)}")
            print(traceback.format_exc())
            # Fallback to generic checklist
            checklist_items = generate_checklist([], {})
        
        if not checklist_items or len(checklist_items) == 0:
            print("Checklist items empty, generating fallback")
            checklist_items = generate_checklist([], {})
        
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
    Generate and download a calendar file (.ics) based on actual conversation programs
    """
    try:
        # Extract programs from conversation (same logic as checklist)
        all_programs = set()
        if request.programs:
            all_programs.update(request.programs)
        
        # Extract programs from conversation history
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
        
        # Generate calendar events based on ACTUAL programs mentioned
        base_date = datetime.now() + timedelta(days=1)
        events = []
        
        event_num = 1
        programs_list = list(all_programs)
        
        # If no programs, create generic events
        if not programs_list:
            programs_list = ['CalFresh', 'Medi-Cal', 'Unemployment Insurance']
        
        calendar_events = {
            'CalFresh': {
                'summary': 'Apply for CalFresh',
                'description': 'Apply for CalFresh food assistance program',
                'url': 'https://benefitscal.com',
                'days_offset': 1
            },
            'Medi-Cal': {
                'summary': 'Apply for Medi-Cal',
                'description': 'Apply for Medi-Cal health insurance',
                'url': 'https://benefitscal.com',
                'days_offset': 3
            },
            'Unemployment Insurance': {
                'summary': 'Apply for Unemployment Insurance',
                'description': 'File your unemployment insurance claim',
                'url': 'https://edd.ca.gov',
                'days_offset': 0
            },
            'CalWORKs': {
                'summary': 'Apply for CalWORKs',
                'description': 'Apply for CalWORKs cash assistance',
                'url': 'https://benefitscal.com',
                'days_offset': 2
            },
            'Section 8': {
                'summary': 'Contact Housing Authority',
                'description': 'Apply for Section 8 housing assistance',
                'url': 'https://211california.org',
                'days_offset': 2
            }
        }
        
        days_offset = 0
        for program in programs_list[:5]:  # Limit to 5 events
            if program in calendar_events:
                event_info = calendar_events[program]
                event_date = base_date + timedelta(days=days_offset)
                
                events.append(f"""BEGIN:VEVENT
UID:benefitsflow-{event_num}@benefitsflow.com
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{event_date.strftime('%Y%m%dT090000Z')}
DTEND:{event_date.strftime('%Y%m%dT100000Z')}
SUMMARY:{event_info['summary']}
DESCRIPTION:{event_info['description']}
LOCATION:Online Application
URL:{event_info['url']}
END:VEVENT""")
                
                event_num += 1
                days_offset += 3  # Space events 3 days apart
        
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

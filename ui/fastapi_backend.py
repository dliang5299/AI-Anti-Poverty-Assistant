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
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# Import your existing modules (fallback)
from rag_backend import get_rag_response
from utils import extract_programs_from_conversation, get_quick_replies

# Import UI generators (all logic in UI folder)
from checklist_generator import generate_checklist
from calendar_generator import generate_calendar_events

# Import metrics tracking (UI folder only)
from metrics import (
    log_conversation,
    log_download,
    log_performance,
    get_monthly_stats,
    export_to_csv
)

# Deric's RAG Service URL
# AWS Deployment (two separate EC2 instances):
#   - Use RAG instance's PRIVATE IP: http://10.0.1.xxx:8000 (recommended, free, stable)
#   - Or use RAG instance's public IP: http://x.x.x.x:8000 (not recommended, changes on restart)
# AWS Deployment (single instance with docker-compose): use service name "app" -> http://app:8000
# Local dev: use "localhost" -> http://localhost:8000
# Check both RAG_SERVICE_URL and RAG_API_URL for compatibility
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL") or os.getenv("RAG_API_URL") or "http://localhost:8000"

# Debug: Print RAG service URL on startup to help diagnose connection issues
print(f"🔍 [AWS DEBUG] RAG_SERVICE_URL configured as: {RAG_SERVICE_URL}")
print(f"🔍 [AWS DEBUG] RAG_SERVICE_URL env var: {os.getenv('RAG_SERVICE_URL')}")
print(f"🔍 [AWS DEBUG] RAG_API_URL env var: {os.getenv('RAG_API_URL')}")
if not os.getenv("RAG_SERVICE_URL") and not os.getenv("RAG_API_URL"):
    print(f"⚠️ [AWS WARNING] No RAG_SERVICE_URL or RAG_API_URL set! Using default: {RAG_SERVICE_URL}")
    print(f"⚠️ [AWS WARNING] For AWS deployment, set RAG_API_URL=http://app:8000 in docker-compose.yml or environment")

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

class ChecklistPreviewResponse(BaseModel):
    checklist_items: List[Dict[str, Any]] = []
    markdown: str = ""
    has_sufficient_context: bool = False
    message: Optional[str] = None

# Serve static files (images, CSS, etc.)
static_dir = Path(__file__).parent
if (static_dir / "images").exists():
    app.mount("/images", StaticFiles(directory=str(static_dir / "images")), name="images")

# Serve favicon files
@app.get("/favicon.ico")
async def favicon_ico():
    """Serve favicon.ico"""
    favicon_path = static_dir / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/x-icon")
    raise HTTPException(status_code=404)

@app.get("/favicon-16x16.png")
async def favicon_16():
    """Serve 16x16 favicon"""
    favicon_path = static_dir / "favicon-16x16.png"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/png")
    raise HTTPException(status_code=404)

@app.get("/favicon-32x32.png")
async def favicon_32():
    """Serve 32x32 favicon"""
    favicon_path = static_dir / "favicon-32x32.png"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/png")
    raise HTTPException(status_code=404)

@app.get("/apple-touch-icon.png")
async def apple_touch_icon():
    """Serve Apple touch icon"""
    icon_path = static_dir / "apple-touch-icon.png"
    if icon_path.exists():
        return FileResponse(str(icon_path), media_type="image/png")
    raise HTTPException(status_code=404)

@app.get("/site.webmanifest")
async def site_webmanifest():
    """Serve site.webmanifest"""
    manifest_path = static_dir / "site.webmanifest"
    if manifest_path.exists():
        return FileResponse(str(manifest_path), media_type="application/manifest+json")
    raise HTTPException(status_code=404)

# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML frontend"""
    html_file = static_dir / "benefitsflow_frontend.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>BenefitsFlow</h1><p>Frontend file not found</p>")

@app.get("/")
async def api_root():
    """API root endpoint"""
    return {"message": "BenefitsFlow API is running!", "status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint - handles user messages and returns AI responses
    Calls Deric's RAG service, with fallback to demo if unavailable
    """
    start_time = time.time()
    rag_time_ms = None
    error_type = None
    
    try:
        # Try to call Deric's RAG service first
        try:
                rag_start = time.time()
                print(f"🔍 [DEBUG] Attempting to connect to RAG service at: {RAG_SERVICE_URL}/chat")
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
                rag_time_ms = int((time.time() - rag_start) * 1000)
                print(f"✅ [SUCCESS] Connected to RAG service! Response time: {rag_time_ms}ms")
                
                result = ChatResponse(
                    response=rag_result["response"],
                    sources=rag_result.get("sources", []),
                    programs=rag_result.get("programs", [])
                )
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            # Fallback to demo RAG if Deric's service is unavailable
            error_type = type(e).__name__
            print(f"⚠️ [WARNING] RAG service unavailable at {RAG_SERVICE_URL}")
            print(f"⚠️ [WARNING] Error type: {error_type}")
            print(f"⚠️ [WARNING] Error details: {str(e)}")
            print(f"⚠️ [WARNING] Using fallback demo RAG responses")
            response_text, sources, programs = get_rag_response(
                request.message, 
                request.conversation_history, 
                {"situation": request.situation}
            )
            
            result = ChatResponse(
                response=response_text,
                sources=sources,
                programs=programs
            )
        
        # Log metrics
        response_time_ms = int((time.time() - start_time) * 1000)
        message_count = len(request.conversation_history) + 1 if request.conversation_history else 1
        
        log_conversation(message_count=message_count)
        log_performance(
            response_time_ms=response_time_ms,
            rag_time_ms=rag_time_ms,
            error_type=error_type
        )
        
        return result
        
    except Exception as e:
        error_type = type(e).__name__
        log_performance(error_type=error_type)
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

def _escape_xml(text: str) -> str:
    """Escape XML/HTML special characters for safe PDF generation"""
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))

def generate_checklist_pdf(checklist_items: List[Dict[str, Any]], situation: str, programs: List[str]) -> bytes:
    """
    Generate a nicely formatted PDF checklist using reportlab
    
    Args:
        checklist_items: List of checklist item dictionaries
        situation: User's situation
        programs: List of programs mentioned
    
    Returns:
        PDF file content as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           rightMargin=0.75*inch, leftMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define custom styles
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=HexColor('#1a5490'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Subtitle style
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=HexColor('#666666'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    # Section header style
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=HexColor('#1a5490'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold',
        borderWidth=1,
        borderColor=HexColor('#1a5490'),
        borderPadding=8,
        backColor=HexColor('#e8f0f8')
    )
    
    # Item title style
    item_title_style = ParagraphStyle(
        'ItemTitle',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=HexColor('#2c3e50'),
        spaceAfter=6,
        spaceBefore=16,
        fontName='Helvetica-Bold'
    )
    
    # Description style
    desc_style = ParagraphStyle(
        'Description',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#444444'),
        spaceAfter=8,
        leftIndent=20
    )
    
    # Detail style
    detail_style = ParagraphStyle(
        'Detail',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#555555'),
        spaceAfter=4,
        leftIndent=40,
        bulletIndent=30
    )
    
    # Deadline style
    deadline_style = ParagraphStyle(
        'Deadline',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#c0392b'),
        spaceAfter=6,
        leftIndent=20,
        fontName='Helvetica-Bold'
    )
    
    # Link style
    link_style = ParagraphStyle(
        'Link',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#3498db'),
        spaceAfter=8,
        leftIndent=20
    )
    
    # Normal text style
    normal_style = styles['Normal']
    
    # Add title
    elements.append(Paragraph("BenefitsFlow Personalized Checklist", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", subtitle_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Add situation section
    if situation and situation != 'General':
        elements.append(Paragraph("Your Situation", section_style))
        elements.append(Paragraph(_escape_xml(situation), desc_style))
        elements.append(Spacer(1, 0.15*inch))
    
    # Add programs section if available
    if programs:
        elements.append(Paragraph("Programs Mentioned", section_style))
        programs_text = ", ".join([_escape_xml(str(p)) for p in programs if p])
        if programs_text:
            elements.append(Paragraph(programs_text, desc_style))
        elements.append(Spacer(1, 0.15*inch))
    
    # Add checklist items section
    elements.append(Paragraph("Checklist Items", section_style))
    
    # Add each checklist item
    for i, item in enumerate(checklist_items, 1):
        if not isinstance(item, dict):
            continue
        
        # Item number and title with checkbox
        title = _escape_xml(item.get('title', 'Item'))
        item_header = f"☐ {i}. {title}"
        elements.append(Paragraph(item_header, item_title_style))
        
        # Description
        description = item.get('description', '')
        if description:
            elements.append(Paragraph(_escape_xml(description), desc_style))
        
        # Deadline
        deadline = item.get('deadline', '')
        if deadline:
            deadline_escaped = _escape_xml(deadline)
            deadline_text = f"<b>Deadline:</b> {deadline_escaped}"
            elements.append(Paragraph(deadline_text, deadline_style))
        
        # Action items/details
        details = item.get('details', [])
        if details and isinstance(details, list):
            for detail in details:
                if detail:
                    # Use bullet point
                    detail_escaped = _escape_xml(str(detail))
                    detail_text = f"• {detail_escaped}"
                    elements.append(Paragraph(detail_text, detail_style))
        
        # Link
        link = item.get('link', '')
        if link:
            link_escaped = _escape_xml(link)
            link_text = f"<link href='{link_escaped}' color='blue'><u>Visit: {link_escaped}</u></link>"
            elements.append(Paragraph(link_text, link_style))
        
        # Add spacing between items
        elements.append(Spacer(1, 0.1*inch))
    
    # Add next steps section
    elements.append(PageBreak())
    elements.append(Paragraph("Next Steps", section_style))
    
    next_steps = [
        "Review each item above carefully",
        "Check eligibility requirements for each program",
        "Gather required documents before applying",
        "Apply for benefits that match your situation",
        "Keep track of application deadlines and follow up"
    ]
    
    for step in next_steps:
        elements.append(Paragraph(f"• {step}", detail_style))
    
    elements.append(Spacer(1, 0.2*inch))
    
    # Add helpful resources section
    elements.append(Paragraph("Helpful Resources", section_style))
    
    resources = [
        ("BenefitsCal.com", "Apply for CalFresh, Medi-Cal, and more"),
        ("EDD.ca.gov", "Unemployment Insurance and job services"),
        ("DHCS.ca.gov", "Health coverage and Medi-Cal information"),
        ("211california.org", "Local resources and assistance")
    ]
    
    for resource_name, resource_desc in resources:
        resource_text = f"<b>{resource_name}</b> - {resource_desc}"
        elements.append(Paragraph(resource_text, desc_style))
        elements.append(Spacer(1, 0.05*inch))
    
    elements.append(Spacer(1, 0.2*inch))
    
    # Add footer
    footer_text = "Generated by BenefitsFlow - California Benefits Navigator<br/>For questions or assistance, visit: https://benefitscal.com"
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#888888'),
        alignment=TA_CENTER,
        spaceBefore=20
    )
    elements.append(Paragraph(footer_text, footer_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes

def checklist_to_markdown(checklist_items: List[Dict[str, Any]], situation: str, programs: List[str]) -> str:
    """
    Convert checklist items to nicely formatted markdown
    
    Args:
        checklist_items: List of checklist item dictionaries
        situation: User's situation
        programs: List of programs mentioned
    
    Returns:
        Markdown formatted string
    """
    lines = []
    
    # Title
    lines.append("# BenefitsFlow Personalized Checklist")
    lines.append(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    lines.append("")
    
    # Situation section
    if situation and situation != 'General':
        lines.append("## Your Situation")
        lines.append(situation)
        lines.append("")
    
    # Programs section
    if programs:
        lines.append("## Programs Mentioned")
        lines.append(", ".join(programs))
        lines.append("")
    
    # Checklist items
    lines.append("## Checklist Items")
    lines.append("")
    
    for i, item in enumerate(checklist_items, 1):
        if not isinstance(item, dict):
            continue
        
        # Item header with checkbox
        title = item.get('title', 'Item')
        lines.append(f"### ☐ {i}. {title}")
        lines.append("")
        
        # Description
        description = item.get('description', '')
        if description:
            lines.append(description)
            lines.append("")
        
        # Deadline
        deadline = item.get('deadline', '')
        if deadline:
            lines.append(f"**Deadline:** {deadline}")
            lines.append("")
        
        # Action items/details
        details = item.get('details', [])
        if details and isinstance(details, list):
            for detail in details:
                if detail:
                    lines.append(f"- {detail}")
            lines.append("")
        
        # Link
        link = item.get('link', '')
        if link:
            lines.append(f"🔗 [Visit: {link}]({link})")
            lines.append("")
        
        # Add spacing between items
        if i < len(checklist_items):
            lines.append("---")
            lines.append("")
    
    # Next steps section
    lines.append("## Next Steps")
    lines.append("")
    next_steps = [
        "Review each item above carefully",
        "Check eligibility requirements for each program",
        "Gather required documents before applying",
        "Apply for benefits that match your situation",
        "Keep track of application deadlines and follow up"
    ]
    for step in next_steps:
        lines.append(f"- {step}")
    lines.append("")
    
    # Helpful resources
    lines.append("## Helpful Resources")
    lines.append("")
    resources = [
        ("BenefitsCal.com", "Apply for CalFresh, Medi-Cal, and more", "https://benefitscal.com"),
        ("EDD.ca.gov", "Unemployment Insurance and job services", "https://edd.ca.gov"),
        ("DHCS.ca.gov", "Health coverage and Medi-Cal information", "https://dhcs.ca.gov"),
        ("211california.org", "Local resources and assistance", "https://211california.org")
    ]
    for resource_name, resource_desc, resource_url in resources:
        lines.append(f"- **[{resource_name}]({resource_url})** - {resource_desc}")
    lines.append("")
    
    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by BenefitsFlow - California Benefits Navigator*")
    lines.append("*For questions or assistance, visit: https://benefitscal.com*")
    
    return "\n".join(lines)

@app.post("/checklist/preview", response_model=ChecklistPreviewResponse)
async def preview_checklist_post(request: DownloadRequest):
    """
    Get checklist preview as markdown (for display in modal before downloading PDF)
    """
    try:
        # Validate request
        if not isinstance(request.conversation_history, list):
            request.conversation_history = []
        if not isinstance(request.programs, list):
            request.programs = []
        
        # Extract programs from conversation (same logic as download endpoint)
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
        
        # Generate checklist using UI generator
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
            return ChecklistPreviewResponse(
                checklist_items=[],
                markdown="",
                has_sufficient_context=False,
                message="Not enough conversation context to generate a personalized checklist. Please have a few more exchanges with the assistant about your specific situation and needs."
            )
        
        # Convert to markdown
        markdown_content = checklist_to_markdown(
            checklist_items,
            request.situation or 'General',
            list(all_programs)
        )
        
        return ChecklistPreviewResponse(
            checklist_items=checklist_items,
            markdown=markdown_content,
            has_sufficient_context=True,
            message=None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating preview: {str(e)}")

@app.post("/download/checklist")
async def download_checklist(request: DownloadRequest):
    """
    Generate and download a personalized checklist as a PDF file using RAG service
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
            print(f"DEBUG: Generating checklist - conversation history length: {len(request.conversation_history)}")
            print(f"DEBUG: Programs extracted: {list(all_programs)}")
            
            user_context = {
                "situation": request.situation,
                "programs": list(all_programs)
            }
            checklist_items = generate_checklist(request.conversation_history, user_context)
            print(f"DEBUG: Checklist items generated: {len(checklist_items)}")
        except Exception as e:
            print(f"Error generating checklist: {e}")
            import traceback
            traceback.print_exc()
            checklist_items = []
        
        if not checklist_items or len(checklist_items) == 0:
            # Return fallback PDF if no items generated
            fallback_items = [{
                'title': 'Continue Conversation',
                'description': 'Not enough conversation context to generate a personalized checklist.',
                'deadline': '',
                'details': [
                    'Continue your conversation with the assistant',
                    'Provide more details about your specific situation',
                    'Mention programs you\'re interested in',
                    'Share any deadlines or important dates',
                    'Describe documents you need to gather'
                ],
                'link': ''
            }]
            pdf_content = generate_checklist_pdf(
                fallback_items,
                request.situation or 'General',
                list(all_programs)
            )
        else:
            # Generate PDF with checklist items
            pdf_content = generate_checklist_pdf(
                checklist_items,
                request.situation or 'General',
                list(all_programs)
            )
        
        filename = f'benefits-checklist-{datetime.now().strftime("%Y%m%d")}.pdf'
        
        # Log download metrics
        log_download('checklist', list(all_programs) if all_programs else None)
        
        return Response(
            content=pdf_content,
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_content))
            }
        )
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Checklist download error: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Error generating checklist: {str(e)}")

@app.post("/download/calendar")
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
        
        # Log download metrics
        log_download('calendar', list(all_programs) if all_programs else None)
        
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

@app.get("/situations")
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

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/health/rag")
async def rag_health_check():
    """
    Check if RAG service is accessible
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{RAG_SERVICE_URL}/health")
            response.raise_for_status()
            rag_status = response.json()
            return {
                "status": "connected",
                "rag_service_url": RAG_SERVICE_URL,
                "rag_service_status": rag_status,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "status": "disconnected",
            "rag_service_url": RAG_SERVICE_URL,
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.now().isoformat()
        }

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(days: int = 30):
    """
    Admin dashboard page with stats and download link
    """
    try:
        stats = get_monthly_stats(days=days)
        
        # Format stats for display
        conversations_total = stats.get('conversations', {}).get('total', 0)
        total_messages = stats.get('conversations', {}).get('total_messages', 0)
        downloads = stats.get('downloads', {})
        performance = stats.get('performance', {})
        program_popularity = stats.get('program_popularity', {})
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>BenefitsFlow Admin Dashboard</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 40px auto;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .header {{
                    background: #2c3e50;
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }}
                .stat-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .stat-card h3 {{
                    margin: 0 0 10px 0;
                    color: #2c3e50;
                    font-size: 14px;
                    text-transform: uppercase;
                }}
                .stat-card .value {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #3498db;
                }}
                .download-section {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .download-btn {{
                    background: #27ae60;
                    color: white;
                    padding: 15px 30px;
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    margin: 10px;
                }}
                .download-btn:hover {{
                    background: #229954;
                }}
                .program-list {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .program-list ul {{
                    list-style: none;
                    padding: 0;
                }}
                .program-list li {{
                    padding: 8px;
                    border-bottom: 1px solid #eee;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 BenefitsFlow Admin Dashboard</h1>
                <p>Performance metrics for the last {days} days</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total Conversations</h3>
                    <div class="value">{conversations_total}</div>
                </div>
                <div class="stat-card">
                    <h3>Total Messages</h3>
                    <div class="value">{total_messages}</div>
                </div>
                <div class="stat-card">
                    <h3>Avg Response Time</h3>
                    <div class="value">{performance.get('avg_response_time_ms', 0):.0f}ms</div>
                </div>
                <div class="stat-card">
                    <h3>Errors</h3>
                    <div class="value">{performance.get('error_count', 0)}</div>
                </div>
            </div>
            
            <div class="download-section">
                <h2>📥 Download Reports</h2>
                <p>Export metrics data as CSV files or view JSON stats online.</p>
                <a href="/admin/export/csv" class="download-btn">Download CSV Report</a>
                <a href="/admin/stats?days={days}" target="_blank" class="download-btn" style="background: #3498db;">View JSON Stats</a>
            </div>
            
            <div class="stats-grid" style="margin-top: 20px;">
                <div class="stat-card">
                    <h3>Downloads by Type</h3>
                    <ul>
                        <li>Checklists: {downloads.get('checklist', 0)}</li>
                        <li>Calendars: {downloads.get('calendar', 0)}</li>
                    </ul>
                </div>
                <div class="program-list">
                    <h3>Top Programs</h3>
                    <ul>
                        {''.join([f'<li>{prog}: {count} mentions</li>' for prog, count in list(program_popularity.items())[:10]])}
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading admin dashboard: {str(e)}")

@app.get("/admin/stats")
async def get_stats(days: int = 30):
    """
    Get monthly statistics (admin endpoint)
    
    Args:
        days: Number of days to look back (default 30)
    
    Returns:
        Dictionary with statistics
    """
    try:
        stats = get_monthly_stats(days=days)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

@app.get("/admin/export/csv")
async def export_csv_report(table: str = "all"):
    """
    Export metrics database to CSV file (admin endpoint)
    
    Args:
        table: Which table to export - "conversations", "downloads", "performance", or "all" (default)
    
    Returns:
        CSV file(s) - if "all", returns conversations.csv (others can be accessed via ?table=downloads, etc.)
    """
    try:
        from pathlib import Path
        import csv
        from metrics import get_db
        
        # Export to temporary directory
        temp_dir = Path("/tmp") / "benefitsflow_export"
        temp_dir.mkdir(exist_ok=True)
        
        if table == "all":
            # Export all tables and return the first one (conversations) as primary
            csv_files = export_to_csv(output_dir=temp_dir)
            if not csv_files:
                raise HTTPException(status_code=404, detail="No data to export")
            # Return conversations.csv as the primary file
            csv_path = temp_dir / "conversations.csv"
            if csv_path.exists():
                return FileResponse(
                    path=str(csv_path),
                    media_type='text/csv',
                    filename=f'benefitsflow_conversations_{datetime.now().strftime("%Y%m%d")}.csv'
                )
            # Fallback to first available file
            return FileResponse(
                path=str(csv_files[0]),
                media_type='text/csv',
                filename=f'benefitsflow_metrics_{datetime.now().strftime("%Y%m%d")}.csv'
            )
        else:
            # Export specific table
            with get_db() as conn:
                cursor = conn.execute(f'SELECT * FROM {table}')
                columns = [description[0] for description in cursor.description]
                
                csv_path = temp_dir / f'{table}.csv'
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(columns)
                    writer.writerows(cursor.fetchall())
                
                return FileResponse(
                    path=str(csv_path),
                    media_type='text/csv',
                    filename=f'benefitsflow_{table}_{datetime.now().strftime("%Y%m%d")}.csv'
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting CSV: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # AWS Deployment: UI runs on port 8501, RAG service on port 8000
    # Port is configured in docker-compose.yml or can be overridden with UI_PORT env var
    ui_port = int(os.getenv("UI_PORT", "8501"))
    print(f"🚀 [AWS] Starting UI backend on port {ui_port}")
    print(f"🔗 [AWS] RAG service expected at: {RAG_SERVICE_URL}")
    uvicorn.run(app, host="0.0.0.0", port=ui_port)

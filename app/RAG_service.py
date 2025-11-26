# --- imports (near top of file) ---
import os, json
import boto3
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from functools import lru_cache
from botocore.exceptions import ProfileNotFound

from app.RAG_ingest import RAGIngestor
from app.RAG_search import RAGSearcher, get_rag_response
from app.config import get_regions, get_models, get_bedrock_bearer_token
from app.generators.checklist_generator import generate_checklist
from app.generators.calendar_generator import generate_calendar_events

regions = get_regions()
models = get_models()

app = FastAPI(title="BenefitsFlow RAG API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- robust Bedrock client (lazy) ---
@lru_cache(maxsize=None)
def get_bedrock():
    try:
        return boto3.client("bedrock-runtime", region_name=regions["bedrock"])
    except ProfileNotFound:
        os.environ.pop("AWS_PROFILE", None)
        return boto3.client("bedrock-runtime", region_name=regions["bedrock"])

# --- parse Bedrock output safely across providers/APIs ---
def _extract_text_from_bedrock(resp: dict | bytes | str) -> str:
    if isinstance(resp, (bytes, str)):
        try:
            resp = json.loads(resp)
        except Exception:
            return ""

    # Converse shape: output.message.content = [{"type":"text","text":"..."}]
    try:
        parts = (
            resp.get("output", {})
                .get("message", {})
                .get("content", [])
        )
        if isinstance(parts, list):
            texts = []
            for p in parts:
                if isinstance(p, dict) and "text" in p:
                    texts.append(p["text"])
            if texts:
                return "\n".join(texts).strip()
    except Exception:
        pass

    # Anthropic invoke_model: {"content":[{"type":"text","text":"..."}], ...}
    try:
        content = resp.get("content")
        if isinstance(content, list) and content and isinstance(content[0], dict):
            if "text" in content[0]:
                return content[0]["text"].strip()
    except Exception:
        pass

    # AI21-like: {"generations":[{"text":"..."}]}
    gens = resp.get("generations")
    if isinstance(gens, list) and gens and isinstance(gens[0], dict) and "text" in gens[0]:
        return gens[0]["text"].strip()

    # Cohere/others: sometimes "outputText" / "generation" / "answer"
    for k in ("outputText", "generation", "answer"):
        v = resp.get(k)
        if isinstance(v, str):
            return v.strip()

    return ""

# --- schemas you already have ---
class IngestRequest(BaseModel):
    bucket: str
    prefix: Optional[str] = ""

class ChatRequest(BaseModel):
    message: str
    situation: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = []

class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, str]] = []
    programs: List[str] = []
    context: Optional[str] = None

class ChecklistRequest(BaseModel):
    situation: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = []
    programs: List[str] = []

class ChecklistResponse(BaseModel):
    checklist_items: List[Dict[str, Any]] = []
    has_sufficient_context: bool = False
    message: Optional[str] = None

class CalendarRequest(BaseModel):
    situation: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = []
    programs: List[str] = []

class CalendarResponse(BaseModel):
    events: List[Dict[str, Any]] = []
    has_sufficient_context: bool = False
    message: Optional[str] = None

# Instantiate components
ingestor = RAGIngestor()
searcher = RAGSearcher()

@app.post("/ingest")
def ingest(request: IngestRequest):
    try:
        ingestor.create_index()
        stats = ingestor.ingest_from_s3(request.bucket, request.prefix or "")
        return {"status": "success", "statistics": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Return a Bedrock-generated answer with Pinecone sources; fallback to RAG-only if Bedrock fails."""
    try:
        # 1) Retrieve top-k context from Pinecone via your searcher
        matches = searcher.search_vectors(request.message, limit=10)
        context = searcher.format_context(matches)

        # 2) Build the prompt
        today = datetime.now().strftime("%B %d, %Y")
        system_prompt = (
            "You are a concise, helpful social worker assistant providing assistance to users who have lost their job in California at a 5th-grade reading level. "
            "Explain program basics, eligibility, steps, necessary documents, timelines; include county-variation note. "
            "Suggest other programs that may be relevant even if not directly asked given the context. "
            "Do not guarantee approval or benefit amounts. Do not generalize county-specific rules without stating they vary by county. "
            "Do not provide outdated income limits or timelines. Do not give legal/financial advice beyond program guidance. "
            "Do not fabricate citations or sources. Use empathetic language in your response. "
            "Format your responses using Markdown syntax: use **bold** for emphasis, ## for section headers, "
            "- or * for bullet lists, | for tables, and [link text](url) for links. "
            "Use clear section headers (##) to organize information and tables when presenting structured data. "
            f"Today's date is {today}. "
            "Do not answer questions unrelated to social services or benefits programs in California."
        )
        user_prompt = f"Context:\n{context}\n\nQuestion: {request.message}\n\nAnswer:"

        # 3) Call Bedrock (Converse path shown; adjust modelId from your config)
        text = ""
        try:
            bedrock = get_bedrock()
            br = bedrock.converse(
                modelId=models["llm_model"],  # e.g., "anthropic.claude-3-5-sonnet-20241022-v2:0"
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                system=[{"text": system_prompt}],
                # You can pass inferenceConfig if you want maxTokens/temperature/topP, etc.
            )
            text = _extract_text_from_bedrock(br)
        except Exception as e:
            # Log to server console for diagnosis; don't leak to client
            print("[Bedrock error]", repr(e))

        # 4) If Bedrock returned nothing, fallback to your RAG-only wrapper
        if not text:
            fallback_answer, fallback_sources, programs = get_rag_response(request.message)
            return ChatResponse(response=fallback_answer, sources=fallback_sources, programs=programs, context=context)
    
        # 5) Build sources (names + URLs from Pinecone metadata)
        srcs: List[Dict[str, str]] = []
        for m in matches:
            name = (
                m.get("heading")
                or m.get("doc_id")
                or m.get("s3_key")
                or "RAG chunk"
            )
            url = m.get("source_url") or ""
            date = m.get("captured_at") or ""

            srcs.append(
                {
                    "name": name,
                    "url": url,
                    "date": date,
                    # explicit source_url so tests can rely on it
                    "source_url": url,
                    "text": m.get("text", ""),
                    "chunk_id": str(m.get("chunk_id") or ""),
                    "doc_id": str(m.get("doc_id") or ""),
                    "section_id": str(m.get("section_id") or ""),
                    "score": str(m.get("score", "")),
                }
            )

        return ChatResponse(response=text, sources=srcs, programs=[], context=context)


    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/checklist", response_model=ChecklistResponse)
def generate_checklist_endpoint(request: ChecklistRequest):
    """Generate personalized checklist based on conversation using RAG"""
    try:
        user_context = {
            "situation": request.situation,
            "programs": request.programs
        }
        
        checklist_items = generate_checklist(request.conversation_history, user_context)
        
        if not checklist_items:
            return ChecklistResponse(
                checklist_items=[],
                has_sufficient_context=False,
                message="Not enough conversation context to generate a personalized checklist. Please have a few more exchanges with the assistant about your specific situation and needs."
            )
        
        return ChecklistResponse(
            checklist_items=checklist_items,
            has_sufficient_context=True,
            message=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating checklist: {str(e)}")

@app.post("/calendar", response_model=CalendarResponse)
def generate_calendar_endpoint(request: CalendarRequest):
    """Generate personalized calendar events based on conversation using RAG"""
    try:
        user_context = {
            "situation": request.situation,
            "programs": request.programs
        }
        
        events = generate_calendar_events(request.conversation_history, user_context)
        
        if not events:
            return CalendarResponse(
                events=[],
                has_sufficient_context=False,
                message="Not enough conversation context to generate personalized calendar events. Please discuss specific deadlines, renewal dates, or important dates with the assistant."
            )
        
        return CalendarResponse(
            events=events,
            has_sufficient_context=True,
            message=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating calendar: {str(e)}")

@app.get("/health")
def health():
    return {"service": "ok", "regions": regions, "model": models["llm_model"]}

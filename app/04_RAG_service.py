
import os
import boto3
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.02_RAG_ingest import RAGIngestor  # align to app file names
from app.03_RAG_search import RAGSearcher, get_rag_response
from app.00_config import get_regions, get_models, get_bedrock_bearer_token

regions = get_regions()
models = get_models()

app = FastAPI(title="BenefitsFlow RAG API", version="2.0.0")

# Enable broad CORS so the HTML UI can call the API locally or via ALB
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bedrock client in us-west-2
bedrock = boto3.client("bedrock-runtime", region_name=regions["bedrock"])

# Schemas expected by the UI backend
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
    """Match UI's expected /chat contract and return {response, sources, programs}."""
    try:
        # Retrieve context with our searcher
        matches = searcher.search_vectors(request.message, limit=5)
        context = searcher.format_context(matches)

        # Compose prompt
        system_prompt = "You are a helpful assistant. Only answer using the provided context."
        user_prompt = f"Context:\n{context}\n\nQuestion: {request.message}\n\nAnswer:"

        # Optional bearer token header placeholder (if used)
        bearer = get_bedrock_bearer_token()

        # Invoke Bedrock Claude
        response = bedrock.converse(
            modelId=models["llm_model"],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"maxTokens": 600, "temperature": 0.5},
            system=[{"text": system_prompt}],
        )

        text = response["output"]["message"]["content"][0]["text"] if "output" in response else ""

        # Convert sources to UI shape
        srcs = []
        for m in matches:
            name = m.get("s3_key","")
            srcs.append({"name": name or "S3 Document", "url": "", "date": ""})

        # Programs placeholder (integration point for BenefitsFlow specific outputs)
        programs: List[str] = []

        return ChatResponse(response=text, sources=srcs, programs=programs)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"service": "ok", "regions": regions, "model": models["llm_model"]}

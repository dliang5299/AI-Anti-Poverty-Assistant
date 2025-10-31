import os
import boto3
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.RAGIngest import RAGIngestor
from app.RAGSearch import RAGSearcher
from app.config import get_regions, get_models, get_bedrock_bearer_token

regions = get_regions()
models = get_models()

app = FastAPI(title="RAG AI Search Service", version="1.1.0")

# Bedrock client in us-west-2
bedrock = boto3.client("bedrock-runtime", region_name=regions["bedrock"])

# RAG components
ingestor = RAGIngestor()
searcher = RAGSearcher()

class IngestRequest(BaseModel):
    bucket: str
    prefix: Optional[str] = ""

class ChatRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    max_tokens: Optional[int] = 500
    temperature: Optional[float] = 0.7

class ChatResponse(BaseModel):
    query: str
    answer: str
    sources: list
    context_used: str

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
    try:
        matches = searcher.search_vectors(request.query, limit=request.top_k or 5)
        context = searcher.format_context(matches)

        system_prompt = "You are a helpful AI assistant. Answer based on the provided context."
        user_prompt = f"Context:\n{context}\n\nQuestion: {request.query}\n\nAnswer:"

        # Optional bearer token header if provided via Secrets Manager
        extra_headers = {}
        bearer = get_bedrock_bearer_token()
        if bearer:
            extra_headers["x-amz-bedrock-bearer"] = bearer

        response = bedrock.converse(
            modelId=models["llm_model"],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={
                "maxTokens": request.max_tokens or 500,
                "temperature": float(request.temperature or 0.7)
            },
            system=[{"text": system_prompt}],
            # Pass optional headers if needed (botocore may not accept arbitrary headers; include here for clarity)
            # headers=extra_headers
        )

        answer = response["output"]["message"]["content"][0]["text"]
        sources = [
            {"file": m["s3_key"], "score": m["score"], "chunk_index": m["chunk_index"]}
            for m in matches
        ]

        return ChatResponse(query=request.query, answer=answer, sources=sources, context_used=context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"service": "ok", "regions": regions, "model": models["llm_model"]}

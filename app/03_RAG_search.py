from typing import List, Dict, Any
from openai import OpenAI
from pinecone import Pinecone
from app.config import get_openai_api_key, get_pinecone_api_key, get_pinecone_config, get_models

class RAGSearcher:
    """Query embedding and top-k vector search in Pinecone."""

    def __init__(self, index_name: str | None = None):
        self.pcfg = get_pinecone_config()
        self.models = get_models()
        self.index_name = index_name or self.pcfg["index_name"]

        self.pc = Pinecone(api_key=get_pinecone_api_key())
        self.index = self.pc.Index(self.index_name)

        self.openai_client = OpenAI(api_key=get_openai_api_key())

    def embed_query(self, query: str) -> List[float]:
        resp = self.openai_client.embeddings.create(
            model=self.models["embed_model"],
            input=query
        )
        return resp.data[0].embedding

    def search_vectors(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        qv = self.embed_query(query)
        res = self.index.query(vector=qv, top_k=limit, include_metadata=True)
        out = []
        for m in res.get("matches", []):
            out.append({
                "text": m["metadata"].get("text", ""),
                "score": m["score"],
                "s3_key": m["metadata"].get("s3_key", ""),
                "chunk_index": m["metadata"].get("chunk_index", 0),
            })
        return out

    def format_context(self, matches: List[Dict[str, Any]]) -> str:
        if not matches:
            return "No relevant context found."
        parts = []
        for i, m in enumerate(matches, 1):
            parts.append(f"[Source {i}] (Score: {m['score']:.3f}, File: {m['s3_key']})\n{m['text']}\n")
        return "\n".join(parts)

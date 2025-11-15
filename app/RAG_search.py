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

        out: List[Dict[str, Any]] = []
        for m in res.get("matches", []):
            md = m.get("metadata", {}) or {}
            out.append(
                {
                    "text": md.get("text", ""),
                    "score": m.get("score", 0.0),
                    "s3_key": md.get("s3_key", ""),
                    "chunk_index": md.get("chunk_index", 0),
                    # extra metadata from RAG_ingest
                    "chunk_id": md.get("chunk_id"),
                    "doc_id": md.get("doc_id"),
                    "section_id": md.get("section_id"),
                    "heading": md.get("heading"),
                    "source_url": md.get("source_url"),
                    "captured_at": md.get("captured_at"),
                }
            )
        return out

    def format_context(self, matches: List[Dict[str, Any]]) -> str:
        if not matches:
            return "No relevant context found."
        parts: List[str] = []
        for i, m in enumerate(matches, 1):
            src_name = m.get("heading") or m.get("s3_key") or m.get("doc_id") or f"chunk {i}"
            url = m.get("source_url") or ""
            meta_bits = [f"Score: {m['score']:.3f}", f"Source: {src_name}"]
            if url:
                meta_bits.append(f"URL: {url}")
            meta_str = ", ".join(meta_bits)
            parts.append(f"[Source {i}] ({meta_str})\n{m['text']}\n")
        return "\n".join(parts)


# === UI Integration Wrapper ===
def get_rag_response(
    query: str,
    conversation_history: list | None = None,
    user_context: dict | None = None,
):
    """Return (response_text, sources, programs) for UI integration."""
    searcher = RAGSearcher()
    matches = searcher.search_vectors(query, limit=5)
    context = searcher.format_context(matches)

    answer = (
        f"Based on {len(matches)} retrieved chunks, here are findings:\n\n"
        f"{context}\n\nQuestion: {query}"
    )

    # Convert our match metadata to UI's source format
    sources: List[Dict[str, str]] = []
    for m in matches:
        name = (
            m.get("heading")
            or m.get("doc_id")
            or m.get("s3_key")
            or "RAG chunk"
        )
        url = m.get("source_url") or ""
        date = m.get("captured_at") or ""

        sources.append(
            {
                "name": name,
                "url": url,
                "date": date,
                # keep an explicit source_url field as well
                "source_url": url,
                "chunk_id": (m.get("chunk_id") or ""),
                "doc_id": (m.get("doc_id") or ""),
                "section_id": (m.get("section_id") or ""),
            }
        )

    programs: List[str] = []
    return answer, sources, programs



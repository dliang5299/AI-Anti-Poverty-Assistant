import json
from typing import List, Dict, Any
from openai import OpenAI
from pinecone import Pinecone
import boto3
from app.config import (
    get_openai_api_key,
    get_pinecone_api_key,
    get_pinecone_config,
    get_models,
    get_regions,
)

class RAGSearcher:
    """Query embedding and top-k vector search in Pinecone."""

    def __init__(self, index_name: str | None = None):
        self.pcfg = get_pinecone_config()
        self.models = get_models()
        self.regions = get_regions()
        self.index_name = index_name or self.pcfg["index_name"]

        self.pc = Pinecone(api_key=get_pinecone_api_key())
        self.index = self.pc.Index(self.index_name)

        self.openai_client = OpenAI(api_key=get_openai_api_key())
        self.bedrock_client = None
        self.bedrock_rerank_model = (self.models.get("bedrock_rerank_model") or "").strip()

    def embed_query(self, query: str) -> List[float]:
        resp = self.openai_client.embeddings.create(
            model=self.models["embed_model"],
            input=query
        )
        return resp.data[0].embedding

    def search_vectors(self, query: str, limit: int) -> List[Dict[str, Any]]:
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
                    "chunk_id": md.get("chunk_id"),
                    "section_id": md.get("section_id"),
                    "heading": md.get("heading"),
                    "source_url": md.get("source_url"),
                }
            )
        return out

    def rerank_matches(self, query: str, matches: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
        """
        Prefer a dedicated Bedrock reranker (if configured), otherwise fall back
        to LLM-based cross-encoder scoring. Always returns at most top_n items.
        """
        if not matches:
            return []
        if len(matches) <= top_n:
            return matches

        # Bedrock reranker path (e.g., Cohere Rerank on Bedrock)
        if self.bedrock_rerank_model:
            try:
                if self.bedrock_client is None:
                    self.bedrock_client = boto3.client("bedrock-runtime", region_name=self.regions["bedrock"])

                # Cohere Rerank on Bedrock expects api_version plus documents as a list of strings
                docs: List[str] = []
                for m in matches:
                    text = (m.get("text") or "").strip()
                    snippet = " ".join(text.split())
                    docs.append(snippet)

                payload = {
                    # Cohere Rerank on Bedrock expects integer api_version (e.g., 2)
                    "api_version": 2,
                    "query": query,
                    "documents": docs,
                    "top_n": top_n,
                }
                resp = self.bedrock_client.invoke_model(
                    modelId=self.bedrock_rerank_model,
                    body=json.dumps(payload),
                    contentType="application/json",
                    accept="application/json",
                )
                body = resp.get("body")
                data = json.loads(body.read() if hasattr(body, "read") else body or "{}")
                results = data.get("results") or data.get("reranked_documents") or []
                scored = []
                for item in results:
                    idx = item.get("index") if "index" in item else item.get("id")
                    score = item.get("relevance_score") or item.get("score")
                    try:
                        idx_int = int(idx)
                        score_f = float(score)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= idx_int <= len(matches):
                        scored.append((score_f, idx_int))

                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    ordered = []
                    used = set()
                    for _, idx_int in scored:
                        if idx_int in used:
                            continue
                        ordered.append(matches[idx_int - 1])
                        used.add(idx_int)
                        if len(ordered) >= top_n:
                            break
                    if len(ordered) < top_n:
                        for pos, match in enumerate(matches, 1):
                            if pos in used:
                                continue
                            ordered.append(match)
                            if len(ordered) >= top_n:
                                break
                    return ordered[:top_n]
            except Exception as exc:
                print(f"[RERANK/Bedrock] falling back to LLM rerank: {exc}")

        # Fallback: cross-encoder style rerank using an LLM
        items = []
        for idx, m in enumerate(matches, 1):
            text = (m.get("text") or "").strip()
            snippet = " ".join(text.split())
            if len(snippet) > 800:
                snippet = snippet[:800] + "..."
            items.append({"index": idx, "text": snippet})

        prompt = {
            "query": query,
            "instruction": (
                "Score each chunk from 0 to 1 for how well it answers the query. "
                "Higher means more relevant and specific. Return JSON with "
                "a 'scores' list of objects: {'index': <chunk_number>, 'score': <float 0-1>}."
            ),
            "chunks": items,
            "max_results": top_n,
        }

        def _run_llm_rerank(model_name: str) -> dict:
            return self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a reranker. Only return valid JSON as instructed."},
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                temperature=0,
                max_tokens=400,
                response_format={"type": "json_object"},
            )

        try:
            model_choice = (
                self.models.get("rerank_model")
                or self.models.get("llm_model")
                or "gpt-4o-mini"
            )
            try:
                resp = _run_llm_rerank(model_choice)
            except Exception as primary_exc:
                # If the chosen model is unavailable, fall back to gpt-4o-mini
                if model_choice != "gpt-4o-mini":
                    resp = _run_llm_rerank("gpt-4o-mini")
                else:
                    raise primary_exc
            content = resp.choices[0].message.content or "{}"
            data = json.loads(content)
            scores = data.get("scores") or []
            scored = []
            for s in scores:
                try:
                    idx = int(s.get("index"))
                    sc = float(s.get("score"))
                except (TypeError, ValueError):
                    continue
                if 1 <= idx <= len(matches):
                    scored.append((sc, idx))

            scored.sort(key=lambda x: x[0], reverse=True)
            ordered: List[Dict[str, Any]] = []
            seen = set()
            for _, idx in scored:
                if idx in seen:
                    continue
                ordered.append(matches[idx - 1])
                seen.add(idx)
                if len(ordered) >= top_n:
                    break

            if len(ordered) < top_n:
                for pos, match in enumerate(matches, 1):
                    if pos in seen:
                        continue
                    ordered.append(match)
                    if len(ordered) >= top_n:
                        break

            return ordered[:top_n]
        except Exception as exc:
            print(f"[RERANK] fell back to vector order: {exc}")
            return matches[:top_n]

    def format_context(self, matches: List[Dict[str, Any]]) -> str:
        if not matches:
            return "No relevant context found."
        parts: List[str] = []
        for i, m in enumerate(matches, 1):
            title = (
                m.get("heading")
                or m.get("s3_key")
                or m.get("doc_id")
                or f"Source {i}"
            )
            url = m.get("source_url") or ""
            lines = [f"[Source {i}] {title}".strip()]
            if url:
                lines.append(f"URL: {url}")
            lines.append(m.get("text", ""))
            parts.append("\n".join(lines).strip())
        return "\n\n".join(parts)


# === UI Integration Wrapper ===
def get_rag_response(
    query: str,
    conversation_history: list | None = None,
    user_context: dict | None = None,
):
    """Return (response_text, sources, programs) for UI integration."""
    searcher = RAGSearcher()
    initial_matches = searcher.search_vectors(query, limit=50)
    matches = searcher.rerank_matches(query, initial_matches, top_n=10)
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

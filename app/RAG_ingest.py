import uuid
import json
import re
from typing import List, Dict, Any

import boto3
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

from app.config import (
    get_openai_api_key,
    get_regions,
    get_pinecone_api_key,
    get_pinecone_config,
    get_models,
)

def estimate_tokens(text: str) -> int:
    """Crude but stable token estimate: ~4 chars per token."""
    if not text:
        return 1
    return max(1, int(len(text) / 4))

def split_markdown_into_chunks(md: str, target_chars: int = 1500, overlap_chars: int = 300):
    """Chunk markdown by paragraphs/lists to ~target_chars, with overlap."""
    import re as _re
    if not md:
        return []
    paras = [p for p in _re.split(r"\n\s*\n", md.strip()) if p.strip()]
    chunks = []
    cur = []
    cur_len = 0
    for p in paras:
        p_block = p.strip()
        # if a single paragraph is huge, hard-split by lines
        if len(p_block) > target_chars * 1.25:
            lines = p_block.splitlines()
            buf, blen = [], 0
            for ln in lines:
                if blen + len(ln) + 1 > target_chars and buf:
                    chunks.append("\n".join(buf).strip())
                    # overlap from end of buf
                    overlap_text = "\n".join(buf)[-overlap_chars:]
                    buf, blen = ([overlap_text], len(overlap_text))
                buf.append(ln)
                blen += len(ln) + 1
            if buf:
                chunks.append("\n".join(buf).strip())
            continue

        if cur_len + len(p_block) + 2 <= target_chars:
            cur.append(p_block)
            cur_len += len(p_block) + 2
        else:
            if cur:
                chunks.append("\n\n".join(cur).strip())
                # add overlap: take the last 'overlap_chars' of the chunk
                last = chunks[-1]
                overlap = last[-overlap_chars:] if len(last) > overlap_chars else last
                cur, cur_len = ([overlap], len(overlap))
            cur.append(p_block)
            cur_len += len(p_block) + 2
    if cur:
        chunks.append("\n\n".join(cur).strip())
    return [c for c in chunks if c.strip()]

class RAGIngestor:
    """
    Document ingestion: read S3 (us-west-2), chunk (markdown-aware),
    embed (OpenAI), upsert to Pinecone (us-east-1).
    """

    def __init__(
        self,
        index_name: str | None = None,
        chunk_size: int = 1000,
        overlap_chars: int = 250,
    ):
        self.regions = get_regions()
        self.models = get_models()
        self.pcfg = get_pinecone_config()

        self.index_name = index_name or self.pcfg["index_name"]
        self.chunk_size = chunk_size
        self.overlap_chars = overlap_chars

        # AWS clients in explicit regions
        self.s3 = boto3.client("s3", region_name=self.regions["s3"])

        # OpenAI client (key from Secrets Manager)
        self.openai_client = OpenAI(api_key=get_openai_api_key())

        # Pinecone client (key from Secrets Manager)
        self.pc = Pinecone(api_key=get_pinecone_api_key())
        self.index = None

    def create_index(self) -> bool:
        # Check if index exists
        existing = self.pc.list_indexes()
        names = [idx.get("name") for idx in existing]
        if self.index_name in names:
            print(f"[Pinecone] Index '{self.index_name}' already exists")
            self.index = self.pc.Index(self.index_name)
            return False

        print(
            f"[Pinecone] Creating serverless index '{self.index_name}' "
            f"in {self.regions['pinecone']} (dim {self.pcfg['dimension']})"
        )
        self.pc.create_index(
            name=self.index_name,
            dimension=self.pcfg["dimension"],
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=self.regions["pinecone"]),
        )
        self.index = self.pc.Index(self.index_name)
        return True

    def chunk_text(self, text: str) -> List[str]:
        """Markdown-aware paragraph/list chunking with overlap."""
        return split_markdown_into_chunks(
            text,
            target_chars=self.chunk_size,
            overlap_chars=self.overlap_chars,
        )

    def embed_text(self, text: str) -> List[float]:
        # Approximate tokens := len(text) / 4 chars per token
        approx_tokens = max(1, len(text) // 4)

        # Hard safety: keep well under 8,192 token limit
        MAX_TOKENS = 5000       # a bit of margin below 8192
        if approx_tokens > MAX_TOKENS:
            max_chars = MAX_TOKENS * 4
            # Trim the text to stay under limit
            text = text[:max_chars]

        resp = self.openai_client.embeddings.create(
            model=self.models["embed_model"],
            input=text,
        )
        return resp.data[0].embedding

    def upsert_point(self, id: str, vector: List[float], metadata: Dict[str, Any]):
        if self.index is None:
            self.index = self.pc.Index(self.index_name)
        self.index.upsert(vectors=[(id, vector, metadata)])

    def _ingest_docs_jsonl(self, key: str, body: str, stats: Dict[str, Any]):
        """Ingest a .docs.jsonl file produced by scrape_allbenefits.py."""
        total_chunks = 0
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                print(f"[INGEST] Skipping malformed line in {key}")
                continue

            doc_id = doc.get("doc_id")
            source_url = doc.get("source_url", "")
            captured_at = doc.get("captured_at", "")
            sections = doc.get("sections") or []

            for sec in sections:
                md = (sec.get("markdown") or "").strip()
                section_id = sec.get("section_id", "")
                heading = sec.get("heading", "")

                # Remove heading line from chunk body (keep heading in metadata)
                body_md = re.sub(r"^##[^\n]+\n*", "", md).strip()
                if not body_md:
                    body_md = md

                pieces = self.chunk_text(body_md)
                for idx, piece in enumerate(pieces, start=1):
                    if not piece.strip():
                        continue
                    chunk_id = f"{doc_id}:{section_id}:{idx:03d}"
                    vec = self.embed_text(piece)
                    metadata = {
                        "text": piece,
                        "s3_key": key,
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "section_id": section_id,
                        "heading": heading,
                        "source_url": source_url,
                        "captured_at": captured_at,
                        "char_count": len(piece),
                        "approx_tokens": estimate_tokens(piece),
                    }
                    self.upsert_point(chunk_id, vec, metadata)
                    total_chunks += 1

        stats["files_processed"] += 1
        stats["total_chunks"] += total_chunks
        print(f"[INGEST] {key} -> {total_chunks} chunks from .docs.jsonl")

    def ingest_from_s3(self, bucket: str, prefix: str = "") -> Dict[str, Any]:
        """Scan S3, chunk, embed, upsert."""
        stats: Dict[str, Any] = {"files_processed": 0, "total_chunks": 0, "errors": []}
        paginator = self.s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue

                try:
                    body_obj = self.s3.get_object(Bucket=bucket, Key=key)
                    body = body_obj["Body"].read().decode("utf-8", errors="ignore")

                    if key.endswith(".docs.jsonl"):
                        self._ingest_docs_jsonl(key, body, stats)
                        continue

                    if key.endswith(".chunks.jsonl"):
                        # Old pre-chunked files are ignored now
                        print(f"[INGEST] Skipping legacy chunks file {key}")
                        continue

                    # Fallback: treat whole object as one markdown blob
                    chunks = self.chunk_text(body)
                    for i, chunk in enumerate(chunks):
                        vec = self.embed_text(chunk)
                        self.upsert_point(str(uuid.uuid4()), vec, {
                            "text": chunk,
                            "s3_key": key,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                        })
                    stats["files_processed"] += 1
                    stats["total_chunks"] += len(chunks)
                    print(f"[INGEST] {key} -> {len(chunks)} chunks")

                except Exception as e:
                    msg = f"Failed {key}: {e}"
                    print(msg)
                    stats["errors"].append(msg)

        return stats

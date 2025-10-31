import os
import uuid
from typing import List, Dict, Any
import boto3
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from app.config import get_openai_api_key, get_regions, get_pinecone_api_key, get_pinecone_config, get_models

class RAGIngestor:
    """
    Document ingestion: read S3 (us-west-2), chunk, embed (OpenAI), upsert to Pinecone (us-east-1).
    """

    def __init__(self, index_name: str | None = None, chunk_size: int = 1000):
        self.regions = get_regions()
        self.models = get_models()
        self.pcfg = get_pinecone_config()

        self.index_name = index_name or self.pcfg["index_name"]
        self.chunk_size = chunk_size

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

        print(f"[Pinecone] Creating serverless index '{self.index_name}' in {self.regions['pinecone']} (dim {self.pcfg['dimension']})")
        self.pc.create_index(
            name=self.index_name,
            dimension=self.pcfg["dimension"],
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=self.regions["pinecone"]),
        )
        self.index = self.pc.Index(self.index_name)
        return True

    def chunk_text(self, text: str) -> List[str]:
        return [text[i:i+self.chunk_size] for i in range(0, len(text), self.chunk_size)]

    def embed_text(self, text: str) -> List[float]:
        resp = self.openai_client.embeddings.create(
            model=self.models["embed_model"],
            input=text
        )
        return resp.data[0].embedding

    def upsert_point(self, id: str, vector: List[float], metadata: Dict[str, Any]):
        if self.index is None:
            self.index = self.pc.Index(self.index_name)
        self.index.upsert(vectors=[(id, vector, metadata)])

    def ingest_from_s3(self, bucket: str, prefix: str = "") -> Dict[str, Any]:
        stats = {"files_processed": 0, "total_chunks": 0, "errors": []}
        paginator = self.s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                try:
                    body = self.s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8", errors="ignore")
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

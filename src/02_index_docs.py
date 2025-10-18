# !pip install boto3 faiss-cpu sentence-transformers pypdf python-docx chardet --quiet
import os
import io
import json
import tempfile
import unicodedata
import chardet
import boto3
from pathlib import Path
from pypdf import PdfReader
from docx import Document as DocxDocument
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

s3 = boto3.client("s3")

BUCKET = "mids-capstone-benefitsflow"
PREFIX = "rag/raw"          # where the raw docs live
INDEX_PREFIX = "rag/index"  # where to write the FAISS index + metadata
EMBED_MODEL_NAME = ""  # swap if you prefer

def s3_list_objects(bucket, prefix):
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"]

def s3_read_text(bucket, key):
    # best-effort decode for arbitrary text files
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    det = chardet.detect(body)
    return body.decode(det["encoding"] or "utf-8", errors="ignore")

def extract_text(bucket, key):
    ext = key.lower().split(".")[-1]
    obj = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if ext in ("txt", "md", "csv", "log"):
        det = chardet.detect(obj)
        return obj.decode(det["encoding"] or "utf-8", errors="ignore")
    if ext in ("pdf",):
        with io.BytesIO(obj) as f:
            reader = PdfReader(f)
            return "\n".join([page.extract_text() or "" for page in reader.pages])
    if ext in ("docx",):
        with io.BytesIO(obj) as f:
            doc = DocxDocument(f)
            return "\n".join([p.text for p in doc.paragraphs])
    # fallback: try text
    det = chardet.detect(obj)
    return obj.decode(det["encoding"] or "utf-8", errors="ignore")

def normalize_ws(s):
    s = unicodedata.normalize("NFKC", s)
    return " ".join(s.split())

def chunk_text(text, chunk_chars=800, overlap=150):
    text = normalize_ws(text)
    chunks = []
    i = 0
    while i < len(text):
        j = min(len(text), i + chunk_chars)
        chunks.append(text[i:j])
        i = j - overlap
        if i < 0: i = 0
    return [c for c in chunks if c.strip()]

# 1) Gather docs
docs = []
for key in s3_list_objects(BUCKET, PREFIX):
    if key.endswith("/"): 
        continue
    try:
        txt = extract_text(BUCKET, key)
        for c in chunk_text(txt):
            docs.append({"s3_key": key, "text": c})
    except Exception as e:
        print(f"Skip {key}: {e}")

print(f"Collected {len(docs)} chunks")

# 2) Embed
model = SentenceTransformer(EMBED_MODEL_NAME)
embs = model.encode([d["text"] for d in docs], batch_size=64, show_progress_bar=True, normalize_embeddings=True)
embs = np.array(embs, dtype="float32")

# 3) FAISS index
d = embs.shape[1]
index = faiss.IndexFlatIP(d)     # cosine if normalized
index.add(embs)
print("Index size:", index.ntotal)

# 4) Save index + metadata locally
with tempfile.TemporaryDirectory() as td:
    idx_path = Path(td) / "faiss.index"
    faiss.write_index(index, str(idx_path))
    meta = {
        "embedding_model": EMBED_MODEL_NAME,
        "dimension": d,
        "count": len(docs),
        "docs": [{"s3_key": d["s3_key"], "text": d["text"][:500]} for d in docs]  # truncate texts in metadata
    }
    meta_path = Path(td) / "meta.json"
    meta_path.write_text(json.dumps(meta))

    # 5) Upload to S3
    s3.upload_file(str(idx_path), BUCKET, f"{INDEX_PREFIX}/faiss.index")
    s3.upload_file(str(meta_path), BUCKET, f"{INDEX_PREFIX}/meta.json")

print("Index and metadata uploaded to s3://{}/{}".format(BUCKET, INDEX_PREFIX))

# Initialize
# !pip install faiss-cpu sentence-transformers --quiet
import json
import io
import tempfile
import boto3
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from pathlib import Path

s3 = boto3.client("s3")
rt = boto3.client("sagemaker-runtime")

BUCKET = "YOUR_BUCKET"
INDEX_PREFIX = "rag/index"
TOP_K = 5
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
JUMPSTART_ENDPOINT = "YOUR_JUMPSTART_ENDPOINT"


def load_index_from_s3(bucket, index_prefix):
    with tempfile.TemporaryDirectory() as td:
        idx_key = f"{index_prefix}/faiss.index"
        meta_key = f"{index_prefix}/meta.json"
        idx_path = f"{td}/faiss.index"
        meta_path = f"{td}/meta.json"
        s3.download_file(bucket, idx_key, idx_path)
        s3.download_file(bucket, meta_key, meta_path)
        index = faiss.read_index(idx_path)
        meta = json.loads(Path(meta_path).read_text())
    return index, meta


def embed_query(q, model_name=EMBED_MODEL_NAME):
    m = SentenceTransformer(model_name)
    v = m.encode([q], normalize_embeddings=True)
    return np.array(v, dtype="float32")


def retrieve(qvec, index, meta, top_k=TOP_K):
    D, I = index.search(qvec, top_k)  # inner product
    hits = []
    for rank, i in enumerate(I[0]):
        if i < 0: 
            continue
        doc = meta["docs"][int(i)]
        hits.append({"rank": rank+1, "score": float(D[0][rank]), "s3_key": doc["s3_key"], "text": doc["text"]})
    return hits


def build_prompt(user_query, contexts):
    context_block = "\n\n".join(
        [f"[Source {i['rank']}] (s3://{BUCKET}/{i['s3_key']})\n{i['text']}" for i in contexts]
    )
    prompt = f"""You are a helpful assistant. Use the CONTEXT to answer the QUESTION.
            If the answer isn't in the context, say you don't know.

            CONTEXT:
            {context_block}

            QUESTION: {user_query}

            Answer concisely, citing Source numbers when relevant."""
    return prompt


def call_jumpstart(endpoint_name, prompt, max_new_tokens=400, temperature=0.2, top_p=0.9):
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p
        }
    }
    resp = rt.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=json.dumps(payload)
    )
    body = resp["Body"].read().decode("utf-8")
    try:
        data = json.loads(body)
    except Exception:
        return body
    # JumpStart responses vary by model; handle common shapes:
    if isinstance(data, list) and data and "generated_text" in data[0]:
        return data[0]["generated_text"]
    if "generated_text" in data:
        return data["generated_text"]
    if "outputs" in data and isinstance(data["outputs"], list):
        return data["outputs"][0]
    return body  # raw

# === Run a query ===
index, meta = load_index_from_s3(BUCKET, INDEX_PREFIX)
q = "Your user question goes here"
qvec = embed_query(q)
ctx = retrieve(qvec, index, meta, top_k=TOP_K)
prompt = build_prompt(q, ctx)
answer = call_jumpstart(JUMPSTART_ENDPOINT, prompt)
print(answer)

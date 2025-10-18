# !pip install boto3 faiss-cpu sentence-transformers --quiet
import json
import tempfile
import numpy as np
import faiss
import boto3
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sagemaker.jumpstart.model import JumpStartModel
import sagemaker

BUCKET = ""
INDEX_PREFIX = "rag/index"
EMBED_MODEL_NAME = ""
MODEL_ID = "meta-textgeneration-llama-3-1-70b-instruct"
INSTANCE_TYPE = "ml.c5.large"
ENDPOINT_NAME = ""

# --- utility: load index and metadata ---
def load_index(bucket, prefix):
    s3 = boto3.client("s3")
    with tempfile.TemporaryDirectory() as td:
        s3.download_file(bucket, f"{prefix}/faiss.index", f"{td}/faiss.index")
        s3.download_file(bucket, f"{prefix}/meta.json", f"{td}/meta.json")
        index = faiss.read_index(f"{td}/faiss.index")
        meta = json.loads(Path(f"{td}/meta.json").read_text())
    return index, meta

def embed_query(q):
    m = SentenceTransformer(EMBED_MODEL_NAME)
    v = m.encode([q], normalize_embeddings=True)
    return np.array(v, dtype="float32")

def retrieve(qvec, index, meta, k=5):
    D, I = index.search(qvec, k)
    return [meta["docs"][int(i)] for i in I[0] if i >= 0]

def build_prompt(query, contexts):
    context_block = "\n\n".join([f"[Source {i+1}] {c['text']}" for i, c in enumerate(contexts)])
    return f"""You are a helpful assistant. Use the CONTEXT below to answer the QUESTION.
            If the answer is not found in the context, say "I don't know."

            CONTEXT:
            {context_block}

            QUESTION: {query}
            """

# --- run query with auto-cleanup ---
session = sagemaker.Session()
role = sagemaker.get_execution_role()
sm_client = boto3.client("sagemaker")
rt_client = boto3.client("sagemaker-runtime")

index, meta = load_index(BUCKET, INDEX_PREFIX)
query = "Summarize the main topics discussed in the uploaded documents."

predictor = None
try:
    print("🚀 Deploying JumpStart model...")
    js_model = JumpStartModel(model_id=MODEL_ID, role=role)
    predictor = js_model.deploy(
        initial_instance_count=1,
        instance_type=INSTANCE_TYPE,
        endpoint_name=ENDPOINT_NAME
    )

    print("🔍 Retrieving context...")
    qvec = embed_query(query)
    ctx = retrieve(qvec, index, meta, k=5)
    prompt = build_prompt(query, ctx)

    print("💬 Sending prompt to endpoint...")
    response = predictor.predict(prompt)
    print("\n--- MODEL RESPONSE ---\n")
    print(response)

finally:
    # cleanup: delete endpoint, config, and model
    print("\n🧹 Cleaning up resources...")
    if predictor:
        try:
            predictor.delete_endpoint(delete_endpoint_config=True)
        except Exception as e:
            print("Warning deleting endpoint via predictor:", e)
    for name in [ENDPOINT_NAME]:
        try: sm_client.delete_model(ModelName=name)
        except Exception: pass
        try: sm_client.delete_endpoint_config(EndpointConfigName=name)
        except Exception: pass
        try: sm_client.delete_endpoint(EndpointName=name)
        except Exception: pass
    print("✅ Cleanup complete.")

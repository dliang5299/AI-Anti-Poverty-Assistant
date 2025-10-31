# RAG AI (Cloud-Only) — Secrets Manager + Cross-Region Pinecone

This repository is a production-ready starting point for a **cloud-only** RAG stack that:
- Pulls **secrets from AWS Secrets Manager** at runtime
- Uses **S3 and Bedrock in `us-west-2`**
- Uses **Pinecone serverless in `us-east-1`** (free tier compatible)
- Keeps **OpenAI embeddings** (text-embedding-3-small, 1536 dims)
- Provides **FastAPI** backend and optional **Streamlit** UI
- Packaged with **Dockerfiles** and a sample **docker-compose** for local simulation or EC2 (for ECS/Fargate, translate envs to Task Definition)

> Architecture (cloud): S3 (us-west-2) → Embeddings (OpenAI) → Pinecone (us-east-1) → FastAPI (Bedrock Claude in us-west-2) → Streamlit UI

---

## What’s included

- `app/config.py`  
  Centralized configuration + Secrets Manager fetcher. You pass **Secret ARNs or names** via env vars; the app fetches values at runtime using its **Task Role**.

- `app/RAGIngest.py`  
  Ingestion service: reads from **S3 (us-west-2)**, chunks docs, embeds with **OpenAI**, writes vectors to **Pinecone (us-east-1)**.

- `app/RAGSearch.py`  
  Query embedding + Pinecone top-k search with metadata.

- `app/RAGService.py`  
  **FastAPI** app exposing:
  - `POST /ingest` — trigger ingestion from S3 bucket/prefix
  - `POST /chat` — RAG chat pipeline using **Bedrock Claude 3.5 Haiku** by default

- `ui/StreamlitUI.py`  
  Optional chat UI that calls the FastAPI service, controlled via `RAG_SERVICE_URL`.

- Dockerfiles & `docker-compose.yml`  
  For local simulation. In ECS/Fargate, set the same env vars in Task Definition (no local `.env` needed).

- `requirements.txt`

---

## Environment Variables (no secrets in plaintext)

At **runtime**, the app reads these env vars (set in ECS Task Definition or your shell for local testing):

```bash
# Regions
S3_REGION=us-west-2
BEDROCK_REGION=us-west-2
PINECONE_REGION=us-east-1

# Pinecone indexing
PINECONE_ENV=aws-us-east-1        # Pinecone serverless project environment label (common pattern)
PINECONE_INDEX_NAME=knowledge     # or your custom index name
PINECONE_DIM=1536                 # OpenAI embeddings dim

# Model config
EMBED_MODEL=text-embedding-3-small
LLM_MODEL=anthropic.claude-3-5-haiku-20241022-v1:0

# Secrets — pass ARNs or Names (the app resolves both via Secrets Manager)
OPENAI_API_KEY_SECRET_ARN=arn:aws:secretsmanager:...:secret:OPENAI_API_KEY-xxxxx
PINECONE_API_KEY_SECRET_ARN=arn:aws:secretsmanager:...:secret:PINECONE_API_KEY-xxxxx
AWS_BEARER_TOKEN_BEDROCK_SECRET_ARN=arn:aws:secretsmanager:...:secret:AWS_BEARER_TOKEN_BEDROCK-xxxxx   # optional
```

> In **ECS/Fargate**, set these as **Environment variables** (the *_SECRET_ARN values are **not** the secrets themselves).  
> The container retrieves the actual secret values via the Task Role.

---

## IAM Requirements (Task Role)

Attach permissions (principle of least privilege):

- **Bedrock**: `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` on your chosen model ARN(s) in `us-west-2`
- **S3 (read)**: `s3:GetObject` + optional `s3:ListBucket` on your bucket/prefix
- **Secrets Manager**: `secretsmanager:GetSecretValue` for the referenced secrets
- **CloudWatch Logs**: `logs:CreateLogStream`, `logs:PutLogEvents`

If using ECS, the **Task Execution Role** also needs `AmazonECSTaskExecutionRolePolicy`.

---

## Pinecone (serverless, us-east-1)

The code creates/uses a Pinecone **serverless** index in `us-east-1` to match free tier availability and the doc’s 1536-dim OpenAI embeddings. You can change the name/dimension using env vars.

---

## Local simulation (optional)

> For cloud-only ECS, skip this and use Task Definitions. For a quick local test:

```bash
# 1) Export non-secret envs and stub secrets (only for local test)
export S3_REGION=us-west-2
export BEDROCK_REGION=us-west-2
export PINECONE_REGION=us-east-1
export PINECONE_ENV=aws-us-east-1
export PINECONE_INDEX_NAME=knowledge
export PINECONE_DIM=1536
export EMBED_MODEL=text-embedding-3-small
export LLM_MODEL=anthropic.claude-3-5-haiku-20241022-v1:0

# Secrets: you can pass ARNs or names; for local test without AWS, you *could*
# instead set OPENAI_API_KEY / PINECONE_API_KEY directly to bypass Secrets Manager,
# but in cloud you should use the *_SECRET_ARN variables.
export OPENAI_API_KEY=sk-...            # local-only shortcut, not for prod
export PINECONE_API_KEY=pcsk-...        # local-only shortcut
# export OPENAI_API_KEY_SECRET_ARN=...
# export PINECONE_API_KEY_SECRET_ARN=...
# export AWS_BEARER_TOKEN_BEDROCK_SECRET_ARN=...

# 2) Build & run API
docker build -t rag-service:local -f Dockerfile.api .
docker run --rm -p 8000:8000 --name rag --env-file <(env) rag-service:local

# 3) (Optional) Build & run UI
docker build -t rag-ui:local -f Dockerfile.ui .
docker run --rm -p 8501:8501 -e RAG_SERVICE_URL=http://host.docker.internal:8000 rag-ui:local
```

---

## API Usage

**Ingest:**

```bash
curl -X POST "$BASE_URL/ingest" \
  -H "Content-Type: application/json" \
  -d '{"bucket":"your-bucket","prefix":"rag-knowledge/"}'
```

**Chat:**

```bash
curl -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is this document about?","top_k":5,"temperature":0.7}'
```

---

## Notes

- If you eventually upgrade Pinecone to run in `us-west-2`, simply change `PINECONE_REGION`/`PINECONE_ENV` and re-create the index.
- For production, deploy on **ECS/Fargate** behind **ALB** with TLS. Configure `RAG_SERVICE_URL` for the UI.
- The code follows the structure of the original guide but swaps local `.env` usage for **Secrets Manager** and enforces cross-region config.


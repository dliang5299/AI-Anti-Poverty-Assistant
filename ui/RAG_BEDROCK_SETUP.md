# RAG Endpoints & Bedrock Setup Guide

## Architecture Overview

```
Frontend (HTML) 
    ↓ HTTP POST /api/chat
UI Service (FastAPI, port 8501)
    ↓ HTTP POST /chat
RAG Service (FastAPI, port 8000)
    ↓ Uses:
    ├── OpenAI API (embeddings) → needs OPENAI_API_KEY
    ├── Pinecone (vector search) → needs PINECONE_API_KEY  
    └── Bedrock (LLM generation) → uses IAM role
```

## Current Status

### ✅ UI Service (Your Territory)
- **Location**: `UI/fastapi_backend.py`
- **Status**: ✅ Correctly configured
- **RAG Service URL**: `http://app:8000` (docker-compose) or from `RAG_API_URL` env var
- **Endpoints**:
  - `POST /api/chat` - Main chat endpoint (calls RAG service)
  - `GET /api/health` - Health check
  - `GET /api/health/rag` - RAG service health check
  - `POST /api/checklist/preview` - Checklist generation
  - `POST /api/calendar/preview` - Calendar generation

### ⚠️ RAG Service (Deric's Territory)
- **Location**: `app/RAG_service.py`
- **Status**: ⚠️ Needs secret configuration fix
- **Endpoints**:
  - `POST /chat` - Main RAG endpoint (uses Bedrock + Pinecone)
  - `POST /ingest` - Ingest documents to Pinecone
  - `POST /checklist` - Generate checklist
  - `POST /calendar` - Generate calendar
  - `GET /health` - Health check

### 🔧 Required Fixes

#### 1. Secret Configuration (Deric's app/config.py)
**Problem**: RAG service can't find OpenAI API key because:
- Deric's code looks for separate secrets: `benefitsflow/openai-api-key`, `benefitsflow/pinecone-api-key`
- Actual secret is combined: `benefitsflow-rag/secrets` with both keys in JSON

**Solution Needed** (for Deric):
Update `app/config.py` to try combined secret first:
```python
# In get_openai_api_key() and get_pinecone_api_key()
# Try combined secret first
combined_secret = "benefitsflow-rag/secrets"
try:
    secret_json = _fetch_secret(combined_secret, prefer_key="OPENAI_API_KEY")
    if secret_json:
        return secret_json
except:
    pass
# Then fall back to auto-discovery...
```

#### 2. Bedrock Configuration
**Status**: ✅ Already configured correctly
- **Region**: `us-west-2` (Oregon)
- **Model**: From `LLM_MODEL` env var (default: `openai.gpt-oss-120b-1:0`)
- **Access**: Uses IAM role (no API key needed)

#### 3. Docker Compose Configuration
**Status**: ✅ Correctly configured
- UI service connects to RAG via `RAG_API_URL=http://app:8000`
- Both services share `docker.env` for configuration
- Both services have AWS credentials mounted

## Testing the Connection

### 1. Check RAG Service Health
```bash
# From UI container or host
curl http://app:8000/health
# Should return: {"status": "healthy", ...}
```

### 2. Check UI → RAG Connection
```bash
# From UI container
curl http://app:8000/chat \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "conversation_history": []}'
```

### 3. Check Full Flow (Frontend → UI → RAG)
```bash
# From host machine
curl http://localhost:8501/api/chat \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"message": "I need help with healthcare", "conversation_history": []}'
```

## Troubleshooting

### Issue: RAG Service returns 500 errors
**Cause**: Can't find OpenAI/Pinecone secrets
**Fix**: Update `app/config.py` to use combined secret `benefitsflow-rag/secrets`

### Issue: UI can't connect to RAG service
**Check**:
1. Is `RAG_API_URL` set correctly? (should be `http://app:8000` in docker-compose)
2. Are both services on same Docker network? (`bfnet`)
3. Check logs: `docker-compose logs app` and `docker-compose logs ui`

### Issue: Bedrock errors
**Check**:
1. IAM role has `bedrock:InvokeModel` permission
2. Region is correct (`us-west-2`)
3. Model ID is correct (check `LLM_MODEL` env var)

## Environment Variables Summary

### RAG Service (app container)
```bash
OPENAI_API_KEY_SECRET_ARN=  # Optional if using auto-discovery
PINECONE_API_KEY_SECRET_ARN=  # Optional if using auto-discovery
BEDROCK_REGION=us-west-2
LLM_MODEL=openai.gpt-oss-120b-1:0
EMBED_MODEL=text-embedding-3-small
PINECONE_INDEX_NAME=benefitsflow
```

### UI Service (ui container)
```bash
RAG_API_URL=http://app:8000  # For docker-compose
BEDROCK_REGION=us-west-2  # For checklist/calendar generators
```

## Next Steps

1. **For Deric**: Update `app/config.py` to support combined secret `benefitsflow-rag/secrets`
2. **Test**: Verify RAG service can retrieve secrets
3. **Deploy**: Push changes and restart containers on EC2


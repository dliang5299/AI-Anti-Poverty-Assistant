# Using AWS-Native Services (No External APIs)

If you have AWS budget, you can use **100% AWS services** instead of external APIs like OpenAI and Pinecone.

## Current Setup (Mixed)

- ✅ **LLM**: AWS Bedrock (`openai.gpt-oss-120b-1:0`) - Uses AWS balance
- ❌ **Embeddings**: OpenAI (`text-embedding-3-small`) - External API, costs money
- ❌ **Vector DB**: Pinecone - External service, costs money

## AWS-Native Alternative

- ✅ **LLM**: AWS Bedrock (already using)
- ✅ **Embeddings**: AWS Bedrock embedding models
- ✅ **Vector DB**: Amazon OpenSearch Serverless or Bedrock Knowledge Bases

---

## Option 1: Bedrock Embeddings + OpenSearch Serverless

### Embeddings: Use Bedrock Titan Embeddings

**Available Models:**
- `amazon.titan-embed-text-v1` (1024 dimensions)
- `amazon.titan-embed-text-v2` (1024 dimensions)
- `cohere.embed-english-v3` (1024 dimensions)
- `cohere.embed-multilingual-v3` (1024 dimensions)

**Cost:** ~$0.02 per 1K tokens (cheaper than OpenAI for most use cases)

### Vector DB: Amazon OpenSearch Serverless

**Benefits:**
- Fully managed by AWS
- Serverless (pay per use)
- Integrated with Bedrock
- No external API keys needed

**Cost:** ~$0.10 per OCU-hour (On-Demand Compute Unit)

---

## Option 2: Bedrock Knowledge Bases (Easiest)

**Amazon Bedrock Knowledge Bases** is a fully managed RAG solution that:
- Handles document ingestion from S3
- Generates embeddings using Bedrock
- Stores vectors in OpenSearch (managed)
- Provides retrieval API

**Benefits:**
- No code changes needed for vector storage
- Fully managed by AWS
- Integrated with Bedrock
- Automatic scaling

**Cost:** 
- Embeddings: ~$0.02 per 1K tokens
- OpenSearch: ~$0.10 per OCU-hour
- S3 storage: ~$0.023 per GB/month

---

## Migration Path

### Step 1: Replace OpenAI Embeddings with Bedrock

**Current code** (`app/03_RAG_search.py`):
```python
from openai import OpenAI
self.openai_client = OpenAI(api_key=get_openai_api_key())
resp = self.openai_client.embeddings.create(
    model=self.models["embed_model"],
    input=query
)
```

**Replace with Bedrock**:
```python
import boto3
bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-west-2")

response = bedrock_runtime.invoke_model(
    modelId="amazon.titan-embed-text-v1",
    body=json.dumps({"inputText": query})
)
embedding = json.loads(response["body"].read())["embedding"]
```

### Step 2: Replace Pinecone with OpenSearch Serverless

**Current code** uses Pinecone:
```python
from pinecone import Pinecone
self.pc = Pinecone(api_key=get_pinecone_api_key())
self.index = self.pc.Index(self.index_name)
```

**Replace with OpenSearch**:
```python
from opensearchpy import OpenSearch, RequestsHttpConnection
from aws_requests_auth.aws_auth import AWSRequestsAuth

auth = AWSRequestsAuth(
    aws_access_key=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_host="your-opensearch-endpoint.us-west-2.es.amazonaws.com",
    aws_region="us-west-2",
    aws_service="es"
)

client = OpenSearch(
    hosts=[{"host": "your-opensearch-endpoint.us-west-2.es.amazonaws.com", "port": 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)
```

---

## Quick Comparison

| Service | Current | AWS Native | Cost (AWS) |
|---------|---------|------------|------------|
| **LLM** | Bedrock ✅ | Bedrock ✅ | ~$0.0008/1K tokens |
| **Embeddings** | OpenAI ❌ | Bedrock Titan ✅ | ~$0.02/1K tokens |
| **Vector DB** | Pinecone ❌ | OpenSearch Serverless ✅ | ~$0.10/OCU-hour |

**Total AWS Cost:** ~$20-50/month for moderate usage (vs $50-100+ with external APIs)

---

## Benefits of AWS-Native

✅ **Single billing** - Everything on AWS  
✅ **No external API keys** - Use IAM roles  
✅ **Better integration** - All services work together  
✅ **Lower latency** - Same region, same network  
✅ **Better security** - No external API calls  
✅ **Simpler deployment** - All in AWS Secrets Manager  

---

## Implementation Notes

1. **Bedrock Embeddings** require different model IDs:
   - `amazon.titan-embed-text-v1` (1024 dims)
   - `cohere.embed-english-v3` (1024 dims)

2. **OpenSearch Serverless** requires:
   - Creating a collection in OpenSearch
   - Setting up IAM policies
   - Different query syntax than Pinecone

3. **Code changes needed:**
   - `app/03_RAG_search.py` - Replace OpenAI with Bedrock
   - `app/02_RAG_ingest.py` - Replace Pinecone with OpenSearch
   - `app/00_config.py` - Remove OpenAI/Pinecone key functions

---

## Recommendation

**For your capstone with AWS budget:**

1. **Use Bedrock for embeddings** - Easy switch, lower cost
2. **Use OpenSearch Serverless** - Fully managed, AWS-native
3. **Remove OpenAI and Pinecone dependencies** - Cleaner, simpler

This gives you:
- 100% AWS-native stack
- Single billing
- Better security
- Easier deployment

Would you like me to help migrate the code to use Bedrock embeddings and OpenSearch?


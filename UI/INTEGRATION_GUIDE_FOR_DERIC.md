# Integration Guide for Deric's RAG System

## Maya's Role: Frontend Integration
- **FastAPI + HTML frontend** is working
- **API endpoints** are ready
- **Waiting for Deric's RAG system** to connect

## How to Connect Deric's RAG System

### Option 1: Direct Function Import (Easiest)
When Deric has his RAG system ready, he can provide a function like this:

```python
def get_rag_response(query: str, conversation_history: List[Dict], user_context: Dict) -> Tuple[str, List[Dict], List[str]]:
    """
    Deric's RAG system function
    
    Args:
        query: User's question
        conversation_history: Previous conversation
        user_context: User context information
    
    Returns:
        Tuple of (response_text, sources, programs)
    """
    # Deric's RAG logic here
    pass
```

Then Maya just needs to:
1. Replace the import in `fastapi_backend.py`:
   ```python
   from deric_rag_system import get_rag_response  # Replace this line
   ```
2. The rest of the FastAPI backend will work automatically!

### Option 2: SageMaker Endpoint (Production)
If Deric deploys to SageMaker, Maya can use the existing SageMaker integration:

```python
# In fastapi_backend.py, replace the chat endpoint with:
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Call Deric's SageMaker endpoint
        response = sagemaker_client.invoke_endpoint(
            EndpointName="deric-rag-endpoint",
            ContentType='application/json',
            Body=json.dumps({
                "query": request.message,
                "conversation_history": request.conversation_history,
                "user_context": {"situation": request.situation}
            })
        )
        
        result = json.loads(response['Body'].read().decode())
        return ChatResponse(
            response=result['response'],
            sources=result.get('sources', []),
            programs=result.get('programs', [])
        )
    except Exception as e:
        # Fallback to demo
        response_text, sources, programs = get_rag_response(...)
        return ChatResponse(response=response_text, sources=sources, programs=programs)
```

### Option 3: HTTP API (If Deric creates a separate service)
```python
# Call Deric's RAG API
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://deric-rag-service:8001/query",
        json={
            "query": request.message,
            "conversation_history": request.conversation_history,
            "user_context": {"situation": request.situation}
        }
    )
    result = response.json()
```

## What Deric Needs to Provide

### Function Signature:
```python
def get_rag_response(query: str, conversation_history: List[Dict], user_context: Dict) -> Tuple[str, List[Dict], List[str]]:
```

### Return Format:
- **response_text**: String with the AI response
- **sources**: List of dicts with `{'name': str, 'url': str, 'date': str}`
- **programs**: List of strings with program names

### Example:
```python
response_text = "Based on your situation, you may be eligible for CalFresh..."
sources = [
    {'name': 'CalFresh Official Site', 'url': 'https://calfresh.ca.gov', 'date': 'Oct 2025'}
]
programs = ['CalFresh', 'Medi-Cal']
```

## Current Status

### What's Working:
- Beautiful HTML frontend
- FastAPI backend with proper endpoints
- Demo responses (so you can test the UI)
- SageMaker integration ready
- All API endpoints working

### What's Waiting:
- Deric's RAG system to replace demo responses
- Real document retrieval and LLM responses
- Production deployment

## Testing the Integration

### Current Test (Demo Mode):
```bash
cd UI
python serve_frontend.py
# Go to http://localhost:8000
# Try asking: "I lost my job, what benefits can I get?"
```

### When Deric's RAG is Ready:
1. Deric provides the RAG function
2. Maya updates the import in `fastapi_backend.py`
3. Test with real queries
4. Deploy to production

## Communication with Deric

### Questions for Deric:
1. **What's the function signature** for your RAG system?
2. **How do you want to deploy** (direct import, SageMaker, HTTP API)?
3. **What's the expected response format**?
4. **When will it be ready** for integration testing?

### What Maya Can Provide:
1. **Working frontend** for testing
2. **API documentation** at http://localhost:8000/api/docs
3. **Test queries** to validate responses
4. **Integration support** when ready

## Project Status

While other teams are still figuring out Streamlit, you have:
- **Professional FastAPI backend**
- **Beautiful HTML frontend** 
- **Ready for RAG integration**
- **Production-ready architecture**

This gives you a significant advantage for deployment and scaling.

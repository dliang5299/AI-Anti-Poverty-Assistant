"""
Checklist Generator for BenefitsFlow UI
Generates personalized checklists based on conversation using Deric's RAG service for retrieval
and Bedrock for generation. All logic stays in UI folder.
"""

from typing import List, Dict, Any, Optional
import httpx
import boto3
import json
from datetime import datetime
from functools import lru_cache
import os

# Deric's RAG Service URL
# Check both RAG_SERVICE_URL and RAG_API_URL for compatibility
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL") or os.getenv("RAG_API_URL") or "http://localhost:8000"

# AWS Configuration
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-west-2")
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0")

@lru_cache(maxsize=None)
def get_bedrock():
    """Get Bedrock client"""
    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

def _extract_text_from_bedrock(resp: dict) -> str:
    """Extract text from Bedrock response"""
    try:
        parts = resp.get("output", {}).get("message", {}).get("content", [])
        if isinstance(parts, list):
            texts = []
            for p in parts:
                if isinstance(p, dict) and "text" in p:
                    texts.append(p["text"])
            if texts:
                return "\n".join(texts).strip()
    except Exception:
        pass
    return ""

def _has_sufficient_context(conversation_history: List[Dict[str, Any]]) -> bool:
    """
    Check if conversation has enough context to generate a meaningful checklist.
    Returns True if conversation has at least 1-2 meaningful exchanges.
    """
    if not conversation_history or len(conversation_history) < 2:
        return False
    
    # Count meaningful messages (user questions + assistant responses)
    meaningful_count = 0
    total_length = 0
    for msg in conversation_history:
        content = msg.get('content', '')
        if isinstance(content, str) and len(content.strip()) > 10:
            meaningful_count += 1
            total_length += len(content.strip())
    
    # Need at least 2 messages OR substantial content (more than 200 chars total)
    return meaningful_count >= 2 or total_length > 200

async def _get_rag_context_from_deric(query: str) -> tuple[str, List[Dict]]:
    """
    Call Deric's RAG service to get context and sources.
    Returns (context_text, sources_list)
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Call Deric's chat endpoint to get RAG context
            response = await client.post(
                f"{RAG_SERVICE_URL}/chat",
                json={
                    "message": query,
                    "situation": "",
                    "conversation_history": []
                }
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract sources for context
            sources = result.get("sources", [])
            context_parts = []
            for src in sources:
                if src.get("name"):
                    context_parts.append(f"Source: {src['name']}")
            
            # The response text contains the RAG-augmented answer, which includes context
            context_text = result.get("response", "")
            
            return context_text, sources
            
    except Exception as e:
        print(f"Error getting RAG context from Deric's service: {e}")
        return "", []

def generate_checklist(
    conversation_history: List[Dict[str, Any]], 
    user_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate personalized checklist based on conversation using Deric's RAG service.
    This function is synchronous but uses async internally via httpx.
    
    Args:
        conversation_history: List of conversation messages
        user_context: Dict with situation, programs, etc.
    
    Returns:
        List of checklist items, or empty list if insufficient context
    """
    import asyncio
    
    # Check if conversation has enough context
    if not _has_sufficient_context(conversation_history):
        print(f"DEBUG: Insufficient context - history length: {len(conversation_history)}")
        return []
    
    try:
        # Extract key information from conversation
        conversation_text = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in conversation_history[-10:]  # Last 10 messages
        ])
        
        # Extract key phrases from conversation for better RAG search
        query_parts = []
        
        # Extract user messages (they contain the actual questions/needs)
        user_messages = [
            msg.get('content', '') 
            for msg in conversation_history 
            if msg.get('role') == 'user' and len(msg.get('content', '')) > 10
        ]
        if user_messages:
            # Use the most recent user message as primary query
            query_parts.append(user_messages[-1])
        
        # Add program names if mentioned
        if user_context.get('programs'):
            query_parts.extend(user_context['programs'])
        
        # Add situation if provided
        if user_context.get('situation') and user_context['situation'] != 'General':
            query_parts.append(user_context['situation'])
        
        # Combine into query
        query = ' '.join(query_parts) if query_parts else conversation_text[:200]
        
        # Get RAG context from Deric's service
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        context_text, sources = loop.run_until_complete(_get_rag_context_from_deric(query))
        
        print(f"DEBUG: RAG context retrieved - context length: {len(context_text)}, sources: {len(sources)}")
        
        if not context_text or len(sources) < 2:
            # Not enough relevant context found
            print(f"DEBUG: Not enough RAG context - context_text: {bool(context_text)}, sources: {len(sources)}")
            return []
        
        # Build prompt for Bedrock
        today = datetime.now().strftime("%Y-%m-%d")
        system_prompt = f"""You are a helpful assistant that creates personalized action checklists for California public benefits programs. 
Generate a structured checklist based on the conversation and relevant program information. 
Today's date is {today}.
Each checklist item should have:
- title: Clear action item title
- description: Brief description
- deadline: Specific deadline if mentioned, or "As soon as possible" if urgent
- details: List of specific action steps
- link: Relevant website URL if available

Focus on actionable steps, required documents, deadlines, and application processes mentioned in the conversation."""
        
        user_prompt = f"""Based on this conversation and relevant program information, create a personalized checklist of action items.

Conversation:
{conversation_text}

Relevant Program Information (from RAG):
{context_text[:2000]}  # Limit context length

User Situation: {user_context.get('situation', 'General')}
Programs Mentioned: {', '.join(user_context.get('programs', []))}

Generate a JSON array of checklist items. Each item should be a JSON object with:
- "title": string
- "description": string  
- "deadline": string (specific date or "As soon as possible")
- "details": array of strings (action steps)
- "link": string (URL if available)

Return ONLY valid JSON array, no other text."""
        
        # Call Bedrock
        try:
            bedrock = get_bedrock()
            print(f"DEBUG: Calling Bedrock with model: {LLM_MODEL}")
            response = bedrock.converse(
                modelId=LLM_MODEL,
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                system=[{"text": system_prompt}],
                inferenceConfig={"maxTokens": 2000, "temperature": 0.3}
            )
            
            text = _extract_text_from_bedrock(response)
            print(f"DEBUG: Bedrock response length: {len(text) if text else 0}")
            
            if not text:
                print("DEBUG: Bedrock returned empty text")
                return []
        except Exception as e:
            print(f"DEBUG: Bedrock error: {e}")
            return []
        
        # Parse JSON response
        try:
            # Extract JSON from response (might have markdown code blocks)
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            checklist_items = json.loads(text)
            
            if not isinstance(checklist_items, list):
                return []
            
            # Validate and format items
            formatted_items = []
            for item in checklist_items:
                if isinstance(item, dict) and item.get('title'):
                    formatted_items.append({
                        'title': item.get('title', ''),
                        'description': item.get('description', ''),
                        'deadline': item.get('deadline', 'As soon as possible'),
                        'details': item.get('details', []),
                        'link': item.get('link', '')
                    })
            
            return formatted_items if formatted_items else []
            
        except json.JSONDecodeError as e:
            print(f"Error parsing checklist JSON: {e}")
            return []
            
    except Exception as e:
        print(f"Error generating checklist: {e}")
        return []



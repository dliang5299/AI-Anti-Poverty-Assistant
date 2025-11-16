"""
Calendar Generator for BenefitsFlow UI
Generates personalized calendar events based on conversation using Deric's RAG service for retrieval
and Bedrock for generation. All logic stays in UI folder.
"""

from typing import List, Dict, Any, Optional
import httpx
import boto3
import json
from datetime import datetime, timedelta
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
    Check if conversation has enough context to generate meaningful calendar events.
    """
    if not conversation_history or len(conversation_history) < 2:
        return False
    
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

def generate_calendar_events(
    conversation_history: List[Dict[str, Any]], 
    user_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate personalized calendar events based on conversation using Deric's RAG service.
    This function is synchronous but uses async internally via httpx.
    
    Args:
        conversation_history: List of conversation messages
        user_context: Dict with situation, programs, etc.
    
    Returns:
        List of calendar events, or empty list if insufficient context
    """
    import asyncio
    
    # Check if conversation has enough context
    if not _has_sufficient_context(conversation_history):
        return []
    
    try:
        # Extract key information from conversation
        conversation_text = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in conversation_history[-10:]
        ])
        
        # Extract key phrases from conversation for better RAG search
        # Focus on dates, deadlines, and time-sensitive information
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
        
        # Add deadline-related keywords
        query_parts.extend(['deadlines', 'renewal dates', 'application dates', 'important dates'])
        
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
        
        if not context_text or len(sources) < 2:
            return []
        
        # Build prompt for Bedrock
        today = datetime.now().strftime("%Y-%m-%d")
        system_prompt = f"""You are a helpful assistant that creates personalized calendar events for California public benefits programs.
Generate calendar events based on deadlines, renewal dates, and important dates mentioned in the conversation.
Today's date is {today}.
Each event should have:
- summary: Event title
- description: What needs to be done
- start_date: Date in YYYY-MM-DD format (calculate from today if relative dates mentioned)
- url: Relevant website URL if available

Focus on application deadlines, renewal dates, SAR-7 deadlines, and other time-sensitive actions."""
        
        user_prompt = f"""Based on this conversation and relevant program information, create calendar events for important dates and deadlines.

Today's date: {today}

Conversation:
{conversation_text}

Relevant Program Information (from RAG):
{context_text[:2000]}  # Limit context length

User Situation: {user_context.get('situation', 'General')}
Programs Mentioned: {', '.join(user_context.get('programs', []))}

Generate a JSON array of calendar events. Each event should be a JSON object with:
- "summary": string (event title)
- "description": string (what to do)
- "start_date": string (YYYY-MM-DD format, calculate from today if relative dates mentioned)
- "url": string (website URL if available)

Return ONLY valid JSON array, no other text."""
        
        # Call Bedrock
        bedrock = get_bedrock()
        response = bedrock.converse(
            modelId=LLM_MODEL,
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            system=[{"text": system_prompt}],
            inferenceConfig={"maxTokens": 1500, "temperature": 0.3}
        )
        
        text = _extract_text_from_bedrock(response)
        
        if not text:
            return []
        
        # Parse JSON response
        try:
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            events = json.loads(text)
            
            if not isinstance(events, list):
                return []
            
            # Validate and format events
            formatted_events = []
            base_date = datetime.now()
            
            for i, event in enumerate(events):
                if isinstance(event, dict) and event.get('summary'):
                    # Parse start_date
                    start_date_str = event.get('start_date', '')
                    try:
                        if start_date_str:
                            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                        else:
                            # Default: space events 3 days apart
                            start_date = base_date + timedelta(days=(i + 1) * 3)
                    except:
                        start_date = base_date + timedelta(days=(i + 1) * 3)
                    
                    formatted_events.append({
                        'summary': event.get('summary', ''),
                        'description': event.get('description', ''),
                        'start_date': start_date.strftime("%Y-%m-%d"),
                        'url': event.get('url', '')
                    })
            
            return formatted_events if formatted_events else []
            
        except json.JSONDecodeError as e:
            print(f"Error parsing calendar JSON: {e}")
            return []
            
    except Exception as e:
        print(f"Error generating calendar: {e}")
        return []



"""
Calendar Generator using RAG
Generates personalized calendar events based on conversation history using RAG search
"""

from typing import List, Dict, Any, Optional
from app.RAG_search import RAGSearcher
from app.config import get_regions, get_models, get_bedrock_bearer_token
import boto3
import json
from datetime import datetime, timedelta
from functools import lru_cache

regions = get_regions()
models = get_models()

@lru_cache(maxsize=None)
def get_bedrock():
    """Get Bedrock client"""
    return boto3.client("bedrock-runtime", region_name=regions["bedrock"])

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
    if not conversation_history or len(conversation_history) < 4:
        return False
    
    meaningful_count = 0
    for msg in conversation_history:
        content = msg.get('content', '')
        if isinstance(content, str) and len(content.strip()) > 20:
            meaningful_count += 1
    
    return meaningful_count >= 4

def generate_calendar_events(
    conversation_history: List[Dict[str, Any]], 
    user_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate personalized calendar events based on conversation using RAG.
    
    Args:
        conversation_history: List of conversation messages
        user_context: Dict with situation, programs, etc.
    
    Returns:
        List of calendar events, or empty list if insufficient context
    """
    
    # Check if conversation has enough context
    if not _has_sufficient_context(conversation_history):
        return []
    
    try:
        # Extract key information from conversation
        conversation_text = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in conversation_history[-10:]
        ])
        
        # Search for relevant context using RAG
        searcher = RAGSearcher()
        
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
        
        # Combine into query (use conversation text as primary, add keywords)
        query = ' '.join(query_parts) if query_parts else conversation_text[:200]
        
        matches = searcher.search_vectors(query, limit=10)
        context = searcher.format_context(matches)
        
        if not matches or len(matches) < 3:
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

Relevant Program Information:
{context}

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
            modelId=models["llm_model"],
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


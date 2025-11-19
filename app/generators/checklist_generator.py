"""
Checklist Generator using RAG
Generates personalized checklists based on conversation history using RAG search and Bedrock
"""

from typing import List, Dict, Any, Optional
from app.RAG_search import RAGSearcher
from app.config import get_regions, get_models, get_bedrock_bearer_token
import boto3
import json
from datetime import datetime
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
    Check if conversation has enough context to generate a meaningful checklist.
    Returns True if conversation has at least 2-3 meaningful exchanges.
    """
    if not conversation_history or len(conversation_history) < 4:
        return False
    
    # Count meaningful messages (user questions + assistant responses)
    meaningful_count = 0
    for msg in conversation_history:
        content = msg.get('content', '')
        if isinstance(content, str) and len(content.strip()) > 20:
            meaningful_count += 1
    
    # Need at least 2-3 meaningful exchanges
    return meaningful_count >= 4

def generate_checklist(
    conversation_history: List[Dict[str, Any]], 
    user_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate personalized checklist based on conversation using RAG.
    
    Args:
        conversation_history: List of conversation messages
        user_context: Dict with situation, programs, etc.
    
    Returns:
        List of checklist items, or empty list if insufficient context
    """
    
    # Check if conversation has enough context
    if not _has_sufficient_context(conversation_history):
        return []
    
    try:
        # Extract key information from conversation
        conversation_text = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in conversation_history[-10:]  # Last 10 messages
        ])
        
        # Search for relevant context using RAG
        searcher = RAGSearcher()
        
        # Extract key phrases from conversation for better RAG search
        # Use the actual conversation text as the primary query
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
        
        # Combine into query (use conversation text as primary, add keywords)
        query = ' '.join(query_parts) if query_parts else conversation_text[:200]
        
        # Search for relevant documents
        matches = searcher.search_vectors(query, limit=10)
        context = searcher.format_context(matches)
        
        if not matches or len(matches) < 3:
            # Not enough relevant context found
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

Relevant Program Information:
{context}

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
        bedrock = get_bedrock()
        response = bedrock.converse(
            modelId=models["llm_model"],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            system=[{"text": system_prompt}],
            inferenceConfig={"maxTokens": 2000, "temperature": 0.3}
        )
        
        text = _extract_text_from_bedrock(response)
        
        if not text:
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


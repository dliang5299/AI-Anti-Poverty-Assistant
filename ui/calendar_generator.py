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
import asyncio
import concurrent.futures

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
        print(f"DEBUG: Insufficient context - conversation has {len(conversation_history)} messages")
        return []
    
    print(f"DEBUG: Generating calendar with {len(conversation_history)} messages")
    
    try:
        # Extract key information from conversation
        # Include more messages to capture date information that might be in earlier responses
        # Limit to last 20 messages to avoid token limits, but prioritize recent messages
        messages_to_include = conversation_history[-20:] if len(conversation_history) > 20 else conversation_history
        conversation_text = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in messages_to_include
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
            # Use thread pool to run async function (avoids "event loop already running" error)
            # FastAPI runs in an async context, so we need to run the async function in a separate thread
            def run_in_thread(coro):
                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_new_loop)
                    return future.result()
            
            context_text, sources = run_in_thread(_get_rag_context_from_deric(query))
        
            # Don't require RAG sources - we can extract dates directly from conversation
            # RAG context is helpful but not required if conversation has explicit dates
            if not context_text:
                context_text = ""  # Continue even without RAG context
        except Exception as e:
            print(f"DEBUG: Error getting RAG context for calendar (continuing anyway): {e}")
            import traceback
            traceback.print_exc()
            context_text = ""  # Continue even if RAG fails - we can extract from conversation
        
        # Build prompt for Bedrock
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        current_year = today.year
        next_year = current_year + 1
        
        system_prompt = f"""You are a helpful assistant that creates personalized calendar events for California public benefits programs.
Generate calendar events based on deadlines, renewal dates, and important dates mentioned in the USER'S CONVERSATION.
Today's date is {today_str} (year: {current_year}).
Each event should have:
- summary: Event title
- description: What needs to be done
- start_date: Date in YYYY-MM-DD format
- url: Relevant website URL if available

CRITICAL: 
- PRIORITIZE dates mentioned in the conversation text - these are the user's specific needs
- IGNORE generic holiday/closing dates unless the user specifically mentioned them
- Focus on application deadlines, enrollment periods, and deadlines mentioned by the user

IMPORTANT: Extract dates directly from the conversation text. Look for:
- Absolute dates: "Nov 1", "January 31", "Nov 1 – Jan 31" 
  * If date is in the past this year, use next year ({next_year})
  * If date is in the future this year, use this year ({current_year})
  * For date ranges like "Nov 1 – Jan 31", Nov 1 is likely {current_year}-11-01 and Jan 31 is likely {next_year}-01-31
- Relative dates: "60 days from job loss" → calculate from today or mentioned date
- Recurring dates: "Open Enrollment Nov 1 – Jan 31" → create events for both start and end dates
- Time periods: "30-45 days" → create reminder events

Focus on application deadlines, renewal dates, SAR-7 deadlines, open enrollment periods, and other time-sensitive actions."""
        
        rag_section = f"\nRelevant Program Information (from RAG):\n{context_text[:2000]}" if context_text else ""
        
        user_prompt = f"""Based on this conversation and relevant program information, create calendar events for important dates and deadlines.

Today's date: {today_str} (year: {current_year})

**PRIMARY SOURCE - CONVERSATION (READ THIS FIRST):**
{conversation_text}

**SECONDARY SOURCE - PROGRAM INFORMATION (for context only):**
{rag_section}

User Situation: {user_context.get('situation', 'General')}
Programs Mentioned: {', '.join(user_context.get('programs', []))}

**CRITICAL INSTRUCTIONS:**
1. PRIORITIZE dates mentioned in the CONVERSATION above - these are the user's specific needs
2. IGNORE generic holiday/closing dates unless specifically mentioned in the conversation
3. Focus on application deadlines, enrollment periods, and time-sensitive actions mentioned in the conversation
4. Extract ALL dates mentioned in the conversation. Examples:
- "Nov 1 – Jan 31" → Create events for November 1 ({current_year}-11-01) and January 31 ({next_year}-01-31)
- "60 days from job loss" → If job loss mentioned, calculate 60 days from today or mentioned date
- "Open enrollment Nov 1 – Jan 31" → Create events for both dates
- "30-45 days" → Create reminder events at 30 days and 45 days
- "File as soon as possible" → Create event for today or tomorrow

Generate a JSON array of calendar events. Each event should be a JSON object with:
- "summary": string (event title, e.g., "Covered California Open Enrollment Starts")
- "description": string (what to do, include the program name and action needed)
- "start_date": string (YYYY-MM-DD format, use {current_year} or {next_year} as appropriate)
- "url": string (website URL if available, e.g., "https://www.coveredca.com" for Covered California)

Return ONLY valid JSON array, no other text. Example format:
[
  {{"summary": "Covered California Open Enrollment Starts", "description": "Open enrollment period begins for health insurance coverage. Apply at coveredca.com", "start_date": "{current_year}-11-01", "url": "https://www.coveredca.com"}},
  {{"summary": "Covered California Open Enrollment Ends", "description": "Last day to enroll in health insurance for coverage starting February 1", "start_date": "{next_year}-01-31", "url": "https://www.coveredca.com"}},
  {{"summary": "File Unemployment Insurance Claim", "description": "File your unemployment insurance claim as soon as possible after job loss", "start_date": "{today_str}", "url": "https://www.edd.ca.gov"}}
]"""
        
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
            print(f"DEBUG: No text extracted from Bedrock response")
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
            
            if formatted_events:
                print(f"✅ Generated {len(formatted_events)} calendar events")
            return formatted_events if formatted_events else []
            
        except json.JSONDecodeError as e:
            print(f"ERROR: Error parsing calendar JSON: {e}")
            print(f"DEBUG: Raw text that failed to parse: {text[:1000]}")
            import traceback
            traceback.print_exc()
            return []
            
    except Exception as e:
        print(f"ERROR: Error generating calendar: {e}")
        import traceback
        traceback.print_exc()
        return []



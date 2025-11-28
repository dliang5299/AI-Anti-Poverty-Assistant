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
        
            # Filter out generic holiday/closing date information from RAG context
            # These are not user-specific and should not be in the calendar
            if context_text:
                # Check if RAG context contains generic holiday information
                holiday_keywords = [
                    "call center closed", "holiday", "new year's day", "martin luther king",
                    "presidents' day", "memorial day", "independence day", "labor day",
                    "veterans day", "thanksgiving", "christmas day", "cesar chavez day"
                ]
                context_lower = context_text.lower()
                if any(keyword in context_lower for keyword in holiday_keywords):
                    print(f"⚠️ RAG context contains generic holiday info - filtering it out")
                    context_text = ""  # Don't use RAG context if it's just generic holidays
        
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
Your goal is to help users stay organized and on track with their benefits applications and important deadlines.
Today's date is {today_str} (year: {current_year}).
Each event should have:
- summary: Event title (be specific and actionable)
- description: What needs to be done, why it's important, and any helpful tips
- start_date: Date in YYYY-MM-DD format
- url: Relevant website URL if available

CRITICAL INSTRUCTIONS:
1. CREATE HELPFUL REMINDERS: Even if no explicit deadline is mentioned, create actionable reminders based on the conversation:
   - "Apply for UI as soon as possible" → Create reminder for today or tomorrow
   - "Apply for CalFresh right away" → Create reminder for this week
   - "File within 4 weeks" → Create reminder for 2-3 weeks from now
   - "60 days from job loss" → Calculate 60 days and create reminder

2. PRIORITIZE CONVERSATION CONTEXT: Extract dates and deadlines from the conversation first
   - Look for explicit dates: "Nov 1 – Jan 31", "60 days", "within 4 weeks"
   - Look for urgency indicators: "as soon as possible", "right away", "don't wait"
   - Look for deadlines: "file within X weeks", "apply by", "deadline"

3. IGNORE generic holiday/closing dates unless the user specifically asked about them

4. MAKE LOGICAL DECISIONS: Use the entire conversation context to create helpful reminders:
   - If user mentioned job loss → create reminders for UI, CalFresh, health insurance
   - If user mentioned specific programs → create reminders for those applications
   - If user asked about deadlines → extract those and create events

IMPORTANT: Extract dates and create reminders from the conversation. Look for:
- Absolute dates: "Nov 1", "January 31", "Nov 1 – Jan 31" 
  * If date is in the past this year, use next year ({next_year})
  * If date is in the future this year, use this year ({current_year})
  * For date ranges like "Nov 1 – Jan 31", Nov 1 is likely {current_year}-11-01 and Jan 31 is likely {next_year}-01-31
- Relative dates: "60 days from job loss" → calculate from today or mentioned date
- Recurring dates: "Open Enrollment Nov 1 – Jan 31" → create events for both start and end dates
- Time periods: "30-45 days" → create reminder events

Focus on application deadlines, renewal dates, SAR-7 deadlines, open enrollment periods, and other time-sensitive actions."""
        
        # Only include RAG context if it doesn't contain generic holidays
        # and if conversation doesn't already have explicit dates
        conversation_has_dates = any(
            keyword in conversation_text.lower() 
            for keyword in ["nov 1", "jan 31", "january 31", "november 1", "60 days", "enrollment", "deadline"]
        )
        
        rag_section = ""
        if context_text and not conversation_has_dates:
            # Only use RAG if conversation doesn't have explicit dates
            rag_section = f"\n\nAdditional Program Information (for reference only - do NOT create events from this unless mentioned in conversation):\n{context_text[:1000]}"
        
        user_prompt = f"""Based on this ENTIRE conversation, create helpful calendar events and reminders to help the user stay organized with their benefits applications.

Today's date: {today_str} (year: {current_year})

**FULL CONVERSATION CONTEXT:**
{conversation_text}

**ADDITIONAL PROGRAM CONTEXT (for reference only):**
{rag_section}

User Situation: {user_context.get('situation', 'General')}
Programs Mentioned: {', '.join(user_context.get('programs', []))}

**YOUR TASK: Create helpful calendar events based on the conversation. Be proactive and helpful:**

1. **EXPLICIT DEADLINES** - If the conversation mentions specific dates or deadlines:
   - "Nov 1 – Jan 31" → Create events for both start and end dates
   - "60 days from job loss" → Calculate 60 days from today and create reminder
   - "File within 4 weeks" → Create reminder for 3 weeks from now (to give buffer)
   - "Open enrollment Nov 1 – Jan 31" → Create events for both dates

2. **URGENT ACTIONS** - If the conversation says "as soon as possible", "right away", "don't wait":
   - "Apply for UI as soon as possible" → Create reminder for tomorrow
   - "Apply for CalFresh right away" → Create reminder for 2-3 days from now
   - "File your claim immediately" → Create reminder for today or tomorrow

3. **HELPFUL REMINDERS** - Even without explicit dates, create reminders based on context:
   - If user mentioned job loss → Create reminders for: UI application, CalFresh application, health insurance enrollment
   - If user mentioned specific programs → Create reminders for those applications
   - If user asked "what are the important dates?" → Extract all mentioned deadlines and create events

4. **IGNORE** generic holiday/closing dates unless the user specifically asked about them

**Event Format:**
Each event should be a JSON object with:
- "summary": string (clear, actionable title, e.g., "Apply for Unemployment Insurance" or "Covered California Open Enrollment Starts")
- "description": string (what to do, why it's important, helpful tips. Be specific and encouraging)
- "start_date": string (YYYY-MM-DD format)
- "url": string (relevant website if available)

**Examples of helpful events:**
- {{"summary": "Apply for Unemployment Insurance", "description": "File your UI claim as soon as possible. It takes about 3 weeks to process, so the sooner you apply, the sooner you'll receive benefits. Gather your Social Security number, last day worked, and employer information.", "start_date": "{today_str}", "url": "https://edd.ca.gov/Unemployment/"}}
- {{"summary": "Apply for CalFresh (Food Assistance)", "description": "Apply for monthly food assistance. You can apply any time - no deadline, but apply soon to get help faster. You'll need photo ID, proof of address, and proof of income loss.", "start_date": "{(datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')}", "url": "https://www.getcalfresh.org/"}}
- {{"summary": "Covered California Open Enrollment Starts", "description": "Open enrollment period begins. If you lost your job, you have 60 days from job loss to apply for health insurance. Apply early to ensure coverage starts on time.", "start_date": "{current_year}-11-01", "url": "https://www.coveredca.com"}}
- {{"summary": "Covered California Special Enrollment Deadline", "description": "Last day to apply for health insurance if you lost your job. After this date, you'll need to wait for the next open enrollment period.", "start_date": "{(datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')}", "url": "https://www.coveredca.com"}}

**Return ONLY a valid JSON array. Create at least 2-5 helpful reminders based on the conversation, even if no explicit dates are mentioned.**"""
        
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



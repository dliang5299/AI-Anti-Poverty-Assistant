"""
Utility functions for BenefitsFlow
"""

from typing import List, Dict, Any
import re

def extract_programs_from_conversation(conversation_history: List[Dict]) -> Dict:
    """
    Extract program information and user context from conversation.
    
    Args:
        conversation_history: List of messages in the conversation
    
    Returns:
        Dictionary with extracted context
    """
    # In production, this would use NLP to extract structured information
    # For demo, we'll do simple keyword matching
    
    conversation_text = ' '.join([msg['content'] for msg in conversation_history])
    conversation_lower = conversation_text.lower()
    
    context = {
        'situation': None,
        'programs_eligible': [],
        'documents_needed': [],
        'deadlines': []
    }
    
    # Determine situation
    if any(keyword in conversation_lower for keyword in ['job', 'unemployment', 'lost', 'fired']):
        context['situation'] = 'job_loss'
        context['programs_eligible'].extend(['Unemployment Insurance', 'CalFresh', 'Medi-Cal'])
    elif any(keyword in conversation_lower for keyword in ['health', 'medical', 'medi-cal']):
        context['situation'] = 'healthcare'
        context['programs_eligible'].extend(['Medi-Cal', 'Covered California'])
    elif any(keyword in conversation_lower for keyword in ['food', 'calfresh', 'hungry']):
        context['situation'] = 'food_assistance'
        context['programs_eligible'].append('CalFresh')
    elif any(keyword in conversation_lower for keyword in ['housing', 'rent', 'homeless']):
        context['situation'] = 'housing'
        context['programs_eligible'].extend(['Section 8', 'Emergency Housing'])
    
    # Extract documents mentioned
    if 'income' in conversation_lower or 'pay' in conversation_lower:
        context['documents_needed'].append('Proof of income')
    if 'id' in conversation_lower or 'license' in conversation_lower:
        context['documents_needed'].append('Photo ID')
    if 'address' in conversation_lower or 'residence' in conversation_lower:
        context['documents_needed'].append('Proof of residence')
    
    # Extract deadlines
    if 'week' in conversation_lower:
        context['deadlines'].append('File unemployment within 1 week')
    if '30 days' in conversation_lower or 'month' in conversation_lower:
        context['deadlines'].append('Benefits typically start within 30 days')
    
    return context

def get_quick_replies(prompt: str, response: str, conversation_history: List[Dict]) -> List[str]:
    """
    Generate contextual quick reply suggestions.
    
    Args:
        prompt: User's current message
        response: Bot's response
        conversation_history: Previous messages
    
    Returns:
        List of quick reply suggestions
    """
    prompt_lower = prompt.lower()
    response_lower = response.lower()
    
    # Job loss related quick replies
    if any(keyword in prompt_lower for keyword in ['job', 'unemployment', 'lost', 'fired']):
        return [
            "Tell me about UI benefits",
            "How do I apply for CalFresh?",
            "What documents do I need?",
            "Check Medi-Cal eligibility"
        ]
    
    # Healthcare related quick replies
    elif any(keyword in prompt_lower for keyword in ['health', 'medical', 'medi-cal', 'insurance']):
        return [
            "Check Medi-Cal eligibility",
            "What does Medi-Cal cover?",
            "How to apply for Medi-Cal?",
            "Tell me about Covered California"
        ]
    
    # Food assistance related quick replies
    elif any(keyword in prompt_lower for keyword in ['food', 'calfresh', 'hungry', 'groceries']):
        return [
            "Check CalFresh eligibility",
            "How much can I get?",
            "Where can I apply?",
            "What can I buy with CalFresh?"
        ]
    
    # Housing related quick replies
    elif any(keyword in prompt_lower for keyword in ['housing', 'rent', 'homeless', 'shelter']):
        return [
            "Risk of eviction",
            "Currently homeless",
            "Need rent help",
            "Find emergency shelter"
        ]
    
    # Cash assistance related quick replies
    elif any(keyword in prompt_lower for keyword in ['cash', 'money', 'calworks', 'benefits']):
        return [
            "Tell me about CalWORKs",
            "Check eligibility",
            "How to apply?",
            "What documents needed?"
        ]
    
    # General quick replies
    else:
        return [
            "I lost my job",
            "Need healthcare",
            "Need food assistance",
            "Housing help"
        ]

def format_phone_number(phone: str) -> str:
    """
    Format phone number for display.
    
    Args:
        phone: Raw phone number string
    
    Returns:
        Formatted phone number
    """
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Format as (XXX) XXX-XXXX
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone

def validate_email(email: str) -> bool:
    """
    Basic email validation.
    
    Args:
        email: Email address to validate
    
    Returns:
        True if email appears valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def extract_zip_code(text: str) -> str:
    """
    Extract ZIP code from text.
    
    Args:
        text: Text to search for ZIP code
    
    Returns:
        ZIP code if found, empty string otherwise
    """
    # Look for 5-digit ZIP code
    match = re.search(r'\b\d{5}\b', text)
    return match.group() if match else ""

def format_currency(amount: float) -> str:
    """
    Format currency amount for display.
    
    Args:
        amount: Currency amount
    
    Returns:
        Formatted currency string
    """
    return f"${amount:,.2f}"

def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to specified length with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
    
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def get_program_icon(program_name: str) -> str:
    """
    Get appropriate icon for program name.
    
    Args:
        program_name: Name of the program
    
    Returns:
        Emoji icon for the program
    """
    program_lower = program_name.lower()
    
    if 'unemployment' in program_lower or 'ui' in program_lower:
        return "💼"
    elif 'calfresh' in program_lower or 'food' in program_lower:
        return "🍽️"
    elif 'medi-cal' in program_lower or 'health' in program_lower:
        return "🏥"
    elif 'housing' in program_lower or 'section 8' in program_lower:
        return "🏠"
    elif 'calworks' in program_lower or 'cash' in program_lower:
        return "💰"
    elif 'training' in program_lower or 'job' in program_lower:
        return "🎓"
    else:
        return "📋"

def get_priority_color(priority: str) -> str:
    """
    Get color for priority level.
    
    Args:
        priority: Priority level (high, medium, low)
    
    Returns:
        Color code
    """
    colors = {
        'high': '#E74C3C',    # Red
        'medium': '#F39C12',  # Orange
        'low': '#2ECC71'      # Green
    }
    return colors.get(priority.lower(), '#95A5A6')  # Default gray

def get_program_status_color(status: str) -> str:
    """
    Get color for program status.
    
    Args:
        status: Program status
    
    Returns:
        Color code
    """
    colors = {
        'active': '#2ECC71',      # Green
        'pending': '#F39C12',     # Orange
        'expired': '#E74C3C',     # Red
        'suspended': '#95A5A6',   # Gray
        'unknown': '#3498DB'      # Blue
    }
    return colors.get(status.lower(), '#95A5A6')  # Default gray

def sanitize_input(text: str) -> str:
    """
    Sanitize user input to prevent XSS and other issues.
    
    Args:
        text: User input text
    
    Returns:
        Sanitized text
    """
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', 'javascript:', 'data:', 'vbscript:']
    
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    # Limit length
    text = text[:1000]
    
    return text.strip()

def generate_session_id() -> str:
    """
    Generate a unique session ID.
    
    Returns:
        Unique session ID
    """
    import uuid
    return str(uuid.uuid4())[:8]

def format_timestamp(timestamp: str) -> str:
    """
    Format timestamp for display.
    
    Args:
        timestamp: ISO format timestamp
    
    Returns:
        Formatted timestamp string
    """
    from datetime import datetime
    
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%B %d, %Y at %I:%M %p')
    except:
        return timestamp

def get_benefit_category(program_name: str) -> str:
    """
    Get benefit category for a program.
    
    Args:
        program_name: Name of the program
    
    Returns:
        Benefit category
    """
    program_lower = program_name.lower()
    
    if any(keyword in program_lower for keyword in ['unemployment', 'ui', 'job', 'training']):
        return 'Employment'
    elif any(keyword in program_lower for keyword in ['calfresh', 'food', 'nutrition']):
        return 'Food Assistance'
    elif any(keyword in program_lower for keyword in ['medi-cal', 'health', 'medical', 'covered california']):
        return 'Healthcare'
    elif any(keyword in program_lower for keyword in ['housing', 'section 8', 'rent', 'shelter']):
        return 'Housing'
    elif any(keyword in program_lower for keyword in ['calworks', 'cash', 'temporary']):
        return 'Cash Assistance'
    elif any(keyword in program_lower for keyword in ['child care', 'daycare']):
        return 'Child Care'
    elif any(keyword in program_lower for keyword in ['energy', 'utility', 'heating']):
        return 'Energy Assistance'
    else:
        return 'Other'

"""
Utility functions for BenefitsFlow
"""

from typing import List, Dict, Any

def extract_programs_from_conversation(conversation_history: List[Dict]) -> Dict:
    """
    Extract program information and user context from conversation.
    
    Args:
        conversation_history: List of messages in the conversation
    
    Returns:
        Dictionary with extracted context
    """
    # Simple keyword extraction for demo
    conversation_text = ' '.join([msg.get('content', '') for msg in conversation_history])
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
    
    return context

def get_quick_replies(situation: str) -> List[str]:
    """
    Get quick reply suggestions based on situation.
    
    Args:
        situation: User's current situation
    
    Returns:
        List of quick reply suggestions
    """
    quick_replies = {
        'job_loss': [
            'Tell me about UI benefits',
            'How do I apply for CalFresh?',
            'What documents do I need?'
        ],
        'healthcare': [
            'Check Medi-Cal eligibility',
            'What does Medi-Cal cover?',
            'How to apply?'
        ],
        'food_assistance': [
            'Check eligibility',
            'How much can I get?',
            'Where can I apply?'
        ],
        'housing': [
            'Risk of eviction',
            'Currently homeless',
            'Need rent help'
        ],
        'default': [
            'I lost my job',
            'Need healthcare',
            'Need food assistance',
            'Housing help'
        ]
    }
    
    return quick_replies.get(situation, quick_replies['default'])
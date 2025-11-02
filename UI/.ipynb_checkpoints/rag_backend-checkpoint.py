"""
RAG Backend Integration for BenefitsFlow
Handles retrieval-augmented generation for California benefits information.
"""

import json
import random
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Sample responses for demo purposes - in production, this would connect to your vector DB
SAMPLE_RESPONSES = {
    'job_loss': {
        'text': """I understand losing your job is stressful. Let me help you find the support you need. In California, you may be eligible for:

**Unemployment Insurance (UI)**
• Weekly payments while you look for work
• File online at EDD.ca.gov or call 1-800-300-5616
• File within the first week of unemployment

**CalFresh (Food Assistance)**
• Monthly benefits loaded onto an EBT card
• Average $200-600/month depending on household size
• Apply at BenefitsCal.com

**Medi-Cal (Health Coverage)**
• Free or low-cost health insurance
• No waiting period if you qualify
• Apply at BenefitsCal.com

**Job Training Programs**
• Free skills training and career services
• Available through local workforce development boards

Which of these would you like to know more about?""",
        'sources': [
            {'name': 'EDD California', 'url': 'https://edd.ca.gov', 'date': 'Oct 2025'},
            {'name': 'CalFresh', 'url': 'https://calfresh.ca.gov', 'date': 'Oct 2025'},
            {'name': 'DHCS', 'url': 'https://dhcs.ca.gov', 'date': 'Oct 2025'}
        ],
        'programs': ['Unemployment Insurance', 'CalFresh', 'Medi-Cal', 'Job Training']
    },
    
    'healthcare': {
        'text': """California offers several healthcare options to help you get coverage:

**Medi-Cal**
• Free or low-cost health coverage for low-income individuals
• Covers doctor visits, hospital care, prescriptions, and more
• No monthly premiums for most people
• Apply at BenefitsCal.com or call 1-800-300-1506

**Covered California**
• Health insurance marketplace with financial assistance
• Premium tax credits and cost-sharing reductions available
• Open enrollment typically November-January
• Special enrollment if you have qualifying life events

**Emergency Medi-Cal**
• Immediate coverage for emergency medical conditions
• Available regardless of immigration status
• Apply at any hospital or county office

**Pregnancy Support**
• Comprehensive prenatal and postnatal care
• No-cost pregnancy-related services
• Available through Medi-Cal or local health departments

Would you like help checking your eligibility for any of these programs?""",
        'sources': [
            {'name': 'DHCS', 'url': 'https://dhcs.ca.gov', 'date': 'Oct 2025'},
            {'name': 'Covered California', 'url': 'https://coveredca.com', 'date': 'Oct 2025'},
            {'name': 'BenefitsCal', 'url': 'https://benefitscal.com', 'date': 'Oct 2025'}
        ],
        'programs': ['Medi-Cal', 'Covered California', 'Emergency Medi-Cal']
    },
    
    'food_assistance': {
        'text': """CalFresh (formerly food stamps) helps families buy nutritious food. Here's what you need to know:

**Benefits**
• Monthly benefits loaded onto an EBT card
• Average $200-600/month depending on household size
• Can be used at most grocery stores, farmers markets, and online retailers
• Benefits are based on household income and expenses

**Eligibility**
• Must be a California resident
• Income limits vary by household size
• Most people who work can still qualify
• Students, seniors, and people with disabilities may have special rules

**How to Apply**
• Online at BenefitsCal.com (fastest method)
• In-person at your local county office
• By phone at 1-877-847-3663
• Application takes about 30 minutes

**What to Expect**
• Interview scheduled within 10 days of application
• Benefits typically start within 30 days
• EBT card mailed to your address
• Benefits renew every 6-12 months

Would you like help determining if you're eligible or need assistance with the application?""",
        'sources': [
            {'name': 'CalFresh', 'url': 'https://calfresh.ca.gov', 'date': 'Oct 2025'},
            {'name': 'BenefitsCal', 'url': 'https://benefitscal.com', 'date': 'Oct 2025'},
            {'name': 'CDSS', 'url': 'https://cdss.ca.gov', 'date': 'Oct 2025'}
        ],
        'programs': ['CalFresh']
    },
    
    'housing': {
        'text': """California has several housing assistance programs to help with different situations:

**Section 8 Housing Choice Vouchers**
• Helps pay rent in private housing
• You pay 30% of your income toward rent
• Waitlists can be long - apply as soon as possible
• Contact your local housing authority

**Emergency Housing Assistance**
• Immediate shelter for homeless individuals and families
• Transitional housing programs
• Rapid rehousing services
• Call 211 or visit your local county office

**Rent Relief Programs**
• Help with back rent and utilities
• COVID-19 rent relief may still be available
• Local programs vary by county
• Check with your county's housing department

**Homeless Services**
• Emergency shelters and warming centers
• Transitional housing and permanent supportive housing
• Case management and support services
• Coordinated entry system in most counties

**Are you currently:**
1. At risk of losing your housing?
2. Already homeless?
3. Need help with rent payments?
4. Looking for affordable housing options?

Let me know your situation so I can provide more specific guidance.""",
        'sources': [
            {'name': 'HUD', 'url': 'https://hud.gov', 'date': 'Oct 2025'},
            {'name': 'California Housing', 'url': 'https://hcd.ca.gov', 'date': 'Oct 2025'},
            {'name': '211 California', 'url': 'https://211california.org', 'date': 'Oct 2025'}
        ],
        'programs': ['Section 8', 'Emergency Housing', 'Rent Relief', 'Homeless Services']
    },
    
    'cash_assistance': {
        'text': """CalWORKs provides temporary cash assistance and employment services to eligible families:

**Cash Benefits**
• Monthly cash payments to help with basic needs
• Amount depends on family size and income
• Maximum benefit for family of 3: about $900/month
• Benefits are time-limited (48 months lifetime)

**Employment Services**
• Job search assistance and training
• Education and vocational programs
• Work experience opportunities
• Child care assistance while working or in school

**Support Services**
• Child care assistance
• Transportation help
• Work-related expenses
• Domestic violence services

**Eligibility Requirements**
• Must have minor children in the home
• Must participate in work activities
• Income and asset limits apply
• Must be California resident

**How to Apply**
• Online at BenefitsCal.com
• In-person at your local county office
• Application includes interview and verification

Would you like more information about eligibility or the application process?""",
        'sources': [
            {'name': 'CDSS', 'url': 'https://cdss.ca.gov', 'date': 'Oct 2025'},
            {'name': 'BenefitsCal', 'url': 'https://benefitscal.com', 'date': 'Oct 2025'}
        ],
        'programs': ['CalWORKs']
    },
    
    'default': {
        'text': """I'm here to help you navigate California's public benefits. I can provide information about:

**Food Assistance**
• CalFresh (food stamps) - monthly benefits for groceries

**Healthcare**
• Medi-Cal - free or low-cost health insurance
• Covered California - marketplace with financial help

**Cash Assistance**
• CalWORKs - temporary cash aid for families with children
• General Relief - emergency cash assistance (varies by county)

**Housing Help**
• Section 8 vouchers - help paying rent
• Emergency housing - immediate shelter assistance
• Rent relief programs

**Unemployment**
• Unemployment Insurance - weekly payments while job searching
• Job training programs - free skills training

**Other Programs**
• Disability benefits (SSI/SSDI)
• Senior services and programs
• Child care assistance
• Energy assistance (LIHEAP)

What situation are you facing? I can provide more specific information and help you understand your options.""",
        'sources': [
            {'name': 'BenefitsCal', 'url': 'https://benefitscal.com', 'date': 'Oct 2025'},
            {'name': 'CDSS', 'url': 'https://cdss.ca.gov', 'date': 'Oct 2025'}
        ],
        'programs': []
    }
}

def get_rag_response(prompt: str, conversation_history: List[Dict], user_context: Dict) -> Tuple[str, List[Dict], List[str]]:
    """
    Get RAG response based on user prompt and conversation history.
    
    Args:
        prompt: User's current message
        conversation_history: List of previous messages
        user_context: Extracted user context from conversation
    
    Returns:
        Tuple of (response_text, sources, programs_mentioned)
    """
    # In production, this would:
    # 1. Query your vector database with the prompt + conversation context
    # 2. Retrieve relevant documents
    # 3. Generate response using LLM with retrieved context
    # 4. Extract metadata (sources, programs, etc.)
    
    # For demo purposes, we'll use keyword matching
    prompt_lower = prompt.lower()
    
    # Determine response category based on keywords
    if any(keyword in prompt_lower for keyword in ['job', 'unemployment', 'lost', 'fired', 'laid off', 'work']):
        response_data = SAMPLE_RESPONSES['job_loss']
    elif any(keyword in prompt_lower for keyword in ['health', 'medical', 'medi-cal', 'insurance', 'doctor', 'hospital']):
        response_data = SAMPLE_RESPONSES['healthcare']
    elif any(keyword in prompt_lower for keyword in ['food', 'calfresh', 'hungry', 'groceries', 'eat']):
        response_data = SAMPLE_RESPONSES['food_assistance']
    elif any(keyword in prompt_lower for keyword in ['housing', 'rent', 'homeless', 'shelter', 'eviction']):
        response_data = SAMPLE_RESPONSES['housing']
    elif any(keyword in prompt_lower for keyword in ['cash', 'money', 'calworks', 'benefits', 'assistance']):
        response_data = SAMPLE_RESPONSES['cash_assistance']
    else:
        response_data = SAMPLE_RESPONSES['default']
    
    return response_data['text'], response_data['sources'], response_data['programs']

def generate_checklist(conversation_history: List[Dict], user_context: Dict) -> List[Dict]:
    """
    Generate a personalized checklist based on conversation history.
    
    Args:
        conversation_history: List of messages in the conversation
        user_context: Extracted context about user's situation
    
    Returns:
        List of checklist items
    """
    # In production, this would use AI to analyze the conversation
    # and generate personalized action items
    
    # For demo, we'll generate a generic checklist based on common scenarios
    checklist_items = []
    
    # Always include document gathering
    checklist_items.append({
        'title': 'Gather Required Documents',
        'description': 'Collect these documents before applying for benefits:',
        'details': [
            'Proof of income (pay stubs from last 30 days)',
            'Photo ID (Driver\'s License or State ID)',
            'Proof of residence (utility bill or lease)',
            'Social Security numbers for all household members',
            'Bank statements (if required)',
            'Birth certificates for children (if applicable)'
        ],
        'deadline': 'Before starting applications',
        'type': 'Documents',
        'priority': 'high'
    })
    
    # Add program-specific items based on conversation
    conversation_text = ' '.join([msg['content'] for msg in conversation_history])
    conversation_lower = conversation_text.lower()
    
    if any(keyword in conversation_lower for keyword in ['job', 'unemployment', 'lost', 'fired']):
        checklist_items.append({
            'title': 'Apply for Unemployment Insurance',
            'description': 'File your UI claim as soon as possible after job loss:',
            'details': [
                'Visit EDD.ca.gov to file online (fastest method)',
                'Or call 1-800-300-5616 to file by phone',
                'Have employment history and last employer information ready',
                'File within the first week of unemployment for full benefits',
                'Complete weekly certification to receive payments'
            ],
            'deadline': 'Within 1 week of job loss',
            'type': 'Action',
            'priority': 'high',
            'link': 'https://edd.ca.gov'
        })
    
    if any(keyword in conversation_lower for keyword in ['food', 'calfresh', 'hungry', 'groceries']):
        checklist_items.append({
            'title': 'Submit CalFresh Application',
            'description': 'Apply for food assistance benefits:',
            'details': [
                'Complete online application at BenefitsCal.com',
                'Or visit your local county office in person',
                'Interview will be scheduled within 10 days',
                'Benefits typically arrive within 30 days',
                'Keep receipts for any work-related expenses'
            ],
            'deadline': 'Apply as soon as possible',
            'type': 'Action',
            'priority': 'high',
            'link': 'https://benefitscal.com'
        })
    
    if any(keyword in conversation_lower for keyword in ['health', 'medical', 'medi-cal', 'insurance']):
        checklist_items.append({
            'title': 'Check Medi-Cal Eligibility',
            'description': 'See if you qualify for health coverage:',
            'details': [
                'Use online eligibility calculator at BenefitsCal.com',
                'Based on household size and monthly income',
                'Coverage can start the same month if eligible',
                'No waiting period for most people',
                'Apply even if you think you might not qualify'
            ],
            'deadline': 'Check within 15 days',
            'type': 'Check',
            'priority': 'medium',
            'link': 'https://benefitscal.com'
        })
    
    if any(keyword in conversation_lower for keyword in ['housing', 'rent', 'homeless', 'shelter']):
        checklist_items.append({
            'title': 'Contact Housing Resources',
            'description': 'Get help with housing needs:',
            'details': [
                'Call 211 for local housing resources',
                'Contact your county housing authority',
                'Check for emergency shelter availability',
                'Apply for Section 8 if waitlist is open',
                'Document any housing-related expenses'
            ],
            'deadline': 'Contact within 24-48 hours if urgent',
            'type': 'Action',
            'priority': 'high',
            'link': 'https://211california.org'
        })
    
    # Add follow-up items
    checklist_items.append({
        'title': 'Follow Up on Applications',
        'description': 'Stay on top of your benefit applications:',
        'details': [
            'Check application status regularly',
            'Respond to any requests for additional information',
            'Keep copies of all submitted documents',
            'Note important dates and deadlines',
            'Contact caseworkers if you have questions'
        ],
        'deadline': 'Ongoing',
        'type': 'Follow-up',
        'priority': 'medium'
    })
    
    return checklist_items

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

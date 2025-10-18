"""
Configuration settings for BenefitsFlow
"""

import os
from typing import Dict, Any

# Application settings
APP_NAME = "BenefitsFlow"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "California Benefits Navigator"

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-3.5-turbo"
OPENAI_MAX_TOKENS = 1000
OPENAI_TEMPERATURE = 0.7

# Vector Database Configuration
CHROMA_PERSIST_DIRECTORY = "./chroma_db"
CHROMA_COLLECTION_NAME = "california_benefits"

# RAG Configuration
RAG_TOP_K_RESULTS = 5
RAG_SIMILARITY_THRESHOLD = 0.7
RAG_MAX_CONTEXT_LENGTH = 4000

# UI Configuration
MAX_MESSAGE_HISTORY = 50
MAX_QUICK_REPLIES = 4
SESSION_TIMEOUT_MINUTES = 30

# Source Configuration
OFFICIAL_SOURCES = {
    "EDD": {
        "name": "Employment Development Department",
        "url": "https://edd.ca.gov",
        "description": "Unemployment insurance and job services"
    },
    "CDSS": {
        "name": "California Department of Social Services",
        "url": "https://cdss.ca.gov",
        "description": "Social services and benefits programs"
    },
    "DHCS": {
        "name": "Department of Health Care Services",
        "url": "https://dhcs.ca.gov",
        "description": "Health care programs and Medi-Cal"
    },
    "BenefitsCal": {
        "name": "BenefitsCal",
        "url": "https://benefitscal.com",
        "description": "Online benefits application portal"
    },
    "CoveredCA": {
        "name": "Covered California",
        "url": "https://coveredca.com",
        "description": "Health insurance marketplace"
    },
    "HUD": {
        "name": "U.S. Department of Housing and Urban Development",
        "url": "https://hud.gov",
        "description": "Housing assistance programs"
    },
    "211CA": {
        "name": "211 California",
        "url": "https://211california.org",
        "description": "Local resource directory"
    }
}

# Program Categories
PROGRAM_CATEGORIES = {
    "employment": {
        "name": "Employment & Training",
        "icon": "💼",
        "programs": ["Unemployment Insurance", "Job Training", "Workforce Development"]
    },
    "food": {
        "name": "Food Assistance",
        "icon": "🍽️",
        "programs": ["CalFresh", "WIC", "School Meals"]
    },
    "healthcare": {
        "name": "Healthcare",
        "icon": "🏥",
        "programs": ["Medi-Cal", "Covered California", "Emergency Medi-Cal"]
    },
    "housing": {
        "name": "Housing",
        "icon": "🏠",
        "programs": ["Section 8", "Emergency Housing", "Rent Relief"]
    },
    "cash": {
        "name": "Cash Assistance",
        "icon": "💰",
        "programs": ["CalWORKs", "General Relief", "SSI"]
    },
    "childcare": {
        "name": "Child Care",
        "icon": "👶",
        "programs": ["Child Care Assistance", "Head Start", "Preschool"]
    },
    "energy": {
        "name": "Energy Assistance",
        "icon": "⚡",
        "programs": ["LIHEAP", "Weatherization", "Energy Efficiency"]
    }
}

# Quick Start Scenarios
QUICK_START_SCENARIOS = {
    "job_loss": {
        "title": "Job Loss",
        "icon": "💼",
        "description": "Unemployment, training programs",
        "keywords": ["job", "unemployment", "lost", "fired", "laid off"]
    },
    "healthcare": {
        "title": "Healthcare",
        "icon": "🏥",
        "description": "Medi-Cal, health coverage",
        "keywords": ["health", "medical", "medi-cal", "insurance", "doctor"]
    },
    "food_assistance": {
        "title": "Food",
        "icon": "🍽️",
        "description": "CalFresh, food programs",
        "keywords": ["food", "calfresh", "hungry", "groceries", "eat"]
    },
    "housing": {
        "title": "Housing",
        "icon": "🏠",
        "description": "Rental assistance, shelters",
        "keywords": ["housing", "rent", "homeless", "shelter", "eviction"]
    }
}

# Trust Badges
TRUST_BADGES = [
    {
        "icon": "🔒",
        "text": "Privacy First",
        "description": "Session-based, no PII stored"
    },
    {
        "icon": "📚",
        "text": "Evidence-Based",
        "description": "All information from official sources"
    },
    {
        "icon": "♿",
        "text": "Accessible",
        "description": "Designed for all users"
    },
    {
        "icon": "🔄",
        "text": "Always Updated",
        "description": "Current benefit information"
    }
]

# Error Messages
ERROR_MESSAGES = {
    "api_error": "I'm having trouble connecting to our information system. Please try again in a moment.",
    "no_results": "I couldn't find specific information about that. Could you rephrase your question?",
    "invalid_input": "I didn't understand that. Could you please try asking in a different way?",
    "system_error": "I encountered an unexpected error. Please try again or contact support if the problem persists."
}

# Success Messages
SUCCESS_MESSAGES = {
    "checklist_generated": "Your personalized checklist has been generated!",
    "feedback_submitted": "Thank you for your feedback!",
    "session_cleared": "Your session has been cleared. You can start a new conversation."
}

# Validation Rules
VALIDATION_RULES = {
    "max_message_length": 1000,
    "max_conversation_length": 50,
    "min_message_length": 1,
    "allowed_file_types": [".pdf", ".doc", ".docx", ".txt"],
    "max_file_size_mb": 10
}

# Feature Flags
FEATURE_FLAGS = {
    "enable_checklist_generation": True,
    "enable_feedback_collection": True,
    "enable_quick_replies": True,
    "enable_source_links": True,
    "enable_progress_tracking": True,
    "enable_export_functionality": False,  # For future implementation
    "enable_user_accounts": False,  # For future implementation
    "enable_analytics": False  # For future implementation
}

def get_config() -> Dict[str, Any]:
    """Get complete configuration dictionary"""
    return {
        "app": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "description": APP_DESCRIPTION
        },
        "api": {
            "openai_key": OPENAI_API_KEY,
            "openai_model": OPENAI_MODEL,
            "openai_max_tokens": OPENAI_MAX_TOKENS,
            "openai_temperature": OPENAI_TEMPERATURE
        },
        "vector_db": {
            "chroma_persist_directory": CHROMA_PERSIST_DIRECTORY,
            "chroma_collection_name": CHROMA_COLLECTION_NAME
        },
        "rag": {
            "top_k_results": RAG_TOP_K_RESULTS,
            "similarity_threshold": RAG_SIMILARITY_THRESHOLD,
            "max_context_length": RAG_MAX_CONTEXT_LENGTH
        },
        "ui": {
            "max_message_history": MAX_MESSAGE_HISTORY,
            "max_quick_replies": MAX_QUICK_REPLIES,
            "session_timeout_minutes": SESSION_TIMEOUT_MINUTES
        },
        "sources": OFFICIAL_SOURCES,
        "categories": PROGRAM_CATEGORIES,
        "quick_start": QUICK_START_SCENARIOS,
        "trust_badges": TRUST_BADGES,
        "errors": ERROR_MESSAGES,
        "success": SUCCESS_MESSAGES,
        "validation": VALIDATION_RULES,
        "features": FEATURE_FLAGS
    }

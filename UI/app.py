"""
BenefitsFlow - California Benefits Navigator
A Streamlit application for helping users navigate California's public benefits programs.
"""

import streamlit as st
import time
import json
from datetime import datetime
from typing import List, Dict, Any
import os

# Import our custom modules
from rag_backend import get_rag_response, generate_checklist
from utils import extract_programs_from_conversation, get_quick_replies

# Page configuration
st.set_page_config(
    page_title="BenefitsFlow - California Benefits Navigator",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for BenefitsFlow branding and design
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Root variables matching BenefitsFlow design system */
    :root {
        --primary-color: #4A90A4;
        --secondary-color: #F4A261;
        --bg-color: #FAFAFA;
        --text-color: #2D3436;
        --light-gray: #E8E8E8;
        --success: #2ECC71;
        --warning: #F39C12;
        --error: #E74C3C;
        --white: #FFFFFF;
        --user-bubble: #E3F2FD;
        --bot-bubble: #FFF8E7;
        --shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    /* Main app styling */
    .main {
        background-color: var(--bg-color);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, var(--primary-color) 0%, #2c5f6f 100%);
        color: white;
        padding: 1rem 2rem;
        margin: -1rem -1rem 2rem -1rem;
        border-radius: 0 0 16px 16px;
        box-shadow: var(--shadow);
    }
    
    .header-content {
        display: flex;
        align-items: center;
        gap: 1rem;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    .logo-container {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .logo-placeholder {
        width: 50px;
        height: 50px;
        background: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        color: var(--primary-color);
    }
    
    .brand-info h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    
    .brand-info p {
        margin: 0;
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    /* Chat message styling */
    .stChatMessage {
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: var(--shadow);
    }
    
    .stChatMessage[data-testid="user-message"] {
        background-color: var(--user-bubble);
        border-left: 4px solid var(--secondary-color);
    }
    
    .stChatMessage[data-testid="assistant-message"] {
        background-color: var(--bot-bubble);
        border-left: 4px solid var(--primary-color);
    }
    
    /* Landing page styling */
    .landing-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 60vh;
        text-align: center;
        padding: 2rem;
    }
    
    .hero-icon {
        width: 120px;
        height: 120px;
        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 3rem;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        color: white;
    }
    
    .landing-title {
        font-size: 2.5rem;
        color: var(--primary-color);
        margin-bottom: 1rem;
        font-weight: 700;
    }
    
    .landing-subtitle {
        font-size: 1.2rem;
        color: #666;
        max-width: 600px;
        margin-bottom: 3rem;
        line-height: 1.6;
    }
    
    /* Quick start cards */
    .quick-start-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        width: 100%;
        max-width: 900px;
        margin-bottom: 2rem;
    }
    
    .quick-card {
        background: white;
        padding: 2rem 1.5rem;
        border-radius: 12px;
        box-shadow: var(--shadow);
        cursor: pointer;
        transition: all 0.3s;
        border: 2px solid transparent;
        text-align: center;
    }
    
    .quick-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 5px 20px rgba(0,0,0,0.15);
        border-color: var(--primary-color);
    }
    
    .quick-card-icon {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    
    .quick-card h3 {
        font-size: 1.2rem;
        margin-bottom: 0.5rem;
        color: var(--primary-color);
    }
    
    .quick-card p {
        font-size: 0.9rem;
        color: #666;
        margin: 0;
    }
    
    /* Trust badges */
    .trust-badges {
        display: flex;
        gap: 2rem;
        justify-content: center;
        flex-wrap: wrap;
        margin-top: 2rem;
    }
    
    .trust-badge {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #666;
        font-size: 0.9rem;
    }
    
    /* Source tags */
    .source-tag {
        display: inline-block;
        background: #e0f2fe;
        color: #0369a1;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        margin: 0.25rem 0.25rem 0.25rem 0;
        text-decoration: none;
        transition: all 0.2s;
    }
    
    .source-tag:hover {
        background: #bae6fd;
        text-decoration: none;
        color: #0369a1;
    }
    
    /* Quick reply buttons */
    .quick-replies {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-top: 0.75rem;
    }
    
    .quick-reply-btn {
        background: white;
        border: 1px solid var(--primary-color);
        color: var(--primary-color);
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.2s;
        text-decoration: none;
        display: inline-block;
    }
    
    .quick-reply-btn:hover {
        background: var(--primary-color);
        color: white;
        text-decoration: none;
    }
    
    /* Sidebar styling */
    .sidebar .stButton > button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid var(--light-gray);
        background: white;
        color: var(--text-color);
        transition: all 0.2s;
    }
    
    .sidebar .stButton > button:hover {
        background: var(--bg-color);
        border-color: var(--primary-color);
    }
    
    /* Action buttons */
    .action-buttons {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        z-index: 50;
    }
    
    .action-btn {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        border: none;
        font-size: 1.5rem;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transition: all 0.3s;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .action-btn:hover {
        transform: scale(1.1);
    }
    
    .action-btn.checklist {
        background: var(--success);
        color: white;
    }
    
    .action-btn.restart {
        background: var(--warning);
        color: white;
    }
    
    .action-btn.feedback {
        background: var(--secondary-color);
        color: white;
    }
    
    /* Progress indicator */
    .progress-container {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        box-shadow: var(--shadow);
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .landing-title {
            font-size: 2rem;
        }
        
        .landing-subtitle {
            font-size: 1rem;
        }
        
        .quick-start-grid {
            grid-template-columns: 1fr;
        }
        
        .action-buttons {
            right: 1rem;
            bottom: 1rem;
        }
        
        .action-btn {
            width: 50px;
            height: 50px;
            font-size: 1.2rem;
        }
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant", 
                "content": "Hi! I'm here to help you navigate California's public benefits. What brings you here today?",
                "timestamp": datetime.now().isoformat()
            }
        ]
    
    if "programs_mentioned" not in st.session_state:
        st.session_state.programs_mentioned = set()
    
    if "user_context" not in st.session_state:
        st.session_state.user_context = {
            "situation": None,
            "programs_eligible": [],
            "documents_needed": [],
            "deadlines": []
        }
    
    if "conversation_started" not in st.session_state:
        st.session_state.conversation_started = False
    
    if "checklist_data" not in st.session_state:
        st.session_state.checklist_data = None

def render_header():
    """Render the BenefitsFlow header"""
    st.markdown("""
    <div class="main-header">
        <div class="header-content">
            <div class="logo-container">
                <div class="logo-placeholder">🌍</div>
                <div class="brand-info">
                    <h1>BenefitsFlow</h1>
                    <p>Your California Benefits Navigator</p>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_landing_page():
    """Render the landing page with quick start options"""
    st.markdown("""
    <div class="landing-container">
        <div class="hero-icon">🌍</div>
        <h1 class="landing-title">Find the Right Benefits for Your Situation</h1>
        <p class="landing-subtitle">
            Get personalized guidance on California's public assistance programs. 
            We'll help you navigate food assistance, healthcare, cash aid, and more.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick start cards
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    
    with col1:
        if st.button("💼 **Job Loss**\n\nUnemployment, training programs", 
                    use_container_width=True, key="quick_job"):
            st.session_state.quick_start = "job loss"
            st.rerun()
    
    with col2:
        if st.button("🏥 **Healthcare**\n\nMedi-Cal, health coverage", 
                    use_container_width=True, key="quick_health"):
            st.session_state.quick_start = "healthcare"
            st.rerun()
    
    with col3:
        if st.button("🍽️ **Food**\n\nCalFresh, food programs", 
                    use_container_width=True, key="quick_food"):
            st.session_state.quick_start = "food assistance"
            st.rerun()
    
    with col4:
        if st.button("🏠 **Housing**\n\nRental assistance, shelters", 
                    use_container_width=True, key="quick_housing"):
            st.session_state.quick_start = "housing"
            st.rerun()
    
    # Trust badges
    st.markdown("""
    <div class="trust-badges">
        <div class="trust-badge">
            <span>🔒</span>
            <span>Privacy First</span>
        </div>
        <div class="trust-badge">
            <span>📚</span>
            <span>Evidence-Based</span>
        </div>
        <div class="trust-badge">
            <span>♿</span>
            <span>Accessible</span>
        </div>
        <div class="trust-badge">
            <span>🔄</span>
            <span>Always Updated</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    """Render the sidebar with session info and controls"""
    with st.sidebar:
        st.markdown("### 📊 Your Session")
        
        # Programs mentioned
        if st.session_state.programs_mentioned:
            st.markdown("**Programs Discussed:**")
            for program in st.session_state.programs_mentioned:
                st.write(f"• {program}")
        else:
            st.caption("Start a conversation to see programs")
        
        st.divider()
        
        # Settings
        st.markdown("### ⚙️ Settings")
        
        if st.button("🗑️ Clear Chat", use_container_width=True):
            # Clear all session state
            for key in list(st.session_state.keys()):
                if key not in ["_streamlit_rerun_count"]:
                    del st.session_state[key]
            st.rerun()
        
        if st.button("💬 Send Feedback", use_container_width=True):
            st.session_state.show_feedback = True
            st.rerun()
        
        if st.button("❓ Help", use_container_width=True):
            st.session_state.show_help = True
            st.rerun()
        
        st.divider()
        
        # Privacy notice
        st.markdown("""
        <div style="background: #f0f9ff; padding: 1rem; border-radius: 8px; font-size: 0.85rem; color: #0c4a6e;">
            <strong>🔒 Privacy & Security</strong><br>
            • Session-based, no PII stored<br>
            • Data last updated: October 2025<br>
            • Evidence-based information
        </div>
        """, unsafe_allow_html=True)

def render_chat_interface():
    """Render the main chat interface"""
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show sources if available
            if message.get("sources"):
                with st.expander("📚 Sources"):
                    for source in message["sources"]:
                        st.markdown(f"[{source['name']}]({source['url']}) - Last updated: {source['date']}")
            
            # Show quick replies if available
            if message.get("quick_replies"):
                st.markdown("**Quick replies:**")
                cols = st.columns(len(message["quick_replies"]))
                for i, reply in enumerate(message["quick_replies"]):
                    with cols[i]:
                        if st.button(reply, key=f"quick_{i}_{message['timestamp']}"):
                            st.session_state.quick_reply = reply
                            st.rerun()
    
    # Chat input
    if prompt := st.chat_input("Ask me about available programs..."):
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().isoformat()
        })
        
        # Show user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get RAG response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response, sources, programs = get_rag_response(
                        prompt, 
                        st.session_state.messages,
                        st.session_state.user_context
                    )
                    
                    st.markdown(response)
                    
                    # Show sources
                    if sources:
                        with st.expander("📚 Sources"):
                            for source in sources:
                                st.markdown(f"[{source['name']}]({source['url']}) - Last updated: {source['date']}")
                    
                    # Get quick replies
                    quick_replies = get_quick_replies(prompt, response, st.session_state.messages)
                    
                    if quick_replies:
                        st.markdown("**Quick replies:**")
                        cols = st.columns(len(quick_replies))
                        for i, reply in enumerate(quick_replies):
                            with cols[i]:
                                if st.button(reply, key=f"reply_{i}_{datetime.now().timestamp()}"):
                                    st.session_state.quick_reply = reply
                                    st.rerun()
                    
                    # Store assistant response
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "sources": sources,
                        "quick_replies": quick_replies,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Update programs mentioned
                    if programs:
                        st.session_state.programs_mentioned.update(programs)
                    
                    # Update user context
                    st.session_state.user_context = extract_programs_from_conversation(
                        st.session_state.messages
                    )
                    
                except Exception as e:
                    st.error(f"Sorry, I encountered an error: {str(e)}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "I apologize, but I'm having trouble processing your request right now. Please try again.",
                        "timestamp": datetime.now().isoformat()
                    })

def render_action_buttons():
    """Render floating action buttons"""
    if st.session_state.conversation_started:
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button("📋", help="Generate Checklist", key="action_checklist"):
                st.session_state.show_checklist = True
                st.rerun()
        
        with col2:
            if st.button("🔄", help="Start Over", key="action_restart"):
                if st.session_state.get("confirm_restart"):
                    # Clear session
                    for key in list(st.session_state.keys()):
                        if key not in ["_streamlit_rerun_count"]:
                            del st.session_state[key]
                    st.rerun()
                else:
                    st.session_state.confirm_restart = True
                    st.rerun()
        
        with col3:
            if st.button("💬", help="Feedback", key="action_feedback"):
                st.session_state.show_feedback = True
                st.rerun()

def render_checklist_modal():
    """Render the checklist generation modal"""
    if st.session_state.get("show_checklist"):
        st.markdown("### 📋 Your Personalized Checklist")
        st.markdown("Based on our conversation, here are the steps you need to take:")
        
        try:
            checklist_data = generate_checklist(st.session_state.messages, st.session_state.user_context)
            st.session_state.checklist_data = checklist_data
            
            for i, item in enumerate(checklist_data):
                with st.expander(f"☐ {item['title']}", expanded=True):
                    st.markdown(f"**Description:** {item['description']}")
                    
                    if item.get('details'):
                        st.markdown("**Details:**")
                        for detail in item['details']:
                            st.markdown(f"• {detail}")
                    
                    if item.get('deadline'):
                        st.markdown(f"**⏰ Deadline:** {item['deadline']}")
                    
                    if item.get('link'):
                        st.markdown(f"**🔗 [Visit Website]({item['link']})**")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 Download PDF", use_container_width=True):
                    st.success("PDF download would be implemented here!")
            
            with col2:
                if st.button("📧 Email Me", use_container_width=True):
                    st.success("Email functionality would be implemented here!")
            
            if st.button("Close", use_container_width=True):
                st.session_state.show_checklist = False
                st.rerun()
                
        except Exception as e:
            st.error(f"Error generating checklist: {str(e)}")

def render_feedback_modal():
    """Render the feedback modal"""
    if st.session_state.get("show_feedback"):
        st.markdown("### 💬 Send Feedback")
        st.markdown("Help us improve BenefitsFlow:")
        
        feedback = st.text_area(
            "Share your thoughts, suggestions, or report issues:",
            placeholder="Your feedback here...",
            height=120
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Cancel", use_container_width=True):
                st.session_state.show_feedback = False
                st.rerun()
        
        with col2:
            if st.button("Submit Feedback", use_container_width=True):
                if feedback:
                    st.success("Thank you for your feedback!")
                    st.session_state.show_feedback = False
                    st.rerun()
                else:
                    st.warning("Please enter your feedback before submitting.")

def render_help_modal():
    """Render the help modal"""
    if st.session_state.get("show_help"):
        st.markdown("### ❓ Help & Support")
        
        st.markdown("""
        **How to use BenefitsFlow:**
        
        1. **Start a conversation** - Ask about your situation or use the quick start cards
        2. **Get personalized guidance** - Our AI will provide relevant benefit information
        3. **Check sources** - All information comes from official government sources
        4. **Generate a checklist** - Get a personalized action plan based on your conversation
        5. **Take action** - Follow the steps to apply for benefits
        
        **Privacy & Security:**
        - Your conversations are not stored permanently
        - No personal information is collected
        - All data is session-based and secure
        
        **Need more help?**
        - Contact your local county benefits office
        - Visit [BenefitsCal.com](https://benefitscal.com) for official applications
        - Call 211 for local assistance
        """)
        
        if st.button("Close", use_container_width=True):
            st.session_state.show_help = False
            st.rerun()

def main():
    """Main application function"""
    # Initialize session state
    initialize_session_state()
    
    # Render header
    render_header()
    
    # Handle quick start
    if st.session_state.get("quick_start"):
        st.session_state.messages.append({
            "role": "user",
            "content": f"I need help with {st.session_state.quick_start}",
            "timestamp": datetime.now().isoformat()
        })
        st.session_state.conversation_started = True
        del st.session_state.quick_start
        st.rerun()
    
    # Handle quick reply
    if st.session_state.get("quick_reply"):
        st.session_state.messages.append({
            "role": "user",
            "content": st.session_state.quick_reply,
            "timestamp": datetime.now().isoformat()
        })
        del st.session_state.quick_reply
        st.rerun()
    
    # Render sidebar
    render_sidebar()
    
    # Main content area
    if not st.session_state.conversation_started:
        render_landing_page()
    else:
        render_chat_interface()
    
    # Render modals
    render_checklist_modal()
    render_feedback_modal()
    render_help_modal()
    
    # Render action buttons
    render_action_buttons()

if __name__ == "__main__":
    main()

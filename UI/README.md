# BenefitsFlow - California Benefits Navigator

A Streamlit-based web application that helps California residents navigate public benefits programs using conversational AI and RAG (Retrieval-Augmented Generation).

## Features

- **Conversational Interface**: Chat-based interaction for natural language queries
- **RAG-Powered Responses**: Evidence-based answers with source transparency
- **Personalized Checklists**: Generate action plans based on user conversations
- **Mobile-First Design**: Responsive design optimized for mobile devices
- **Session-Based Privacy**: No PII storage, session-based data handling
- **Quick Start Cards**: Easy access to common benefit scenarios
- **Source Transparency**: All information linked to official government sources

## Design Philosophy

- **Mobile-First**: 53% of benefits programs aren't mobile-responsive - we stand out
- **Empathetic Tone**: Trust-building, supportive communication
- **Plain Language**: Accessible to users facing daily complexity
- **Evidence-Based**: All information sourced from official government documents

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd AI-Anti-Poverty-Assistant/UI
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   streamlit run app.py
   ```

4. **Access the app**:
   Open your browser to `http://localhost:8501`

## Project Structure

```
UI/
├── app.py                 # Main Streamlit application
├── rag_backend.py         # RAG integration and response generation
├── utils.py              # Utility functions
├── requirements.txt      # Python dependencies
├── README.md            # This file
└── images/              # Brand assets and images
    ├── Logo.png
    └── [other images]
```

## Key Components

### 1. Main Application (`app.py`)
- Streamlit interface with custom CSS styling
- Session state management
- Chat interface with message history
- Landing page with quick start options
- Sidebar with session tracking
- Modal dialogs for checklists and feedback

### 2. RAG Backend (`rag_backend.py`)
- Response generation based on user queries
- Source attribution and metadata extraction
- Checklist generation from conversation context
- Program eligibility and context extraction

### 3. Utilities (`utils.py`)
- Helper functions for text processing
- Input validation and sanitization
- Formatting utilities
- Program categorization

## Design System

### Color Palette
- **Primary**: #4A90A4 (Teal/Blue-Green) - Trust, calm, government
- **Secondary**: #F4A261 (Warm Orange) - Friendly, accessible
- **Background**: #FAFAFA (Off-white)
- **Text**: #2D3436 (Dark gray) - Readability
- **Success**: #2ECC71 (Green)
- **Warning**: #F39C12 (Amber)
- **Error**: #E74C3C (Soft Red)

### Typography
- **Headers**: Inter (clean, modern, accessible)
- **Body**: System fonts for fast loading
- **Size**: Minimum 16px for body (mobile accessibility)

## User Flow

1. **Landing Page**: Welcome screen with quick start cards
2. **Chat Interface**: Conversational interaction with the AI
3. **Context Tracking**: Programs and information tracked in sidebar
4. **Checklist Generation**: Personalized action plans
5. **Source Transparency**: All information linked to official sources

## Integration Points

### RAG System Integration
The application is designed to integrate with your existing RAG pipeline:

1. **Vector Database**: Connect to your ChromaDB or similar vector store
2. **Document Retrieval**: Query relevant benefit documents
3. **LLM Integration**: Use OpenAI or other LLM for response generation
4. **Source Attribution**: Link responses to official government sources

### Backend Integration
- Replace mock responses in `rag_backend.py` with actual API calls
- Connect to your document indexing pipeline
- Integrate with your vector database
- Add authentication if needed

## Customization

### Adding New Programs
1. Update `SAMPLE_RESPONSES` in `rag_backend.py`
2. Add program icons in `utils.py`
3. Update quick reply suggestions
4. Add to program categorization

### Styling Changes
1. Modify CSS in `app.py` (st.markdown with custom styles)
2. Update color variables in `:root` section
3. Adjust responsive breakpoints as needed

### Adding Features
1. **Email Integration**: Add email functionality for checklists
2. **PDF Generation**: Implement PDF download for checklists
3. **User Accounts**: Add authentication and user profiles
4. **Analytics**: Track user interactions and popular queries

## Development

### Running in Development Mode
```bash
streamlit run app.py --server.runOnSave true
```

### Testing
- Test on mobile devices for responsive design
- Verify accessibility with screen readers
- Test with different benefit scenarios
- Validate source links and information accuracy

### Deployment
- Deploy to Streamlit Cloud, Heroku, or similar platform
- Set up environment variables for API keys
- Configure domain and SSL certificates
- Set up monitoring and analytics

## Privacy & Security

- **Session-Based**: No permanent data storage
- **No PII**: Personal information not collected or stored
- **Secure**: All communications over HTTPS
- **Transparent**: Clear privacy notices and data handling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Add your license information here]

## Support

For questions or issues:
- Create an issue in the repository
- Contact the development team
- Check the documentation

## Roadmap

- [ ] Integration with real RAG pipeline
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Mobile app version
- [ ] Integration with county systems
- [ ] Real-time benefit status checking

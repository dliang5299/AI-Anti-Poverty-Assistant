# BenefitsFlow Setup Guide

This guide will help you set up and run the BenefitsFlow application.

## Quick Start

### Option 1: Simple Python Setup (Recommended for Development)

1. **Navigate to the UI directory**:
   ```bash
   cd UI
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python run.py
   ```

4. **Open your browser** to `http://localhost:8501`

### Option 2: Docker Setup (Recommended for Production)

1. **Build and run with Docker Compose**:
   ```bash
   cd UI
   docker-compose up --build
   ```

2. **Access the application** at `http://localhost:8501`

## Detailed Setup Instructions

### Prerequisites

- Python 3.9 or higher
- pip (Python package installer)
- Git (for cloning the repository)

### Step 1: Clone the Repository

```bash
git clone <your-repository-url>
cd AI-Anti-Poverty-Assistant/UI
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the UI directory:

```bash
# Optional: OpenAI API Key for enhanced responses
OPENAI_API_KEY=your-openai-api-key-here

# Optional: Vector database configuration
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Optional: Streamlit configuration
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=localhost
```

### Step 5: Run the Application

```bash
# Option 1: Use the run script (recommended)
python run.py

# Option 2: Run directly with Streamlit
streamlit run app.py
```

### Step 6: Access the Application

Open your web browser and navigate to:
- **Local**: `http://localhost:8501`
- **Network**: `http://your-ip-address:8501`

## Integration with Your RAG Pipeline

### Current Status

The application currently uses mock responses for demonstration purposes. To integrate with your existing RAG pipeline:

### Step 1: Update RAG Backend

Edit `rag_backend.py` and replace the mock `get_rag_response` function with calls to your existing modules:

```python
# Import your existing modules
from src.03_rag_query import query_rag_system
from src.02_index_docs import get_vector_store

def get_rag_response(prompt: str, conversation_history: List[Dict], user_context: Dict):
    """
    Real RAG integration with your existing pipeline
    """
    try:
        # 1. Prepare query with conversation context
        context = " ".join([msg["content"] for msg in conversation_history[-5:]])
        full_query = f"Context: {context}\n\nQuery: {prompt}"
        
        # 2. Query your vector database
        results = query_rag_system(full_query, top_k=5)
        
        # 3. Generate response using your LLM
        response_text = generate_llm_response(prompt, results, user_context)
        
        # 4. Extract sources and metadata
        sources = extract_sources_from_results(results)
        programs = extract_programs_from_response(response_text)
        
        return response_text, sources, programs
        
    except Exception as e:
        # Fallback to mock responses if RAG system is unavailable
        return get_mock_response(prompt)
```

### Step 2: Configure Vector Database

Update the configuration in `config.py`:

```python
# Vector Database Configuration
CHROMA_PERSIST_DIRECTORY = "./chroma_db"  # Path to your vector database
CHROMA_COLLECTION_NAME = "california_benefits"  # Your collection name
```

### Step 3: Test Integration

Run the demo integration script to test your setup:

```bash
python demo_integration.py
```

## Deployment Options

### Option 1: Streamlit Cloud (Easiest)

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Deploy with one click

### Option 2: Heroku

1. Create a `Procfile`:
   ```
   web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
   ```

2. Deploy:
   ```bash
   git add .
   git commit -m "Deploy BenefitsFlow"
   git push heroku main
   ```

### Option 3: Docker

1. Build the Docker image:
   ```bash
   docker build -t benefitsflow .
   ```

2. Run the container:
   ```bash
   docker run -p 8501:8501 benefitsflow
   ```

### Option 4: Docker Compose (Recommended for Production)

```bash
# Start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

## Customization

### Adding New Programs

1. Update `SAMPLE_RESPONSES` in `rag_backend.py`
2. Add program icons in `utils.py`
3. Update quick reply suggestions
4. Add to program categorization

### Changing Colors and Branding

Edit the CSS variables in `app.py`:

```css
:root {
    --primary-color: #4A90A4;      /* Your primary color */
    --secondary-color: #F4A261;    /* Your secondary color */
    --bg-color: #FAFAFA;           /* Background color */
    --text-color: #2D3436;         /* Text color */
}
```

### Adding Features

1. **Email Integration**: Add email functionality for checklists
2. **PDF Generation**: Implement PDF download for checklists
3. **User Accounts**: Add authentication and user profiles
4. **Analytics**: Track user interactions and popular queries

## Troubleshooting

### Common Issues

1. **Port already in use**:
   ```bash
   # Kill process using port 8501
   lsof -ti:8501 | xargs kill -9
   ```

2. **Dependencies not installing**:
   ```bash
   # Upgrade pip
   pip install --upgrade pip
   
   # Install with verbose output
   pip install -r requirements.txt -v
   ```

3. **Streamlit not starting**:
   ```bash
   # Check Streamlit installation
   streamlit --version
   
   # Run with debug mode
   streamlit run app.py --logger.level=debug
   ```

4. **Docker build failing**:
   ```bash
   # Clean Docker cache
   docker system prune -a
   
   # Build with no cache
   docker build --no-cache -t benefitsflow .
   ```

### Getting Help

1. Check the logs in the terminal
2. Verify all dependencies are installed
3. Ensure you're in the correct directory
4. Check that port 8501 is available
5. Review the configuration files

## Performance Optimization

### For Development

- Use `streamlit run app.py --server.runOnSave true` for auto-reload
- Enable caching for expensive operations
- Use `st.cache_data` for data loading

### For Production

- Use Docker for consistent deployment
- Set up reverse proxy (nginx) for SSL and load balancing
- Monitor memory usage and scale as needed
- Use CDN for static assets

## Security Considerations

- Never commit API keys to version control
- Use environment variables for sensitive data
- Enable HTTPS in production
- Regularly update dependencies
- Monitor for security vulnerabilities

## Next Steps

1. **Integrate with your RAG pipeline** using the demo integration script
2. **Customize the branding** and colors to match your design
3. **Add your specific programs** and responses
4. **Deploy to your preferred platform**
5. **Monitor usage** and gather feedback
6. **Iterate and improve** based on user needs

## Support

For questions or issues:
- Check the troubleshooting section above
- Review the code comments and documentation
- Create an issue in the repository
- Contact the development team

---

**Happy coding! 🌍**

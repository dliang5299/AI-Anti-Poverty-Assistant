# Run BenefitsFlow Locally

## Quick Start (Easiest)

```bash
cd UI
python start_app.py
```

This will:
1. Install dependencies automatically
2. Start FastAPI backend on port 8000
3. Open your browser to http://localhost:8000

**Press Ctrl+C to stop**

**Note:** Make sure you have Python 3.7+ installed. The script will automatically install required packages.

---

## Manual Start (Alternative)

### Step 1: Install Dependencies

```bash
cd UI
pip install -r requirements_ui.txt
```

### Step 2: Run FastAPI Backend

```bash
python fastapi_backend.py
```

Or using uvicorn directly:

```bash
uvicorn fastapi_backend:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag auto-restarts when you change code files (useful for development).

### Step 3: Open Browser

Visit: **http://localhost:8000**

---

## Test Features

### 1. Chat Interface
- Type a message like "I lost my job, what benefits can I get?"
- See AI responses with sources

### 2. Checklist Download
- Start a conversation
- Click the checklist button (📋)
- Click "Download Text File"
- Verify `.txt` file downloads with formatted checklist

### 3. Calendar Download
- Click calendar button (📅)
- Downloads `.ics` file you can import to calendar apps

---

## Troubleshooting

**Port 8000 already in use?**
```bash
# Find what's using port 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # Mac/Linux

# Or use a different port
uvicorn fastapi_backend:app --port 8001
# Then visit: http://localhost:8001
```

**Dependencies not installing?**
```bash
pip install --upgrade pip
pip install -r requirements_ui.txt
```

**Module not found errors?**
- Make sure you're in the `UI` directory
- Check that `rag_backend.py` and `utils.py` are present in the UI folder
- Verify `fastapi_backend.py`, `benefitsflow_frontend.html` exist
- Make sure all dependencies installed: `pip install -r requirements_ui.txt`

**"Failed to load resource" or 422 errors?**
- Restart the FastAPI backend (stop with Ctrl+C and run `python start_app.py` again)
- Clear browser cache or try incognito/private mode
- Check that the backend is running: visit http://localhost:8000/api/health

---

## Development Tips

**Auto-reload on file changes:**
```bash
uvicorn fastapi_backend:app --reload
```

**Check API endpoints:**
- Visit: http://localhost:8000/api/docs (Interactive API docs)
- Visit: http://localhost:8000/api/health (Health check)

**View logs:**
- FastAPI will show request logs in the terminal
- Check browser console (F12) for frontend errors

# UI Folder Structure for Updates

## Current Structure on EC2 (After Initial Deployment)

```
/home/ec2-user/
└── AI-Anti-Poverty-Assistant/
    └── UI/
        ├── Dockerfile                    # Container build config
        ├── requirements_ui.txt            # Python dependencies
        │
        ├── fastapi_backend.py            # ⚠️ Main API backend
        ├── rag_backend.py                 # ⚠️ RAG integration (demo)
        ├── utils.py                       # ⚠️ Utility functions
        │
        ├── benefitsflow_frontend.html     # ⚠️ Main HTML frontend
        ├── benefitsflow_architecture_improved_flow.html
        │
        ├── images/                        # ⚠️ Static assets
        │   ├── Logo.png
        │   ├── BenefitFlow Logo text.png
        │   └── ... (other images)
        │
        └── [deployment docs]              # Documentation (not needed in container)
            ├── DEPLOY_EC2_STEP_BY_STEP.md
            ├── AUTO_STOP_SETUP.md
            └── ...
```

## Files That Affect Deployment (Need Update)

### 🔴 Critical - Must Update Container:
1. **`fastapi_backend.py`** - API logic, endpoints
2. **`benefitsflow_frontend.html`** - Frontend UI
3. **`rag_backend.py`** - RAG integration (when connecting to teammate)
4. **`utils.py`** - Helper functions
5. **`requirements_ui.txt`** - If adding new Python packages
6. **`images/`** - If adding/changing images

### 🟡 Sometimes Updated:
- **`Dockerfile`** - Only if changing build process
- **`Dockerfile` dependencies** - If changing Python version, base image

### 🟢 Never Need to Update:
- Documentation files (`.md` files)
- Scripts that run on EC2 (not in container)

---

## Update Process Flow

### When You Change Code Locally:

```
Your Local Machine:
├── UI/
│   ├── fastapi_backend.py    ← Edit this
│   └── benefitsflow_frontend.html  ← Edit this
│
└── git push                    ← Push to GitHub
```

### On EC2 (Update Steps):

```
SSH into EC2:
cd AI-Anti-Poverty-Assistant
git pull                         ← Pull latest from GitHub
cd UI
docker stop benefitsflow        ← Stop current container
docker rm benefitsflow          ← Remove old container
docker build -t benefitsflow-ui .  ← Rebuild with new code
docker run -d -p 8000:8000 --name benefitsflow --restart unless-stopped benefitsflow-ui
```

---

## What Gets Copied Into Docker Container

**From `Dockerfile`:**
```dockerfile
COPY requirements_ui.txt .        # Dependencies
COPY . .                         # ALL files in UI/ folder
```

**So these files are in the container:**
- ✅ `fastapi_backend.py`
- ✅ `benefitsflow_frontend.html`
- ✅ `rag_backend.py`
- ✅ `utils.py`
- ✅ `images/` folder
- ✅ `requirements_ui.txt`
- ❌ Documentation `.md` files (not needed at runtime)

---

## Example Update Scenarios

### Scenario 1: Change Frontend HTML
```bash
# 1. Edit locally: benefitsflow_frontend.html
# 2. Push: git push
# 3. On EC2:
cd AI-Anti-Poverty-Assistant && git pull
cd UI
docker stop benefitsflow && docker rm benefitsflow
docker build -t benefitsflow-ui .
docker run -d -p 8000:8000 --name benefitsflow --restart unless-stopped benefitsflow-ui
```

### Scenario 2: Change API Backend
```bash
# 1. Edit locally: fastapi_backend.py
# 2. Push: git push
# 3. On EC2: (same steps as above)
```

### Scenario 3: Connect to Teammate's RAG
```bash
# 1. Edit locally: fastapi_backend.py (add RAG endpoint call)
# 2. Edit locally: requirements_ui.txt (if adding boto3, httpx, etc.)
# 3. Push: git push
# 4. On EC2: (rebuild container with new code)
```

### Scenario 4: Add New Image
```bash
# 1. Add image to UI/images/
# 2. Update HTML to reference it
# 3. Push: git push
# 4. On EC2: (rebuild container - images folder is copied)
```

---

## Quick Reference: Update Commands

**One-liner update script (on EC2):**
```bash
cd AI-Anti-Poverty-Assistant && git pull && cd UI && \
docker stop benefitsflow && docker rm benefitsflow && \
docker build -t benefitsflow-ui . && \
docker run -d -p 8000:8000 --name benefitsflow --restart unless-stopped benefitsflow-ui
```

**Or save as script:**
```bash
# Create update script on EC2
cat > ~/update-benefitsflow.sh << 'EOF'
#!/bin/bash
cd ~/AI-Anti-Poverty-Assistant
git pull
cd UI
docker stop benefitsflow 2>/dev/null
docker rm benefitsflow 2>/dev/null
docker build -t benefitsflow-ui .
docker run -d -p 8000:8000 --name benefitsflow --restart unless-stopped benefitsflow-ui
echo "✅ BenefitsFlow updated!"
EOF

chmod +x ~/update-benefitsflow.sh

# Then just run:
~/update-benefitsflow.sh
```

---

## File Dependencies Map

```
fastapi_backend.py
    ├── imports: rag_backend.py
    ├── imports: utils.py
    └── serves: benefitsflow_frontend.html (via / endpoint)

benefitsflow_frontend.html
    ├── calls: /api/* endpoints
    └── loads: /images/* assets

Dockerfile
    ├── uses: requirements_ui.txt
    └── copies: all files (COPY . .)
```

---

## Summary

**What to update:**
- Code files (`.py`, `.html`)
- Images in `images/` folder
- Dependencies in `requirements_ui.txt`

**How to update:**
1. Edit locally → `git push`
2. On EC2: `git pull` → rebuild container

**What stays the same:**
- Docker setup (one-time)
- EC2 instance config (one-time)
- Auto-stop schedule (one-time, unless you change it)

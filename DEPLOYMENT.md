# Deployment Guide - Single EC2 Instance

## Prerequisites

- EC2 instance running (Ubuntu/Amazon Linux)
- Docker and docker-compose installed
- AWS credentials configured (IAM role or ~/.aws/credentials)
- Security group allows:
  - Port 80 (HTTP - Nginx reverse proxy)
  - Port 8501 (UI service - optional, for direct access)
  - Port 8000 (RAG service - optional, for testing)

## Quick Setup (One-Time)

### 1. Create docker.env on EC2

```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Navigate to project
cd ~/AI-Anti-Poverty-Assistant

# Create docker.env with your ARNs
cp docker.env.template docker.env
nano docker.env  # Add your actual ARNs
```

### 2. Set Up Auto-Start (One-Time Setup)

```bash
# Make startup script executable
chmod +x startup.sh

# Option A: Use systemd service (recommended)
sudo cp benefitsflow.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable benefitsflow.service
sudo systemctl start benefitsflow.service

# Option B: Add to EC2 user-data (for new instances)
# Copy startup.sh content to EC2 Launch Template user-data
```

### 3. Done! 

Your app will now:
- ✅ Start automatically when instance boots
- ✅ Restart automatically if containers crash
- ✅ Be accessible at: `http://YOUR_EC2_IP` or `http://benefitsflow.org` (no port needed!)

## Manual Deployment (If Not Using Auto-Start)

### 1. Clone/Update Repository on EC2

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Navigate to your project directory
cd ~/AI-Anti-Poverty-Assistant

# Pull latest code (if using git)
git pull origin main
```

### 2. Create docker.env File

```bash
# Copy the template
cp docker.env.template docker.env

# Edit with your actual ARNs
nano docker.env
# or
vi docker.env
```

**Required in docker.env:**
```bash
# AWS Secrets Manager ARNs (REQUIRED - get these from AWS Console)
OPENAI_API_KEY_SECRET_ARN=arn:aws:secretsmanager:us-west-2:YOUR_ACCOUNT_ID:secret:benefitsflow/openai-XXXXXX
PINECONE_API_KEY_SECRET_ARN=arn:aws:secretsmanager:us-west-2:YOUR_ACCOUNT_ID:secret:benefitsflow/pinecone-XXXXXX

# Regions
S3_REGION=us-west-2
PINECONE_REGION=us-east-1
PINECONE_ENV=aws-us-east-1
BEDROCK_REGION=us-east-1

# Pinecone Configuration
PINECONE_INDEX_NAME=benefitsflow  # or "knowledge" if that's your index name
PINECONE_DIM=1536

# Model Configuration
EMBED_MODEL=text-embedding-3-small
LLM_MODEL=openai.gpt-oss-120b-1:0

# DO NOT set RAG_API_URL - it will default to http://app:8000 automatically
```

### 3. Verify docker.env

```bash
# Check that docker.env exists and has values (don't show full content for security)
cat docker.env | grep -E "^[A-Z_]+=" | head -5
```

### 4. Build and Start Services

```bash
# Build and start both services
docker-compose up --build -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 5. Test Services

```bash
# Test RAG service
curl http://localhost:8000/health

# Test UI service
curl http://localhost:8501/health

# Test UI → RAG connection
curl http://localhost:8501/health/rag
```

### 6. Access the Application

- **UI Frontend**: `http://YOUR_EC2_IP` or `http://benefitsflow.org` (via Nginx on port 80)
- **UI Direct**: `http://YOUR_EC2_IP:8501` (optional, direct access)
- **API Docs**: `http://YOUR_EC2_IP/api/docs` or `http://benefitsflow.org/api/docs`
- **RAG Health**: `http://YOUR_EC2_IP:8000/health` (optional)

## Useful Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app    # RAG service
docker-compose logs -f ui     # UI service
docker-compose logs -f nginx  # Nginx reverse proxy
```

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Rebuild After Code Changes
```bash
docker-compose up --build -d
```

### Check Container Status
```bash
docker-compose ps
docker ps
```

## Troubleshooting

### Services won't start
```bash
# Check logs
docker-compose logs

# Check if ports are in use
sudo netstat -tulpn | grep -E '8000|8501'
```

### UI can't connect to RAG
```bash
# Check if RAG service is running
docker-compose ps app

# Check RAG logs
docker-compose logs app

# Test connection from UI container
docker-compose exec ui curl http://app:8000/health
```

### ARN errors
```bash
# Verify docker.env is being read
docker-compose config | grep OPENAI_API_KEY_SECRET_ARN

# Check AWS credentials
aws sts get-caller-identity
```

## Security Group Rules

Ensure your EC2 security group allows:
- **Inbound Port 80** (HTTP - Nginx reverse proxy) - from 0.0.0.0/0 for public access
- **Inbound Port 8501** (UI service) - optional, only if you want direct access
- **Inbound Port 8000** (RAG service) - optional, only if you want direct access
- **Outbound** - All traffic (for AWS API calls)

## Elastic IP (Recommended)

To keep a fixed IP address:
1. Allocate Elastic IP in AWS Console
2. Associate with your EC2 instance
3. Update your demo URL to use the Elastic IP

Cost: $0 when instance is running, ~$3.60/month when stopped.


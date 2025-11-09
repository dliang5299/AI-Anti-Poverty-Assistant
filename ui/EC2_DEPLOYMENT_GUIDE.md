# EC2 Deployment Guide - BenefitsFlow

Complete step-by-step guide for deploying BenefitsFlow to AWS EC2 following the two-instance architecture.

## Quick Reference

**Instance 1 (UI/API):**
- Port: **8501**
- Dockerfile: `Dockerfile.ui`
- Command: `docker build -f Dockerfile.ui -t benefitsflow-ui-api .`
- Runs: `UI.serve_frontend:app`
- Access: http://[INSTANCE-1-IP]:8501

**Instance 2 (RAG):**
- Port: **8000**
- Dockerfile: `Dockerfile.api`
- Command: `docker build -f Dockerfile.api -t benefitsflow-rag .`
- Runs: `app.RAG_service:app`
- Needs: IAM role with Bedrock permissions, Secrets Manager ARNs

**Connection:**
- Instance 1 → Instance 2: `RAG_SERVICE_URL=http://[INSTANCE-2-PRIVATE-IP]:8000` in `.env`

**Services Used:**
- AWS Bedrock (LLM)
- Pinecone (Vector DB)
- OpenAI (Embeddings)
- AWS Secrets Manager (API keys)

---

## Architecture Overview

```
┌───────────────────── AWS VPC ─────────────────────┐
│                                                   │
│  ┌─── EC2 Instance 1 ───┐        ┌─── EC2 Instance 2 ───┐
│  │  UI/API Server       │        │  RAG Server            │
│  │  • FastAPI Backend   │        │  • RAG Service        │
│  │  • HTML Frontend     │        │  • Vector DB Client    │
│  └──────────────────────┘        └──────────────────────┘
│           │                            │
│           └───── API calls ────────────┘
│
└───────────────────────────────────────────────────┘
                │                    │
                ▼                    ▼
     ┌──── AWS Bedrock ────┐  ┌──── Pinecone ─────┐
     │ LLM (OpenAI/Claude) │  │ Vector database    │
     └─────────────────────┘  └───────────────────┘
```

## Prerequisites

- AWS account with EC2 access
- Two EC2 instances (t2.micro or larger)
- Security groups configured
- IAM roles for Bedrock access
- Pinecone account and API key

---

## Step 1: Launch EC2 Instances

### Instance 1: UI/API Server

**Specifications:**
- Instance type: t2.micro (or t3.small for better performance)
- AMI: Amazon Linux 2023
- Security Group: Allow ports 22 (SSH), 8000 (HTTP)
- IAM Role: Attach role with Bedrock permissions (optional, if Instance 1 needs direct access)

**Current Status:**
- ✅ Instance launched: `34.229.193.254`
- ✅ Docker installed
- ✅ Git installed
- ✅ Repository cloned

### Instance 2: RAG Server

**Specifications:**
- Instance type: t2.micro (or t3.small for better performance)
- AMI: Amazon Linux 2023
- Security Group: Allow ports 22 (SSH), 8000 (HTTP)
- IAM Role: **Required** - Attach role with:
  - Bedrock: `InvokeModel`, `InvokeModelWithResponseStream`
  - S3: `GetObject`, `ListBucket` (if using S3 for documents)
  - Secrets Manager: `GetSecretValue` (if using Secrets Manager)

**Launch Steps:**
```bash
# In AWS Console:
# 1. EC2 → Launch Instance
# 2. Name: benefitsflow-rag
# 3. Select Amazon Linux 2023 AMI
# 4. Instance type: t2.micro
# 5. Key pair: Select your key pair
# 6. Network: Same VPC as Instance 1
# 7. Security group: Same as Instance 1 (or create new with port 8000)
# 8. IAM role: Select role with Bedrock permissions
# 9. Launch instance
```

---

## Step 2: Setup Instance 1 (UI/API Server)

### SSH into Instance 1

```bash
ssh -i your-key.pem ec2-user@34.229.193.254
```

### Verify Setup

```bash
# Check Docker
docker --version
# Should show: Docker version 25.0.13 or similar

# Check Git
git --version
# Should show: git version 2.50.1 or similar

# Check repository
cd AI-Anti-Poverty-Assistant
ls -la
```

### Build and Run UI/API Container

```bash
# Navigate to project root (NOT UI directory - Dockerfile.ui builds from root)
cd AI-Anti-Poverty-Assistant

# Check if Dockerfile.ui exists
ls -la Dockerfile.ui

# Note: You'll need Instance 2's private IP first
# Get it from AWS Console → EC2 → Instance 2 → Private IPv4 address
# Example: 172.31.45.123

# Create .env file in project root with Instance 2's private IP
echo "RAG_SERVICE_URL=http://[INSTANCE-2-PRIVATE-IP]:8000" > .env
# Replace [INSTANCE-2-PRIVATE-IP] with actual IP, e.g.:
# echo "RAG_SERVICE_URL=http://172.31.45.123:8000" > .env

# Build Docker image using Dockerfile.ui (builds from project root)
docker build -f Dockerfile.ui -t benefitsflow-ui-api .

# Run container (exposes port 8501, not 8000)
docker run -d \
  -p 8501:8501 \
  --name benefitsflow \
  --env-file .env \
  --restart unless-stopped \
  benefitsflow-ui-api

# Check if container is running
docker ps

# Check logs
docker logs benefitsflow

# Follow logs in real-time
docker logs -f benefitsflow
```

### Verify Instance 1 is Working

```bash
# Test from within Instance 1 (port 8501, not 8000)
curl http://localhost:8501/api/health

# Should return: {"status":"healthy",...}

# Test frontend
curl http://localhost:8501/

# Should return HTML content
```

---

## Step 3: Setup Instance 2 (RAG Server)

### SSH into Instance 2

```bash
# Get public IP from AWS Console
ssh -i your-key.pem ec2-user@[INSTANCE-2-PUBLIC-IP]
```

### Install Docker and Git

```bash
# Update system
sudo yum update -y

# Install Docker
sudo yum install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Install Git
sudo yum install git -y

# Install Docker Compose (optional, but recommended)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in for docker group to take effect
exit
# Then reconnect via SSH
```

### Clone Repository and Setup

```bash
# Clone repository
git clone https://github.com/dliang5299/AI-Anti-Poverty-Assistant.git
cd AI-Anti-Poverty-Assistant
```

### Configure Environment Variables

Create `.env` file in project root:

```bash
nano .env
```

**Add these variables:**

```env
# Regions
S3_REGION=us-west-2
BEDROCK_REGION=us-west-2
PINECONE_REGION=us-east-1
PINECONE_ENV=aws-us-east-1

# Models
EMBED_MODEL=text-embedding-3-small
LLM_MODEL=openai.gpt-oss-120b-1:0

# Pinecone Index
PINECONE_INDEX_NAME=knowledge
PINECONE_DIM=1536

# API Keys - Use Secrets Manager ARNs for production (recommended)
# Option 1: AWS Secrets Manager (Production - Recommended)
OPENAI_API_KEY_SECRET_ARN=arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:benefitsflow/openai-api-key-XXXXXX
PINECONE_API_KEY_SECRET_ARN=arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:benefitsflow/pinecone-api-key-XXXXXX

# Option 2: Direct API keys (Development only - NOT recommended for production)
# OPENAI_API_KEY=sk-...
# PINECONE_API_KEY=pc-...
```

**Important:** 
- For production, use Secrets Manager ARNs (Option 1)
- The IAM role on Instance 2 will automatically fetch secrets
- Never commit `.env` with actual API keys to Git

**Save and exit:** `Ctrl+X`, then `Y`, then `Enter`

### Build and Run RAG Container

**Option A: Using Docker Compose (Recommended for local testing)**

```bash
# From project root
# Note: This runs both UI and RAG together - use for local testing only
docker-compose up -d --build

# Check logs
docker-compose logs -f api
```

**Option B: Using Docker directly (For EC2 deployment)**

```bash
# From project root
# Build RAG service using Dockerfile.api
docker build -f Dockerfile.api -t benefitsflow-rag .

# Run container
docker run -d \
  -p 8000:8000 \
  --name rag-service \
  --env-file .env \
  --restart unless-stopped \
  benefitsflow-rag

# Check logs
docker logs rag-service

# Follow logs in real-time
docker logs -f rag-service
```

### Verify Instance 2 is Working

```bash
# Test RAG service health
curl http://localhost:8000/health

# Should return: {"service":"ok","regions":{...},"model":"..."}
```

---

## Step 4: Connect Instance 1 to Instance 2

### Get Instance 2's Private IP

```bash
# On Instance 2, get private IP
hostname -I
# Or check AWS Console → EC2 → Instance 2 → Private IPv4 address
```

### Update Instance 1 Configuration

```bash
# SSH into Instance 1
ssh -i your-key.pem ec2-user@34.229.193.254

# Navigate to project root (NOT UI directory)
cd AI-Anti-Poverty-Assistant

# Update .env file with Instance 2's private IP
nano .env
# Update RAG_SERVICE_URL=http://[INSTANCE-2-PRIVATE-IP]:8000
# Example: RAG_SERVICE_URL=http://172.31.45.123:8000

# Restart container with updated environment
docker stop benefitsflow
docker rm benefitsflow
docker run -d \
  -p 8501:8501 \
  --name benefitsflow \
  --env-file .env \
  --restart unless-stopped \
  benefitsflow-ui-api

# Check logs
docker logs -f benefitsflow
```

### Test Connection

```bash
# On Instance 1, test connection to Instance 2
curl http://[INSTANCE-2-PRIVATE-IP]:8000/health

# Should return RAG service health check
```

---

## Step 5: Configure IAM Roles

### Create IAM Role for Instance 2

**In AWS Console:**

1. **IAM → Roles → Create Role**
2. **Trusted entity:** EC2
3. **Permissions:** Create new policy or attach existing:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-west-2::foundation-model/openai.gpt-oss-120b-1:0",
        "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::benefitsflow-data",
        "arn:aws:s3:::benefitsflow-data/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-west-2:*:secret:benefitsflow/*"
      ]
    }
  ]
}
```

4. **Name:** `BenefitsFlow-RAG-Role`
5. **Attach to Instance 2:**
   - EC2 Console → Select Instance 2
   - Actions → Security → Modify IAM role
   - Select `BenefitsFlow-RAG-Role`

---

## Step 6: Configure Pinecone

### Create Pinecone Index

1. **Sign up:** https://app.pinecone.io/
2. **Create Index:**
   - Name: `knowledge`
   - Dimensions: `1536` (for OpenAI embeddings)
   - Metric: `cosine`
   - Type: `serverless`
   - Region: `us-east-1` (or `aws-us-east-1`)

3. **Get API Key:**
   - Go to API Keys section
   - Copy API key (starts with `pc-`)

### Add Pinecone Key to Instance 2

```bash
# On Instance 2
cd AI-Anti-Poverty-Assistant
nano .env

# Add or update:
PINECONE_API_KEY=pc-...
PINECONE_INDEX_NAME=knowledge
PINECONE_DIM=1536
PINECONE_ENV=aws-us-east-1

# Restart container
docker-compose restart api
# Or if using Docker directly:
docker restart rag-service
```

---

## Step 7: Configure Security Groups

### Allow Communication Between Instances

**Instance 1 Security Group:**
- Inbound: Port **8501** from your IP (for testing frontend)
- Inbound: Port 22 from your IP (for SSH)
- **Outbound:** Port 8000 to Instance 2's security group (for RAG API calls)

**Instance 2 Security Group:**
- Inbound: Port **8000** from Instance 1's security group (for RAG API calls)
- Inbound: Port 22 from your IP (for SSH)
- **Outbound:** All traffic (for Bedrock, Pinecone, OpenAI API calls)

**Steps:**
1. EC2 Console → Security Groups
2. Select Instance 1's security group
3. Edit inbound rules
4. Add rule: Type: Custom TCP, Port: 8000, Source: Instance 2's security group ID
5. Save rules

---

## Step 8: Test End-to-End

### Test from Your Local Machine

```bash
# Test Instance 1 (UI/API) - Note: port 8501, not 8000
curl http://34.229.193.254:8501/api/health

# Test Instance 2 (RAG) - if you opened port 8000 publicly
curl http://[INSTANCE-2-PUBLIC-IP]:8000/health

# Test full flow - send chat message
curl -X POST http://34.229.193.254:8501/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I lost my job, what benefits can I get?",
    "conversation_history": [],
    "situation": "unemployed"
  }'
```

### Test in Browser

1. **Open browser:** http://34.229.193.254:8501 (Note: port 8501, not 8000)
2. **Send a test message**
3. **Check logs on both instances:**

```bash
# Instance 1 logs (UI/API)
docker logs -f benefitsflow

# Instance 2 logs (RAG Service)
docker logs -f rag-service
```

---

## Step 9: Production Optimizations

### Use AWS Secrets Manager (Recommended for Production)

Instead of storing API keys in `.env` file, use AWS Secrets Manager:

1. **Create secrets in Secrets Manager:**

   **Using AWS Console:**
   - Go to AWS Secrets Manager → Store a new secret
   - Secret type: Other type of secret
   - Key/value: `OPENAI_API_KEY` = `sk-...`
   - Secret name: `benefitsflow/openai-api-key`
   - Repeat for Pinecone: `PINECONE_API_KEY` = `pc-...`, name: `benefitsflow/pinecone-api-key`

   **Using AWS CLI:**
   ```bash
   # Create OpenAI secret
   aws secretsmanager create-secret \
     --name benefitsflow/openai-api-key \
     --secret-string '{"OPENAI_API_KEY":"sk-..."}' \
     --region us-west-2
   
   # Create Pinecone secret
   aws secretsmanager create-secret \
     --name benefitsflow/pinecone-api-key \
     --secret-string '{"PINECONE_API_KEY":"pc-..."}' \
     --region us-west-2
   
   # Get ARNs (you'll need these)
   aws secretsmanager describe-secret \
     --secret-id benefitsflow/openai-api-key \
     --region us-west-2 \
     --query 'ARN' --output text
   ```

2. **Update `.env` on Instance 2 to use ARNs:**
   ```env
   # Remove plaintext keys, use ARNs instead
   OPENAI_API_KEY_SECRET_ARN=arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:benefitsflow/openai-api-key-XXXXXX
   PINECONE_API_KEY_SECRET_ARN=arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:benefitsflow/pinecone-api-key-XXXXXX
   ```

3. **Ensure IAM role has Secrets Manager permissions:**
   - The IAM role on Instance 2 needs `secretsmanager:GetSecretValue` permission
   - See Step 5 for IAM role setup

4. **Restart container:**
   ```bash
   docker restart rag-service
   ```

### Set Up Auto-Restart

Containers are already set with `--restart unless-stopped`, but you can also:

```bash
# Create systemd service (optional)
sudo nano /etc/systemd/system/benefitsflow.service
```

### Monitor Logs

```bash
# View logs
docker logs -f benefitsflow  # Instance 1
docker logs -f rag-service   # Instance 2

# Or use CloudWatch Logs (advanced)
```

---

## Troubleshooting

### Instance 1 can't connect to Instance 2

**Check:**
1. Security groups allow communication
2. Instance 2's private IP is correct
3. Instance 2's RAG service is running: `docker ps` on Instance 2
4. Test connection: `curl http://[INSTANCE-2-IP]:8000/health` from Instance 1

### RAG service errors

**Check:**
1. IAM role is attached to Instance 2
2. Bedrock permissions are correct
3. Pinecone API key is valid
4. Pinecone index exists and is named `knowledge`
5. Check logs: `docker logs rag-service`

### Bedrock access denied

**Fix:**
1. Verify IAM role has `bedrock:InvokeModel` permission
2. Check Bedrock model is available in us-west-2
3. Verify model ID is correct: `openai.gpt-oss-120b-1:0`

### Pinecone connection failed

**Fix:**
1. Verify API key is correct
2. Check index name matches: `knowledge`
3. Verify index dimension is 1536
4. Check Pinecone environment/region matches

---

## Next Steps

1. **Load data into Pinecone:**
   - Run ingestion script to create embeddings
   - Upload vectors to Pinecone index

2. **Set up domain name (optional):**
   - Use Route 53 or CloudFront
   - Point to Instance 1's public IP

3. **Set up HTTPS (optional):**
   - Use Application Load Balancer with SSL certificate
   - Or use CloudFront with SSL

4. **Monitor and scale:**
   - Set up CloudWatch alarms
   - Consider Auto Scaling Groups for high traffic

---

## Summary

✅ **Instance 1:** UI/API Server running on port **8501** (uses `Dockerfile.ui`, runs `UI.serve_frontend:app`)  
✅ **Instance 2:** RAG Server running on port **8000** (uses `Dockerfile.api`, runs `app.RAG_service:app`)  
✅ **Connection:** Instance 1 → Instance 2 via private IP (`RAG_SERVICE_URL` in `.env`)  
✅ **External Services:** AWS Bedrock (LLM) + Pinecone (Vector DB) + OpenAI (Embeddings)  
✅ **Access:** http://[INSTANCE-1-PUBLIC-IP]:8501

**Architecture:**
- **Instance 1:** FastAPI serves HTML frontend + API endpoints, calls RAG service on Instance 2
- **Instance 2:** RAG service uses Bedrock (LLM), OpenAI (embeddings), Pinecone (vector DB)
- **AWS Services:** Bedrock for LLM, Secrets Manager for API keys, IAM roles for permissions

Your BenefitsFlow application is now deployed and ready for testing! 🚀


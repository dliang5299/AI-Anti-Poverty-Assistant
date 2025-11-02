# AWS Deployment Guide for BenefitsFlow UI

This guide covers deploying your FastAPI backend + HTML frontend to AWS.

## Deployment Options

### Option 1: AWS Elastic Beanstalk (Easiest - Recommended)

**Best for:** Quick deployment, automatic scaling, zero-downtime updates

#### Steps:

1. **Install EB CLI** (if not already installed):
   ```bash
   pip install awsebcli
   ```

2. **Initialize Elastic Beanstalk** (in UI folder):
   ```bash
   cd UI
   eb init -p python-3.11 benefitsflow-ui --region us-west-2
   ```

3. **Create application and environment**:
   ```bash
   eb create benefitsflow-prod
   ```

4. **Deploy**:
   ```bash
   eb deploy
   ```

5. **Open your app**:
   ```bash
   eb open
   ```

Elastic Beanstalk will:
- Automatically build your Dockerfile
- Handle load balancing
- Set up auto-scaling
- Provide a URL like: `benefitsflow-prod.elasticbeanstalk.com`

---

### Option 2: AWS ECS/Fargate (Production-Ready)

**Best for:** Production deployments with Docker containers

#### Steps:

1. **Build and push Docker image to ECR**:
   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com
   
   # Create ECR repository
   aws ecr create-repository --repository-name benefitsflow-ui --region us-west-2
   
   # Build and tag image
   cd UI
   docker build -t benefitsflow-ui .
   docker tag benefitsflow-ui:latest <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/benefitsflow-ui:latest
   
   # Push to ECR
   docker push <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/benefitsflow-ui:latest
   ```

2. **Create Task Definition** (via AWS Console or CLI):
   - Go to ECS → Task Definitions → Create
   - Container name: `benefitsflow-ui`
   - Image: `<ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/benefitsflow-ui:latest`
   - Port mappings: `8000:8000`
   - Memory: 512 MB
   - CPU: 256 (.25 vCPU)

3. **Create ECS Service**:
   - Use Fargate launch type
   - Configure Application Load Balancer
   - Set desired tasks: 1-2

---

### Option 3: EC2 Instance (Simple but Manual)

**Best for:** Testing or simple single-instance deployment

#### Steps:

1. **Launch EC2 instance**:
   - AMI: Amazon Linux 2023 or Ubuntu 22.04
   - Instance type: t3.small or t3.medium
   - Security group: Allow HTTP (80), HTTPS (443), and port 8000

2. **SSH into instance and setup**:
   ```bash
   # Install Docker
   sudo yum update -y
   sudo yum install -y docker
   sudo systemctl start docker
   sudo usermod -aG docker ec2-user
   
   # Install git
   sudo yum install -y git
   
   # Clone your repo
   git clone https://github.com/dliang5299/AI-Anti-Poverty-Assistant.git
   cd AI-Anti-Poverty-Assistant/UI
   
   # Build and run
   docker build -t benefitsflow-ui .
   docker run -d -p 8000:8000 --name benefitsflow benefitsflow-ui
   ```

3. **Set up Nginx reverse proxy** (optional, for port 80):
   ```bash
   sudo yum install -y nginx
   # Configure nginx to proxy port 8000
   ```

---

## Environment Variables (if needed)

If you need to configure your app for AWS:

1. **For Elastic Beanstalk**: Set in EB console → Configuration → Software
2. **For ECS**: Add to Task Definition → Environment variables
3. **For EC2**: Export in shell or use `/etc/environment`

Common variables:
```bash
API_BASE_URL=http://localhost:8000/api  # For production, use your domain
```

---

## Connecting to RAG Backend

When your teammate's RAG system is ready:

1. **Update `fastapi_backend.py`**:
   ```python
   # Replace the import:
   from rag_backend import get_rag_response  # Current (demo)
   # With either:
   # Option A: Direct import if in same container
   from deric_rag_system import get_rag_response
   
   # Option B: HTTP call if separate service
   # Inside chat_endpoint():
   import httpx
   async with httpx.AsyncClient() as client:
       rag_response = await client.post(
           "http://rag-service-url:8001/query",
           json={"query": request.message, ...}
       )
   ```

2. **Deploy again** with updated code

---

## Quick Test (Local → AWS)

Before deploying, test locally:
```bash
cd UI
docker build -t benefitsflow-ui .
docker run -p 8000:8000 benefitsflow-ui
# Visit http://localhost:8000
```

---

## Production Considerations

- **HTTPS/SSL**: Use AWS Certificate Manager (ACM) with ALB
- **Domain**: Route 53 for custom domain
- **Monitoring**: CloudWatch for logs and metrics
- **Auto-scaling**: Configure based on CPU/memory usage
- **Security**: Use security groups, IAM roles, and secrets management

---

## Cost Estimates (Approximate)

- **Elastic Beanstalk**: Free tier (750 hours/month), then ~$15-30/month
- **ECS Fargate**: ~$15-30/month (512MB, minimal traffic)
- **EC2**: ~$7-15/month (t3.small on-demand)

---

## Troubleshooting

- **Check logs**: 
  - EB: `eb logs`
  - ECS: CloudWatch Logs
  - EC2: `docker logs benefitsflow`
  
- **Port issues**: Ensure security groups allow port 8000 (or 80/443 if using ALB)
- **CORS errors**: Update `allow_origins` in `fastapi_backend.py` to your domain

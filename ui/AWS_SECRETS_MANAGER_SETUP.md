# AWS Secrets Manager Setup for Production

This guide shows you how to store API keys in AWS Secrets Manager and deploy to EC2 using the shared AWS account.

---

## Step 1: Create Secrets in AWS Secrets Manager

### Option A: Using AWS Console

1. **Go to AWS Secrets Manager:**
   - AWS Console → Secrets Manager → Store a new secret

2. **Create OpenAI API Key Secret:**
   - Secret type: **Other type of secret**
   - Key/value: `OPENAI_API_KEY` = `sk-...` (your actual key)
   - Secret name: `benefitsflow/openai-api-key`
   - Description: "OpenAI API key for BenefitsFlow embeddings"
   - Click **Store**

3. **Create Pinecone API Key Secret:**
   - Secret type: **Other type of secret**
   - Key/value: `PINECONE_API_KEY` = `pc-...` (your actual key)
   - Secret name: `benefitsflow/pinecone-api-key`
   - Description: "Pinecone API key for BenefitsFlow vector database"
   - Click **Store**

4. **Note the ARNs:**
   - After creating each secret, copy the **ARN** (looks like: `arn:aws:secretsmanager:us-west-2:123456789012:secret:benefitsflow/openai-api-key-AbCdEf`)

### Option B: Using AWS CLI

```bash
# Create OpenAI secret
aws secretsmanager create-secret \
  --name benefitsflow/openai-api-key \
  --description "OpenAI API key for BenefitsFlow embeddings" \
  --secret-string '{"OPENAI_API_KEY":"sk-..."}' \
  --region us-west-2

# Create Pinecone secret
aws secretsmanager create-secret \
  --name benefitsflow/pinecone-api-key \
  --description "Pinecone API key for BenefitsFlow vector database" \
  --secret-string '{"PINECONE_API_KEY":"pc-..."}' \
  --region us-west-2

# Get ARNs
aws secretsmanager describe-secret \
  --secret-id benefitsflow/openai-api-key \
  --region us-west-2 \
  --query 'ARN' \
  --output text

aws secretsmanager describe-secret \
  --secret-id benefitsflow/pinecone-api-key \
  --region us-west-2 \
  --query 'ARN' \
  --output text
```

---

## Step 2: Create IAM Role for EC2

The EC2 instance needs permissions to:
- Read secrets from Secrets Manager
- Invoke Bedrock models
- Read from S3 (if using S3 for documents)
- Write CloudWatch logs

### Using AWS Console:

1. **Go to IAM → Roles → Create Role**

2. **Select Trust Entity:**
   - Trusted entity type: **AWS service**
   - Use case: **EC2**
   - Click **Next**

3. **Add Permissions:**
   - Create a new policy or attach existing policies:

**Policy JSON:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-west-2:*:secret:benefitsflow/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-west-2::foundation-model/openai.gpt-oss-120b-1:0"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-benefits-bucket",
        "arn:aws:s3:::your-benefits-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:CreateLogGroup"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

4. **Name the policy:** `BenefitsFlow-EC2-Policy`
5. **Name the role:** `BenefitsFlow-EC2-Role`
6. **Create role**

### Using AWS CLI:

```bash
# Create policy
aws iam create-policy \
  --policy-name BenefitsFlow-EC2-Policy \
  --policy-document file://ec2-policy.json

# Create role
aws iam create-role \
  --role-name BenefitsFlow-EC2-Role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach policy to role
aws iam attach-role-policy \
  --role-name BenefitsFlow-EC2-Role \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/BenefitsFlow-EC2-Policy
```

---

## Step 3: Launch EC2 Instance with IAM Role

1. **Launch EC2 Instance:**
   - AMI: Amazon Linux 2023 or Ubuntu 22.04
   - Instance type: t3.medium (2 vCPU, 4GB RAM) minimum
   - Security Group: Allow HTTP (80), HTTPS (443), SSH (22)
   - **IAM Role:** Select `BenefitsFlow-EC2-Role` (created in Step 2)
   - Launch instance

2. **SSH into EC2:**
```bash
ssh ec2-user@<EC2-IP>
```

---

## Step 4: Install Docker on EC2

```bash
# Amazon Linux 2023
sudo yum update -y
sudo yum install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in for group changes
exit
# SSH back in
```

---

## Step 5: Upload Code to EC2

```bash
# On your local machine
scp -r . ec2-user@<EC2-IP>:/home/ec2-user/benefitsflow/

# Or use Git
ssh ec2-user@<EC2-IP>
git clone <your-repo> /home/ec2-user/benefitsflow
```

---

## Step 6: Configure Environment Variables

Create a `.env` file on EC2 (or set environment variables):

```bash
cd /home/ec2-user/benefitsflow
nano .env
```

**Add these (using Secret ARNs, NOT the actual keys):**
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

# Secrets Manager ARNs (replace with your actual ARNs)
OPENAI_API_KEY_SECRET_ARN=arn:aws:secretsmanager:us-west-2:123456789012:secret:benefitsflow/openai-api-key-AbCdEf
PINECONE_API_KEY_SECRET_ARN=arn:aws:secretsmanager:us-west-2:123456789012:secret:benefitsflow/pinecone-api-key-XyZaBc

# Optional: Bedrock bearer token (if needed)
# AWS_BEARER_TOKEN_BEDROCK_SECRET_ARN=arn:aws:secretsmanager:us-west-2:123456789012:secret:benefitsflow/bedrock-token-...

# Frontend
RAG_SERVICE_URL=http://api:8000
```

**Important:** 
- Use **Secret ARNs**, not the actual API keys
- The IAM role allows EC2 to read these secrets automatically
- No API keys in code or environment variables!

---

## Step 7: Update docker-compose.yml for Production

The `docker-compose.yml` already supports Secrets Manager. Just make sure it reads from `.env`:

```yaml
version: "3.9"
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: rag-api
    ports:
      - "8000:8000"
    env_file:
      - .env  # Loads from .env file
    environment:
      # These will be read from .env
      S3_REGION: ${S3_REGION:-us-west-2}
      BEDROCK_REGION: ${BEDROCK_REGION:-us-west-2}
      # ... etc
      OPENAI_API_KEY_SECRET_ARN: ${OPENAI_API_KEY_SECRET_ARN}
      PINECONE_API_KEY_SECRET_ARN: ${PINECONE_API_KEY_SECRET_ARN}
    # Mount AWS credentials (IAM role is used automatically, but this helps)
    volumes:
      - /home/ec2-user/.aws:/root/.aws:ro

  ui:
    build:
      context: .
      dockerfile: Dockerfile.ui
    container_name: rag-ui
    ports:
      - "8501:8501"
    env_file:
      - .env
    environment:
      RAG_SERVICE_URL: ${RAG_SERVICE_URL:-http://api:8000}
    depends_on:
      - api
```

---

## Step 8: Build and Run

```bash
cd /home/ec2-user/benefitsflow
docker-compose up -d --build
```

**Check logs:**
```bash
docker-compose logs -f api
docker-compose logs -f ui
```

**Test:**
```bash
# Test RAG service
curl http://localhost:8000/health

# Test frontend
curl http://localhost:8501
```

---

## Step 9: Set Up Nginx (Optional - for Port 80)

```bash
# Install Nginx
sudo yum install nginx -y

# Configure
sudo nano /etc/nginx/conf.d/benefitsflow.conf
```

**Add:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## Step 10: Verify Secrets Are Working

```bash
# SSH into EC2
ssh ec2-user@<EC2-IP>

# Check if secrets can be read (using IAM role)
aws secretsmanager get-secret-value \
  --secret-id benefitsflow/openai-api-key \
  --region us-west-2

# Should return the secret (without showing the actual key value in output)
```

**Test the application:**
- Visit: http://<EC2-IP>:8501
- Send a chat message
- Check logs: `docker-compose logs -f api`

If you see errors about secrets, check:
1. IAM role is attached to EC2 instance
2. IAM policy has `secretsmanager:GetSecretValue` permission
3. Secret ARNs in `.env` are correct
4. Secrets exist in the same region (us-west-2)

---

## Troubleshooting

### "AccessDeniedException" when reading secrets

**Fix:**
- Verify IAM role is attached to EC2 instance
- Check IAM policy includes `secretsmanager:GetSecretValue`
- Verify secret ARN is correct

### "ResourceNotFoundException" for secret

**Fix:**
- Check secret name/ARN is correct
- Verify secret exists in us-west-2 region
- Check secret name matches exactly (case-sensitive)

### "Bedrock access denied"

**Fix:**
- Verify IAM role has `bedrock:InvokeModel` permission
- Check Bedrock model is available in us-west-2
- Verify model ID is correct: `openai.gpt-oss-120b-1:0`

### Secrets not loading in Docker

**Fix:**
- Verify `.env` file exists and has correct ARNs
- Check `docker-compose.yml` has `env_file: - .env`
- Restart containers: `docker-compose restart`

---

## Security Best Practices

✅ **DO:**
- Use IAM roles (no keys in code)
- Store secrets in Secrets Manager
- Use least-privilege IAM policies
- Rotate secrets regularly
- Monitor CloudTrail for secret access

❌ **DON'T:**
- Store API keys in code
- Commit `.env` files to Git
- Share secret ARNs publicly
- Use admin-level IAM permissions

---

## Summary

1. ✅ Create secrets in AWS Secrets Manager
2. ✅ Create IAM role with Secrets Manager permissions
3. ✅ Launch EC2 with IAM role attached
4. ✅ Set environment variables with Secret ARNs (not keys!)
5. ✅ Deploy with `docker-compose up`
6. ✅ No API keys in code or environment variables!

The application automatically fetches actual keys from Secrets Manager at runtime using the IAM role. Secure and production-ready! 🔒


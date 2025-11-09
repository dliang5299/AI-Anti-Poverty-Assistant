# API Keys Setup: Individual vs Shared Accounts

> **Note:** If you have AWS budget, consider using **100% AWS-native services** instead. See `AWS_NATIVE_SETUP.md` for using Bedrock embeddings + OpenSearch (no external APIs needed).

## Options

### Option 1: Individual Accounts (Recommended for Development)

**Use your own accounts:**
- ✅ Each person controls their own keys
- ✅ No shared costs
- ✅ Easy to set up
- ✅ Good for development/testing
- ❌ Costs come from your personal accounts

**Setup:**
```bash
# Each team member sets up their own:
# 1. AWS Account (or use free tier)
# 2. OpenAI account (pay-as-you-go)
# 3. Pinecone account (free tier available)
```

**Costs (approximate):**
- **AWS Bedrock**: ~$0.0008 per 1K input tokens, ~$0.0024 per 1K output tokens
- **OpenAI Embeddings**: ~$0.13 per 1M tokens (text-embedding-3-small)
- **Pinecone**: Free tier = 1 index, 100K vectors, then ~$0.096 per 100K vectors/month
- **AWS S3**: ~$0.023 per GB/month (storage)

**For light testing:** Probably $5-20/month per person

---

### Option 2: Shared Team Account (Recommended for Production)

**Create shared project accounts:**
- ✅ Shared costs (split among team)
- ✅ Centralized management
- ✅ Better for production/deployment
- ✅ Easier to track project expenses
- ❌ Need to coordinate access
- ❌ Someone needs to manage billing

**Setup:**
1. **AWS Account:**
   - Create a shared AWS account (or use one person's)
   - Create IAM users for each team member
   - Set up billing alerts

2. **OpenAI Account:**
   - Create shared OpenAI organization account
   - Add team members as users
   - Set usage limits

3. **Pinecone Account:**
   - Create shared Pinecone account
   - Share API key securely (use AWS Secrets Manager)

**For Production:**
- Use AWS Secrets Manager to store shared keys
- Set up IAM roles for EC2/ECS
- No keys in code or environment variables

---

### Option 3: Hybrid (Best Practice)

**Development:** Individual accounts  
**Production:** Shared account

- Each person uses their own keys for local development
- Production deployment uses shared keys from AWS Secrets Manager
- Best of both worlds!

---

## Recommendation for Your Capstone

**For now (development):** Use **individual accounts**
- Fastest to get started
- No coordination needed
- Each person pays their own costs (usually minimal for testing)

**For production/deployment:** Consider **shared account**
- If deploying to EC2, use shared AWS account
- Store keys in AWS Secrets Manager
- Use IAM roles (no keys in code)

---

## How to Set Up Individual Accounts

### 1. AWS Account

**Option A: Use existing AWS account**
```bash
aws configure
# Enter your Access Key ID and Secret Access Key
```

**Option B: Create new AWS account**
- Go to https://aws.amazon.com/
- Sign up (free tier available)
- Create IAM user with programmatic access
- Attach policy: `bedrock:InvokeModel`, `s3:GetObject`, `secretsmanager:GetSecretValue`
- Download Access Key ID and Secret

**Cost:** Free tier covers most testing needs

---

### 2. OpenAI Account

1. Go to https://platform.openai.com/
2. Sign up
3. Add payment method (required, but pay-as-you-go)
4. Go to API Keys: https://platform.openai.com/api-keys
5. Create new API key
6. Copy key (starts with `sk-`)

**Cost:** ~$0.13 per 1M tokens for embeddings (very cheap for testing)

---

### 3. Pinecone Account

1. Go to https://app.pinecone.io/
2. Sign up (free tier available)
3. Create API key
4. Create index:
   - Name: `knowledge`
   - Dimension: `1536`
   - Metric: `cosine`
   - Type: `serverless`
   - Region: `us-east-1` (free tier)

**Cost:** Free tier = 1 index, 100K vectors (plenty for testing)

---

## Setting Up Your Keys Locally

### Option 1: Environment Variables

```bash
# In your terminal (Mac/Linux)
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export OPENAI_API_KEY=sk-...
export PINECONE_API_KEY=pc-...

# Or add to ~/.bashrc or ~/.zshrc to make permanent
```

```powershell
# In PowerShell (Windows)
$env:AWS_ACCESS_KEY_ID="AKIA..."
$env:AWS_SECRET_ACCESS_KEY="..."
$env:OPENAI_API_KEY="sk-..."
$env:PINECONE_API_KEY="pc-..."
```

### Option 2: .env File (Recommended)

Create `.env` file in project root (add to `.gitignore`!):

```bash
# .env (DO NOT COMMIT THIS FILE!)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-west-2
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pc-...
```

**Load in Docker:**
```bash
# docker-compose.yml will automatically load .env file
docker-compose up
```

**Load in Python:**
```bash
pip install python-dotenv
# Then in your code:
from dotenv import load_dotenv
load_dotenv()
```

### Option 3: AWS CLI (For AWS Only)

```bash
aws configure
# This sets up AWS credentials in ~/.aws/credentials
# Docker will use these if you mount ~/.aws
```

---

## Security Best Practices

### ✅ DO:
- Use `.env` file (add to `.gitignore`)
- Use AWS Secrets Manager for production
- Use IAM roles on EC2 (no keys needed)
- Rotate keys regularly
- Set usage limits on OpenAI/Pinecone

### ❌ DON'T:
- Commit API keys to Git
- Share keys in Slack/email
- Hardcode keys in code
- Use production keys for development

---

## Cost Estimates

### Light Development/Testing (per person):
- **AWS Bedrock**: ~$1-5/month (depending on usage)
- **OpenAI Embeddings**: ~$1-3/month
- **Pinecone**: Free tier (0-100K vectors)
- **AWS S3**: ~$0.10/month (minimal storage)
- **Total**: ~$2-8/month per person

### Production (shared):
- **AWS Bedrock**: ~$10-50/month (depending on traffic)
- **OpenAI Embeddings**: ~$5-20/month
- **Pinecone**: ~$10-50/month (if over free tier)
- **AWS S3**: ~$1-5/month
- **EC2**: ~$15-30/month (t3.medium)
- **Total**: ~$40-150/month (split among team)

---

## Quick Start: Individual Setup

1. **Get AWS credentials:**
   ```bash
   aws configure
   ```

2. **Get OpenAI key:**
   - https://platform.openai.com/api-keys
   - Copy key

3. **Get Pinecone key:**
   - https://app.pinecone.io/
   - Create index: `knowledge`, dimension `1536`

4. **Create `.env` file:**
   ```bash
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   OPENAI_API_KEY=sk-...
   PINECONE_API_KEY=pc-...
   ```

5. **Run:**
   ```bash
   docker-compose up
   ```

---

## Summary

**For development:** Use **individual accounts** - fastest, easiest, each person pays their own costs

**For production:** Consider **shared account** with AWS Secrets Manager

**Cost:** ~$2-8/month per person for development, ~$40-150/month shared for production


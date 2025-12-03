# AWS Secrets Manager Guide for BenefitsFlow

## ⚠️ IMPORTANT: Never Hardcode API Keys

**BAD PRACTICE** ❌:
```python
OPENAI_API_KEY = "sk-proj-..."  # NEVER DO THIS
PINECONE_API_KEY = "pcs-..."    # NEVER DO THIS
```

**GOOD PRACTICE** ✅:
- Always use AWS Secrets Manager
- Use IAM roles for authentication (no hardcoded credentials)
- Retrieve secrets at runtime using boto3

---

## Our AWS Secrets Manager Setup

### Secret Structure

We use a **single combined secret** that contains both API keys in JSON format:

**Secret Name**: `benefitsflow-rag/secrets`  
**Region**: `us-west-2`  
**Format**: JSON with key-value pairs

**Secret Content**:
```json
{
  "OPENAI_API_KEY": "sk-proj-...",
  "PINECONE_API_KEY": "pcs-..."
}
```

### Why Combined Secret?

- **Single source of truth**: Both keys managed together
- **Easier rotation**: Update one secret instead of two
- **Simpler IAM policies**: One secret to grant access to
- **Cost efficient**: One secret instead of multiple

---

## How to Retrieve Secrets

### Method 1: Using boto3 (Recommended)

```python
import boto3
import json
from botocore.exceptions import ClientError

def get_secret_from_aws(secret_name: str, region_name: str = "us-west-2", key: str = None):
    """
    Retrieve a secret from AWS Secrets Manager by name.
    
    Args:
        secret_name: Name of the secret (e.g., "benefitsflow-rag/secrets")
        region_name: AWS region (default: us-west-2)
        key: Optional key to extract from JSON secret
    
    Returns:
        Secret value as string, or None if not found
    """
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        print(f"⚠️ Error retrieving secret '{secret_name}': {error_code}")
        return None
    
    # Extract secret string
    secret_string = get_secret_value_response.get('SecretString')
    
    if not secret_string:
        return None
    
    # If a specific key is requested, parse JSON and extract it
    if key:
        try:
            secret_json = json.loads(secret_string)
            if isinstance(secret_json, dict) and key in secret_json:
                return secret_json[key]
        except json.JSONDecodeError:
            return None
    
    # Return the full secret string
    return secret_string

# Usage examples:
# Get entire secret as JSON string
secret = get_secret_from_aws("benefitsflow-rag/secrets")

# Get specific key from JSON
openai_key = get_secret_from_aws("benefitsflow-rag/secrets", key="OPENAI_API_KEY")
pinecone_key = get_secret_from_aws("benefitsflow-rag/secrets", key="PINECONE_API_KEY")
```

### Method 2: Using Our Utility (UI Directory)

We have a utility module `UI/secrets_manager.py` that provides helper functions:

```python
from secrets_manager import (
    get_combined_secrets,
    get_openai_key_from_secrets,
    get_pinecone_key_from_secrets
)

# Get both keys at once
secrets = get_combined_secrets()
if secrets['openai_api_key']:
    # Use OpenAI key
    pass

# Or get just one key
openai_key = get_openai_key_from_secrets()
pinecone_key = get_pinecone_key_from_secrets()
```

### Method 3: In app/config.py (RAG Service)

The RAG service (`app/config.py`) automatically tries the combined secret first:

```python
# It tries these in order:
# 1. Combined secret: "benefitsflow-rag/secrets"
# 2. Auto-discovery: looks for secrets containing "openai" or "pinecone"
# 3. Explicit ARN: from OPENAI_API_KEY_SECRET_ARN env var

# Usage (automatic):
from app.config import get_openai_api_key, get_pinecone_api_key

openai_key = get_openai_api_key()  # Automatically retrieves from combined secret
pinecone_key = get_pinecone_api_key()  # Automatically retrieves from combined secret
```

---

## IAM Permissions Required

The EC2 instance or Lambda function needs these IAM permissions:

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
      "Resource": "arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:benefitsflow-rag/secrets-*"
    }
  ]
}
```

**Note**: You can use the secret name directly (no ARN needed) if you have `GetSecretValue` permission.

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Hardcoding Keys
```python
# DON'T DO THIS
api_key = "sk-proj-abc123..."
```

### ❌ Mistake 2: Using Environment Variables in Production
```python
# DON'T DO THIS (security risk)
import os
api_key = os.getenv("OPENAI_API_KEY")  # If set in docker.env, it's still a risk
```

### ❌ Mistake 3: Assuming Separate Secrets
```python
# DON'T ASSUME separate secrets exist
# Our setup uses ONE combined secret
```

### ✅ Correct Approach
```python
# DO THIS: Retrieve from AWS Secrets Manager
import boto3
client = boto3.client('secretsmanager', region_name='us-west-2')
response = client.get_secret_value(SecretId='benefitsflow-rag/secrets')
secret_json = json.loads(response['SecretString'])
api_key = secret_json['OPENAI_API_KEY']
```

---

## Troubleshooting

### Issue: "Could not retrieve OPENAI API key from secret"

**Possible causes**:
1. Secret name is wrong (should be `benefitsflow-rag/secrets`)
2. Secret is in wrong region (should be `us-west-2`)
3. IAM role doesn't have `secretsmanager:GetSecretValue` permission
4. Secret doesn't contain the expected JSON keys

**Solution**:
```bash
# Check if secret exists
aws secretsmanager describe-secret --secret-id benefitsflow-rag/secrets --region us-west-2

# Check IAM permissions
aws sts get-caller-identity
aws iam get-role-policy --role-name YourRoleName --policy-name YourPolicyName
```

### Issue: "ResourceNotFoundException"

**Cause**: Secret name doesn't exist or is misspelled

**Solution**: Verify exact secret name in AWS Console:
1. Go to AWS Secrets Manager
2. Find secret: `benefitsflow-rag/secrets`
3. Copy exact name (including any suffixes AWS may have added)

### Issue: "AccessDeniedException"

**Cause**: IAM role doesn't have permission

**Solution**: Add `secretsmanager:GetSecretValue` permission to IAM role

---

## Best Practices Summary

1. ✅ **Always use AWS Secrets Manager** - Never hardcode keys
2. ✅ **Use IAM roles** - No access keys in code
3. ✅ **Retrieve at runtime** - Don't cache keys in environment variables
4. ✅ **Handle errors gracefully** - Log errors but don't expose secrets
5. ✅ **Use combined secrets** - Easier to manage multiple keys
6. ✅ **Test locally** - Use AWS credentials for local development
7. ✅ **Rotate secrets regularly** - Update secrets in AWS Console

---

## For AI Assistants

When working on this codebase:

1. **NEVER suggest hardcoding API keys** - Always use AWS Secrets Manager
2. **The secret is combined** - `benefitsflow-rag/secrets` contains both keys in JSON
3. **Use the existing utilities** - Check `UI/secrets_manager.py` and `app/config.py`
4. **IAM authentication** - The code uses boto3 with IAM roles (no explicit credentials)
5. **Region is us-west-2** - All secrets are in Oregon region

If you see code like this:
```python
api_key = "sk-..."  # BAD
```

Suggest replacing with:
```python
from app.config import get_openai_api_key
api_key = get_openai_api_key()  # GOOD
```

---

## References

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [boto3 Secrets Manager Client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager.html)
- [AWS Best Practices for Secrets](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)

---

## Quick Reference

**Secret Name**: `benefitsflow-rag/secrets`  
**Region**: `us-west-2`  
**Format**: JSON  
**Keys**: `OPENAI_API_KEY`, `PINECONE_API_KEY`  
**Authentication**: IAM role (no hardcoded credentials)  
**Retrieval Method**: `boto3.client('secretsmanager').get_secret_value()`


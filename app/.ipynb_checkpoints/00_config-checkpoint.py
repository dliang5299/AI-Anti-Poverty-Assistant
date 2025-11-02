import os
import json
import boto3
from functools import lru_cache

def _get_env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name, default)
    return v

def _resolve_secret_value(secret_id_or_arn: str, region: str | None = None) -> str:
    """Fetch secret string from AWS Secrets Manager.
    Accepts either a full ARN or a name; uses provided region or BEDROCK_REGION/S3_REGION as fallback.
    """
    if not region:
        region = os.getenv("BEDROCK_REGION") or os.getenv("S3_REGION") or "us-west-2"
    sm = boto3.client("secretsmanager", region_name=region)
    resp = sm.get_secret_value(SecretId=secret_id_or_arn)
    if "SecretString" in resp:
        return resp["SecretString"]
    # If binary, decode
    import base64
    return base64.b64decode(resp["SecretBinary"]).decode("utf-8")

@lru_cache(maxsize=4)
def get_openai_api_key() -> str:
    # Prefer secret ARN, fallback to OPENAI_API_KEY env (handy for local tests)
    secret_arn = _get_env("OPENAI_API_KEY_SECRET_ARN")
    if secret_arn:
        val = _resolve_secret_value(secret_arn, region=os.getenv("S3_REGION") or "us-west-2")
        try:
            # Secret may be raw string or JSON {"OPENAI_API_KEY":"..."}
            data = json.loads(val)
            return data.get("OPENAI_API_KEY") or data.get("openai_api_key") or val
        except json.JSONDecodeError:
            return val
    env_val = _get_env("OPENAI_API_KEY")
    if not env_val:
        raise RuntimeError("OPENAI_API_KEY not set and OPENAI_API_KEY_SECRET_ARN not provided")
    return env_val

@lru_cache(maxsize=4)
def get_pinecone_api_key() -> str:
    secret_arn = _get_env("PINECONE_API_KEY_SECRET_ARN")
    if secret_arn:
        val = _resolve_secret_value(secret_arn, region=os.getenv("S3_REGION") or "us-west-2")
        try:
            data = json.loads(val)
            return data.get("PINECONE_API_KEY") or data.get("pinecone_api_key") or val
        except json.JSONDecodeError:
            return val
    env_val = _get_env("PINECONE_API_KEY")
    if not env_val:
        raise RuntimeError("PINECONE_API_KEY not set and PINECONE_API_KEY_SECRET_ARN not provided")
    return env_val

@lru_cache(maxsize=2)
def get_bedrock_bearer_token() -> str | None:
    secret_arn = _get_env("AWS_BEARER_TOKEN_BEDROCK_SECRET_ARN")
    if not secret_arn:
        return None
    val = _resolve_secret_value(secret_arn, region=os.getenv("BEDROCK_REGION") or "us-west-2")
    try:
        data = json.loads(val)
        return data.get("AWS_BEARER_TOKEN_BEDROCK") or data.get("bedrock_bearer_token") or val
    except json.JSONDecodeError:
        return val

def get_regions():
    return {
        "s3": _get_env("S3_REGION", "us-west-2"),
        "bedrock": _get_env("BEDROCK_REGION", "us-west-2"),
        "pinecone": _get_env("PINECONE_REGION", "us-east-1"),
    }

def get_models():
    return {
        "embed_model": _get_env("EMBED_MODEL", "text-embedding-3-small"),
        "llm_model": _get_env("LLM_MODEL", "openai.gpt-oss-120b-1:0"),
    }

def get_pinecone_config():
    return {
        "index_name": _get_env("PINECONE_INDEX_NAME", "knowledge"),
        "dimension": int(_get_env("PINECONE_DIM", "1536")),
        # project env label commonly used by Pinecone serverless (e.g., aws-us-east-1)
        "environment": _get_env("PINECONE_ENV", "aws-us-east-1"),
    }

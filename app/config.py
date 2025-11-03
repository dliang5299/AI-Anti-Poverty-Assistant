import os
import json
import boto3
from functools import lru_cache
from typing import Optional, Dict, Any

def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)

def _region_fallback() -> str:
    return _get_env("BEDROCK_REGION") or _get_env("S3_REGION") or "us-west-2"

def _fetch_secret(secret_arn: str, region: Optional[str] = None) -> Optional[str]:
    sm = boto3.client("secretsmanager", region_name=region or _region_fallback())
    resp = sm.get_secret_value(SecretId=secret_arn)
    val = resp.get("SecretString")
    if not val and "SecretBinary" in resp:
        val = resp["SecretBinary"].decode("utf-8", errors="ignore")
    try:
        obj = json.loads(val)
        for k in ("OPENAI_API_KEY","PINECONE_API_KEY","api_key","token","key"):
            if k in obj and isinstance(obj[k], str) and obj[k]:
                return obj[k]
        return val
    except json.JSONDecodeError:
        return val

@lru_cache(maxsize=None)
def get_regions() -> Dict[str,str]:
    return {
        "s3": _get_env("S3_REGION", "us-west-2"),
        "pinecone": _get_env("PINECONE_REGION", "us-east-1"),
        "bedrock": _get_env("BEDROCK_REGION", "us-east-1"),
        "pinecone_env": _get_env("PINECONE_ENV", "aws-us-east-1"),
    }

@lru_cache(maxsize=None)
def get_models() -> Dict[str,str]:
    return {
        "embed_model": _get_env("EMBED_MODEL", "text-embedding-3-small"),
        "llm_model": _get_env("LLM_MODEL", "openai.gpt-oss-120b-1:0"),
    }

@lru_cache(maxsize=None)
def get_pinecone_config() -> Dict[str,Any]:
    return {
        "index_name": _get_env("PINECONE_INDEX_NAME", "knowledge"),
        "dimension": int(_get_env("PINECONE_DIM", "1536")),
        "environment": get_regions()["pinecone_env"],
    }

@lru_cache(maxsize=None)
def get_openai_api_key() -> str:
    arn = _get_env("OPENAI_API_KEY_SECRET_ARN")
    if not arn:
        raise RuntimeError("OPENAI_API_KEY_SECRET_ARN is required (ARN-only build).")
    key = _fetch_secret(arn, get_regions()["bedrock"])
    if not key:
        raise RuntimeError("Failed to resolve OPENAI API key from Secrets Manager.")
    return key

@lru_cache(maxsize=None)
def get_pinecone_api_key() -> str:
    arn = _get_env("PINECONE_API_KEY_SECRET_ARN")
    if not arn:
        raise RuntimeError("PINECONE_API_KEY_SECRET_ARN is required (ARN-only build).")
    key = _fetch_secret(arn, get_regions()["pinecone"])
    if not key:
        raise RuntimeError("Failed to resolve PINECONE API key from Secrets Manager.")
    return key

@lru_cache(maxsize=None)
def get_bedrock_bearer_token() -> Optional[str]:
    arn = _get_env("AWS_BEDROCK_BEARER_TOKEN_SECRET_ARN")
    if not arn:
        return None
    return _fetch_secret(arn, get_regions()["bedrock"])

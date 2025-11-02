
import os
import json
import boto3
from functools import lru_cache
from typing import Optional, Dict, Any

"""
Centralized configuration that favors environment variables but will fall back
to AWS Secrets Manager when *_SECRET_ARN environment variables are provided.

Supported env vars:
  # Regions
  S3_REGION                  (default "us-west-2")
  PINECONE_REGION            (default "us-east-1")
  PINECONE_ENV               (default "aws-us-east-1")
  BEDROCK_REGION             (default "us-east-1")

  # Direct secrets (preferred for local dev)
  OPENAI_API_KEY
  PINECONE_API_KEY

  # Secret ARNs (preferred for prod)
  OPENAI_API_KEY_SECRET_ARN
  PINECONE_API_KEY_SECRET_ARN
  AWS_BEDROCK_BEARER_TOKEN_SECRET_ARN

  # Pinecone index settings
  PINECONE_INDEX_NAME        (default "knowledge")
  PINECONE_DIM               (default "1536")

  # Model IDs
  EMBED_MODEL                (default "text-embedding-3-small")
  LLM_MODEL                  (default "openai.gpt-oss-120b-1:0")
"""

def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)

def _aws_region_fallback() -> str:
    return _get_env("BEDROCK_REGION") or _get_env("S3_REGION") or "us-west-2"

def _fetch_secret(secret_arn: str, region: Optional[str] = None) -> Optional[str]:
    """Fetch secret string from AWS Secrets Manager (returns None if not found)."""
    try:
        sm = boto3.client("secretsmanager", region_name=region or _aws_region_fallback())
        resp = sm.get_secret_value(SecretId=secret_arn)
        val = resp.get("SecretString")
        if not val and "SecretBinary" in resp:
            val = resp["SecretBinary"].decode("utf-8", errors="ignore")
        # Allow JSON secrets: return the first plausible key if JSON
        try:
            obj = json.loads(val)
            # Common key names
            for k in ("OPENAI_API_KEY", "api_key", "token", "PINECONE_API_KEY", "key"):
                if k in obj and isinstance(obj[k], str) and obj[k]:
                    return obj[k]
            # else just return stringified JSON
            return val
        except json.JSONDecodeError:
            return val
    except Exception:
        return None

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
    # Prefer explicit env var
    key = _get_env("OPENAI_API_KEY")
    if key:
        return key
    # Fallback to secret manager
    arn = _get_env("OPENAI_API_KEY_SECRET_ARN")
    if arn:
        sec = _fetch_secret(arn, get_regions()["bedrock"])  # region doesn't really matter
        if sec:
            return sec
    raise RuntimeError("OPENAI_API_KEY not set (env) and OPENAI_API_KEY_SECRET_ARN not resolvable.")

@lru_cache(maxsize=None)
def get_pinecone_api_key() -> str:
    key = _get_env("PINECONE_API_KEY")
    if key:
        return key
    arn = _get_env("PINECONE_API_KEY_SECRET_ARN")
    if arn:
        sec = _fetch_secret(arn, get_regions()["pinecone"])
        if sec:
            return sec
    raise RuntimeError("PINECONE_API_KEY not set (env) and PINECONE_API_KEY_SECRET_ARN not resolvable.")

@lru_cache(maxsize=None)
def get_bedrock_bearer_token() -> Optional[str]:
    arn = _get_env("AWS_BEDROCK_BEARER_TOKEN_SECRET_ARN")
    if not arn:
        return None
    return _fetch_secret(arn, get_regions()["bedrock"])

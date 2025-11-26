# app/config.py
import os
import re
import json
from functools import lru_cache
from typing import Optional, Dict, Any

import boto3

# ========================
# ENV HELPERS & REGIONS
# ========================

def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def _region_fallback() -> str:
    """Fallback AWS region if unknown."""
    return _get_env("BEDROCK_REGION") or _get_env("S3_REGION") or "us-west-2"


def _region_from_secret_arn(secret_id: str) -> Optional[str]:
    """Extract AWS region from a Secrets Manager ARN."""
    m = re.match(r"^arn:aws:secretsmanager:([a-z0-9-]+):\d+:secret:", secret_id or "")
    return m.group(1) if m else None


def _secret_region_for(secret_id: str, hint_region: Optional[str] = None) -> str:
    """
    Determines the correct region for the secret:
    1) Parse from ARN
    2) SECRET_REGION env override
    3) Provided hint
    4) Default global fallback
    """
    return (
        _region_from_secret_arn(secret_id)
        or _get_env("SECRET_REGION")
        or (hint_region or _region_fallback())
    )


# ========================
# SECRET FETCHING
# ========================

def _fetch_secret(
    secret_id: str,
    hint_region: Optional[str] = None,
    prefer_key: Optional[str] = None
) -> Optional[str]:
    """Fetch & decode secret, auto-detect region or use prefer_key if in JSON."""
    region = _secret_region_for(secret_id, hint_region)
    sm = boto3.client("secretsmanager", region_name=region)
    resp = sm.get_secret_value(SecretId=secret_id)

    val = resp.get("SecretString")
    if not val and "SecretBinary" in resp:
        v = resp["SecretBinary"]
        val = v.decode("utf-8", errors="ignore") if isinstance(v, (bytes, bytearray)) else v

    if not isinstance(val, str):
        return None

    # Try JSON decode
    try:
        obj = json.loads(val)

        # If a specific key is requested, return that key only
        if prefer_key and isinstance(obj.get(prefer_key), str) and obj[prefer_key]:
            return obj[prefer_key]

        # Otherwise scan common names (fallback)
        for k in ("OPENAI_API_KEY", "PINECONE_API_KEY", "api_key", "token", "key"):
            if isinstance(obj.get(k), str) and obj[k]:
                return obj[k]
        return val
    except json.JSONDecodeError:
        # Not JSON — raw string secret
        return val


# ========================
# GETTERS
# ========================

@lru_cache(maxsize=None)
def get_regions() -> Dict[str, str]:
    """Central region config — Pinecone may differ from AWS secret region."""
    return {
        "s3":      _get_env("S3_REGION", "us-west-2"),
        "pinecone": _get_env("PINECONE_REGION", "us-east-1"),
        "bedrock": _get_env("BEDROCK_REGION", "us-west-2"),  # Changed to us-west-2 (Oregon)
        "pinecone_env": _get_env("PINECONE_ENV", "aws-us-east-1"),
    }


@lru_cache(maxsize=None)
def get_models() -> Dict[str, str]:
    return {
        "embed_model": _get_env("EMBED_MODEL", "text-embedding-3-small"),
        "llm_model": _get_env("LLM_MODEL", "meta.llama3-1-70b-instruct-v1:0"),
    }


@lru_cache(maxsize=None)
def get_pinecone_config() -> Dict[str, Any]:
    return {
        "index_name": _get_env("PINECONE_INDEX_NAME", "knowledge"),
        "dimension": int(_get_env("PINECONE_DIM", "1536")),
        "environment": get_regions()["pinecone_env"],
    }


@lru_cache(maxsize=1)
def _get_combined_secrets() -> Dict[str, Any]:
    """
    Fetch the combined secret containing both API keys.
    Falls back to individual secrets if SECRETS_ARN is not set (backward compatibility).
    """
    # Try combined secret first
    combined_secret_arn = _get_env("SECRETS_ARN")
    if combined_secret_arn:
        hint = _get_env("SECRETS_REGION") or get_regions()["bedrock"]
        secret_json = _fetch_secret(combined_secret_arn, hint_region=hint, prefer_key=None)
        if secret_json:
            try:
                return json.loads(secret_json)
            except json.JSONDecodeError:
                raise RuntimeError(f"Combined secret at {combined_secret_arn} is not valid JSON.")
    
    # Fallback: return empty dict if using individual secrets (handled below)
    return {}

@lru_cache(maxsize=None)
def get_openai_api_key() -> str:
    # Try combined secret first
    combined_secrets = _get_combined_secrets()
    if combined_secrets:
        key = combined_secrets.get("OPENAI_API_KEY")
        if key:
            return key
    
    # Fallback to individual secret (backward compatibility)
    secret_id = _get_env("OPENAI_API_KEY_SECRET_ARN")
    if not secret_id:
        raise RuntimeError("Either SECRETS_ARN or OPENAI_API_KEY_SECRET_ARN is required.")

    hint = _get_env("OPENAI_SECRET_REGION") or get_regions()["bedrock"]
    key = _fetch_secret(secret_id, hint_region=hint, prefer_key="OPENAI_API_KEY")

    if not key:
        raise RuntimeError("Could not retrieve OPENAI API key from secret.")
    return key


@lru_cache(maxsize=None)
def get_pinecone_api_key() -> str:
    # Try combined secret first
    combined_secrets = _get_combined_secrets()
    if combined_secrets:
        key = combined_secrets.get("PINECONE_API_KEY")
        if key:
            return key
    
    # Fallback to individual secret (backward compatibility)
    secret_id = _get_env("PINECONE_API_KEY_SECRET_ARN")
    if not secret_id:
        raise RuntimeError("Either SECRETS_ARN or PINECONE_API_KEY_SECRET_ARN is required.")

    hint = _get_env("PINECONE_SECRET_REGION") or get_regions()["pinecone"]
    key = _fetch_secret(secret_id, hint_region=hint, prefer_key="PINECONE_API_KEY")

    if not key:
        raise RuntimeError("Could not retrieve PINECONE API key from secret.")
    return key


@lru_cache(maxsize=None)
def get_bedrock_bearer_token() -> Optional[str]:
    secret_id = _get_env("AWS_BEDROCK_BEARER_TOKEN_SECRET_ARN")
    if not secret_id:
        return None
    hint = _get_env("BEDROCK_TOKEN_SECRET_REGION") or get_regions()["bedrock"]
    return _fetch_secret(secret_id, hint_region=hint)

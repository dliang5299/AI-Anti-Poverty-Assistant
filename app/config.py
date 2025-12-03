# app/config.py
import os
import re
import json
from functools import lru_cache
from typing import Optional, Dict, Any, List

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
# SECRET DISCOVERY
# ========================

def _discover_secret_arn_by_name(
    name_patterns: List[str],
    region: str = "us-west-2"
) -> Optional[str]:
    """
    Auto-discover secret ARN by trying common secret names directly.
    Works with IAM permissions that allow GetSecretValue and DescribeSecret.
    AWS Secrets Manager names have format: benefitsflow/secret-name-RANDOM_SUFFIX
    """
    sm = boto3.client("secretsmanager", region_name=region)
    
    # Try each pattern as a direct secret name/ARN
    # AWS Secrets Manager accepts partial names - it will find the secret even with suffix
    for pattern in name_patterns:
        # Try various name formats (AWS adds random suffix, but partial names work)
        for secret_name_variant in [
            f"benefitsflow/{pattern}-api-key",  # Most likely: benefitsflow/openai-api-key-XXXXXX
            f"benefitsflow/{pattern}",           # Alternative: benefitsflow/openai-XXXXXX
            f"benefitsflow-{pattern}-api-key",  # Alternative format
            f"{pattern}-api-key",                # Without prefix
            pattern,                              # Just the pattern
        ]:
            try:
                # Strategy 1: Try DescribeSecret first (gets full ARN)
                try:
                    resp = sm.describe_secret(SecretId=secret_name_variant)
                    arn = resp.get("ARN")
                    if arn:
                        print(f"✅ Auto-discovered secret via DescribeSecret: {secret_name_variant} -> {arn}")
                        return arn
                except sm.exceptions.ResourceNotFoundException:
                    # Secret not found with this name, try next variant
                    continue
                except Exception as e:
                    # If DescribeSecret fails with access error, try GetSecretValue directly
                    error_str = str(e)
                    if "AccessDenied" in error_str or "not authorized" in error_str.lower():
                        # Don't have DescribeSecret, try GetSecretValue (which we do have)
                        try:
                            # Try to get the secret value directly - if this works, use the name
                            # AWS will accept the name even without full ARN
                            test_resp = sm.get_secret_value(SecretId=secret_name_variant)
                            # If we get here, the secret exists and we can access it
                            # Try to get ARN from describe, or use name (AWS accepts both)
                            try:
                                desc_resp = sm.describe_secret(SecretId=secret_name_variant)
                                arn = desc_resp.get("ARN")
                                if arn:
                                    print(f"✅ Auto-discovered secret: {secret_name_variant} -> {arn}")
                                    return arn
                            except:
                                # Use name directly - AWS accepts it
                                print(f"✅ Found secret by name (using name as identifier): {secret_name_variant}")
                                return secret_name_variant
                        except sm.exceptions.ResourceNotFoundException:
                            continue  # Try next variant
                        except Exception:
                            continue
                    else:
                        continue  # Other error, try next variant
            except Exception:
                continue  # Try next variant
    
    # If we get here, none of the direct name attempts worked
    # This means either:
    # 1. Secrets don't exist with those names
    # 2. Names are different than expected
    print(f"⚠️ Could not auto-discover secret. Tried patterns: {name_patterns}")
    print(f"⚠️ Make sure secrets exist in region {region} with names containing: {', '.join(name_patterns)}")
    return None


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
        "llm_model": _get_env("LLM_MODEL", "openai.gpt-oss-120b-1:0"),
        "bedrock_rerank_model": _get_env("BEDROCK_RERANK_MODEL", "cohere.rerank-v3-5:0"),
    }


@lru_cache(maxsize=None)
def get_pinecone_config() -> Dict[str, Any]:
    return {
        "index_name": _get_env("PINECONE_INDEX_NAME", "knowledge"),
        "dimension": int(_get_env("PINECONE_DIM", "1536")),
        "environment": get_regions()["pinecone_env"],
    }


@lru_cache(maxsize=None)
def get_openai_api_key() -> str:
    # Prefer direct env for local/dev convenience
    direct_key = _get_env("OPENAI_API_KEY")
    if direct_key:
        return direct_key

    hint_region = _get_env("OPENAI_SECRET_REGION") or get_regions()["bedrock"]
    
    # Try combined secret first (benefitsflow-rag/secrets contains both keys)
    combined_secret_names = ["benefitsflow-rag/secrets", "benefitsflow/rag/secrets", "benefitsflow/secrets"]
    for secret_name in combined_secret_names:
        try:
            print(f"🔍 Trying combined secret: {secret_name}")
            key = _fetch_secret(secret_name, hint_region=hint_region, prefer_key="OPENAI_API_KEY")
            if key:
                print(f"✅ Found OpenAI API key in combined secret: {secret_name}")
                return key
        except Exception as e:
            print(f"⚠️ Could not retrieve from {secret_name}: {type(e).__name__}")
            continue

    # Otherwise use the dedicated secret
    secret_id = _get_env("OPENAI_API_KEY_SECRET_ARN")
    
    # Auto-discover secret if ARN not provided (works with IAM permissions)
    if not secret_id:
        print("🔍 Auto-discovering OpenAI API key secret...")
        secret_id = _discover_secret_arn_by_name(
            ["openai", "openai-api-key", "benefitsflow/openai"],
            region=hint_region
        )
    
    if not secret_id:
        raise RuntimeError(
            "OPENAI_API_KEY_SECRET_ARN is required, or a secret containing 'openai' "
            "must exist in AWS Secrets Manager. Tried combined secrets: " + ", ".join(combined_secret_names) +
            " and patterns: openai, openai-api-key, benefitsflow/openai"
        )

    key = _fetch_secret(secret_id, hint_region=hint_region, prefer_key="OPENAI_API_KEY")

    if not key:
        raise RuntimeError(f"Could not retrieve OPENAI API key from secret: {secret_id}")
    return key


@lru_cache(maxsize=None)
def get_pinecone_api_key() -> str:
    # Prefer direct env for local/dev convenience
    direct_key = _get_env("PINECONE_API_KEY")
    if direct_key:
        return direct_key

    hint_region = _get_env("PINECONE_SECRET_REGION") or get_regions()["pinecone"]
    
    # Try combined secret first (benefitsflow-rag/secrets contains both keys)
    combined_secret_names = ["benefitsflow-rag/secrets", "benefitsflow/rag/secrets", "benefitsflow/secrets"]
    for secret_name in combined_secret_names:
        try:
            print(f"🔍 Trying combined secret: {secret_name}")
            key = _fetch_secret(secret_name, hint_region=hint_region, prefer_key="PINECONE_API_KEY")
            if key:
                print(f"✅ Found Pinecone API key in combined secret: {secret_name}")
                return key
        except Exception as e:
            print(f"⚠️ Could not retrieve from {secret_name}: {type(e).__name__}")
            continue

    # Otherwise use the dedicated secret
    secret_id = _get_env("PINECONE_API_KEY_SECRET_ARN")
    
    # Auto-discover secret if ARN not provided (works with IAM permissions)
    if not secret_id:
        print("🔍 Auto-discovering Pinecone API key secret...")
        secret_id = _discover_secret_arn_by_name(
            ["pinecone", "pinecone-api-key", "benefitsflow/pinecone"],
            region=hint_region
        )
    
    if not secret_id:
        raise RuntimeError(
            "PINECONE_API_KEY_SECRET_ARN is required, or a secret containing 'pinecone' "
            "must exist in AWS Secrets Manager. Tried combined secrets: " + ", ".join(combined_secret_names)
        )

    key = _fetch_secret(secret_id, hint_region=hint_region, prefer_key="PINECONE_API_KEY")

    if not key:
        raise RuntimeError(f"Could not retrieve PINECONE API key from secret: {secret_id}")
    return key


@lru_cache(maxsize=None)
def get_bedrock_bearer_token() -> Optional[str]:
    secret_id = _get_env("AWS_BEDROCK_BEARER_TOKEN_SECRET_ARN")
    if not secret_id:
        return None
    hint = _get_env("BEDROCK_TOKEN_SECRET_REGION") or get_regions()["bedrock"]
    return _fetch_secret(secret_id, hint_region=hint)

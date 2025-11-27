import json
import os
import re

import boto3
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()  # populate env vars from local .env for secret ARN or API key

def _secret_region(secret_id: str) -> str:
    """Get region from ARN or fall back to env/AWS defaults."""
    m = re.match(r"^arn:aws:secretsmanager:([a-z0-9-]+):\\d+:secret:", secret_id or "")
    return (
        m.group(1)
        if m
        else os.environ.get("OPENAI_SECRET_REGION")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-west-2"
    )


def fetch_openai_key() -> str:
    """
    Retrieve the OpenAI key from AWS Secrets Manager.
    Falls back to OPENAI_API_KEY env var for local runs.
    """
    secret_id = os.environ.get("OPENAI_API_KEY_SECRET_ARN")
    if secret_id:
        sm = boto3.client("secretsmanager", region_name=_secret_region(secret_id))
        resp = sm.get_secret_value(SecretId=secret_id)
        val = resp.get("SecretString") or resp.get("SecretBinary")
        if isinstance(val, (bytes, bytearray)):
            val = val.decode("utf-8", errors="ignore")
        if isinstance(val, str):
            try:
                obj = json.loads(val)
                for k in ("OPENAI_API_KEY", "api_key", "token", "key"):
                    if isinstance(obj.get(k), str) and obj[k]:
                        return obj[k]
            except json.JSONDecodeError:
                return val
            if val:
                return val
        raise RuntimeError("Could not decode OpenAI key from secret.")

    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key
    raise RuntimeError("OPENAI_API_KEY_SECRET_ARN or OPENAI_API_KEY is required.")


client = OpenAI(api_key=fetch_openai_key())  # respects OPENAI_BASE_URL too
try:
    m = client.models.retrieve("gpt-4o-mini")
    print("Available:", m.id)
except Exception as e:
    print("Not available:", e)

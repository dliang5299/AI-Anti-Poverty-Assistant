"""
AWS Secrets Manager utility for BenefitsFlow UI
Retrieves secrets from AWS Secrets Manager using IAM permissions.
Inspired by AWS best practices for secret retrieval by name.
"""

import os
import json
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError


def get_secret_from_aws(
    secret_name: str,
    region_name: str = "us-west-2",
    key: Optional[str] = None
) -> Optional[str]:
    """
    Retrieve a secret from AWS Secrets Manager by name.
    
    Args:
        secret_name: Name of the secret (e.g., "benefitsflow-rag/secrets")
        region_name: AWS region where the secret is stored (default: us-west-2)
        key: Optional key to extract from JSON secret (e.g., "OPENAI_API_KEY")
    
    Returns:
        Secret value as string, or None if not found/accessible
    
    Example:
        # Get entire secret as JSON string
        secret = get_secret_from_aws("benefitsflow-rag/secrets")
        
        # Get specific key from JSON secret
        openai_key = get_secret_from_aws("benefitsflow-rag/secrets", key="OPENAI_API_KEY")
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
        # Log error but don't raise - return None for graceful handling
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        print(f"⚠️ [Secrets Manager] Error retrieving secret '{secret_name}': {error_code}")
        return None
    
    # Extract secret string
    secret_string = get_secret_value_response.get('SecretString')
    
    if not secret_string:
        print(f"⚠️ [Secrets Manager] Secret '{secret_name}' has no SecretString")
        return None
    
    # If a specific key is requested, try to parse as JSON and extract the key
    if key:
        try:
            secret_json = json.loads(secret_string)
            if isinstance(secret_json, dict) and key in secret_json:
                return secret_json[key]
            else:
                print(f"⚠️ [Secrets Manager] Key '{key}' not found in secret '{secret_name}'")
                return None
        except json.JSONDecodeError:
            print(f"⚠️ [Secrets Manager] Secret '{secret_name}' is not valid JSON, cannot extract key '{key}'")
            return None
    
    # Return the full secret string
    return secret_string


def get_combined_secrets(
    secret_name: str = "benefitsflow-rag/secrets",
    region_name: str = "us-west-2"
) -> Dict[str, Optional[str]]:
    """
    Retrieve the combined secrets (OpenAI and Pinecone API keys) from AWS.
    
    Args:
        secret_name: Name of the combined secret (default: "benefitsflow-rag/secrets")
        region_name: AWS region where the secret is stored (default: us-west-2)
    
    Returns:
        Dictionary with 'openai_api_key' and 'pinecone_api_key' (None if not found)
    
    Example:
        secrets = get_combined_secrets()
        if secrets['openai_api_key']:
            # Use OpenAI key
            pass
    """
    secret_string = get_secret_from_aws(secret_name, region_name)
    
    if not secret_string:
        return {
            'openai_api_key': None,
            'pinecone_api_key': None
        }
    
    try:
        secret_json = json.loads(secret_string)
        return {
            'openai_api_key': secret_json.get('OPENAI_API_KEY'),
            'pinecone_api_key': secret_json.get('PINECONE_API_KEY')
        }
    except json.JSONDecodeError:
        print(f"⚠️ [Secrets Manager] Secret '{secret_name}' is not valid JSON")
        return {
            'openai_api_key': None,
            'pinecone_api_key': None
        }


def get_openai_key_from_secrets(
    secret_name: str = "benefitsflow-rag/secrets",
    region_name: str = "us-west-2"
) -> Optional[str]:
    """
    Convenience function to get OpenAI API key from combined secret.
    
    Args:
        secret_name: Name of the combined secret
        region_name: AWS region
    
    Returns:
        OpenAI API key or None
    """
    return get_secret_from_aws(secret_name, region_name, key="OPENAI_API_KEY")


def get_pinecone_key_from_secrets(
    secret_name: str = "benefitsflow-rag/secrets",
    region_name: str = "us-west-2"
) -> Optional[str]:
    """
    Convenience function to get Pinecone API key from combined secret.
    
    Args:
        secret_name: Name of the combined secret
        region_name: AWS region
    
    Returns:
        Pinecone API key or None
    """
    return get_secret_from_aws(secret_name, region_name, key="PINECONE_API_KEY")


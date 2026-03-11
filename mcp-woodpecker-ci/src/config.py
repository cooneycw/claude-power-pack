"""Configuration for the MCP Woodpecker CI server."""

import json
import logging
import os

from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def _get_int_env(name: str, default: int) -> int:
    """Get an integer environment variable with validation."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolve_from_aws(secret_name: str, region: str = "us-east-1") -> dict:
    """Fetch secrets from AWS Secrets Manager.

    Returns a dict of key-value pairs, or empty dict on failure.
    """
    try:
        import boto3

        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except Exception as exc:
        logger.warning(f"Could not fetch AWS secret '{secret_name}': {exc}")
        return {}


def _resolve_woodpecker_config() -> tuple[str, str]:
    """Resolve Woodpecker URL and API token from environment or AWS Secrets Manager.

    Priority:
    1. Direct environment variables (WOODPECKER_URL / WOODPECKER_API_TOKEN)
    2. AWS Secrets Manager (AWS_SECRET_NAME env var, default: essent-ai)
    """
    url = os.getenv("WOODPECKER_URL", "")
    token = os.getenv("WOODPECKER_API_TOKEN", "")

    if url and token:
        return url, token

    # Try AWS Secrets Manager
    secret_name = os.getenv("AWS_SECRET_NAME", "essent-ai")
    region = os.getenv("AWS_REGION", "us-east-1")

    secrets = _resolve_from_aws(secret_name, region)
    if secrets:
        if not url:
            url = secrets.get("WOODPECKER_HOST", "")
        if not token:
            token = secrets.get("WOODPECKER_API_TOKEN", "")

    return url, token


_wp_url, _wp_token = _resolve_woodpecker_config()


class Config:
    """Server configuration."""

    SERVER_NAME: str = "mcp-woodpecker-ci"
    SERVER_VERSION: str = "1.0.0"
    SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    SERVER_PORT: int = _get_int_env("MCP_SERVER_PORT", 8085)

    WOODPECKER_URL: str = _wp_url
    WOODPECKER_API_TOKEN: str = _wp_token

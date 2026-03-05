"""Configuration for the MCP Evaluate server."""

import os
from pathlib import Path

from dotenv import load_dotenv

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


class Config:
    """Server configuration."""

    SERVER_NAME: str = "mcp-evaluate-server"
    SERVER_VERSION: str = "1.0.0"
    SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    SERVER_PORT: int = _get_int_env("MCP_SERVER_PORT", 8083)

    # Second Opinion server URL (called internally for multi-model evaluation)
    SECOND_OPINION_URL: str = os.getenv(
        "SECOND_OPINION_URL", "http://127.0.0.1:8080"
    )

    # Request timeout for calling second-opinion server (seconds)
    REQUEST_TIMEOUT: int = _get_int_env("REQUEST_TIMEOUT", 300)

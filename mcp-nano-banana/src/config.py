"""Configuration for the MCP Nano-Banana diagram server."""

import os

from dotenv import load_dotenv
from pathlib import Path

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

    SERVER_NAME: str = "mcp-nano-banana"
    SERVER_VERSION: str = "1.0.0"
    SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    SERVER_PORT: int = _get_int_env("MCP_SERVER_PORT", 8084)

    # Default diagram dimensions (16:9 widescreen)
    DIAGRAM_WIDTH: int = _get_int_env("DIAGRAM_WIDTH", 1920)
    DIAGRAM_HEIGHT: int = _get_int_env("DIAGRAM_HEIGHT", 1080)

"""Configuration management for the Second Opinion MCP Server."""

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class Config:
    """Configuration settings for the MCP server."""

    # Gemini API Configuration
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")

    # Model Selection Strategy
    # Primary: Gemini 3 Pro Preview (best quality)
    # Fallback: Gemini 2.5 Pro (stable, proven)
    GEMINI_MODEL_PRIMARY: str = "gemini-3-pro-preview"
    GEMINI_MODEL_FALLBACK: str = "gemini-2.5-pro"

    # For image/visual analysis (e.g., Playwright screenshots)
    GEMINI_MODEL_IMAGE: str = "gemini-3-pro-image-preview"

    # Gemini API Pricing (per million tokens) - Updated 2025-01
    # Used for cost estimation in responses
    GEMINI_PRICING: Dict[str, Dict[str, float]] = {
        "gemini-3-pro-preview": {"input": 2.50, "output": 10.00},
        "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-3-pro-image-preview": {"input": 2.50, "output": 10.00},
    }

    # Token estimation (characters per token approximation)
    # English text averages ~4 characters per token
    CHARS_PER_TOKEN: int = 4

    # Generation Parameters
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.95
    TOP_K: int = 40

    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_MIN_WAIT: int = 2  # seconds
    RETRY_MAX_WAIT: int = 10  # seconds

    # Server Configuration
    SERVER_NAME: str = "second-opinion-server"
    SERVER_VERSION: str = "1.2.0"  # Bumped for this refactor

    # HTTP/SSE Transport Configuration
    SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", "8080"))

    # Context Caching Configuration
    # Enable Gemini context caching for repeated prompt patterns
    ENABLE_CONTEXT_CACHING: bool = os.getenv("ENABLE_CONTEXT_CACHING", "true").lower() == "true"
    CACHE_TTL_MINUTES: int = int(os.getenv("CACHE_TTL_MINUTES", "60"))  # 1 hour default

    # Session Management Configuration (for multi-turn conversations)
    DEFAULT_SESSION_COST_LIMIT: float = float(os.getenv("DEFAULT_SESSION_COST_LIMIT", "0.50"))
    DEFAULT_MAX_TURNS: int = int(os.getenv("DEFAULT_MAX_TURNS", "10"))
    GLOBAL_DAILY_LIMIT: float = float(os.getenv("GLOBAL_DAILY_LIMIT", "10.00"))
    COST_WARNING_THRESHOLD: float = 0.80  # Warn at 80% of limit

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required. "
                "Get your API key from https://aistudio.google.com/apikey"
            )


# Validate configuration on import
try:
    Config.validate()
except ValueError as e:
    logger.warning(f"Configuration warning: {e}")

"""Configuration management for the Second Opinion MCP Server."""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Load .env file from parent directory (mcp-second-opinion/.env)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

logger = logging.getLogger(__name__)


def _get_int_env(name: str, default: int) -> int:
    """Safely get integer from environment variable with validation."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        result = int(value)
        if result < 0:
            logger.warning(f"{name}={value} is negative, using default {default}")
            return default
        return result
    except ValueError:
        logger.warning(f"{name}={value} is not a valid integer, using default {default}")
        return default


def _get_float_env(name: str, default: float) -> float:
    """Safely get float from environment variable with validation."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        result = float(value)
        if result < 0:
            logger.warning(f"{name}={value} is negative, using default {default}")
            return default
        return result
    except ValueError:
        logger.warning(f"{name}={value} is not a valid number, using default {default}")
        return default


class _SecretStr:
    """
    A string wrapper that prevents accidental exposure in logs/repr.

    The actual value is only accessible via get_secret_value().
    """
    __slots__ = ("_secret_value",)

    def __init__(self, value: Optional[str]):
        self._secret_value = value

    def get_secret_value(self) -> Optional[str]:
        """Get the actual secret value."""
        return self._secret_value

    def __repr__(self) -> str:
        return "SecretStr('**********')" if self._secret_value else "SecretStr(None)"

    def __str__(self) -> str:
        return "**********" if self._secret_value else ""

    def __bool__(self) -> bool:
        return bool(self._secret_value)


class Config:
    """Configuration settings for the MCP server."""

    # ==========================================================================
    # Gemini API Configuration
    # ==========================================================================
    _GEMINI_API_KEY: _SecretStr = _SecretStr(os.getenv("GEMINI_API_KEY"))

    @classmethod
    @property
    def GEMINI_API_KEY(cls) -> Optional[str]:
        """Get the Gemini API key. Use this instead of accessing _GEMINI_API_KEY directly."""
        return cls._GEMINI_API_KEY.get_secret_value()

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

    # ==========================================================================
    # OpenAI API Configuration
    # ==========================================================================
    _OPENAI_API_KEY: _SecretStr = _SecretStr(os.getenv("OPENAI_API_KEY"))

    @classmethod
    @property
    def OPENAI_API_KEY(cls) -> Optional[str]:
        """Get the OpenAI API key. Use this instead of accessing _OPENAI_API_KEY directly."""
        return cls._OPENAI_API_KEY.get_secret_value()

    # OpenAI Models - Using currently available models
    # GPT-4o family (multimodal, fast)
    OPENAI_MODEL_GPT4O: str = "gpt-4o"
    OPENAI_MODEL_GPT4O_MINI: str = "gpt-4o-mini"

    # GPT-4 Turbo (best for complex reasoning)
    OPENAI_MODEL_GPT4_TURBO: str = "gpt-4-turbo"

    # Codex models (use Responses API) - Updated Dec 2025
    # gpt-5.1-codex-max: Most capable for complex coding
    # gpt-5.1-codex-mini: Cost-effective coding model
    # gpt-5-codex: Base codex model
    # o3: Full Codex reasoning agent
    OPENAI_MODEL_CODEX: str = "gpt-5-codex"
    OPENAI_MODEL_CODEX_MAX: str = "gpt-5.1-codex-max"
    OPENAI_MODEL_CODEX_MINI: str = "gpt-5.1-codex-mini"
    OPENAI_MODEL_O3: str = "o3"

    # GPT-5.2 models
    OPENAI_MODEL_GPT52: str = "gpt-5.2"
    OPENAI_MODEL_GPT52_MINI: str = "gpt-5.2-mini"

    # o1 models (reasoning-focused)
    OPENAI_MODEL_O1: str = "o1"
    OPENAI_MODEL_O1_MINI: str = "o1-mini"

    # For image/visual analysis
    OPENAI_MODEL_IMAGE: str = "gpt-4o"

    # Fallback
    OPENAI_MODEL_FALLBACK: str = "gpt-4o-mini"

    # OpenAI API Pricing (per million tokens) - Updated 2025-12
    OPENAI_PRICING: Dict[str, Dict[str, float]] = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        # Codex models (use Responses API)
        "gpt-5.1-codex-max": {"input": 5.00, "output": 20.00},
        "gpt-5.1-codex-mini": {"input": 1.50, "output": 6.00},
        "gpt-5-codex": {"input": 3.00, "output": 12.00},
        "o3": {"input": 10.00, "output": 40.00},
        # Reasoning models
        "o1": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 3.00, "output": 12.00},
        # GPT-5.2 models
        "gpt-5.2": {"input": 5.00, "output": 15.00},
        "gpt-5.2-mini": {"input": 1.00, "output": 4.00},
    }

    # ==========================================================================
    # Available Models for Multi-Model Selection
    # ==========================================================================
    # All models available for second opinion consultation
    AVAILABLE_MODELS: Dict[str, Dict[str, str]] = {
        # Gemini models
        "gemini-3-pro": {
            "provider": "gemini",
            "model_id": "gemini-3-pro-preview",
            "display_name": "Gemini 3 Pro",
            "description": "Google's latest, best for comprehensive analysis",
        },
        "gemini-2.5-pro": {
            "provider": "gemini",
            "model_id": "gemini-2.5-pro",
            "display_name": "Gemini 2.5 Pro",
            "description": "Stable, proven performance",
        },
        # OpenAI GPT-4o family
        "gpt-4o": {
            "provider": "openai",
            "model_id": "gpt-4o",
            "display_name": "GPT-4o",
            "description": "Fast multimodal model, great for code",
        },
        "gpt-4o-mini": {
            "provider": "openai",
            "model_id": "gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "description": "Fast, cost-effective for simpler tasks",
        },
        # OpenAI GPT-4 Turbo
        "gpt-4-turbo": {
            "provider": "openai",
            "model_id": "gpt-4-turbo",
            "display_name": "GPT-4 Turbo",
            "description": "Best for complex reasoning tasks",
        },
        # OpenAI Codex models (uses Responses API)
        "codex-max": {
            "provider": "openai",
            "model_id": "gpt-5.1-codex-max",
            "display_name": "Codex Max",
            "description": "Most capable for complex, long-horizon coding",
        },
        "codex-mini": {
            "provider": "openai",
            "model_id": "gpt-5.1-codex-mini",
            "display_name": "Codex Mini",
            "description": "Cost-effective coding model",
        },
        "o3": {
            "provider": "openai",
            "model_id": "o3",
            "display_name": "o3",
            "description": "Advanced reasoning, powers Codex agent",
        },
        # OpenAI o1 reasoning models
        "o1": {
            "provider": "openai",
            "model_id": "o1",
            "display_name": "o1",
            "description": "Advanced reasoning, best for hard problems",
        },
        "o1-mini": {
            "provider": "openai",
            "model_id": "o1-mini",
            "display_name": "o1 Mini",
            "description": "Faster reasoning model",
        },
        # Base Codex model
        "codex": {
            "provider": "openai",
            "model_id": "gpt-5-codex",
            "display_name": "Codex",
            "description": "Base Codex model for coding tasks",
        },
        # GPT-5.2 models
        "gpt-5.2": {
            "provider": "openai",
            "model_id": "gpt-5.2",
            "display_name": "GPT-5.2",
            "description": "Latest GPT model, excellent reasoning",
        },
        "gpt-5.2-mini": {
            "provider": "openai",
            "model_id": "gpt-5.2-mini",
            "display_name": "GPT-5.2 Mini",
            "description": "Cost-effective GPT-5.2 variant",
        },
    }

    # Default models to use when none specified
    DEFAULT_MODELS: List[str] = ["gemini-3-pro", "gpt-4o"]

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
    SERVER_VERSION: str = "1.6.1"  # Fixed missing model constants

    # HTTP/SSE Transport Configuration (with safe parsing)
    SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    SERVER_PORT: int = _get_int_env("MCP_SERVER_PORT", 8080)

    # Context Caching Configuration
    # Enable Gemini context caching for repeated prompt patterns
    ENABLE_CONTEXT_CACHING: bool = os.getenv("ENABLE_CONTEXT_CACHING", "true").lower() == "true"
    CACHE_TTL_MINUTES: int = _get_int_env("CACHE_TTL_MINUTES", 60)  # 1 hour default

    # Session Management Configuration (for multi-turn conversations)
    DEFAULT_SESSION_COST_LIMIT: float = _get_float_env("DEFAULT_SESSION_COST_LIMIT", 0.50)
    DEFAULT_MAX_TURNS: int = _get_int_env("DEFAULT_MAX_TURNS", 10)
    GLOBAL_DAILY_LIMIT: float = _get_float_env("GLOBAL_DAILY_LIMIT", 10.00)
    COST_WARNING_THRESHOLD: float = 0.80  # Warn at 80% of limit

    # ==========================================================================
    # SSRF Protection Configuration (for fetch_url tool)
    # ==========================================================================

    # Request timeout in seconds (prevents hanging on slow/malicious servers)
    FETCH_URL_TIMEOUT: int = _get_int_env("FETCH_URL_TIMEOUT", 15)

    # Maximum download size in bytes (prevents memory exhaustion)
    # Default: 1MB - sufficient for most documentation pages
    FETCH_URL_MAX_SIZE: int = _get_int_env("FETCH_URL_MAX_SIZE", 1_048_576)

    # Maximum redirects to follow (prevents redirect loops)
    FETCH_URL_MAX_REDIRECTS: int = _get_int_env("FETCH_URL_MAX_REDIRECTS", 5)

    # Pre-approved domains for fetch_url (no user confirmation needed)
    # These are well-known documentation sites considered safe
    FETCH_URL_AUTO_APPROVED_DOMAINS: List[str] = [
        # Code hosting
        "github.com",
        "raw.githubusercontent.com",
        "gitlab.com",
        "bitbucket.org",
        # Python ecosystem
        "docs.python.org",
        "pypi.org",
        "readthedocs.io",
        "readthedocs.org",
        # JavaScript ecosystem
        "npmjs.com",
        "nodejs.org",
        "developer.mozilla.org",
        # Rust ecosystem
        "docs.rs",
        "crates.io",
        # Go ecosystem
        "go.dev",
        "pkg.go.dev",
        # Cloud providers
        "cloud.google.com",
        "aws.amazon.com",
        "learn.microsoft.com",
        "docs.oracle.com",
        # General documentation
        "en.wikipedia.org",
        "stackoverflow.com",
    ]

    # Whether to require user approval for domains not in auto-approved list
    # If True: unknown domains require explicit user approval
    # If False: all domains allowed (less secure, not recommended)
    FETCH_URL_REQUIRE_APPROVAL: bool = True

    # Block internal/private networks (critical SSRF protection - never bypassed)
    FETCH_URL_BLOCK_PRIVATE: bool = True

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        has_gemini = bool(cls.GEMINI_API_KEY)
        has_openai = bool(cls.OPENAI_API_KEY)

        if not has_gemini and not has_openai:
            raise ValueError(
                "At least one API key is required. Set either:\n"
                "  - GEMINI_API_KEY: https://aistudio.google.com/apikey\n"
                "  - OPENAI_API_KEY: https://platform.openai.com/api-keys"
            )

        if not has_gemini:
            logger.warning(
                "GEMINI_API_KEY not set - Gemini models will be unavailable. "
                "Get your API key from https://aistudio.google.com/apikey"
            )

        if not has_openai:
            logger.warning(
                "OPENAI_API_KEY not set - OpenAI/Codex models will be unavailable. "
                "Get your API key from https://platform.openai.com/api-keys"
            )

    @classmethod
    def get_available_model_keys(cls) -> List[str]:
        """Get list of model keys that have valid API keys configured."""
        available = []
        for key, model_info in cls.AVAILABLE_MODELS.items():
            provider = model_info["provider"]
            if provider == "gemini" and cls.GEMINI_API_KEY:
                available.append(key)
            elif provider == "openai" and cls.OPENAI_API_KEY:
                available.append(key)
        return available

    @classmethod
    def get_pricing(cls, model_id: str) -> Dict[str, float]:
        """Get pricing for a model by its model_id."""
        if model_id in cls.GEMINI_PRICING:
            return cls.GEMINI_PRICING[model_id]
        elif model_id in cls.OPENAI_PRICING:
            return cls.OPENAI_PRICING[model_id]
        else:
            # Default fallback pricing
            return {"input": 10.00, "output": 30.00}

    @classmethod
    def is_url_allowed(cls, url: str, approved_domains: List[str] = None) -> tuple[str, str, str]:
        """
        Check if a URL is allowed for fetching (SSRF protection).

        Args:
            url: The URL to check
            approved_domains: Additional domains approved by the user for this session

        Returns:
            Tuple of (status, reason, hostname) where status is one of:
            - "allowed": URL can be fetched
            - "blocked": URL is blocked (private IP, invalid, etc.)
            - "needs_approval": Domain requires user approval
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
        except Exception:
            return "blocked", "Invalid URL format", ""

        # Must be http or https
        if parsed.scheme not in ("http", "https"):
            return "blocked", f"Scheme '{parsed.scheme}' not allowed (only http/https)", ""

        hostname = parsed.hostname or ""

        # Block private/internal networks (ALWAYS - cannot be bypassed)
        if cls.FETCH_URL_BLOCK_PRIVATE:
            import ipaddress
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_reserved:
                    return "blocked", f"Private/internal IP addresses not allowed: {hostname}", hostname
            except ValueError:
                # Not an IP address, check for localhost variants
                if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
                    return "blocked", "Localhost not allowed", hostname
                # Check for internal hostnames
                if hostname.endswith(".local") or hostname.endswith(".internal"):
                    return "blocked", "Internal hostnames not allowed", hostname

        # Check if domain is auto-approved (well-known documentation sites)
        if cls.FETCH_URL_AUTO_APPROVED_DOMAINS:
            is_auto_approved = any(
                hostname == allowed or hostname.endswith(f".{allowed}")
                for allowed in cls.FETCH_URL_AUTO_APPROVED_DOMAINS
            )
            if is_auto_approved:
                return "allowed", "Auto-approved domain", hostname

        # Check if domain was approved by user for this session
        if approved_domains:
            is_user_approved = any(
                hostname == allowed or hostname.endswith(f".{allowed}")
                for allowed in approved_domains
            )
            if is_user_approved:
                return "allowed", "User-approved domain", hostname

        # Domain not in any approved list
        if cls.FETCH_URL_REQUIRE_APPROVAL:
            return "needs_approval", f"Domain '{hostname}' requires user approval", hostname
        else:
            return "allowed", "Approval not required (FETCH_URL_REQUIRE_APPROVAL=False)", hostname


# Validate configuration on import
try:
    Config.validate()
except ValueError as e:
    logger.warning(f"Configuration warning: {e}")

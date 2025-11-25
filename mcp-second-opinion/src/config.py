"""Configuration management for the Second Opinion MCP Server."""

import logging
import os
from typing import Dict, List, Optional

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

    # Gemini API Configuration (wrapped to prevent accidental logging)
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
    SERVER_VERSION: str = "1.4.0"  # Security hardening (secret protection, SSRF mitigation)

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
        if not cls.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required. "
                "Get your API key from https://aistudio.google.com/apikey"
            )

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

"""Configuration management for the Second Opinion MCP Server v2.2.0."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# Load API keys at module level (before class definition)
# This avoids the @classmethod @property pattern which is broken in Python 3.14
_gemini_api_key_secret = _SecretStr(os.getenv("GEMINI_API_KEY"))
_openai_api_key_secret = _SecretStr(os.getenv("OPENAI_API_KEY"))
_anthropic_api_key_secret = _SecretStr(os.getenv("ANTHROPIC_API_KEY"))


class Config:
    """Configuration settings for the MCP server."""

    # ==========================================================================
    # Gemini API Configuration
    # ==========================================================================
    # API key loaded at module level to avoid @classmethod @property issues in Python 3.14
    GEMINI_API_KEY: Optional[str] = _gemini_api_key_secret.get_secret_value()

    # Model Selection Strategy
    # Primary: Gemini 3.5 Flash (fastest, beats 3.1 Pro on coding/agent benchmarks)
    # Fallback: Gemini 3.1 Pro Preview (stable, proven)
    GEMINI_MODEL_PRIMARY: str = "gemini-3.5-flash"
    GEMINI_MODEL_FALLBACK: str = "gemini-3.1-pro-preview"

    # For image/visual analysis (e.g., Playwright screenshots)
    GEMINI_MODEL_IMAGE: str = "gemini-3-pro-image-preview"

    # Gemini API Pricing (per million tokens) - Updated 2026-05
    GEMINI_PRICING: Dict[str, Dict[str, float]] = {
        "gemini-3.5-flash": {"input": 0.15, "output": 0.60},
        "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
        "gemini-3-pro-image-preview": {"input": 2.50, "output": 10.00},
    }

    # ==========================================================================
    # OpenAI API Configuration
    # ==========================================================================
    # API key loaded at module level to avoid @classmethod @property issues in Python 3.14
    OPENAI_API_KEY: Optional[str] = _openai_api_key_secret.get_secret_value()

    # OpenAI Models - Updated May 2026
    # GPT-5.5 family (latest, replaces GPT-5.3 as default)
    OPENAI_MODEL_GPT55: str = "gpt-5.5"
    OPENAI_MODEL_GPT55_PRO: str = "gpt-5.5-pro"

    # GPT-4o family (multimodal, fast)
    OPENAI_MODEL_GPT4O: str = "gpt-4o"
    OPENAI_MODEL_GPT4O_MINI: str = "gpt-4o-mini"

    # Codex models (use Responses API)
    OPENAI_MODEL_CODEX: str = "gpt-5.3-codex"
    OPENAI_MODEL_CODEX_MAX: str = "gpt-5.3-codex"
    OPENAI_MODEL_CODEX_MINI: str = "gpt-5.2-codex"
    OPENAI_MODEL_O3: str = "o3"
    OPENAI_MODEL_O4_MINI: str = "o4-mini"

    # GPT-5.2 models
    OPENAI_MODEL_GPT52: str = "gpt-5.2"
    OPENAI_MODEL_GPT52_MINI: str = "gpt-5.2-mini"

    # For image/visual analysis
    OPENAI_MODEL_IMAGE: str = "gpt-4o"

    # Fallback
    OPENAI_MODEL_FALLBACK: str = "gpt-4o-mini"

    # OpenAI API Pricing (per million tokens) - Updated 2026-05
    OPENAI_PRICING: Dict[str, Dict[str, float]] = {
        # GPT-5.5 family
        "gpt-5.5": {"input": 2.00, "output": 10.00},
        "gpt-5.5-pro": {"input": 5.00, "output": 20.00},
        # GPT-4o family
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        # Codex models (use Responses API)
        "gpt-5.3-codex": {"input": 1.75, "output": 14.00},
        "gpt-5.2-codex": {"input": 1.75, "output": 14.00},
        # Reasoning models (use Responses API)
        "o3": {"input": 2.00, "output": 8.00},
        "o4-mini": {"input": 1.10, "output": 4.40},
        # GPT-5.2 models
        "gpt-5.2": {"input": 1.75, "output": 14.00},
        "gpt-5.2-mini": {"input": 0.25, "output": 2.00},
    }

    # ==========================================================================
    # Anthropic API Configuration
    # ==========================================================================
    # API key loaded at module level to avoid @classmethod @property issues in Python 3.14
    ANTHROPIC_API_KEY: Optional[str] = _anthropic_api_key_secret.get_secret_value()

    # Anthropic Claude Models - Updated May 2026
    ANTHROPIC_MODEL_SONNET: str = "claude-sonnet-4-6"
    ANTHROPIC_MODEL_HAIKU: str = "claude-haiku-4-5-20251001"
    ANTHROPIC_MODEL_OPUS: str = "claude-opus-4-6"

    # Fallback
    ANTHROPIC_MODEL_FALLBACK: str = "claude-haiku-4-5-20251001"

    # Anthropic API Pricing (per million tokens) - Updated 2026-05
    ANTHROPIC_PRICING: Dict[str, Dict[str, float]] = {
        "claude-opus-4-6": {"input": 5.00, "output": 25.00},
        "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    }

    # ==========================================================================
    # Available Models for Multi-Model Selection
    # ==========================================================================
    # All models available for second opinion consultation
    AVAILABLE_MODELS: Dict[str, Dict[str, Any]] = {
        # Gemini models
        "gemini-3.5-flash": {
            "provider": "gemini",
            "model_id": "gemini-3.5-flash",
            "display_name": "Gemini 3.5 Flash",
            "description": "Google's fastest, 4x output speed, beats 3.1 Pro on coding/agent",
            "free": False,
        },
        "gemini-3-pro": {
            "provider": "gemini",
            "model_id": "gemini-3.1-pro-preview",
            "display_name": "Gemini 3.1 Pro",
            "description": "Stable fallback until Gemini 3.5 Pro launches",
            "free": False,
        },
        # Anthropic Claude models
        "claude-sonnet": {
            "provider": "anthropic",
            "model_id": "claude-sonnet-4-6",
            "display_name": "Claude Sonnet 4.6",
            "description": "Fast, excellent for code review and analysis",
            "free": False,
        },
        "claude-haiku": {
            "provider": "anthropic",
            "model_id": "claude-haiku-4-5-20251001",
            "display_name": "Claude Haiku 4.5",
            "description": "Fastest Claude, cost-effective for simpler tasks",
            "free": False,
        },
        "claude-opus": {
            "provider": "anthropic",
            "model_id": "claude-opus-4-6",
            "display_name": "Claude Opus 4.6",
            "description": "Most capable Claude, 1M context, improved agentic coding",
            "free": False,
        },
        # OpenAI GPT-5.5 family
        "gpt-5.5": {
            "provider": "openai",
            "model_id": "gpt-5.5",
            "display_name": "GPT-5.5",
            "description": "Latest GPT model, replaces GPT-5.3 as default",
            "free": False,
        },
        "gpt-5.5-pro": {
            "provider": "openai",
            "model_id": "gpt-5.5-pro",
            "display_name": "GPT-5.5 Pro",
            "description": "Most capable OpenAI model, best for complex tasks",
            "free": False,
        },
        # OpenAI GPT-4o family
        "gpt-4o": {
            "provider": "openai",
            "model_id": "gpt-4o",
            "display_name": "GPT-4o",
            "description": "Fast multimodal model, great for code",
            "free": False,
        },
        "gpt-4o-mini": {
            "provider": "openai",
            "model_id": "gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "description": "Fast, cost-effective for simpler tasks",
            "free": False,
        },
        # OpenAI Codex models (uses Responses API)
        "codex": {
            "provider": "openai",
            "model_id": "gpt-5.3-codex",
            "display_name": "GPT-5.3 Codex",
            "description": "Default Codex model for coding tasks",
            "free": False,
        },
        "codex-mini": {
            "provider": "openai",
            "model_id": "gpt-5.2-codex",
            "display_name": "GPT-5.2 Codex",
            "description": "Cost-effective coding model",
            "free": False,
        },
        # OpenAI reasoning models
        "o3": {
            "provider": "openai",
            "model_id": "o3",
            "display_name": "o3",
            "description": "Advanced reasoning, powers Codex agent",
            "free": False,
        },
        "o4-mini": {
            "provider": "openai",
            "model_id": "o4-mini",
            "display_name": "o4-mini",
            "description": "Fast reasoning model, successor to o3-mini",
            "free": False,
        },
        # GPT-5.2 models
        "gpt-5.2": {
            "provider": "openai",
            "model_id": "gpt-5.2",
            "display_name": "GPT-5.2",
            "description": "Strong GPT model, excellent reasoning",
            "free": False,
        },
        "gpt-5.2-mini": {
            "provider": "openai",
            "model_id": "gpt-5.2-mini",
            "display_name": "GPT-5.2 Mini",
            "description": "Cost-effective GPT-5.2 variant",
            "free": False,
        },
    }

    # Default models to use when none specified
    # Strong cross-provider fan-out across the reliable providers (Gemini/OpenAI)
    DEFAULT_MODELS: List[str] = [
        "gemini-3-pro",
        "gpt-5.2",
        "codex",
        "o4-mini",
    ]

    # Token estimation (characters per token approximation)
    # English text averages ~4 characters per token
    CHARS_PER_TOKEN: int = 4

    # Generation Parameters
    MAX_TOKENS: int = 49152  # 48K base output tokens (detailed verbosity default)

    # Per-model response timeout (seconds) for the multi-model fan-out. Bounds a
    # single hung/slow provider stream so it cannot stall the whole batch. Kept
    # generous by default: a legitimate detailed/in_depth response finishes in
    # ~1-4 min, so 600s never truncates real output and only trips genuine hangs.
    MODEL_RESPONSE_TIMEOUT: int = _get_int_env("MODEL_RESPONSE_TIMEOUT", 600)

    # Provider-level output ceilings used when a model does not specify its own.
    # Empty by default; the kept providers rely on their own per-request limits.
    PROVIDER_MAX_OUTPUT_TOKENS: Dict[str, int] = {}

    # Verbosity-driven output token limits
    VERBOSITY_MAX_TOKENS: Dict[str, int] = {
        "brief": 4096,
        "detailed": 49152,    # 48K
        "in_depth": 65536,    # 64K
    }

    # Synonyms that map to canonical verbosity names
    VERBOSITY_SYNONYMS: Dict[str, str] = {
        "in-depth": "in_depth",
        "comprehensive": "in_depth",
        "thorough": "in_depth",
        "exhaustive": "in_depth",
    }
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.95
    TOP_K: int = 40

    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_MIN_WAIT: int = 2  # seconds
    RETRY_MAX_WAIT: int = 10  # seconds

    # Server Configuration
    SERVER_NAME: str = "second-opinion-server"
    SERVER_VERSION: str = "2.2.0"  # Model catalog update May 2026

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

    # Provider API key map for dynamic availability checks
    _PROVIDER_API_KEY_MAP: Dict[str, str] = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        has_any = any(
            bool(getattr(cls, attr, None))
            for attr in [
                "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
            ]
        )

        if not has_any:
            raise ValueError(
                "At least one API key is required. Set any of:\n"
                "  - GEMINI_API_KEY: https://aistudio.google.com/apikey\n"
                "  - OPENAI_API_KEY: https://platform.openai.com/api-keys\n"
                "  - ANTHROPIC_API_KEY: https://console.anthropic.com/settings/keys"
            )

        _key_info = {
            "GEMINI_API_KEY": ("Gemini", "https://aistudio.google.com/apikey"),
            "OPENAI_API_KEY": ("OpenAI/Codex", "https://platform.openai.com/api-keys"),
            "ANTHROPIC_API_KEY": ("Claude", "https://console.anthropic.com/settings/keys"),
        }
        for env_var, (name, url) in _key_info.items():
            if not getattr(cls, env_var, None):
                logger.warning(
                    f"{env_var} not set - {name} models will be unavailable. "
                    f"Get your API key from {url}"
                )

    @classmethod
    def get_available_model_keys(cls) -> List[str]:
        """Get list of model keys that have valid API keys configured."""
        available = []
        for key, model_info in cls.AVAILABLE_MODELS.items():
            provider = model_info["provider"]
            api_key_attr = cls._PROVIDER_API_KEY_MAP.get(provider)
            if api_key_attr and getattr(cls, api_key_attr, None):
                available.append(key)
        return available

    @classmethod
    def get_pricing(cls, model_id: str) -> Dict[str, float]:
        """Get pricing for a model by its model_id."""
        for pricing_table in [
            cls.GEMINI_PRICING,
            cls.OPENAI_PRICING,
            cls.ANTHROPIC_PRICING,
        ]:
            if model_id in pricing_table:
                return pricing_table[model_id]
        return {"input": 10.00, "output": 30.00}

    @classmethod
    def resolve_verbosity(cls, verbosity: str) -> tuple[str, int]:
        """
        Resolve a verbosity string to its canonical name and max_tokens.

        Handles synonyms like "in-depth", "comprehensive", "thorough", "exhaustive"
        which all map to "in_depth".

        Returns:
            Tuple of (canonical_verbosity_name, max_output_tokens)
        """
        canonical = cls.VERBOSITY_SYNONYMS.get(verbosity, verbosity)
        max_tokens = cls.VERBOSITY_MAX_TOKENS.get(canonical, cls.MAX_TOKENS)
        return canonical, max_tokens

    @classmethod
    def get_model_max_output_tokens(cls, model_key: str) -> Optional[int]:
        """Return the configured output-token ceiling for a model, if one exists."""
        model_info = cls.AVAILABLE_MODELS.get(model_key)
        if not model_info:
            return None

        ceiling = model_info.get("max_output_tokens")
        if isinstance(ceiling, int):
            return ceiling

        provider = model_info.get("provider")
        if isinstance(provider, str):
            return cls.PROVIDER_MAX_OUTPUT_TOKENS.get(provider)

        return None

    @classmethod
    def clamp_max_tokens_for_model(cls, model_key: str, requested_max_tokens: int) -> tuple[int, Optional[int]]:
        """
        Clamp requested output tokens to the provider/model ceiling.

        Returns:
            Tuple of (effective_max_tokens, configured_ceiling).
        """
        ceiling = cls.get_model_max_output_tokens(model_key)
        if ceiling is None:
            return requested_max_tokens, None
        return min(requested_max_tokens, ceiling), ceiling

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

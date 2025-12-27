"""Base classes for secrets management.

This module provides:
- SecretValue: A wrapper that masks secrets in __repr__ and __str__
- SecretsProvider: Abstract interface for credential providers (AWS, env, etc.)
- SecretsError: Base exception for secrets-related errors

Usage:
    from lib.creds.base import SecretValue, SecretsProvider

    # Wrap a secret value
    api_key = SecretValue("sk-abc123...")
    print(api_key)  # Output: ****
    actual = api_key.get_secret_value()  # Returns real value

Pattern adapted from:
    mcp-second-opinion/src/config.py:50-72
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SecretsError(Exception):
    """Base exception for secrets-related errors."""

    pass


class ProviderNotAvailableError(SecretsError):
    """Raised when a secrets provider is not configured or available."""

    pass


class SecretNotFoundError(SecretsError):
    """Raised when a requested secret does not exist."""

    pass


class SecretValue:
    """A string wrapper that prevents accidental exposure in logs/repr.

    The actual value is only accessible via get_secret_value().
    This provides defense-in-depth against accidental credential leaks.

    Example:
        >>> password = SecretValue("super_secret_123")
        >>> print(password)
        ****
        >>> repr(password)
        "SecretValue('****')"
        >>> password.get_secret_value()
        'super_secret_123'
        >>> bool(password)
        True
    """

    __slots__ = ("_secret_value",)

    def __init__(self, value: Optional[str]) -> None:
        """Initialize with a secret value.

        Args:
            value: The actual secret string, or None if not set.
        """
        self._secret_value = value

    def get_secret_value(self) -> Optional[str]:
        """Get the actual secret value.

        This is the ONLY way to access the real value.
        Use sparingly and never log the result.

        Returns:
            The actual secret string, or None if not set.
        """
        return self._secret_value

    def __repr__(self) -> str:
        """Return masked representation for debugging."""
        return "SecretValue('****')" if self._secret_value else "SecretValue(None)"

    def __str__(self) -> str:
        """Return masked string for display."""
        return "****" if self._secret_value else ""

    def __bool__(self) -> bool:
        """Check if secret has a value without exposing it."""
        return bool(self._secret_value)

    def __eq__(self, other: object) -> bool:
        """Compare secrets without exposing values in error messages."""
        if isinstance(other, SecretValue):
            return self._secret_value == other._secret_value
        return False

    def __hash__(self) -> int:
        """Hash based on value (for use in sets/dicts)."""
        return hash(self._secret_value)

    def __len__(self) -> int:
        """Return length of secret without exposing it."""
        return len(self._secret_value) if self._secret_value else 0


class SecretsProvider(ABC):
    """Abstract interface for secrets providers.

    Implement this interface to add support for different secret backends:
    - Environment variables (.env files)
    - AWS Secrets Manager
    - HashiCorp Vault
    - Azure Key Vault
    - Google Cloud Secret Manager

    Example:
        class MyProvider(SecretsProvider):
            @property
            def name(self) -> str:
                return "my-provider"

            def is_available(self) -> bool:
                return os.getenv("MY_PROVIDER_TOKEN") is not None

            def get_secret(self, secret_id: str) -> Dict[str, Any]:
                return {"key": "value", ...}
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name for logging/display.

        Returns:
            Human-readable provider name (e.g., "aws-secrets-manager").
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available.

        This should be a lightweight check (no network calls if possible).
        Used to determine which provider to use in fallback chains.

        Returns:
            True if provider is configured and ready to use.
        """
        pass

    @abstractmethod
    def get_secret(self, secret_id: str) -> Dict[str, Any]:
        """Retrieve a secret by ID.

        Args:
            secret_id: The identifier for the secret (varies by provider).
                       For AWS: the secret name or ARN.
                       For env: the prefix for environment variables.

        Returns:
            Dictionary containing the secret fields.
            Structure depends on how the secret was stored.

        Raises:
            SecretNotFoundError: If secret doesn't exist.
            SecretsError: For other retrieval failures.
        """
        pass

    def get_secret_value(self, secret_id: str, field: str) -> Optional[str]:
        """Retrieve a single field from a secret.

        Convenience method for getting one value from a multi-field secret.

        Args:
            secret_id: The secret identifier.
            field: The field name within the secret.

        Returns:
            The field value, or None if field doesn't exist.

        Raises:
            SecretNotFoundError: If secret doesn't exist.
            SecretsError: For other retrieval failures.
        """
        secret = self.get_secret(secret_id)
        return secret.get(field)

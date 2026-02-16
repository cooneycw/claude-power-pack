"""Base classes for secrets management.

This module provides:
- SecretValue: A wrapper that masks secrets in __repr__ and __str__
- SecretBundle: A collection of key-value secrets for a project
- SecretsProvider: Abstract interface for credential providers (AWS, env, etc.)
- BundleProvider: Extended interface with bundle CRUD operations
- ProviderCaps: Capability flags for provider feature detection
- SecretsError: Base exception for secrets-related errors

Usage:
    from lib.creds.base import SecretValue, SecretsProvider, SecretBundle

    # Wrap a secret value
    api_key = SecretValue("sk-abc123...")
    print(api_key)  # Output: ****
    actual = api_key.get_secret_value()  # Returns real value

    # Work with bundles
    bundle = SecretBundle(project_id="my-app", secrets={"DB_PASSWORD": "secret"})
    print(bundle)  # Keys visible, values masked
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

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


@dataclass
class SecretBundle:
    """A collection of key-value secrets for a project.

    Stores secrets as a flat dict of key -> value pairs.
    Values are always stored as plain strings internally but
    displayed masked in repr/str output.
    """

    project_id: str
    secrets: dict[str, str] = field(default_factory=dict)
    version: str | None = None
    updated_at: datetime | None = None
    provider: str = ""

    @property
    def keys(self) -> list[str]:
        """List all secret key names."""
        return list(self.secrets.keys())

    def get(self, key: str) -> str | None:
        """Get a secret value by key."""
        return self.secrets.get(key)

    def set(self, key: str, value: str) -> None:
        """Set a secret value."""
        self.secrets[key] = value
        self.updated_at = datetime.now(timezone.utc)

    def delete(self, key: str) -> bool:
        """Delete a secret key. Returns True if it existed."""
        if key in self.secrets:
            del self.secrets[key]
            self.updated_at = datetime.now(timezone.utc)
            return True
        return False

    def __len__(self) -> int:
        return len(self.secrets)

    def __repr__(self) -> str:
        keys = ", ".join(self.keys)
        return f"SecretBundle(project_id={self.project_id!r}, keys=[{keys}])"

    def __str__(self) -> str:
        lines = [f"Project: {self.project_id} ({len(self.secrets)} secrets)"]
        for key in sorted(self.secrets):
            lines.append(f"  {key} = ****")
        return "\n".join(lines)


@dataclass(frozen=True)
class ProviderCaps:
    """Capability flags for a secrets provider."""

    can_read: bool = True
    can_write: bool = False
    can_delete: bool = False
    can_list: bool = False
    can_rotate: bool = False
    supports_versions: bool = False


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


class BundleProvider(SecretsProvider):
    """Extended provider interface with bundle CRUD operations.

    Providers that support full secrets management (not just read)
    should inherit from this class.
    """

    @abstractmethod
    def caps(self) -> ProviderCaps:
        """Return capability flags for this provider."""
        pass

    @abstractmethod
    def get_bundle(
        self, project_id: str, version: str | None = None
    ) -> SecretBundle:
        """Get all secrets for a project as a bundle.

        Args:
            project_id: The project identifier.
            version: Optional version to retrieve (provider-specific).

        Returns:
            SecretBundle with all project secrets.

        Raises:
            SecretNotFoundError: If project has no secrets.
        """
        pass

    @abstractmethod
    def put_bundle(
        self,
        bundle: SecretBundle,
        mode: Literal["merge", "replace"] = "merge",
    ) -> SecretBundle:
        """Write secrets for a project.

        Args:
            bundle: The secrets to write.
            mode: "merge" updates only provided keys, "replace" overwrites all.

        Returns:
            Updated SecretBundle with new version/timestamp.
        """
        pass

    @abstractmethod
    def delete_key(self, project_id: str, key: str) -> None:
        """Delete a single secret key from a project.

        Args:
            project_id: The project identifier.
            key: The secret key to delete.

        Raises:
            SecretNotFoundError: If key doesn't exist.
        """
        pass

    @abstractmethod
    def list_keys(self, project_id: str) -> list[str]:
        """List all secret key names for a project.

        Args:
            project_id: The project identifier.

        Returns:
            List of secret key names.
        """
        pass

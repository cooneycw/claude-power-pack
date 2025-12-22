"""Environment variable secrets provider.

This provider reads secrets from:
1. Environment variables
2. .env files (if python-dotenv is available)

Convention: Secrets are stored as PREFIX_FIELD environment variables.
Example: For secret_id="DB", looks for DB_HOST, DB_USER, DB_PASSWORD, etc.

Usage:
    from lib.secrets.providers import EnvSecretsProvider

    provider = EnvSecretsProvider()
    creds = provider.get_secret("DB")
    # Returns: {"host": "...", "user": "...", "password": "...", ...}
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import SecretsProvider, SecretNotFoundError

logger = logging.getLogger(__name__)

# Try to import dotenv, but it's optional
try:
    from dotenv import load_dotenv, dotenv_values

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    load_dotenv = None  # type: ignore
    dotenv_values = None  # type: ignore


class EnvSecretsProvider(SecretsProvider):
    """Secrets provider using environment variables and .env files.

    This provider:
    - Is always available (environment variables always exist)
    - Loads .env files if python-dotenv is installed
    - Uses PREFIX_FIELD convention for variable names

    Example:
        # For secret_id="DATABASE", looks for:
        # DATABASE_HOST, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD, etc.
    """

    def __init__(
        self,
        env_paths: Optional[List[Path]] = None,
        auto_load: bool = True,
    ) -> None:
        """Initialize the environment provider.

        Args:
            env_paths: List of .env file paths to load. If None, searches for
                       .env in current directory and parent directories.
            auto_load: If True, automatically load .env files on init.
        """
        self._env_paths = env_paths or []
        self._loaded = False

        if auto_load:
            self._load_env_files()

    def _load_env_files(self) -> None:
        """Load .env files if dotenv is available."""
        if not DOTENV_AVAILABLE:
            logger.debug("python-dotenv not installed, skipping .env loading")
            return

        if self._loaded:
            return

        # Load specified paths
        for path in self._env_paths:
            if path.exists():
                load_dotenv(path)
                logger.debug(f"Loaded environment from {path}")

        # Also try common locations
        common_paths = [
            Path.cwd() / ".env",
            Path.cwd().parent / ".env",
            Path.home() / ".env",
        ]

        for path in common_paths:
            if path.exists() and path not in self._env_paths:
                load_dotenv(path)
                logger.debug(f"Loaded environment from {path}")

        self._loaded = True

    @property
    def name(self) -> str:
        """Return provider name."""
        return "env-file"

    def is_available(self) -> bool:
        """Environment provider is always available."""
        return True

    def get_secret(self, secret_id: str) -> Dict[str, Any]:
        """Get secret from environment variables.

        Uses PREFIX_FIELD convention. For secret_id="DB", looks for
        environment variables like DB_HOST, DB_USER, DB_PASSWORD.

        Args:
            secret_id: The prefix for environment variables.

        Returns:
            Dictionary of field -> value mappings.

        Raises:
            SecretNotFoundError: If no variables with this prefix exist.
        """
        prefix = secret_id.upper().replace("-", "_")
        result: Dict[str, Any] = {}

        # Gather all env vars with this prefix
        for key, value in os.environ.items():
            if key.startswith(f"{prefix}_"):
                field = key[len(prefix) + 1 :].lower()
                result[field] = value

        # Also check .env file directly for values not yet in environment
        if DOTENV_AVAILABLE and dotenv_values:
            for path in self._env_paths:
                if path.exists():
                    env_values = dotenv_values(path)
                    for key, value in env_values.items():
                        if key.startswith(f"{prefix}_") and value is not None:
                            field = key[len(prefix) + 1 :].lower()
                            if field not in result:  # Don't override env vars
                                result[field] = value

        if not result:
            raise SecretNotFoundError(
                f"No environment variables found with prefix '{prefix}_'. "
                f"Expected variables like {prefix}_HOST, {prefix}_USER, etc."
            )

        logger.debug(f"Found {len(result)} fields for secret '{secret_id}'")
        return result

    def get_database_secret(self, secret_id: str = "DB") -> Dict[str, Any]:
        """Convenience method for database credentials.

        Normalizes field names to standard database credential format.

        Args:
            secret_id: The prefix (default: "DB")

        Returns:
            Dictionary with normalized keys: host, port, database, username, password
        """
        raw = self.get_secret(secret_id)

        # Normalize field names
        return {
            "host": raw.get("host", raw.get("hostname", "localhost")),
            "port": int(raw.get("port", 5432)),
            "database": raw.get("database", raw.get("name", raw.get("db", ""))),
            "username": raw.get("user", raw.get("username", "")),
            "password": raw.get("password", raw.get("pass", "")),
        }

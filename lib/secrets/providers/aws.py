"""AWS Secrets Manager provider.

This provider fetches secrets from AWS Secrets Manager.
Requires boto3 and valid AWS credentials.

Usage:
    from lib.secrets.providers import AWSSecretsProvider

    provider = AWSSecretsProvider(region="us-east-1")
    if provider.is_available():
        creds = provider.get_secret("prod/database")

Pattern adapted from:
    nhl-api/src/nhl_api/config/secrets.py
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, Optional

from ..base import (
    SecretsProvider,
    SecretsError,
    SecretNotFoundError,
    ProviderNotAvailableError,
)

logger = logging.getLogger(__name__)

# Try to import boto3, but it's optional
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore
    NoCredentialsError = Exception  # type: ignore


class AWSSecretsProvider(SecretsProvider):
    """Secrets provider using AWS Secrets Manager.

    This provider:
    - Requires boto3 and valid AWS credentials
    - Caches secrets to minimize API calls
    - Supports both secret names and ARNs

    AWS credentials can be provided via:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - IAM role (when running on EC2/ECS/Lambda)
    - AWS credentials file (~/.aws/credentials)
    """

    def __init__(
        self,
        region: Optional[str] = None,
        cache_enabled: bool = True,
    ) -> None:
        """Initialize the AWS provider.

        Args:
            region: AWS region (default: from AWS_DEFAULT_REGION or us-east-1)
            cache_enabled: If True, cache secrets to minimize API calls
        """
        self._region = region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self._cache_enabled = cache_enabled
        self._client: Any = None
        self._available: Optional[bool] = None

    def _get_client(self) -> Any:
        """Get or create boto3 Secrets Manager client."""
        if not BOTO3_AVAILABLE:
            raise ProviderNotAvailableError(
                "boto3 is not installed. Install with: pip install boto3"
            )

        if self._client is None:
            self._client = boto3.client("secretsmanager", region_name=self._region)

        return self._client

    @property
    def name(self) -> str:
        """Return provider name."""
        return "aws-secrets-manager"

    def is_available(self) -> bool:
        """Check if AWS credentials are configured.

        Performs a lightweight check by listing secrets (max 1 result).
        Caches the result to avoid repeated API calls.

        Returns:
            True if AWS credentials are valid and accessible.
        """
        if self._available is not None:
            return self._available

        if not BOTO3_AVAILABLE:
            self._available = False
            logger.debug("boto3 not installed, AWS provider unavailable")
            return False

        try:
            client = self._get_client()
            # Lightweight check - just verify credentials work
            client.list_secrets(MaxResults=1)
            self._available = True
            logger.debug("AWS Secrets Manager available")
        except NoCredentialsError:
            self._available = False
            logger.debug("No AWS credentials configured")
        except ClientError as e:
            # Access denied still means credentials are valid
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "AccessDeniedException":
                self._available = True
                logger.debug("AWS credentials valid (access denied for list)")
            else:
                self._available = False
                logger.debug(f"AWS error: {error_code}")
        except Exception as e:
            self._available = False
            logger.debug(f"AWS check failed: {e}")

        return self._available

    def get_secret(self, secret_id: str) -> Dict[str, Any]:
        """Retrieve secret from AWS Secrets Manager.

        Args:
            secret_id: The secret name or ARN.

        Returns:
            Dictionary containing the secret fields.

        Raises:
            SecretNotFoundError: If secret doesn't exist.
            ProviderNotAvailableError: If AWS is not configured.
            SecretsError: For other retrieval failures.
        """
        if self._cache_enabled:
            return self._get_secret_cached(secret_id)
        return self._get_secret_uncached(secret_id)

    @lru_cache(maxsize=16)
    def _get_secret_cached(self, secret_id: str) -> Dict[str, Any]:
        """Cached version of secret retrieval."""
        return self._get_secret_uncached(secret_id)

    def _get_secret_uncached(self, secret_id: str) -> Dict[str, Any]:
        """Retrieve secret without caching."""
        if not self.is_available():
            raise ProviderNotAvailableError(
                "AWS Secrets Manager is not available. "
                "Ensure AWS credentials are configured."
            )

        try:
            client = self._get_client()
            response = client.get_secret_value(SecretId=secret_id)

            # Parse the secret string (expected to be JSON)
            secret_string = response.get("SecretString", "{}")
            return json.loads(secret_string)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "ResourceNotFoundException":
                raise SecretNotFoundError(
                    f"Secret '{secret_id}' not found in AWS Secrets Manager"
                ) from e
            elif error_code == "AccessDeniedException":
                raise SecretsError(
                    f"Access denied to secret '{secret_id}'. "
                    "Check IAM permissions."
                ) from e
            elif error_code == "DecryptionFailure":
                raise SecretsError(
                    f"Failed to decrypt secret '{secret_id}'. "
                    "Check KMS permissions."
                ) from e
            else:
                raise SecretsError(
                    f"AWS error retrieving '{secret_id}': {error_code} - {error_msg}"
                ) from e

        except json.JSONDecodeError as e:
            raise SecretsError(
                f"Secret '{secret_id}' is not valid JSON. "
                "Secrets must be stored as JSON objects."
            ) from e

    def clear_cache(self) -> None:
        """Clear the secrets cache.

        Call this after rotating secrets to ensure fresh values.
        """
        self._get_secret_cached.cache_clear()
        logger.debug("AWS secrets cache cleared")

    def get_database_secret(
        self,
        secret_id: str,
        host_key: str = "host",
        port_key: str = "port",
        database_key: str = "database",
        username_key: str = "username",
        password_key: str = "password",
    ) -> Dict[str, Any]:
        """Convenience method for database credentials.

        Normalizes field names from various AWS RDS secret formats.

        Args:
            secret_id: The secret name or ARN
            host_key: Key for host in secret (default: "host")
            port_key: Key for port in secret (default: "port")
            database_key: Key for database in secret (default: "database")
            username_key: Key for username in secret (default: "username")
            password_key: Key for password in secret (default: "password")

        Returns:
            Dictionary with normalized keys: host, port, database, username, password
        """
        raw = self.get_secret(secret_id)

        # Support both RDS-style and generic naming
        return {
            "host": raw.get(host_key, raw.get("POSTGRES_HOST", "localhost")),
            "port": int(raw.get(port_key, raw.get("POSTGRES_PORT", 5432))),
            "database": raw.get(
                database_key, raw.get("POSTGRES_DB", raw.get("dbname", ""))
            ),
            "username": raw.get(
                username_key, raw.get("POSTGRES_USER", raw.get("user", ""))
            ),
            "password": raw.get(
                password_key, raw.get("POSTGRES_PASSWORD", raw.get("pass", ""))
            ),
        }

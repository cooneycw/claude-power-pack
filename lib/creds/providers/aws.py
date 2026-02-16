"""AWS Secrets Manager provider.

This provider fetches secrets from AWS Secrets Manager.
Requires boto3 and valid AWS credentials. Supports per-project
IAM role assumption for isolation.

Usage:
    from lib.creds.providers import AWSSecretsProvider

    provider = AWSSecretsProvider(region="us-east-1")
    if provider.is_available():
        creds = provider.get_secret("prod/database")

    # With role assumption for project isolation
    provider = AWSSecretsProvider(
        role_arn="arn:aws:iam::123456789012:role/cpp-my-project-dev"
    )
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Tuple

from ..base import (
    BundleProvider,
    ProviderCaps,
    SecretBundle,
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


class AWSSecretsProvider(BundleProvider):
    """Secrets provider using AWS Secrets Manager.

    This provider:
    - Requires boto3 and valid AWS credentials
    - Caches secrets to minimize API calls (with TTL)
    - Supports both secret names and ARNs
    - Supports per-project IAM role assumption for isolation

    AWS credentials can be provided via:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - IAM role (when running on EC2/ECS/Lambda)
    - AWS credentials file (~/.aws/credentials)
    """

    # Default cache TTL: 5 minutes (300 seconds)
    DEFAULT_CACHE_TTL = 300

    # Secret naming convention for bundle storage
    BUNDLE_PREFIX = "claude-power-pack"

    def __init__(
        self,
        region: Optional[str] = None,
        cache_enabled: bool = True,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        role_arn: Optional[str] = None,
    ) -> None:
        """Initialize the AWS provider.

        Args:
            region: AWS region (default: from AWS_DEFAULT_REGION or us-east-1)
            cache_enabled: If True, cache secrets to minimize API calls
            cache_ttl: Cache time-to-live in seconds (default: 300)
            role_arn: Optional IAM role ARN to assume for project isolation.
        """
        self._region = region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self._cache_enabled = cache_enabled
        self._cache_ttl = cache_ttl
        self._role_arn = role_arn
        self._client: Any = None
        self._available: Optional[bool] = None
        # Time-based cache: {secret_id: (value, timestamp)}
        self._cache: Dict[str, Tuple[Dict[str, Any], float]] = {}

    def _get_client(self) -> Any:
        """Get or create boto3 Secrets Manager client."""
        if not BOTO3_AVAILABLE:
            raise ProviderNotAvailableError(
                "boto3 is not installed. Install with: pip install boto3"
            )

        if self._client is None:
            if self._role_arn:
                sts = boto3.client("sts", region_name=self._region)
                assumed = sts.assume_role(
                    RoleArn=self._role_arn,
                    RoleSessionName="cpp-secrets",
                )
                creds = assumed["Credentials"]
                self._client = boto3.client(
                    "secretsmanager",
                    region_name=self._region,
                    aws_access_key_id=creds["AccessKeyId"],
                    aws_secret_access_key=creds["SecretAccessKey"],
                    aws_session_token=creds["SessionToken"],
                )
            else:
                self._client = boto3.client(
                    "secretsmanager", region_name=self._region
                )

        return self._client

    def caps(self) -> ProviderCaps:
        return ProviderCaps(
            can_read=True,
            can_write=True,
            can_delete=True,
            can_list=True,
            can_rotate=True,
            supports_versions=True,
        )

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
            ValueError: If secret_id is invalid.
        """
        # Input validation
        if not secret_id or not isinstance(secret_id, str):
            raise ValueError("secret_id must be a non-empty string")
        if len(secret_id) > 512:
            raise ValueError("secret_id too long (max 512 characters)")
        # AWS secret names/ARNs: alphanumeric, hyphens, underscores, slashes, plus, equals, periods, at, colon
        # ARNs start with "arn:" and have colons, so we need to allow those
        if not secret_id.startswith("arn:"):
            # For non-ARN names, be more restrictive
            if not all(c.isalnum() or c in "-_/+.@" for c in secret_id):
                raise ValueError(
                    "secret_id must contain only alphanumeric characters, "
                    "hyphens, underscores, slashes, plus, periods, or at-signs"
                )

        if self._cache_enabled:
            return self._get_secret_cached(secret_id)
        return self._get_secret_uncached(secret_id)

    def _get_secret_cached(self, secret_id: str) -> Dict[str, Any]:
        """Cached version of secret retrieval with TTL."""
        now = time.time()

        # Check if cached and not expired
        if secret_id in self._cache:
            value, timestamp = self._cache[secret_id]
            age = now - timestamp
            if age < self._cache_ttl:
                logger.debug(f"Cache hit for '{secret_id}' (age: {age:.1f}s)")
                return value
            else:
                logger.debug(f"Cache expired for '{secret_id}' (age: {age:.1f}s)")

        # Fetch and cache
        value = self._get_secret_uncached(secret_id)
        self._cache[secret_id] = (value, now)
        logger.debug(f"Cached secret '{secret_id}' (TTL: {self._cache_ttl}s)")
        return value

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
                logger.error(f"Secret '{secret_id}' not found in AWS Secrets Manager")
                raise SecretNotFoundError(
                    f"Secret '{secret_id}' not found in AWS Secrets Manager"
                ) from e
            elif error_code == "AccessDeniedException":
                logger.error(f"Access denied to secret '{secret_id}' - check IAM permissions")
                raise SecretsError(
                    f"Access denied to secret '{secret_id}'. "
                    "Check IAM permissions."
                ) from e
            elif error_code == "DecryptionFailure":
                logger.error(f"Failed to decrypt secret '{secret_id}' - check KMS permissions")
                raise SecretsError(
                    f"Failed to decrypt secret '{secret_id}'. "
                    "Check KMS permissions."
                ) from e
            else:
                logger.error(f"AWS error retrieving '{secret_id}': {error_code} - {error_msg}")
                raise SecretsError(
                    f"AWS error retrieving '{secret_id}': {error_code} - {error_msg}"
                ) from e

        except json.JSONDecodeError as e:
            logger.error(f"Secret '{secret_id}' is not valid JSON")
            raise SecretsError(
                f"Secret '{secret_id}' is not valid JSON. "
                "Secrets must be stored as JSON objects."
            ) from e

    def clear_cache(self) -> None:
        """Clear the secrets cache.

        Call this after rotating secrets to ensure fresh values.
        """
        self._cache.clear()
        logger.info("AWS secrets cache cleared")

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

    # --- Bundle interface ---

    def _bundle_secret_name(self, project_id: str) -> str:
        """Get the AWS secret name for a project bundle."""
        return f"{self.BUNDLE_PREFIX}/{project_id}"

    def get_bundle(
        self, project_id: str, version: str | None = None
    ) -> SecretBundle:
        """Get all secrets for a project as a bundle."""
        secret_name = self._bundle_secret_name(project_id)

        try:
            kwargs: dict[str, Any] = {"SecretId": secret_name}
            if version:
                kwargs["VersionId"] = version

            client = self._get_client()
            response = client.get_secret_value(**kwargs)
            secrets = json.loads(response.get("SecretString", "{}"))

            return SecretBundle(
                project_id=project_id,
                secrets=secrets,
                version=response.get("VersionId"),
                updated_at=datetime.now(timezone.utc),
                provider=self.name,
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ResourceNotFoundException":
                return SecretBundle(
                    project_id=project_id,
                    secrets={},
                    provider=self.name,
                )
            raise SecretsError(f"AWS error: {error_code}") from e

    def put_bundle(
        self,
        bundle: SecretBundle,
        mode: Literal["merge", "replace"] = "merge",
    ) -> SecretBundle:
        """Write secrets for a project to AWS Secrets Manager."""
        secret_name = self._bundle_secret_name(bundle.project_id)
        client = self._get_client()

        if mode == "merge":
            existing = self.get_bundle(bundle.project_id)
            merged = dict(existing.secrets)
            merged.update(bundle.secrets)
        else:
            merged = dict(bundle.secrets)

        secret_string = json.dumps(merged)

        try:
            response = client.put_secret_value(
                SecretId=secret_name,
                SecretString=secret_string,
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ResourceNotFoundException":
                # Secret doesn't exist yet — create it
                response = client.create_secret(
                    Name=secret_name,
                    SecretString=secret_string,
                )
            else:
                raise SecretsError(f"AWS error writing secrets: {error_code}") from e

        # Clear cache for this secret
        self._cache.pop(secret_name, None)

        return SecretBundle(
            project_id=bundle.project_id,
            secrets=merged,
            version=response.get("VersionId"),
            updated_at=datetime.now(timezone.utc),
            provider=self.name,
        )

    def delete_key(self, project_id: str, key: str) -> None:
        """Delete a single key from the project bundle."""
        bundle = self.get_bundle(project_id)
        if key not in bundle.secrets:
            raise SecretNotFoundError(
                f"Key '{key}' not found in project '{project_id}'"
            )

        del bundle.secrets[key]
        self.put_bundle(bundle, mode="replace")

    def list_keys(self, project_id: str) -> list[str]:
        """List all secret key names for a project."""
        bundle = self.get_bundle(project_id)
        return sorted(bundle.secrets.keys())

    def bootstrap_iam(
        self, project_id: str, account_id: str, region: str | None = None
    ) -> dict[str, str]:
        """Generate IAM policy for project isolation.

        Returns a dict with policy_document and role_name that
        can be used to create an IAM role.

        Args:
            project_id: The project identifier.
            account_id: AWS account ID.
            region: AWS region (defaults to provider region).

        Returns:
            Dict with 'role_name' and 'policy_document' (JSON string).
        """
        region = region or self._region
        role_name = f"cpp-{project_id}-dev"
        secret_arn_pattern = (
            f"arn:aws:secretsmanager:{region}:{account_id}"
            f":secret:{self.BUNDLE_PREFIX}/{project_id}*"
        )

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:PutSecretValue",
                        "secretsmanager:CreateSecret",
                        "secretsmanager:DeleteSecret",
                        "secretsmanager:DescribeSecret",
                        "secretsmanager:ListSecretVersionIds",
                    ],
                    "Resource": secret_arn_pattern,
                }
            ],
        }

        return {
            "role_name": role_name,
            "policy_document": json.dumps(policy, indent=2),
        }

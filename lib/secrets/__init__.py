"""Secrets management with provider abstraction and output masking.

This package provides:
- SecretValue: Wrapper that masks secrets in output
- DatabaseCredentials, APICredentials: Typed credential containers
- SecretsProvider: Abstract interface for credential providers
- EnvSecretsProvider, AWSSecretsProvider: Concrete implementations
- OutputMasker: Pattern-based output masking
- PermissionConfig: Access control for database operations

Quick Start:
    from lib.secrets import get_credentials, DatabaseCredentials

    # Get database credentials (auto-detects provider)
    creds = get_credentials("database")
    print(creds)  # Password is masked: SecretValue('****')

    # Use for actual connection
    dsn = creds.dsn  # Contains real password

Provider Priority:
    1. Environment variables (DB_HOST, DB_USER, etc.)
    2. AWS Secrets Manager (if configured)

Example with explicit provider:
    from lib.secrets.providers import AWSSecretsProvider, EnvSecretsProvider

    aws = AWSSecretsProvider(region="us-east-1")
    if aws.is_available():
        raw = aws.get_secret("prod/database")
        creds = DatabaseCredentials.from_dict(raw)
"""

from .base import (
    SecretValue,
    SecretsProvider,
    SecretsError,
    SecretNotFoundError,
    ProviderNotAvailableError,
)
from .credentials import DatabaseCredentials, APICredentials
from .providers import EnvSecretsProvider, AWSSecretsProvider
from .masking import OutputMasker, mask_output, scan_for_secrets
from .permissions import AccessLevel, OperationType, PermissionConfig

__all__ = [
    # Base classes
    "SecretValue",
    "SecretsProvider",
    "SecretsError",
    "SecretNotFoundError",
    "ProviderNotAvailableError",
    # Credentials
    "DatabaseCredentials",
    "APICredentials",
    # Providers
    "EnvSecretsProvider",
    "AWSSecretsProvider",
    # Masking
    "OutputMasker",
    "mask_output",
    "scan_for_secrets",
    # Permissions
    "AccessLevel",
    "OperationType",
    "PermissionConfig",
    # Convenience functions
    "get_credentials",
    "get_provider",
]


def get_provider() -> SecretsProvider:
    """Get the first available secrets provider.

    Tries providers in order:
    1. Environment variables (always available)
    2. AWS Secrets Manager (if credentials configured)

    Returns:
        The first available SecretsProvider.
    """
    # Try environment first (always available)
    env = EnvSecretsProvider()

    # If AWS is available and configured, prefer it for production secrets
    aws = AWSSecretsProvider()
    if aws.is_available():
        return aws

    return env


def get_credentials(
    secret_id: str = "DB",
    provider: SecretsProvider | None = None,
) -> DatabaseCredentials:
    """Get database credentials from the best available provider.

    This is the main entry point for getting credentials.
    Automatically selects the best provider if not specified.

    Args:
        secret_id: The secret identifier.
                  For env provider: variable prefix (e.g., "DB" looks for DB_HOST)
                  For AWS: secret name or ARN
        provider: Specific provider to use, or None to auto-select.

    Returns:
        DatabaseCredentials with masked password.

    Example:
        creds = get_credentials()  # Uses DB_* env vars or AWS
        print(creds.connection_string)  # postgresql://user:****@host:5432/db

        # For actual connection:
        conn = await asyncpg.connect(**creds.dsn)
    """
    if provider is None:
        provider = get_provider()

    # Get raw secret data
    if hasattr(provider, "get_database_secret"):
        raw = provider.get_database_secret(secret_id)
    else:
        raw = provider.get_secret(secret_id)

    # Convert to typed credentials
    return DatabaseCredentials.from_dict(raw)

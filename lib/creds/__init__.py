"""Secrets management with provider abstraction and output masking.

This package provides:
- SecretValue: Wrapper that masks secrets in output
- SecretBundle: Collection of key-value secrets for a project
- DatabaseCredentials, APICredentials: Typed credential containers
- SecretsProvider, BundleProvider: Abstract interfaces for credential providers
- EnvSecretsProvider, AWSSecretsProvider, DotEnvSecretsProvider: Implementations
- OutputMasker: Pattern-based output masking
- PermissionConfig: Access control for database operations

Quick Start:
    from lib.creds import get_credentials, DatabaseCredentials

    # Get database credentials (auto-detects provider)
    creds = get_credentials("database")
    print(creds)  # Password is masked: SecretValue('****')

    # Use for actual connection
    dsn = creds.dsn  # Contains real password

Bundle API (new):
    from lib.creds import get_bundle_provider
    from lib.creds.project import get_project_id

    provider = get_bundle_provider()
    bundle = provider.get_bundle(get_project_id())
    print(bundle)  # Keys visible, values masked

Provider Priority:
    1. Environment variables (DB_HOST, DB_USER, etc.)
    2. AWS Secrets Manager (if configured)

Bundle Provider Priority:
    1. AWS Secrets Manager (if configured)
    2. DotEnv global config (~/.config/claude-power-pack/secrets/)
"""

from .base import (
    BundleProvider,
    ProviderCaps,
    SecretBundle,
    SecretValue,
    SecretsProvider,
    SecretsError,
    SecretNotFoundError,
    ProviderNotAvailableError,
)
from .credentials import DatabaseCredentials, APICredentials
from .providers import EnvSecretsProvider, AWSSecretsProvider, DotEnvSecretsProvider
from .masking import OutputMasker, mask_output, scan_for_secrets
from .permissions import AccessLevel, OperationType, PermissionConfig

__all__ = [
    # Base classes
    "SecretValue",
    "SecretBundle",
    "SecretsProvider",
    "BundleProvider",
    "ProviderCaps",
    "SecretsError",
    "SecretNotFoundError",
    "ProviderNotAvailableError",
    # Credentials
    "DatabaseCredentials",
    "APICredentials",
    # Providers
    "EnvSecretsProvider",
    "AWSSecretsProvider",
    "DotEnvSecretsProvider",
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
    "get_bundle_provider",
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


def get_bundle_provider() -> BundleProvider:
    """Get the first available bundle-capable provider.

    Tries providers in order:
    1. AWS Secrets Manager (if configured)
    2. DotEnv global config (always available)

    Returns:
        The first available BundleProvider.
    """
    aws = AWSSecretsProvider()
    if aws.is_available():
        return aws

    return DotEnvSecretsProvider()


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

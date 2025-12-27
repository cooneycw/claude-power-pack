"""Secrets providers for different backends.

Available providers:
- EnvSecretsProvider: Environment variables and .env files
- AWSSecretsProvider: AWS Secrets Manager

Usage:
    from lib.creds.providers import EnvSecretsProvider, AWSSecretsProvider

    # Get credentials from environment
    env_provider = EnvSecretsProvider()
    if env_provider.is_available():
        creds = env_provider.get_secret("DB")  # Looks for DB_* vars

    # Get credentials from AWS
    aws_provider = AWSSecretsProvider()
    if aws_provider.is_available():
        creds = aws_provider.get_secret("prod/database")
"""

from .env import EnvSecretsProvider
from .aws import AWSSecretsProvider

__all__ = ["EnvSecretsProvider", "AWSSecretsProvider"]

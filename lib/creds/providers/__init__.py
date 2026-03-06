"""Secrets providers for different backends.

Available providers:
- EnvSecretsProvider: Environment variables and .env files (legacy)
- DotEnvSecretsProvider: Global config .env files with bundle support
- AWSSecretsProvider: AWS Secrets Manager with bundle support (requires boto3)

Usage:
    from lib.creds.providers import DotEnvSecretsProvider

    # Global config provider (recommended for new code)
    dotenv = DotEnvSecretsProvider()
    bundle = dotenv.get_bundle("my-project")

    # Legacy environment provider
    from lib.creds.providers import EnvSecretsProvider
    env = EnvSecretsProvider()
    creds = env.get_secret("DB")

    # AWS provider (only if boto3 installed)
    from lib.creds.providers import AWSSecretsProvider
    aws = AWSSecretsProvider()
    if aws.is_available():
        bundle = aws.get_bundle("my-project")
"""

from .dotenv import DotEnvSecretsProvider
from .env import EnvSecretsProvider

# AWS provider is optional - boto3 may not be installed
try:
    from .aws import AWSSecretsProvider
except Exception:
    AWSSecretsProvider = None  # type: ignore

__all__ = ["EnvSecretsProvider", "AWSSecretsProvider", "DotEnvSecretsProvider"]

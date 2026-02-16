"""Secrets providers for different backends.

Available providers:
- EnvSecretsProvider: Environment variables and .env files (legacy)
- DotEnvSecretsProvider: Global config .env files with bundle support
- AWSSecretsProvider: AWS Secrets Manager with bundle support

Usage:
    from lib.creds.providers import EnvSecretsProvider, AWSSecretsProvider
    from lib.creds.providers import DotEnvSecretsProvider

    # Global config provider (recommended for new code)
    dotenv = DotEnvSecretsProvider()
    bundle = dotenv.get_bundle("my-project")

    # Legacy environment provider
    env = EnvSecretsProvider()
    creds = env.get_secret("DB")

    # AWS provider with bundle support
    aws = AWSSecretsProvider()
    bundle = aws.get_bundle("my-project")
"""

from .env import EnvSecretsProvider
from .aws import AWSSecretsProvider
from .dotenv import DotEnvSecretsProvider

__all__ = ["EnvSecretsProvider", "AWSSecretsProvider", "DotEnvSecretsProvider"]

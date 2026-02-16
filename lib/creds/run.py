"""Secret injection for subprocess execution.

Loads secrets into environment variables and executes a command,
ensuring secrets never appear in CLI arguments or logs.

Usage:
    from lib.creds.run import run_with_secrets

    exit_code = run_with_secrets(
        ["make", "deploy"],
        project_id="my-app",
    )

CLI:
    python -m lib.creds run -- make deploy
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys
from typing import Optional

from .audit import log_action
from .base import SecretsError
from .project import get_project_id

logger = logging.getLogger(__name__)


def _get_bundle_provider(provider_name: str | None = None):
    """Get a bundle-capable provider."""
    from .providers.dotenv import DotEnvSecretsProvider
    from .providers.aws import AWSSecretsProvider

    if provider_name == "aws":
        return AWSSecretsProvider()
    elif provider_name == "dotenv":
        return DotEnvSecretsProvider()
    else:
        # Auto-detect: try AWS first, fall back to dotenv
        aws = AWSSecretsProvider()
        if aws.is_available():
            return aws
        return DotEnvSecretsProvider()


def run_with_secrets(
    command: list[str],
    project_id: str | None = None,
    provider_name: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> int:
    """Execute a command with secrets injected as environment variables.

    Secrets are loaded from the configured provider and set in the
    subprocess environment. They never appear in CLI arguments, logs,
    or the parent process environment.

    Args:
        command: Command and arguments to execute.
        project_id: Override auto-detected project ID.
        provider_name: Force a specific provider ("aws", "dotenv").
        extra_env: Additional environment variables to set.

    Returns:
        The subprocess exit code.
    """
    if not command:
        raise ValueError("command must not be empty")

    if project_id is None:
        project_id = get_project_id()

    provider = _get_bundle_provider(provider_name)
    bundle = provider.get_bundle(project_id)

    if not bundle.secrets:
        logger.info(f"No secrets found for project '{project_id}', "
                     "running command without injection")

    # Build subprocess environment
    env = os.environ.copy()
    env.update(bundle.secrets)
    if extra_env:
        env.update(extra_env)

    # Log the action (never the values)
    log_action(
        action="run",
        project_id=project_id,
        details=f"command={shlex.join(command)}, "
                f"secrets_injected={len(bundle.secrets)}, "
                f"provider={provider.name}",
    )

    logger.info(
        f"Running with {len(bundle.secrets)} secrets from {provider.name}: "
        f"{shlex.join(command)}"
    )

    try:
        result = subprocess.run(command, env=env)
        return result.returncode
    except FileNotFoundError:
        print(f"Error: command not found: {command[0]}", file=sys.stderr)
        return 127
    except KeyboardInterrupt:
        return 130

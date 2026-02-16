"""DotEnv secrets provider — global config location.

Stores secrets in ~/.config/claude-power-pack/secrets/{project_id}.env,
keeping them outside the repo to prevent accidental commits.

File permissions are enforced at 600 (owner read/write only).

Usage:
    from lib.creds.providers.dotenv import DotEnvSecretsProvider
    from lib.creds.project import get_project_id

    provider = DotEnvSecretsProvider()
    bundle = provider.get_bundle(get_project_id())
"""

from __future__ import annotations

import logging
import os
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal

from ..base import (
    BundleProvider,
    ProviderCaps,
    SecretBundle,
    SecretNotFoundError,
    SecretsError,
)
from ..project import ensure_secrets_dir, get_project_id

logger = logging.getLogger(__name__)


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into key-value pairs.

    Handles:
    - KEY=value
    - KEY="quoted value"
    - KEY='single quoted'
    - # comments
    - Empty lines
    - export KEY=value
    """
    result: dict[str, str] = {}
    if not path.exists():
        return result

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Strip optional 'export ' prefix
        if line.startswith("export "):
            line = line[7:]

        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        # Remove surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        result[key] = value

    return result


def _write_env_file(path: Path, secrets: dict[str, str]) -> None:
    """Write secrets to a .env file with proper formatting."""
    lines = [
        "# Claude Power Pack secrets",
        f"# Project: {path.parent.name}",
        f"# Updated: {datetime.now(timezone.utc).isoformat()}",
        "#",
        "# DO NOT commit this file. It is stored outside the repo.",
        "",
    ]

    for key in sorted(secrets):
        value = secrets[key]
        # Quote values that contain spaces, special chars, or are empty
        if not value or " " in value or any(c in value for c in '#"\'\\$'):
            value = shlex.quote(value)
        lines.append(f"{key}={value}")

    lines.append("")  # trailing newline

    path.write_text("\n".join(lines))

    # Enforce file permissions: owner read/write only
    path.chmod(0o600)


class DotEnvSecretsProvider(BundleProvider):
    """Secrets provider storing .env files in global config directory.

    Secrets are stored at:
        ~/.config/claude-power-pack/secrets/{project_id}.env

    This keeps secrets outside the repository to prevent accidental
    commits and avoids worktree drift (all worktrees share the same
    secrets since project_id is derived from the main repo root).
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the DotEnv provider.

        Args:
            config_dir: Override the default config directory.
        """
        self._config_dir = config_dir

    def _get_env_path(self, project_id: str) -> Path:
        """Get the .env file path for a project."""
        if self._config_dir:
            secrets_dir = self._config_dir / project_id
            secrets_dir.mkdir(parents=True, exist_ok=True)
            return secrets_dir / ".env"
        return ensure_secrets_dir(project_id) / ".env"

    @property
    def name(self) -> str:
        return "dotenv-global"

    def caps(self) -> ProviderCaps:
        return ProviderCaps(
            can_read=True,
            can_write=True,
            can_delete=True,
            can_list=True,
            can_rotate=False,
            supports_versions=False,
        )

    def is_available(self) -> bool:
        """DotEnv provider is always available."""
        return True

    def get_secret(self, secret_id: str) -> Dict[str, Any]:
        """Get secrets as a flat dict (legacy interface).

        For DotEnv provider, secret_id is the project_id.
        """
        try:
            bundle = self.get_bundle(secret_id)
            return dict(bundle.secrets)
        except SecretNotFoundError:
            raise
        except Exception as e:
            raise SecretsError(f"Error reading secrets: {e}") from e

    def get_bundle(
        self, project_id: str, version: str | None = None
    ) -> SecretBundle:
        """Get all secrets for a project."""
        path = self._get_env_path(project_id)

        if not path.exists():
            return SecretBundle(
                project_id=project_id,
                secrets={},
                provider=self.name,
            )

        # Check file permissions
        stat = path.stat()
        mode = stat.st_mode & 0o777
        if mode != 0o600:
            logger.warning(
                f"Secret file {path} has permissions {oct(mode)}, "
                "fixing to 600"
            )
            path.chmod(0o600)

        secrets = _parse_env_file(path)

        return SecretBundle(
            project_id=project_id,
            secrets=secrets,
            updated_at=datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ),
            provider=self.name,
        )

    def put_bundle(
        self,
        bundle: SecretBundle,
        mode: Literal["merge", "replace"] = "merge",
    ) -> SecretBundle:
        """Write secrets for a project."""
        path = self._get_env_path(bundle.project_id)

        if mode == "merge" and path.exists():
            existing = _parse_env_file(path)
            existing.update(bundle.secrets)
            merged = existing
        else:
            merged = dict(bundle.secrets)

        _write_env_file(path, merged)

        return SecretBundle(
            project_id=bundle.project_id,
            secrets=merged,
            updated_at=datetime.now(timezone.utc),
            provider=self.name,
        )

    def delete_key(self, project_id: str, key: str) -> None:
        """Delete a single secret key."""
        path = self._get_env_path(project_id)

        if not path.exists():
            raise SecretNotFoundError(f"No secrets found for project '{project_id}'")

        secrets = _parse_env_file(path)
        if key not in secrets:
            raise SecretNotFoundError(f"Key '{key}' not found in project '{project_id}'")

        del secrets[key]
        _write_env_file(path, secrets)

    def list_keys(self, project_id: str) -> list[str]:
        """List all secret key names for a project."""
        path = self._get_env_path(project_id)

        if not path.exists():
            return []

        secrets = _parse_env_file(path)
        return sorted(secrets.keys())

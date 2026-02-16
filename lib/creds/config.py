"""Secrets management configuration.

Loads configuration from .claude/secrets.yml (if present)
with sensible defaults for all settings.

Usage:
    from lib.creds.config import SecretsConfig

    config = SecretsConfig.load()
    print(config.default_provider)  # "dotenv" or "aws"
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SecretsConfig:
    """Configuration for the secrets management system."""

    # Default provider: "dotenv", "aws", "auto"
    default_provider: str = "auto"

    # AWS-specific settings
    aws_region: str = "us-east-1"
    aws_role_arn: str = ""

    # UI settings
    ui_host: str = "127.0.0.1"
    ui_port: int = 8090

    # Rotation settings
    rotation_warn_days: int = 90

    @classmethod
    def load(cls, project_root: str | None = None) -> SecretsConfig:
        """Load config from .claude/secrets.yml or return defaults.

        Args:
            project_root: Project root directory. Defaults to cwd.

        Returns:
            SecretsConfig with loaded or default values.
        """
        if project_root is None:
            project_root = os.getcwd()

        config_path = Path(project_root) / ".claude" / "secrets.yml"

        if config_path.exists():
            return cls._from_yaml(config_path)

        return cls()

    @classmethod
    def _from_yaml(cls, path: Path) -> SecretsConfig:
        """Parse YAML config file."""
        try:
            import yaml
        except ImportError:
            logger.debug("PyYAML not installed, using defaults")
            return cls()

        try:
            data = yaml.safe_load(path.read_text()) or {}
        except Exception as e:
            logger.warning(f"Error reading {path}: {e}, using defaults")
            return cls()

        return cls(
            default_provider=data.get("default_provider", "auto"),
            aws_region=data.get("aws", {}).get("region", "us-east-1"),
            aws_role_arn=data.get("aws", {}).get("role_arn", ""),
            ui_host=data.get("ui", {}).get("host", "127.0.0.1"),
            ui_port=data.get("ui", {}).get("port", 8090),
            rotation_warn_days=data.get("rotation", {}).get("warn_days", 90),
        )

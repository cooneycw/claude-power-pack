"""Tests for lib/creds/config.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.creds.config import SecretsConfig


class TestSecretsConfigDefaults:
    """Test default configuration values."""

    def test_defaults(self) -> None:
        config = SecretsConfig()
        assert config.default_provider == "auto"
        assert config.aws_region == "us-east-1"
        assert config.aws_role_arn == ""
        assert config.ui_host == "127.0.0.1"
        assert config.ui_port == 8090
        assert config.rotation_warn_days == 90


class TestSecretsConfigLoad:
    """Test loading configuration from files."""

    def test_load_no_file(self, tmp_path: Path) -> None:
        config = SecretsConfig.load(str(tmp_path))
        assert config.default_provider == "auto"

    def test_load_with_yaml(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        yaml_file = claude_dir / "secrets.yml"
        yaml_file.write_text(
            "default_provider: aws\n"
            "aws:\n"
            "  region: ca-central-1\n"
            "  role_arn: arn:aws:iam::role/test\n"
            "ui:\n"
            "  port: 9090\n"
            "rotation:\n"
            "  warn_days: 60\n"
        )
        try:
            import yaml  # noqa: F401

            config = SecretsConfig.load(str(tmp_path))
            assert config.default_provider == "aws"
            assert config.aws_region == "ca-central-1"
            assert config.ui_port == 9090
            assert config.rotation_warn_days == 60
        except ImportError:
            pytest.skip("PyYAML not installed")

    def test_load_invalid_yaml(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        yaml_file = claude_dir / "secrets.yml"
        yaml_file.write_text(": invalid: yaml: {{{\n")
        try:
            import yaml  # noqa: F401

            config = SecretsConfig.load(str(tmp_path))
            # Should fall back to defaults
            assert config.default_provider == "auto"
        except ImportError:
            pytest.skip("PyYAML not installed")

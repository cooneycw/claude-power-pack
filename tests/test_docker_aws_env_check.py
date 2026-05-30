"""Tests for Docker AWS credential preflight validation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-docker-aws-env.py"


def _run_check(
    tmp_path: Path,
    *args: str,
    env_updates: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        env.pop(name, None)
    if env_updates:
        env.update(env_updates)

    return subprocess.run(
        [sys.executable, str(SCRIPT), "--env-file", str(tmp_path / ".env"), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def test_browser_profile_does_not_require_aws_credentials(tmp_path: Path) -> None:
    result = _run_check(tmp_path, "--profiles", "browser")

    assert result.returncode == 0
    assert "do not start aws-secrets-agent" in result.stdout


def test_core_profile_requires_nonempty_aws_credentials(tmp_path: Path) -> None:
    result = _run_check(tmp_path, "--profiles", "core")

    assert result.returncode == 1
    assert "AWS_ACCESS_KEY_ID is missing" in result.stdout
    assert "AWS_SECRET_ACCESS_KEY is missing" in result.stdout
    assert "--force-recreate aws-secrets-agent" in result.stdout


def test_env_file_credentials_pass_without_printing_values(tmp_path: Path) -> None:
    secret = "super-secret-value"
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
                f"AWS_SECRET_ACCESS_KEY={secret}",
            ]
        )
    )

    result = _run_check(tmp_path, "--profiles", "core cicd")

    assert result.returncode == 0
    assert "OK: AWS credentials available" in result.stdout
    assert secret not in result.stdout


def test_empty_shell_env_overrides_valid_env_file_and_fails(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
                "AWS_SECRET_ACCESS_KEY=valid-but-redacted",
            ]
        )
    )

    result = _run_check(
        tmp_path,
        "--profiles",
        "core",
        env_updates={"AWS_ACCESS_KEY_ID": "", "AWS_SECRET_ACCESS_KEY": "from-shell"},
    )

    assert result.returncode == 1
    assert "AWS_ACCESS_KEY_ID is set but empty in the shell environment" in result.stdout
    assert "valid-but-redacted" not in result.stdout

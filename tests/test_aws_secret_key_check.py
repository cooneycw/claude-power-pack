"""Tests for AWS Secrets Manager key presence validation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-aws-secret-keys.py"


def _write_fake_aws(tmp_path: Path, payload: str, *, describe_success: bool = True) -> Path:
    fake_aws = tmp_path / "aws"
    fake_aws.write_text(
        f"""#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if args[:2] == ["secretsmanager", "describe-secret"]:
    sys.exit(0 if {describe_success!r} else 255)
if args[:2] == ["secretsmanager", "get-secret-value"]:
    print({payload!r})
    sys.exit(0)
sys.exit(1)
""",
    )
    fake_aws.chmod(0o755)
    return fake_aws


def _run_check(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def test_required_secret_with_all_keys_passes_without_printing_values(tmp_path: Path) -> None:
    _write_fake_aws(tmp_path, '{"A":"secret-value","B":"other-secret"}')

    result = _run_check(tmp_path, "--required", "test-secret:A,B")

    assert result.returncode == 0
    assert "OK: Secret 'test-secret' contains expected keys (2)" in result.stdout
    assert "secret-value" not in result.stdout
    assert "other-secret" not in result.stdout


def test_required_secret_missing_key_fails_without_printing_values(tmp_path: Path) -> None:
    _write_fake_aws(tmp_path, '{"A":"secret-value"}')

    result = _run_check(tmp_path, "--required", "test-secret:A,B")

    assert result.returncode == 1
    assert "FAIL: Secret 'test-secret' missing required key(s): B" in result.stdout
    assert "secret-value" not in result.stdout


def test_optional_missing_secret_warns_but_does_not_fail(tmp_path: Path) -> None:
    _write_fake_aws(tmp_path, "{}", describe_success=False)

    result = _run_check(tmp_path, "--optional", "optional-secret:A")

    assert result.returncode == 0
    assert "WARN: Secret 'optional-secret' not found" in result.stdout

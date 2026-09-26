"""Committed negative controls for the gitleaks security adapter (issue #1264).

A secret scan that did not run must report UNKNOWN, never a skip that leaves
the summary reading as clean - the #1044 pip-audit shape applied to gitleaks.
The binary is always stubbed, so these run the same with or without gitleaks
installed on the host.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from lib.security.modules import gitleaks


@pytest.fixture(autouse=True)
def _block_real_subprocesses(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_subprocess(*args: object, **kwargs: object) -> None:
        pytest.fail(f"unexpected real subprocess call: {args!r} {kwargs!r}")

    monkeypatch.setattr(gitleaks.subprocess, "run", unexpected_subprocess)


def _completed(stdout: str, returncode: int, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["gitleaks"], returncode, stdout, stderr)


def _is_unknown(result) -> bool:
    return (
        any(error.startswith("UNKNOWN") for error in result.errors)
        and result.passed == []
        and result.findings == []
    )


def test_missing_gitleaks_is_unknown_not_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE RED CASE: pre-fix this appended to `skipped` and left no error."""
    run = Mock()
    monkeypatch.setattr(gitleaks.subprocess, "run", run)
    monkeypatch.setattr(gitleaks, "is_available", lambda: False)

    result = gitleaks.scan(str(tmp_path))

    run.assert_not_called()
    assert _is_unknown(result)
    assert result.skipped == []


def test_binary_vanishing_mid_run_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gitleaks, "is_available", lambda: True)
    monkeypatch.setattr(gitleaks.subprocess, "run", Mock(side_effect=FileNotFoundError))

    result = gitleaks.scan(str(tmp_path))

    assert _is_unknown(result)
    assert result.skipped == []


def test_a_failing_gitleaks_is_unknown_not_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-fix, an exit that was neither 0 nor 1 with empty stdout returned an
    EMPTY result - no pass, no finding, no error - which reads as nothing to report."""
    monkeypatch.setattr(gitleaks, "is_available", lambda: True)
    monkeypatch.setattr(
        gitleaks.subprocess, "run", Mock(return_value=_completed("", 126, "bad config"))
    )

    result = gitleaks.scan(str(tmp_path))

    assert _is_unknown(result)


def test_clean_scan_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The GOOD side: without it, an adapter that always said UNKNOWN would pass."""
    monkeypatch.setattr(gitleaks, "is_available", lambda: True)
    monkeypatch.setattr(gitleaks.subprocess, "run", Mock(return_value=_completed("[]", 0)))

    result = gitleaks.scan(str(tmp_path))

    assert result.errors == []
    assert result.passed


def test_leak_yields_masked_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    leak = [{"RuleID": "aws-key", "Description": "AWS key", "Secret": "AKIAEXAMPLE", "File": "a.py"}]
    monkeypatch.setattr(gitleaks, "is_available", lambda: True)
    monkeypatch.setattr(
        gitleaks.subprocess, "run", Mock(return_value=_completed(json.dumps(leak), 1))
    )

    result = gitleaks.scan(str(tmp_path))

    assert result.errors == []
    assert [f.id for f in result.findings] == ["GITLEAKS_AWS-KEY"]
    assert result.findings[0].raw_match == "AKIA****"

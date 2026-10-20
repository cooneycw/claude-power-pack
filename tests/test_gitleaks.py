"""Committed negative controls for the gitleaks security adapter (issue #1264).

A secret scan that did not run must report UNKNOWN, never a skip that leaves
the summary reading as clean - the #1044 pip-audit shape applied to gitleaks.
The binary is always stubbed, so these run the same with or without gitleaks
installed on the host.
"""

from __future__ import annotations

import json
import shutil
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


@pytest.mark.parametrize(
    "stdout", ["", "[]", '{"not": "a list"}'], ids=["empty", "empty-list", "object"]
)
def test_exit_1_without_a_readable_report_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    """Counter-model review: gitleaks exits 1 for a nonexistent source too, with
    no report. Only a report can say secrets were found."""
    monkeypatch.setattr(gitleaks, "is_available", lambda: True)
    monkeypatch.setattr(
        gitleaks.subprocess, "run", Mock(return_value=_completed(stdout, 1, "no such source"))
    )

    result = gitleaks.scan(str(tmp_path))

    assert _is_unknown(result)


def test_clean_scan_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The GOOD side: without it, an adapter that always said UNKNOWN would pass."""
    monkeypatch.setattr(gitleaks, "is_available", lambda: True)
    monkeypatch.setattr(gitleaks.subprocess, "run", Mock(return_value=_completed("[]", 0)))

    (tmp_path / "app.py").write_text("print(123)\n")
    result = gitleaks.scan(str(tmp_path))

    assert result.errors == []
    assert result.passed == [
        "No secrets found by gitleaks (working tree; 1 files handed to gitleaks)"
    ]


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


def test_empty_target_is_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert not list(tmp_path.iterdir()), "negative fixture must contain no files"
    monkeypatch.setattr(gitleaks, "is_available", lambda: True)
    monkeypatch.setattr(gitleaks.subprocess, "run", Mock(return_value=_completed("[]", 0)))
    assert _is_unknown(gitleaks.scan(str(tmp_path)))


@pytest.mark.parametrize("count", [0, 3])
def test_reported_commit_count_is_authoritative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int,
) -> None:
    (tmp_path / "app.py").write_text("print(123)\n")
    monkeypatch.setattr(gitleaks, "is_available", lambda: True)
    monkeypatch.setattr(gitleaks.subprocess, "run", Mock(
        return_value=_completed("[]", 0, f"INF {count} commits scanned.")))
    result = gitleaks.scan(str(tmp_path), include_history=True)
    if count == 0:
        assert _is_unknown(result)
    else:
        assert result.passed == [
            "No secrets found by gitleaks (code and git history; 3 commits scanned)"
        ]


@pytest.mark.skipif(shutil.which("gitleaks") is None, reason="needs real gitleaks")
def test_real_populated_target_passes_with_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()  # Restore the real subprocess only for this guarded integration test.
    (tmp_path / "app.py").write_text("print(123)\n")
    result = gitleaks.scan(str(tmp_path))
    assert result.errors == []
    assert result.passed == [
        "No secrets found by gitleaks (working tree; 1 files handed to gitleaks)"
    ]

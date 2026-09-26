"""Committed negative controls for the npm-audit security adapter (issue #1264).

The adapter's verdict is read by a person in any repository and never
re-derived (ADR 0008, `lib.security scan`), so an audit that did not run must
say UNKNOWN - never skip into a summary that reads as clean. These are the
#1044 pip-audit cases applied to npm.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from lib.security.modules import npm_audit


@pytest.fixture(autouse=True)
def _block_real_subprocesses(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_subprocess(*args: object, **kwargs: object) -> None:
        pytest.fail(f"unexpected real subprocess call: {args!r} {kwargs!r}")

    monkeypatch.setattr(npm_audit.subprocess, "run", unexpected_subprocess)


def _node_project(tmp_path: Path, *, lockfile: bool = True) -> Path:
    (tmp_path / "package.json").write_text('{"name": "fixture"}\n', encoding="utf-8")
    if lockfile:
        (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")
    return tmp_path


def _completed(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["npm", "audit", "--json"], returncode, stdout, stderr)


def _is_unknown(result) -> bool:
    return any(error.startswith("UNKNOWN") for error in result.errors) and result.passed == []


def test_missing_npm_in_a_node_project_is_unknown_not_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE RED CASE: pre-fix this appended to `skipped` and left no error."""
    run = Mock()
    monkeypatch.setattr(npm_audit.subprocess, "run", run)
    monkeypatch.setattr(npm_audit, "is_available", lambda: False)

    result = npm_audit.scan(str(_node_project(tmp_path)))

    run.assert_not_called()
    assert _is_unknown(result)
    assert result.skipped == []


def test_binary_vanishing_mid_run_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(npm_audit, "is_available", lambda: True)
    monkeypatch.setattr(npm_audit.subprocess, "run", Mock(side_effect=FileNotFoundError))

    result = npm_audit.scan(str(_node_project(tmp_path)))

    assert _is_unknown(result)
    assert result.skipped == []


@pytest.mark.parametrize(
    "proc",
    [
        _completed("", returncode=1, stderr="npm ERR! crashed"),
        _completed(json.dumps({"error": {"code": "ENOLOCK"}}), returncode=1),
        _completed("not json", returncode=0),
        _completed(json.dumps({"vulnerabilities": None}), returncode=0),
        _completed(json.dumps({"vulnerabilities": []}), returncode=0),
        _completed(json.dumps({"vulnerabilities": ["left-pad"]}), returncode=1),
        _completed(json.dumps({"vulnerabilities": {}}), returncode=2),
        _completed(json.dumps({"vulnerabilities": {}}), returncode=-9),
        _completed(json.dumps({"vulnerabilities": {}}), returncode=1),
    ],
    ids=[
        "empty-stdout", "error-object", "unparseable", "null-map", "empty-list", "list",
        "report-then-exit-2", "report-then-signal", "exit-1-no-findings",
    ],
)
def test_an_audit_that_produced_no_report_is_unknown_not_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, proc: subprocess.CompletedProcess
) -> None:
    """Pre-fix, an empty stdout parsed as `{}` and passed as 'no vulnerabilities'."""
    monkeypatch.setattr(npm_audit, "is_available", lambda: True)
    monkeypatch.setattr(npm_audit.subprocess, "run", Mock(return_value=proc))

    result = npm_audit.scan(str(_node_project(tmp_path)))

    assert _is_unknown(result)


def test_clean_report_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The GOOD side: without it, an adapter that always said UNKNOWN would pass."""
    monkeypatch.setattr(npm_audit, "is_available", lambda: True)
    monkeypatch.setattr(
        npm_audit.subprocess,
        "run",
        Mock(return_value=_completed(json.dumps({"vulnerabilities": {}}))),
    )

    result = npm_audit.scan(str(_node_project(tmp_path)))

    assert result.errors == []
    assert result.passed


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"dependencies": {"total": 12}}, "12 dependencies examined"),
        ({"dependencies": {"total": 0}}, "0 dependencies examined"),
        (None, "dependency count not reported"),
    ],
    ids=["populated", "empty-population", "no-metadata"],
)
def test_a_clean_verdict_states_what_it_examined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, metadata: object, expected: str
) -> None:
    """A clean pass over 12 dependencies and one over 0 must not read alike."""
    report: dict[str, object] = {"vulnerabilities": {}}
    if metadata is not None:
        report["metadata"] = metadata
    monkeypatch.setattr(npm_audit, "is_available", lambda: True)
    monkeypatch.setattr(
        npm_audit.subprocess, "run", Mock(return_value=_completed(json.dumps(report)))
    )

    result = npm_audit.scan(str(_node_project(tmp_path)))

    assert result.errors == []
    assert len(result.passed) == 1 and expected in result.passed[0], result.passed


def test_vulnerable_report_yields_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = {"vulnerabilities": {"left-pad": {"severity": "high", "fixAvailable": True}}}
    monkeypatch.setattr(npm_audit, "is_available", lambda: True)
    monkeypatch.setattr(
        npm_audit.subprocess, "run", Mock(return_value=_completed(json.dumps(report), 1))
    )

    result = npm_audit.scan(str(_node_project(tmp_path)))

    assert result.errors == []
    assert [f.id for f in result.findings] == ["NPM_AUDIT_LEFT_PAD"]


def test_not_a_node_project_is_skipped_as_not_applicable(tmp_path: Path) -> None:
    result = npm_audit.scan(str(tmp_path))

    assert result.errors == []
    assert result.skipped

"""A Makefile-less Python repository through the SHIPPED runner path (issue #1289, part B).

Part A (#1310) made detection report what a repository contains. This part
exercises what the runner then RUNS for the commonest consumer shape: a Python
project with a `pyproject.toml` and no Makefile, gated by `BUILTIN_PLANS["check"]`
exactly as `/flow:check` and the finish gate resolve it.

Nothing is installed or fetched. `uv` - which every gate's no-Makefile fallback
calls as `uv run --extra dev <tool>` - is a stub on PATH that records each argv
and answers like the tool would. The questions are about RESOLUTION, not about
ruff or mypy:

- a DECLARED scope is honoured: `[tool.mypy] files = [...]` reaches mypy as a
  bare `mypy` (so mypy reads its own `files`), and an undeclared scope gets `.`;
- a declared check that FAILS fails the run - the check really ran, it was not
  resolved to something that could not fail;
- a tool the project does NOT configure is skipped, and the skip is reported by
  name rather than rendered as a pass.
"""

from __future__ import annotations

import os
import shutil
from io import StringIO
from pathlib import Path

import pytest

from lib.cicd.runner import DeterministicRunner
from lib.cicd.steps import BUILTIN_PLANS

requires_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh for the uv stub")

DECLARED_ALL = '[tool.ruff]\n[tool.pytest.ini_options]\n[tool.mypy]\nfiles = ["src"]\n'


def _repo(tmp_path: Path, pyproject: str, failing: str | None = None) -> tuple[Path, Path]:
    """A Makefile-less Python repo and a stub `uv` that records its argv.

    `failing` names the tool whose invocation must fail (a deliberately broken
    declared check); every other tool answers the way the real one does.
    """
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    assert not (root / "Makefile").exists(), "precondition: no Makefile, so the fallback path runs"
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    log = tmp_path / "uv-calls.log"
    fail_case = f"  *' {failing}'*) echo 'FAILED tests/test_x.py::test_declared - assert 0'; " \
        "echo '== 1 failed, 2 passed in 0.10s =='; exit 1 ;;\n" if failing else ""
    (stub_dir / "uv").write_text(
        "#!/bin/sh\n"
        f'echo "$*" >> "{log}"\n'
        'case " $*" in\n'
        f"{fail_case}"
        "  *' pytest'*) echo '== 3 passed in 0.10s ==' ;;\n"
        "  *' mypy'*) echo 'Success: no issues found in 4 source files' ;;\n"
        "  *' ruff'*) echo 'All checks passed!' ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (stub_dir / "uv").chmod(0o755)
    return root, stub_dir


def _run(root: Path, stub_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PATH", f"{stub_dir}{os.pathsep}{os.environ['PATH']}")
    assert shutil.which("uv") == str(stub_dir / "uv"), "precondition: the stub, never a real uv"
    log = StringIO()
    result = DeterministicRunner(project_root=root, output=log).run(
        "check", step_defs=list(BUILTIN_PLANS["check"])
    )
    return result, log.getvalue()


def _calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "uv-calls.log"
    return log.read_text().splitlines() if log.exists() else []


@requires_sh
def test_a_declared_mypy_scope_reaches_mypy_unmodified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, stub = _repo(tmp_path, DECLARED_ALL)
    result, _ = _run(root, stub, monkeypatch)
    assert result.success
    calls = _calls(tmp_path)
    assert "run --extra dev mypy" in calls, calls
    assert "run --extra dev mypy ." not in calls, "a declared scope was overridden with '.'"


@requires_sh
def test_an_undeclared_mypy_scope_checks_the_whole_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half: without `files`, the gate must not run a scopeless mypy."""
    root, stub = _repo(tmp_path, '[tool.ruff]\n[tool.pytest.ini_options]\n[tool.mypy]\nstrict = true\n')
    result, _ = _run(root, stub, monkeypatch)
    assert result.success
    assert "run --extra dev mypy ." in _calls(tmp_path)


@requires_sh
def test_a_failing_declared_check_fails_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The declared test gate really ran: its deliberate failure is the verdict."""
    root, stub = _repo(tmp_path, DECLARED_ALL, failing="pytest")
    result, text = _run(root, stub, monkeypatch)
    assert not result.success
    assert "run --extra dev pytest" in _calls(tmp_path)
    assert "test: FAILED" in text, text


@requires_sh
def test_an_undeclared_tool_is_skipped_and_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No `[tool.ruff]`: lint is not run, and the run says so by name."""
    root, stub = _repo(tmp_path, '[tool.pytest.ini_options]\n[tool.mypy]\nfiles = ["src"]\n')
    result, text = _run(root, stub, monkeypatch)
    assert result.success
    calls = _calls(tmp_path)
    assert not any("ruff" in c for c in calls), "an undeclared tool was run"
    # ...and ONLY it was skipped: the configured gates still ran (counter-model
    # review) - a regression skipping every gate would otherwise satisfy all of
    # the above with `SKIPPED GATES: lint, test, typecheck`.
    assert "run --extra dev pytest" in calls and "run --extra dev mypy" in calls, calls
    assert "completed WITH WARNINGS" in text
    assert "SKIPPED GATES: lint (" in text, text

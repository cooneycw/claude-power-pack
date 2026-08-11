"""Tests for scripts/check-negative-fixture-preconditions.py - the #697 gate.

Contract:
- Fires on the #695 shape: a fixture that replaces ``PATH`` wholesale to create
  an absence, with no assertion that the absence is the one it intended.
- Stays silent on all three shapes issue #697 explicitly names as safe - a
  ``PATH`` prepend, ``monkeypatch.delenv``, and outcome assertions - so the
  convention cannot be over-applied.
- Honours the ``# negative-fixture: allow <reason>`` escape.
- Runs clean on CPP's real ``tests/`` tree.

The load-bearing test in this module is
``test_gate_fires_when_the_real_precondition_is_stripped``: it MUTATES the one
real instance in the suite (``test_cpp_commands_link.py``, whose precondition
landed in PR #695) and proves the gate goes red. Without it, this gate would be
one more measurement whose broken version is indistinguishable from its working
version - the exact defect class #697 belongs to (#673, #674, #677, #685, #698),
and the reason a green run over a one-line population proves nothing on its own.

This module deliberately shells out to NOTHING: the checker is pure source
analysis, so its own test drives it in-process over sources written to
``tmp_path``. That is what lets it run in the CI ``validate`` image.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-negative-fixture-preconditions.py"


def _load_checker():
    """Import the hyphenated CLI script as a module."""
    spec = importlib.util.spec_from_file_location("check_negative_fixture_preconditions", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()

PREAMBLE = """\
import os
import shutil

"""


def _findings(tmp_path: Path, source: str) -> list:
    path = tmp_path / "test_sample.py"
    path.write_text(PREAMBLE + source, encoding="utf-8")
    return checker.check_paths([path])


# --------------------------------------------------------------------------- #
# The mutation proof - this gate's own falsifiability
# --------------------------------------------------------------------------- #
def test_gate_fires_when_the_real_precondition_is_stripped(tmp_path: Path) -> None:
    """Remove the shipped assertion from the real fixture; the gate must go red.

    The detectable population in this repo is currently ONE line and it is
    already compliant, so a passing run over the real tree is equally consistent
    with a gate that cannot fire at all. This test is what distinguishes them:
    it deletes the ``fixture must lack git`` assertion from a copy of the real
    ``test_cpp_commands_link.py`` and requires a finding.

    A failure here means the guard has stopped guarding, whatever the real-tree
    run says.
    """
    real = ROOT / "tests" / "test_cpp_commands_link.py"
    source = real.read_text(encoding="utf-8")
    assert "fixture must lack git" in source, (
        "the #695 precondition is gone from the real fixture - either it was "
        "removed (a #697 regression) or renamed, and this mutation proof is "
        "no longer measuring anything"
    )

    mutated = "".join(
        line for line in source.splitlines(keepends=True) if "fixture must lack git" not in line
    )
    target = tmp_path / "test_cpp_commands_link.py"
    target.write_text(mutated, encoding="utf-8")

    findings = checker.check_paths([target])
    assert len(findings) == 1, f"stripped precondition not caught: {findings}"
    assert findings[0].func == "test_fail_open_when_git_is_absent"


def test_real_tests_tree_is_clean() -> None:
    """CPP's own suite satisfies the directive.

    This is what runs the gate in CI (the ``validate`` step runs pytest), the
    same wiring ``check-test-binary-guards.py`` relies on.
    """
    findings = checker.check_tree(ROOT / "tests")
    assert not findings, "\n".join(f.render(ROOT) for f in findings)


# --------------------------------------------------------------------------- #
# Fires: constructed absences with no precondition
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            'def test_thing(tmp_path):\n    env = dict(os.environ)\n    env["PATH"] = ""\n',
            id="empty-path-the-695-shape",
        ),
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    env = dict(os.environ)\n'
            '    env["PATH"] = str(tmp_path / "stub")\n',
            id="wholesale-replacement",
        ),
        pytest.param(
            'def test_thing(monkeypatch, tmp_path):\n'
            '    monkeypatch.setenv("PATH", str(tmp_path))\n',
            id="setenv-wholesale",
        ),
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    os.environ["PATH"] = str(tmp_path)\n',
            id="os-environ-direct",
        ),
    ],
)
def test_fires_on_constructed_absence(tmp_path: Path, body: str) -> None:
    findings = _findings(tmp_path, body)
    assert len(findings) == 1, f"expected one finding, got {findings}"


def test_finding_names_the_function_and_assignment_line(tmp_path: Path) -> None:
    findings = _findings(
        tmp_path,
        'def test_fail_open(tmp_path):\n    env = dict(os.environ)\n    env["PATH"] = ""\n',
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.func == "test_fail_open"
    rendered = finding.render(tmp_path)
    assert "test_fail_open" in rendered
    assert "PATH" in rendered


# --------------------------------------------------------------------------- #
# Stays silent: the shapes #697 names as safe (over-application guard)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    env = dict(os.environ)\n'
            '    env["PATH"] = f"{tmp_path}:{env[\'PATH\']}"\n',
            id="prepend-is-additive",
        ),
        pytest.param(
            'def test_thing(monkeypatch):\n'
            '    monkeypatch.setenv("PATH", f"/stub:{os.environ[\'PATH\']}")\n',
            id="setenv-prepend",
        ),
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    env = dict(os.environ)\n'
            '    env["PATH"] = os.pathsep.join([str(tmp_path), os.environ.get("PATH", "")])\n',
            id="derived-via-environ-get",
        ),
        pytest.param(
            'def test_thing(monkeypatch):\n'
            '    monkeypatch.delenv("CPP_HARNESS", raising=False)\n',
            id="delenv-is-a-named-removal",
        ),
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    produced = tmp_path / "out"\n'
            '    assert not produced.exists()\n',
            id="outcome-assertion-not-a-precondition",
        ),
    ],
)
def test_silent_on_sanctioned_shapes(tmp_path: Path, body: str) -> None:
    assert not _findings(tmp_path, body)


def test_precondition_assertion_clears_the_finding(tmp_path: Path) -> None:
    """The shipped #695 shape - the whole point of the convention."""
    assert not _findings(
        tmp_path,
        'def test_thing(tmp_path):\n'
        '    stub = tmp_path / "nogitbin"\n'
        '    stub.mkdir()\n'
        '    assert shutil.which("git", path=str(stub)) is None, "fixture must lack git"\n'
        '    env = dict(os.environ)\n'
        '    env["PATH"] = str(stub)\n',
    )


# --------------------------------------------------------------------------- #
# Escape hatch + structural edge cases
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("anchor", ["same-line", "line-above"], ids=["same-line", "line-above"])
def test_allow_escape_suppresses(tmp_path: Path, anchor: str) -> None:
    comment = "# negative-fixture: allow deliberate total-absence probe"
    if anchor == "same-line":
        assignment = f'    env["PATH"] = ""  {comment}\n'
    else:
        assignment = f'    {comment}\n    env["PATH"] = ""\n'
    assert not _findings(
        tmp_path,
        "def test_thing(tmp_path):\n    env = dict(os.environ)\n" + assignment,
    )


def test_nested_helper_is_reported_once(tmp_path: Path) -> None:
    """A replacement inside a nested function is attributed to that function only."""
    findings = _findings(
        tmp_path,
        'def test_thing(tmp_path):\n'
        '    def _build():\n'
        '        env = dict(os.environ)\n'
        '        env["PATH"] = ""\n'
        '        return env\n'
        '    return _build()\n',
    )
    assert len(findings) == 1, f"expected exactly one finding, got {findings}"
    assert findings[0].func == "_build"


# --------------------------------------------------------------------------- #
# CLI contract
# --------------------------------------------------------------------------- #
def test_cli_reports_and_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_bad.py").write_text(
        PREAMBLE + 'def test_thing(tmp_path):\n    env = dict(os.environ)\n    env["PATH"] = ""\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "unasserted precondition" in out
    assert "fixture must lack git" in out, "the remedy must name the shape to copy"


def test_cli_is_silent_success_on_a_clean_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(
        PREAMBLE + 'def test_thing(tmp_path):\n    assert tmp_path.exists()\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 0
    assert "ok" in capsys.readouterr().out


def test_cli_tolerates_a_missing_tests_dir(tmp_path: Path) -> None:
    """Fail-open on a repo with no tests/ - the gate has nothing to say, not a verdict."""
    assert checker.main(["--root", str(tmp_path)]) == 0

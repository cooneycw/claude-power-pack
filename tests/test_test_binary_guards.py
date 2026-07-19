"""Tests for scripts/check-test-binary-guards.py - the #602 shell-out gate.

Contract:
- Fires on the #577 shape: an unguarded ``subprocess.run(["git", ...])`` inside a
  ``test_`` function.
- Fires on the INDIRECT shape: a ``test_`` that calls a module-level helper which
  shells out, transitively.
- Clears every guard idiom the suite actually uses - an inline
  ``@pytest.mark.skipif(shutil.which(...))``, a module-level ``requires_git``
  alias, a class-level marker, ``pytestmark``, and an in-body
  ``if shutil.which(...) is None: pytest.skip(...)``.
- Honours the ``# binary-guard: allow <reason>`` escape.
- Runs clean on CPP's real ``tests/`` tree.

This module deliberately shells out to NOTHING (issue #602 acceptance criterion
4): the checker is pure source analysis, so its own test drives it in-process
over sources written to ``tmp_path``. That is what lets this gate run in the CI
``validate`` image - the very image whose missing binaries it exists to defend.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-test-binary-guards.py"


def _load_checker():
    """Import the hyphenated CLI script as a module."""
    spec = importlib.util.spec_from_file_location("check_test_binary_guards", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _findings(tmp_path: Path, source: str) -> list:
    path = tmp_path / "test_sample.py"
    path.write_text(source, encoding="utf-8")
    return checker.check_paths([path])


PREAMBLE = """\
import shutil
import subprocess

import pytest

"""


# --------------------------------------------------------------------------- #
# The regression the gate exists for (#451, #489, #577)
# --------------------------------------------------------------------------- #
def test_fires_on_the_577_shape(tmp_path: Path) -> None:
    """The exact shape that turned the pipeline red on PR #600."""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
def test_posture_file_is_tracked():
    result = subprocess.run(["git", "check-ignore", "-q", "x"], check=False)
    assert result.returncode != 0
""",
    )
    assert len(findings) == 1, findings
    assert findings[0].test == "test_posture_file_is_tracked"
    assert findings[0].binaries == ("git",)
    assert findings[0].indirect_via is None


def test_fires_on_the_indirect_helper_shape(tmp_path: Path) -> None:
    """Several existing tests shell out only through a module-level helper."""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True)


def _init_repo(repo):
    _git(repo, "init", "-q")


def test_repo_is_initialized(tmp_path):
    _init_repo(tmp_path)
""",
    )
    assert len(findings) == 1, findings
    assert findings[0].test == "test_repo_is_initialized"
    assert findings[0].binaries == ("git",)
    assert findings[0].indirect_via == "_init_repo", "the transitive hop must be named"


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        ('subprocess.run(["docker", "ps"])', ("docker",)),
        ('subprocess.Popen(["gitleaks", "detect"])', ("gitleaks",)),
        ('subprocess.check_call(["/usr/bin/git", "status"])', ("git",)),
        ('subprocess.check_output("git rev-parse HEAD", shell=True)', ("git",)),
        ('subprocess.run(f"git -C {tmp_path} log")', ("git",)),
        ('os.system("docker compose up")', ("docker",)),
    ],
    ids=["docker", "gitleaks", "abs-path", "shell-str", "fstring", "os-system"],
)
def test_recognizes_each_invocation_shape(tmp_path: Path, call: str, expected: tuple) -> None:
    findings = _findings(
        tmp_path,
        PREAMBLE
        + f"""\
import os


def test_thing(tmp_path):
    {call}
""",
    )
    assert len(findings) == 1, f"{call} was not recognized"
    assert findings[0].binaries == expected


def test_ignores_unguarded_binaries_and_dynamic_argv(tmp_path: Path) -> None:
    """bash IS in the validate image, and a runtime-built argv is unresolvable.

    The second case is an accepted false negative, pinned here so nobody
    mistakes the gate for proof of total coverage.
    """
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
def test_bash_helper(tmp_path):
    subprocess.run(["bash", "script.sh"], check=False)


def test_dynamic_argv(tmp_path):
    cmd = ["git", "status"]
    subprocess.run(cmd, check=False)
""",
    )
    assert findings == []


# --------------------------------------------------------------------------- #
# Guard idioms that must clear - every one is in live use in tests/
# --------------------------------------------------------------------------- #
GUARDED_SOURCES = {
    "inline-skipif": """\
@pytest.mark.skipif(shutil.which("git") is None, reason="no git")
def test_thing():
    subprocess.run(["git", "status"], check=False)
""",
    "module-alias": """\
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="no git")


@requires_git
def test_thing():
    subprocess.run(["git", "status"], check=False)
""",
    "pytestmark": """\
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="no git"
)


def test_thing():
    subprocess.run(["git", "status"], check=False)
""",
    "class-level": """\
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="no git")


@requires_git
class TestThings:
    def test_thing(self):
        subprocess.run(["git", "status"], check=False)
""",
    "body-level-skip": """\
def test_thing():
    if shutil.which("git") is None:
        pytest.skip("git unavailable")
    subprocess.run(["git", "status"], check=False)
""",
    "indirect-guarded": """\
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="no git")


def _git(*args):
    subprocess.run(["git", *args], check=False)


@requires_git
def test_thing():
    _git("status")
""",
}


@pytest.mark.parametrize("source", GUARDED_SOURCES.values(), ids=list(GUARDED_SOURCES))
def test_guard_idioms_clear(tmp_path: Path, source: str) -> None:
    assert _findings(tmp_path, PREAMBLE + source) == []


def test_guard_must_name_the_binary_actually_invoked(tmp_path: Path) -> None:
    """A docker skipif does not excuse a git shell-out."""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
@pytest.mark.skipif(shutil.which("docker") is None, reason="no docker")
def test_thing():
    subprocess.run(["git", "status"], check=False)
""",
    )
    assert len(findings) == 1
    assert findings[0].binaries == ("git",)


@pytest.mark.parametrize("anchor", ["def", "call"], ids=["on-def", "on-call"])
def test_allow_escape_suppresses(tmp_path: Path, anchor: str) -> None:
    def_comment = "  # binary-guard: allow intentional" if anchor == "def" else ""
    call_comment = "  # binary-guard: allow intentional" if anchor == "call" else ""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + f"""\
def test_thing():{def_comment}
    subprocess.run(["git", "status"], check=False){call_comment}
""",
    )
    assert findings == []


# --------------------------------------------------------------------------- #
# The gate itself
# --------------------------------------------------------------------------- #
def test_real_tests_tree_is_clean() -> None:
    """CPP's own suite must satisfy the rule this script enforces.

    This is the assertion that makes the #577 class of failure reproducible on a
    dev box, where `git` is present and the red pipeline is otherwise invisible.
    """
    findings = checker.check_tree(ROOT / "tests")
    rendered = "\n".join(f.render(ROOT) for f in findings)
    assert findings == [], f"unguarded shell-outs in tests/:\n{rendered}"


def test_this_module_does_not_shell_out() -> None:
    """Acceptance criterion 4 - the gate's own test needs no binary.

    Checked structurally rather than by grep: the sources this module feeds the
    checker are full of ``subprocess.run`` text, but they are string literals,
    never executed. What matters is that the module itself never imports a way
    to spawn one - so it can never be the unguarded test it is here to catch.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & {"subprocess", "os"}, (
        f"the binary-guard test must not import a subprocess API (found {imported})"
    )


def test_cli_reports_and_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_bad.py").write_text(
        PREAMBLE + 'def test_thing():\n    subprocess.run(["git", "status"])\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "test_thing" in out
    assert "shutil.which" in out, "the failure must show the fix, not just the finding"


def test_cli_is_silent_success_on_a_clean_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text("def test_thing():\n    assert True\n", encoding="utf-8")
    assert checker.main(["--root", str(tmp_path)]) == 0
    assert "ok" in capsys.readouterr().out

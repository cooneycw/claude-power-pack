"""`/flow:deploy` logs the DEPLOYMENT's exit status (issue #1712, seq 644).

Step 6 wrote `$?` into `.claude/deploy.log` after `mkdir -p .claude`, so the
status column recorded whether a directory could be made. `/flow:auto` reads a
`0` in that column as "already deployed". The blocks below are the document's
own, extracted and run; only the runner invocation is replaced by a stand-in
exit status, because the real runner needs a CPP checkout and a plan.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOCUMENT = REPO / ".claude" / "commands" / "flow" / "deploy.md"

requires_tools = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("make") is None or shutil.which("bash") is None,
    reason="needs git, make and bash",
)


def _block_after(heading: str, containing: str) -> str:
    """The first fenced bash block after `heading` that contains `containing`."""
    text = DOCUMENT.read_text(encoding="utf-8")
    section = text[text.index(heading) :]
    for block in re.findall(r"```bash\n(.*?)```", section, re.DOTALL):
        if containing in block:
            return block
    raise AssertionError(f"no bash block containing {containing!r} after {heading!r}")


def _project(root: Path, deploy_recipe: str) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "Makefile").write_text(f"deploy:\n\t{deploy_recipe}\n", encoding="utf-8")


def _logged_status(root: Path) -> str:
    line = (root / ".claude" / "deploy.log").read_text(encoding="utf-8").strip().splitlines()[-1]
    return line.split("|")[4].strip()


@requires_tools
@pytest.mark.parametrize(("recipe", "expected"), [("@exit 7", "2"), ("@true", "0")])
def test_the_fallback_path_logs_makes_own_status(tmp_path: Path, recipe: str, expected: str) -> None:
    """A failed recipe is make's exit 2; the log must say 2, not the 0 of the `mkdir` after it."""
    _project(tmp_path, recipe)
    fallback = _block_after("### Step 5:", 'make "$TARGET"')
    script = "TARGET=deploy\n" + fallback + _block_after("### Step 6:", "deploy.log")
    subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert _logged_status(tmp_path) == expected


@requires_tools
@pytest.mark.parametrize("runner_exit", ["5", "0"])
def test_the_runner_path_logs_the_runners_status(tmp_path: Path, runner_exit: str) -> None:
    _project(tmp_path, "@true")
    runner = _block_after("### Step 4:", "RUNNER_EXIT=$?")
    invocation = re.search(r"^.*python -m lib\.cicd run --plan deploy.*$", runner, re.MULTILINE)
    assert invocation, "the runner invocation moved; this test replaces that one line"
    assert "RUNNER_EXIT=$?" in runner[invocation.end() :], "the status is no longer captured right after the runner"
    stand_in = runner[runner.index(invocation.group(0)) :].replace(invocation.group(0), f"    (exit {runner_exit})")
    # Keep only from the invocation to the end of its `if`: the lines before it locate the CPP checkout.
    script = "TARGET=deploy\nif true; then\n" + stand_in + _block_after("### Step 6:", "deploy.log")
    ran = subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert (tmp_path / ".claude" / "deploy.log").is_file(), ran.stderr
    assert _logged_status(tmp_path) == runner_exit


def test_the_verification_step_logs_the_same_variable() -> None:
    """Step 8.5 already wrote `$DEPLOY_EXIT`, which nothing in the document assigned."""
    text = DOCUMENT.read_text(encoding="utf-8")
    assert text.count("DEPLOY_EXIT=") == 2, "expected one assignment on each of the two deploy paths"
    assert "| $?" not in text, "a log line still records `$?` of whatever ran last"

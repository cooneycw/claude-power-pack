"""`/flow:deploy <TARGET>` runs the target it was given (issue #1759).

The document validated TARGET, then ran the deterministic runner's `deploy`
plan whenever a CPP checkout was found. That plan's last step is the literal
`make deploy`. So `/flow:deploy deploy-staging` ran `make deploy` and logged
`deploy-staging`: asked for staging, deployed production.

These tests RUN the document's own bash blocks, in the order and under the
conditions its prose gives, against a Makefile whose two targets each write a
different marker file. Nothing real is deployed. Two things stand in for the
real thing and the tests say nothing about them:

- `uv` is a stub on PATH. Asked for the deploy plan, it does what that plan's
  last step does (`make deploy`); asked for the security gate, it records the
  call. The real runner and the real gate are not run.
- "the agent follows the prose" is this file's `_script()`. An agent reading
  the document differently is not covered.

`test_the_real_deploy_plan_still_ends_in_make_deploy` ties the stub to the
real plan: the document's condition (runner only for `deploy`) is right only
while that plan cannot take a target.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOCUMENT = REPO / ".claude" / "commands" / "flow" / "deploy.md"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("make") is None or shutil.which("bash") is None,
    reason="needs git, make and bash",
)

UV_STUB = """#!/usr/bin/env bash
# Stand-in for `uv run ...` (issue #1759 tests). Records every call.
printf '%s\\n' "$*" >> "$STUB_LOG"
case "$*" in
  *"lib.cicd run --plan deploy"*)
    echo runner >> "$STUB_CALLS"
    [ -n "${STUB_RUNNER_FAILS:-}" ] && exit 5   # a plan step failed before `make deploy`
    exec make deploy ;;
  *"lib.security gate flow_deploy"*) echo gate >> "$STUB_CALLS"; exit "${STUB_GATE_EXIT:-0}" ;;
  *) echo "unexpected uv call: $*" >&2; exit 97 ;;
esac
"""

MAKEFILE = (
    "deploy:\n\t@echo ran-deploy > marker-deploy\n"
    "deploy-other:\n\t@echo ran-deploy-other > marker-deploy-other\n"
    "deploy-broken:\n\t@echo ran-deploy-broken > marker-deploy-broken; exit 7\n"
)


def _block(heading: str, containing: str) -> str:
    text = DOCUMENT.read_text(encoding="utf-8")
    section = text[text.index(heading) :]
    for block in re.findall(r"```bash\n(.*?)```", section, re.DOTALL):
        if containing in block:
            return block
    raise AssertionError(f"no bash block containing {containing!r} after {heading!r}")


def _script() -> str:
    """The document's blocks, joined by the conditions its prose states."""
    validate = _block("### Step 3: Verify Target Exists", 'TARGET="${1:-deploy}"')
    runner = _block("### Step 4b:", "lib.cicd run --plan deploy")
    gate = _block("**Fallback path**", "lib.security gate flow_deploy")
    fallback = _block("### Step 5:", 'make "$TARGET"')
    log = _block("### Step 6:", "deploy.log")
    return (
        validate
        + runner
        + 'if [ -n "${RUNNER_EXIT+set}" ]; then\n'
        # "If runner fails (exit non-zero): ... report the failed step, and stop."
        + '    [ "$RUNNER_EXIT" -eq 0 ] || exit 1\n'
        # "If runner succeeds (exit 0): ... skip to Step 6."
        + "else\n"
        + gate
        # "If the gate fails (critical or high findings): stop and report."
        + "    [ $? -eq 0 ] || exit 1\n"
        + fallback
        + "fi\n"
        + log
    )


def _run(
    tmp_path: Path, *, runner_found: bool, target: str | None, gate_exit: int = 0, runner_fails: bool = False
) -> dict[str, list[str]]:
    project = tmp_path / "project"
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    for directory in (project, home, bin_dir):
        directory.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "Makefile").write_text(MAKEFILE, encoding="utf-8")
    if runner_found:
        cpp = home / "Projects" / "claude-power-pack"
        cpp.mkdir(parents=True)
        (cpp / "CLAUDE.md").write_text("stub checkout\n", encoding="utf-8")
    stub = bin_dir / "uv"
    stub.write_text(UV_STUB, encoding="utf-8")
    stub.chmod(0o755)
    calls = tmp_path / "calls"
    calls.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "STUB_LOG": str(tmp_path / "uv.log"),
        "STUB_CALLS": str(calls),
        "STUB_GATE_EXIT": str(gate_exit),
        "STUB_RUNNER_FAILS": "1" if runner_fails else "",
    }
    args = ["bash", "-c", _script(), "flow-deploy"] + ([target] if target else [])
    ran = subprocess.run(args, cwd=project, env=env, capture_output=True, text=True, check=False)
    log = project / ".claude" / "deploy.log"
    markers = sorted(path.name for path in project.glob("marker-*"))
    if not log.is_file():
        return {"markers": markers, "calls": calls.read_text(encoding="utf-8").split(), "logged": []}
    assert ran.returncode == 0, ran.stdout + ran.stderr
    fields = [field.strip() for field in log.read_text(encoding="utf-8").strip().splitlines()[-1].split("|")]
    return {
        "markers": markers,
        "calls": calls.read_text(encoding="utf-8").split(),
        "logged": [fields[1], fields[4]],  # the target named in the log line, and its status
    }


@pytest.mark.parametrize("target", [None, "deploy"])
def test_row_1_the_default_target_with_the_runner_found_takes_the_runner(tmp_path: Path, target: str | None) -> None:
    result = _run(tmp_path, runner_found=True, target=target)
    assert result["calls"] == ["runner"], "the default target must still go through the runner, unchanged"
    assert result["markers"] == ["marker-deploy"]
    assert result["logged"] == ["deploy", "0"]


@pytest.mark.parametrize("target", [None, "deploy"])
def test_row_2_the_default_target_with_no_runner_takes_the_gate_then_make(tmp_path: Path, target: str | None) -> None:
    result = _run(tmp_path, runner_found=False, target=target)
    assert result["calls"] == ["gate"]
    assert result["markers"] == ["marker-deploy"]
    assert result["logged"] == ["deploy", "0"]


def test_row_3_another_target_with_the_runner_found_runs_that_target_and_not_deploy(tmp_path: Path) -> None:
    """The defect. On main the runner is called and `marker-deploy` is what gets written."""
    result = _run(tmp_path, runner_found=True, target="deploy-other")
    assert result["markers"] == ["marker-deploy-other"], "the wrong target ran"
    assert "runner" not in result["calls"], "the runner's plan can only run `make deploy`"
    assert result["calls"] == ["gate"], "the security gate must still run before a non-default target"
    assert result["logged"] == ["deploy-other", "0"]


def test_row_4_another_target_with_no_runner_is_unchanged(tmp_path: Path) -> None:
    result = _run(tmp_path, runner_found=False, target="deploy-other")
    assert result["calls"] == ["gate"]
    assert result["markers"] == ["marker-deploy-other"]
    assert result["logged"] == ["deploy-other", "0"]


@pytest.mark.parametrize("runner_found", [True, False])
def test_a_failing_non_default_target_is_logged_with_its_own_status(tmp_path: Path, runner_found: bool) -> None:
    """make exits 2 for a failed recipe; the log must carry that, for the target that ran."""
    result = _run(tmp_path, runner_found=runner_found, target="deploy-broken")
    assert result["markers"] == ["marker-deploy-broken"]
    assert result["logged"] == ["deploy-broken", "2"]


def test_the_real_deploy_plan_still_ends_in_make_deploy() -> None:
    """If the plan ever learns to take a target, the document's `= "deploy"` condition is wrong: come here."""
    from lib.cicd.steps import BUILTIN_PLANS

    last = BUILTIN_PLANS["deploy"][-1]
    assert (last.id, last.command) == ("deploy", "make deploy")


# --- the two places the prose says STOP (counter-model review, pass 1) -------
#
# The first version of `_script()` sent every outcome on to Step 6, so nothing
# here showed that a refused gate or a failed runner deploys nothing.

@pytest.mark.parametrize(("runner_found", "target"), [(True, "deploy-other"), (False, "deploy-other"), (False, None)])
def test_a_failed_security_gate_deploys_nothing_and_logs_nothing(
    tmp_path: Path, runner_found: bool, target: str | None
) -> None:
    result = _run(tmp_path, runner_found=runner_found, target=target, gate_exit=1)
    assert result["calls"] == ["gate"]
    assert result["markers"] == [], "a target ran after the security gate refused"
    assert result["logged"] == [], "a deployment was logged after the security gate refused"


def test_a_failed_runner_stops_before_the_log_and_does_not_fall_back(tmp_path: Path) -> None:
    result = _run(tmp_path, runner_found=True, target=None, runner_fails=True)
    assert result["calls"] == ["runner"], "a failed runner must not be followed by the fallback path"
    assert result["markers"] == []
    assert result["logged"] == []

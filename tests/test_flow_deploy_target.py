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
  *"lib.security gate flow_deploy"*)
    echo gate >> "$STUB_CALLS"
    # The real gate prints ONE verdict line on every path (lib/security/cli.py).
    [ -n "${STUB_GATE_VERDICT:-}" ] && echo "SECURITY_GATE: flow_deploy $STUB_GATE_VERDICT (stub)"
    exit "${STUB_GATE_EXIT:-0}" ;;
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


#: Where a CPP checkout can live; the documents look in exactly these.
CPP_HOME_LOCATIONS = ("Projects/claude-power-pack", ".claude-power-pack")


def _run(
    tmp_path: Path,
    *,
    runner_found: bool,
    target: str | None,
    gate_exit: int = 0,
    runner_fails: bool = False,
    gate_verdict: str | None = "auto",
    cpp_at: str = CPP_HOME_LOCATIONS[0],
) -> dict[str, list[str]]:
    """`runner_found` means a CPP checkout exists (at `cpp_at`, under HOME).
    `gate_verdict`: "auto" prints PASS for exit 0 and FAIL otherwise, as the
    real gate does; None prints no verdict line at all."""
    project = tmp_path / "project"
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    for directory in (project, home, bin_dir):
        directory.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "Makefile").write_text(MAKEFILE, encoding="utf-8")
    if runner_found:
        cpp = home / cpp_at
        (cpp / "lib" / "security").mkdir(parents=True)
        (cpp / "CLAUDE.md").write_text("stub checkout\n", encoding="utf-8")
        (cpp / "lib" / "security" / "__init__.py").write_text("", encoding="utf-8")
    if gate_verdict == "auto":
        gate_verdict = "PASS" if gate_exit == 0 else "FAIL"
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
        "STUB_GATE_VERDICT": gate_verdict or "",
        "STUB_RUNNER_FAILS": "1" if runner_fails else "",
    }
    args = ["bash", "-c", _script(), "flow-deploy"] + ([target] if target else [])
    ran = subprocess.run(args, cwd=project, env=env, capture_output=True, text=True, check=False)
    log = project / ".claude" / "deploy.log"
    markers = sorted(path.name for path in project.glob("marker-*"))
    uv_log = tmp_path / "uv.log"
    extra = {
        "stderr": [ran.stderr],
        "returncode": [str(ran.returncode)],
        "uv": uv_log.read_text(encoding="utf-8").splitlines() if uv_log.is_file() else [],
    }
    if not log.is_file():
        return {"markers": markers, "calls": calls.read_text(encoding="utf-8").split(), "logged": [], **extra}
    assert ran.returncode == 0, ran.stdout + ran.stderr
    fields = [field.strip() for field in log.read_text(encoding="utf-8").strip().splitlines()[-1].split("|")]
    return {
        "markers": markers,
        "calls": calls.read_text(encoding="utf-8").split(),
        "logged": [fields[1], fields[4]],  # the target named in the log line, and its status
        **extra,
    }


@pytest.mark.parametrize("target", [None, "deploy"])
def test_row_1_the_default_target_with_the_runner_found_takes_the_runner(tmp_path: Path, target: str | None) -> None:
    result = _run(tmp_path, runner_found=True, target=target)
    assert result["calls"] == ["runner"], "the default target must still go through the runner, unchanged"
    assert result["markers"] == ["marker-deploy"]
    assert result["logged"] == ["deploy", "0"]


@pytest.mark.parametrize("target", [None, "deploy", "deploy-other"])
def test_rows_2_and_4_with_no_checkout_the_scan_cannot_run_so_nothing_is_deployed(
    tmp_path: Path, target: str | None
) -> None:
    """Issue #1760. These rows used to read "takes the gate then make": the
    scan command named one location and the next line said to skip it when
    unavailable, so with no checkout the deploy went out unscanned. (The stub
    `uv` answered for any path, which is how the old rows passed.)"""
    result = _run(tmp_path, runner_found=False, target=target)
    assert result["calls"] == [], "no scanner exists, so nothing may be called"
    assert result["markers"] == [], "a target ran with no security scan"
    assert result["logged"] == []
    assert result["returncode"] != ["0"]
    stop = result["stderr"][0]
    assert stop.startswith("STOP: no scanner in "), stop
    for location in ("~/Projects/claude-power-pack", "/opt/claude-power-pack", "~/.claude-power-pack"):
        assert location in stop, f"the stop message does not name {location}"


def test_row_3_another_target_with_the_runner_found_runs_that_target_and_not_deploy(tmp_path: Path) -> None:
    """The defect. On main the runner is called and `marker-deploy` is what gets written."""
    result = _run(tmp_path, runner_found=True, target="deploy-other")
    assert result["markers"] == ["marker-deploy-other"], "the wrong target ran"
    assert "runner" not in result["calls"], "the runner's plan can only run `make deploy`"
    assert result["calls"] == ["gate"], "the security gate must still run before a non-default target"
    assert result["logged"] == ["deploy-other", "0"]


def test_the_scan_runs_from_wherever_the_checkout_is(tmp_path: Path) -> None:
    """Issue #1760: a checkout at another known location. The scan command
    named `${HOME}/Projects/claude-power-pack` whatever was found."""
    elsewhere = CPP_HOME_LOCATIONS[1]
    result = _run(tmp_path, runner_found=True, target="deploy-other", cpp_at=elsewhere)
    assert result["calls"] == ["gate"]
    gate_call = next(line for line in result["uv"] if "lib.security gate flow_deploy" in line)
    assert f"/{elsewhere} " in gate_call + " ", gate_call
    assert "Projects/claude-power-pack" not in gate_call
    assert result["markers"] == ["marker-deploy-other"]


@pytest.mark.parametrize(
    ("gate_exit", "gate_verdict"),
    [
        (0, None),         # exit 0 and no verdict line: something else answered
        (0, "FAIL"),       # a verdict line that is not PASS
        (2, "UNKNOWN"),    # the gate's own "could not decide"
        (2, None),         # uv could not start it at all
    ],
)
def test_only_exit_0_WITH_the_pass_line_lets_a_deploy_through(
    tmp_path: Path, gate_exit: int, gate_verdict: str | None
) -> None:
    """Exit 2 is both the gate's UNKNOWN and uv's "no such project", so the
    exit code alone cannot say the scan passed (issue #1760)."""
    result = _run(tmp_path, runner_found=True, target="deploy-other", gate_exit=gate_exit, gate_verdict=gate_verdict)
    assert result["calls"] == ["gate"]
    assert result["markers"] == [], "a target ran without a passing scan"
    assert result["logged"] == []
    assert "STOP: scan did not pass" in result["stderr"][0]


def test_the_document_no_longer_tells_the_reader_to_skip_the_scan() -> None:
    text = DOCUMENT.read_text(encoding="utf-8")
    fallback = text[text.index("**Fallback path**") : text.index("### Step 5:")]
    assert "skip this step" not in fallback.lower()
    assert "${HOME}/Projects/claude-power-pack" not in fallback
    assert "Never skip the scan" in fallback


@pytest.mark.parametrize("cpp_at", CPP_HOME_LOCATIONS)
def test_a_failing_non_default_target_is_logged_with_its_own_status(tmp_path: Path, cpp_at: str) -> None:
    """make exits 2 for a failed recipe; the log must carry that, for the target that ran."""
    result = _run(tmp_path, runner_found=True, target="deploy-broken", cpp_at=cpp_at)
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

@pytest.mark.parametrize("cpp_at", CPP_HOME_LOCATIONS)
def test_a_failed_security_gate_deploys_nothing_and_logs_nothing(tmp_path: Path, cpp_at: str) -> None:
    result = _run(tmp_path, runner_found=True, target="deploy-other", gate_exit=1, cpp_at=cpp_at)
    assert result["calls"] == ["gate"]
    assert result["markers"] == [], "a target ran after the security gate refused"
    assert result["logged"] == [], "a deployment was logged after the security gate refused"


def test_a_failed_runner_stops_before_the_log_and_does_not_fall_back(tmp_path: Path) -> None:
    result = _run(tmp_path, runner_found=True, target=None, runner_fails=True)
    assert result["calls"] == ["runner"], "a failed runner must not be followed by the fallback path"
    assert result["markers"] == []
    assert result["logged"] == []


# --- the reader of the log line: /flow:auto's already-deployed check ---------
#
# Step 9 of /flow:auto skips `make deploy` when `.claude/deploy.log` already
# records a successful deployment of HEAD. Its match on the target column was
# unanchored, so a `deploy-other` line counted as a deployment of `deploy`.
# That was accidentally true while /flow:deploy ran `make deploy` for every
# target; once the named target runs, it is a skipped production deploy.

def _already_deployed_check() -> str:
    text = (REPO / ".claude" / "commands" / "flow" / "auto.md").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if "awk -F'|'" in line and ".claude/deploy.log" in line]
    assert len(lines) == 1, "auto.md's already-deployed check moved; this test extracts that one line"
    condition = re.search(r"&& (awk -F'\|'.*\.claude/deploy\.log); then", lines[0])
    assert condition, lines[0]
    return condition.group(1)


@pytest.mark.parametrize(
    ("logged_target", "status", "deployed"),
    [
        ("deploy", "0", True),
        ("deploy-other", "0", False),   # the defect: another target's success read as this one's
        ("deploy-staging", "0", False),
        ("predeploy", "0", False),
        ("deploy", "2", False),         # a failed deploy is not a deployment
    ],
)
def test_only_a_successful_deploy_of_the_default_target_marks_head_as_deployed(
    tmp_path: Path, logged_target: str, status: str, deployed: bool
) -> None:
    (tmp_path / ".claude").mkdir()
    line = f"2026-11-12T00:00:00-05:00 | {logged_target} | abc1234 | main | {status}\n"
    (tmp_path / ".claude" / "deploy.log").write_text(line, encoding="utf-8")
    script = 'HEAD_SHA=abc1234\n' + _already_deployed_check()
    ran = subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert (ran.returncode == 0) is deployed, f"{logged_target} | {status}: awk exited {ran.returncode}"


def test_a_deploy_line_and_another_targets_line_for_the_same_commit(tmp_path: Path) -> None:
    """Both in one log: the `deploy` line is what marks HEAD deployed, in either order."""
    (tmp_path / ".claude").mkdir()
    other = "2026-11-12T00:00:00-05:00 | deploy-other | abc1234 | main | 0\n"
    real = "2026-11-12T00:05:00-05:00 | deploy | abc1234 | main | 0\n"
    script = "HEAD_SHA=abc1234\n" + _already_deployed_check()
    log = tmp_path / ".claude" / "deploy.log"
    for content, deployed in ((other, False), (other + real, True), (real + other, True)):
        log.write_text(content, encoding="utf-8")
        ran = subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True, check=False)
        assert (ran.returncode == 0) is deployed, content

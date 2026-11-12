"""A curl stand-in that is piped a header must read it (issue #1718).

`flow-ci-status.sh` and `gh-pr-merge.sh` hand curl its Authorization header on
stdin (`printf ... | curl -H @- ...`) under `pipefail`. Real curl reads the
header before it does anything else. A stub that answers and exits without
reading it can close the pipe before the writer has run; the writer then dies
on the closed pipe, the pipeline fails, and the script reports that it could
not look. Nothing was wrong with the script. That one race read as two
different flakes:

- the `flow-ci-status-stalled` control's known-bad case scoring GOOD
  (pipelines 3553, 3620), and
- `test_coordination_signal_preserves_queue_unless_explicitly_enabled`
  failing with `assert 0 == 3` (pipelines 3612, 3635, 3773).

It does not happen often enough to wait for - 150 runs of the second, at a
load average of 24, never lost it - so these tests make the writer late on
purpose: a `BASH_ENV` file that sleeps before the one header write and
changes nothing else. With the stubs as they were, the first assertion in
each test fails.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_gh_pr_merge import _make_stubs

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    any(shutil.which(name) is None for name in ("bash", "sh", "git", "jq", "sed", "grep", "cat")),
    reason="requires bash, sh, git, jq, sed, grep and cat",
)

CONTROLS = ("flow-ci-status-stalled", "flow-ci-status", "flow-ci-status-wait", "flow-ci-status-cancellation")


@pytest.fixture()
def late_header(tmp_path: Path) -> dict[str, str]:
    """An environment in which every bash the scripts start writes the
    Authorization header 0.3 seconds late, and does nothing else differently."""
    hook = tmp_path / "late-header.bashenv"
    hook.write_text(
        "printf() { case \"$1\" in 'Authorization: Bearer %s\\n') sleep 0.3 ;; esac; builtin printf \"$@\"; }\n")
    return {**os.environ, "BASH_ENV": str(hook)}


def test_the_late_header_hook_delays_that_write_and_no_other(late_header: dict[str, str]) -> None:
    """The perturbation itself: without it the tests below could pass by not
    perturbing anything."""
    timed = ("start=$(date +%s%N); printf 'Authorization: Bearer %s\\n' x >/dev/null; mid=$(date +%s%N); "
             "printf 'other %s\\n' x >/dev/null; end=$(date +%s%N); "
             "echo $(( (mid - start) / 1000000 )) $(( (end - mid) / 1000000 ))")
    script = Path(late_header["BASH_ENV"]).parent / "timed.sh"
    script.write_text(timed + "\n")
    header_ms, other_ms = map(int, subprocess.run(
        ["bash", str(script)], env=late_header, capture_output=True, text=True, check=True).stdout.split())
    assert header_ms >= 290, f"the header write was not delayed ({header_ms} ms)"
    assert other_ms < 200, f"another write was delayed too ({other_ms} ms)"


@pytest.mark.parametrize("control", CONTROLS)
def test_a_control_still_passes_when_the_header_arrives_late(control: str, late_header: dict[str, str]) -> None:
    """Each control drives `flow-ci-status.sh` through a curl stub. Before the
    stubs read stdin, a late header made the gate print that it could not
    look, and the stalled control scored its known-bad case GOOD."""
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-negative-controls.py"), "--root", str(ROOT),
         "--strict", "--control", f"controls/{control}"],
        env=late_header, capture_output=True, text=True, timeout=100, check=False)
    assert "NEGATIVE_CONTROL_VERDICT: PASS" in done.stdout, done.stdout[-1500:] + done.stderr[-500:]
    assert done.returncode == 0


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq absent; the gate needs it")
def test_the_stalled_runner_does_not_score_a_gate_that_could_not_look_as_good(
        tmp_path: Path, late_header: dict[str, str]) -> None:
    """The second half of that control's defect: its runner mapped `running`
    to the good answer without reading the gate's stall-check line. With the
    stub's read taken back out and the header late, the gate says it could not
    check - and the runner now says it cannot run, not `running`."""
    runner = (ROOT / "controls" / "flow-ci-status-stalled" / "run-case.sh").read_text()
    read = "cat >/dev/null 2>&1 || true\n"
    assert runner.count(read) == 1, "precondition: the stub's read is where this test expects it"
    without = tmp_path / "run-case-without-the-read.sh"
    without.write_text(runner.replace(read, ""))
    case = ROOT / "controls" / "flow-ci-status-stalled" / "cases" / "bad-past-timeout"
    gate = ROOT / "scripts" / "flow-ci-status.sh"
    done = subprocess.run(["sh", str(without), str(case), str(gate)], env=late_header,
                          capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 3, done.stdout + done.stderr
    assert "FLOW_CI_STALLED_CONTROL: cannot-run" in done.stdout
    assert "FLOW_CI_STALL_CHECK: unavailable" in done.stdout
    # and with the read in place the same late header changes nothing
    intact = subprocess.run(["sh", str(ROOT / "controls" / "flow-ci-status-stalled" / "run-case.sh"),
                             str(case), str(gate)], env=late_header, capture_output=True, text=True,
                            timeout=60, check=False)
    assert (intact.returncode, intact.stdout.strip().splitlines()[-1]) == (1, "FLOW_CI_STALLED_CONTROL: stalled")


def test_the_merge_helpers_curl_stub_reads_a_late_header(tmp_path: Path) -> None:
    """The stub `tests/test_gh_pr_merge.py` builds, driven the way the script
    drives it: a writer that is late, under pipefail. The pipeline succeeds
    only if the stub is still there to read."""
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    curl = stubs["GH_PR_MERGE_CURL"]
    piped = subprocess.run(
        ["bash", "-o", "pipefail", "-c",
         '(sleep 0.3; printf "Authorization: Bearer %s\\n" t) | "$0" -sf -H @- '
         '-H "Accept: application/json" https://wp.example.invalid/api/repos/lookup/o/r', curl],
        capture_output=True, text=True, timeout=30, check=False)
    assert piped.returncode == 0, f"the writer lost the pipe (exit {piped.returncode}): {piped.stderr}"
    assert '"id"' in piped.stdout


def test_the_merge_helpers_curl_stub_leaves_stdin_alone_when_nothing_is_piped(tmp_path: Path) -> None:
    """It reads only where a header is piped (`-H @-`). Given an open stdin
    that never closes and no `@-`, it must not wait on it."""
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    curl = stubs["GH_PR_MERGE_CURL"]
    held = subprocess.Popen(["sleep", "30"], stdout=subprocess.PIPE)
    try:
        done = subprocess.run([curl, "-sf", "https://wp.example.invalid/api/repos/lookup/o/r"],
                              stdin=held.stdout, capture_output=True, text=True, timeout=10, check=False)
    finally:
        held.kill()
        held.wait()
    assert done.returncode == 0

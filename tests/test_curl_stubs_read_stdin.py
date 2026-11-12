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
load average of 24, never lost it - and a test that only DELAYS the writer
would itself depend on scheduling: under load the stub may still be there
when a late, small write arrives, and the write succeeds into the pipe's
buffer unread. So these tests take timing out of it. A `BASH_ENV` file makes
the one header write larger than a pipe can hold. A writer of that much
cannot finish unless something reads it: with a stub that reads, it finishes;
with a stub that exits unread, it dies on the closed pipe, every time,
whichever of them was scheduled first. With the stubs as they were, the
first assertion in each test fails.
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
    any(shutil.which(name) is None for name in ("bash", "sh", "git", "jq", "sed", "grep", "cat", "head", "wc")),
    reason="requires bash, sh, git, jq, sed, grep, cat, head and wc",
)

CONTROLS = ("flow-ci-status-stalled", "flow-ci-status", "flow-ci-status-wait", "flow-ci-status-cancellation")


#: More than any pipe holds (Linux: 64 KiB by default, 1 MiB at most
#: unprivileged). A write this size cannot complete into a buffer.
PAD_BYTES = 2 * 1024 * 1024


@pytest.fixture()
def late_header(tmp_path: Path) -> dict[str, str]:
    """An environment in which every bash the scripts start follows the
    Authorization header with more bytes than a pipe can hold, and writes
    everything else as before. The name is what it stands in for: a header a
    stub that does not read can never have received in full."""
    hook = tmp_path / "unreadable-header.bashenv"
    hook.write_text(
        "printf() {\n"
        "  case \"$1\" in\n"
        "    'Authorization: Bearer %s\\n')\n"
        "      builtin printf \"$@\" || return\n"
        f"      head -c {PAD_BYTES} /dev/zero || return\n"
        "      return 0 ;;\n"
        "  esac\n"
        "  builtin printf \"$@\"\n"
        "}\n")
    return {**os.environ, "BASH_ENV": str(hook)}


def test_the_hook_pads_that_one_write_and_no_other(late_header: dict[str, str], tmp_path: Path) -> None:
    """The perturbation itself, by byte count and not by a clock: without it
    the tests below could pass by not perturbing anything."""
    script = tmp_path / "count.sh"
    script.write_text("printf 'Authorization: Bearer %s\\n' x | wc -c\nprintf 'other %s\\n' x | wc -c\n")
    header, other = map(int, subprocess.run(
        ["bash", str(script)], env=late_header, capture_output=True, text=True, check=True).stdout.split())
    assert header == len("Authorization: Bearer x\n") + PAD_BYTES
    assert other == len("other x\n")


def test_a_writer_of_that_much_dies_when_nothing_reads_it(late_header: dict[str, str], tmp_path: Path) -> None:
    """And the mechanism: a reader that exits unread fails the pipeline under
    pipefail; one that reads does not. No sleep on either side."""
    script = tmp_path / "pipe.sh"
    script.write_text("set -o pipefail\nprintf 'Authorization: Bearer %s\\n' x | \"$@\"\n")
    unread = subprocess.run(["bash", str(script), "true"], env=late_header, capture_output=True, timeout=30)
    read = subprocess.run(["bash", str(script), "cat"], env=late_header, capture_output=True, timeout=30)
    assert unread.returncode != 0, "a reader that exits unread did not fail the pipeline"
    assert read.returncode == 0


@pytest.mark.parametrize("control", CONTROLS)
def test_a_control_still_passes_when_the_header_cannot_be_buffered(control: str, late_header: dict[str, str]) -> None:
    """Each control drives `flow-ci-status.sh` through a curl stub. Before the
    stubs read stdin, a header the stub had not read made the gate print that
    it could not look, and the stalled control scored its known-bad case GOOD."""
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
    stub's read taken back out and the header unbufferable, the gate says it could not
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
    # and with the read in place the same header changes nothing
    intact = subprocess.run(["sh", str(ROOT / "controls" / "flow-ci-status-stalled" / "run-case.sh"),
                             str(case), str(gate)], env=late_header, capture_output=True, text=True,
                            timeout=60, check=False)
    assert (intact.returncode, intact.stdout.strip().splitlines()[-1]) == (1, "FLOW_CI_STALLED_CONTROL: stalled")


def test_the_merge_helpers_curl_stub_reads_a_header_too_large_to_buffer(tmp_path: Path) -> None:
    """The stub `tests/test_gh_pr_merge.py` builds, driven the way the script
    drives it, under pipefail, with a writer that cannot finish into a buffer.
    The pipeline succeeds only if the stub reads."""
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    curl = stubs["GH_PR_MERGE_CURL"]
    piped = subprocess.run(
        ["bash", "-o", "pipefail", "-c",
         f'(printf "Authorization: Bearer %s\\n" t; head -c {PAD_BYTES} /dev/zero) | "$0" -sf -H @- '
         '-H "Accept: application/json" https://wp.example.invalid/api/repos/lookup/o/r', curl],
        capture_output=True, text=True, timeout=30, check=False)
    assert piped.returncode == 0, f"the writer lost the pipe (exit {piped.returncode}): {piped.stderr}"
    assert '"id"' in piped.stdout


def test_the_merge_helpers_curl_stub_leaves_stdin_alone_when_nothing_is_piped(tmp_path: Path) -> None:
    """It reads only where a header is piped (`-H @-`). Given an open stdin
    that never closes and no `@-`, it must not wait on it."""
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    curl = stubs["GH_PR_MERGE_CURL"]
    # A Python holder, not `sleep`: one binary fewer to depend on.
    held = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], stdout=subprocess.PIPE)
    try:
        done = subprocess.run([curl, "-sf", "https://wp.example.invalid/api/repos/lookup/o/r"],
                              stdin=held.stdout, capture_output=True, text=True, timeout=10, check=False)
    finally:
        held.kill()
        held.wait()
    assert done.returncode == 0

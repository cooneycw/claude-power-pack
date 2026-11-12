"""The sweep's `--apply` control deletes, so its runner is itself controlled (issue #1726).

`controls/flow-worktree-sweep-apply/run-case.sh` runs the real sweep with
`--apply`, and then runs an anchor that is a naive sweep written to be blind:
it removes any worktree whose pull request merged. Both delete worktrees of
whatever repository they are pointed at.

So the runner builds its own target under one temporary directory, names it
by `--repo` and by nothing in the environment, and before invoking the gate
checks that every worktree git lists for that repository lies under that
directory. These tests show the refusal firing, and show that it is the check
and not an accident of the fixture.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls" / "flow-worktree-sweep-apply"
RUNNER = CONTROL / "run-case.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None or shutil.which("sh") is None,
    reason="the runner builds a real git repository",
)


def _recording_gate(tmp_path: Path) -> tuple[Path, Path]:
    """A stand-in for the sweep that records that it was invoked, and with what."""
    log = tmp_path / "gate-was-invoked.log"
    gate = tmp_path / "recording-gate.sh"
    gate.write_text(f'#!/bin/bash\nprintf "%s\\n" "$*" >> "{log}"\necho "FLOW_WORKTREE_SWEEP: ok"\n',
                    encoding="utf-8")
    gate.chmod(0o755)
    return gate, log


def _case(tmp_path: Path, **facts: str) -> Path:
    case = tmp_path / "case"
    case.mkdir()
    (case / "facts.txt").write_text("".join(f"{k}={v}\n" for k, v in facts.items()), encoding="utf-8")
    return case


def _run(case: Path, gate: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", str(RUNNER), str(case), str(gate)], cwd=ROOT, capture_output=True, text=True,
                          timeout=120, check=False, env={**os.environ, **(env or {})})


def test_the_runner_refuses_when_a_worktree_lies_outside_its_directory(tmp_path: Path) -> None:
    gate, log = _recording_gate(tmp_path)
    done = _run(_case(tmp_path, pr="merged-at-tip", outside="1"), gate)
    assert done.returncode == 2, done.stdout + done.stderr
    assert ("FLOW_WORKTREE_SWEEP_APPLY_CONTROL: refused - a worktree of the fixture repository lies outside"
            in done.stdout)
    assert "nothing was invoked" in done.stdout
    assert not log.exists(), "the gate was invoked for a repository with a worktree outside the runner's directory"


def test_the_same_case_without_the_outside_worktree_does_invoke_the_gate(tmp_path: Path) -> None:
    """Wrong-reason control: the refusal above is the check. Drop the one fact
    and the same recording gate is invoked, with --repo and --apply."""
    gate, log = _recording_gate(tmp_path)
    _run(_case(tmp_path, pr="merged-at-tip"), gate)
    assert log.exists(), "the gate was never invoked, so the refusal test proves nothing"
    argv = log.read_text().split()
    assert "--apply" in argv and "--repo" in argv


def test_the_runner_takes_its_target_from_nothing_in_the_environment(tmp_path: Path) -> None:
    """Every path-like variable a sweep or git might honour, pointed at a
    decoy repository: the gate is still invoked on the runner's own."""
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(decoy)], check=True, capture_output=True, timeout=60)
    gate, log = _recording_gate(tmp_path)
    _run(_case(tmp_path, pr="merged-at-tip"), gate,
         env={"GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy), "REPO": str(decoy),
              "START_PATH": str(decoy), "WT": str(decoy)})
    argv = log.read_text().split()
    target = argv[argv.index("--repo") + 1]
    assert str(decoy) not in target, f"the runner was steered to {target}"
    assert not Path(target).exists(), "the runner's own directory is removed when it exits"


@pytest.mark.parametrize("case,expected", [
    ("bad-unpushed-commit-after-the-merge", "finding - kept, and the reason names work: skip unpushed"),
    ("bad-github-cannot-answer", "finding - could not tell, and said so: undecidable"),
    ("good-merged-and-nothing-left", "no-finding - removed"),
])
def test_the_real_sweep_on_each_committed_case(case: str, expected: str) -> None:
    done = _run(CONTROL / "cases" / case, ROOT / "scripts" / "flow-worktree-sweep.sh")
    assert f"FLOW_WORKTREE_SWEEP_APPLY_CONTROL: {expected}" in done.stdout, done.stdout[-600:]


@pytest.mark.parametrize("case,deleted", [
    ("bad-unpushed-commit-after-the-merge", "no-finding - removed"),
    ("bad-github-cannot-answer", "no-finding - kept as having no finished PR; run ok"),
])
def test_the_naive_anchor_misses_both_bad_cases(case: str, deleted: str) -> None:
    """What the control is for: the anchor deletes unpushed work in one case
    and reports a clean run it could not have established in the other."""
    anchor = CONTROL / "anchors" / "constructed-merged-means-remove-flow-worktree-sweep.sh"
    done = _run(CONTROL / "cases" / case, anchor)
    assert done.returncode == 0 and f"FLOW_WORKTREE_SWEEP_APPLY_CONTROL: {deleted}" in done.stdout, done.stdout[-600:]

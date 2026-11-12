"""The three worktree controls' runners act on their own fixture and nothing else (issue #1726).

Each runner builds a git repository in a temporary directory and commits to
it. Git, though, is steered by its environment: with a caller's `GIT_DIR`,
`GIT_WORK_TREE` or `GIT_INDEX_FILE` in place, `git -C <fixture>` acts on the
CALLER's repository - a fixture commit would commit the caller's staged
changes - and an inherited `GIT_CONFIG_COUNT` or `GIT_TEMPLATE_DIR` runs
somebody's hooks on the fixture's commits. A control is run from inside
other git work (a hook, a rebase, a gate), so that environment is ordinary.

These tests hand each runner a hostile environment aimed at a decoy
repository and a recording hook, and check that the decoy is untouched, the
hook never ran, and the runner still reached its normal verdict.

The last tests hold the other half of the review: a good case must require
ITS answer. `held` and `free` shared one good signal, so a helper that called
a live owner's claim `free` passed; and the sweep's clean case passed without
removing anything.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    any(shutil.which(name) is None for name in ("git", "bash", "sh", "sed", "env")),
    reason="the runners build real git repositories",
)

#: control, a case, the gate, and the line the runner prints for that case.
RUNNERS = [
    ("flow-worktree-claim", "good-owner-alive", "scripts/flow-worktree-claim.sh",
     "FLOW_CLAIM_CONTROL: no-finding - held"),
    ("flow-worktree-claim", "bad-owner-is-a-zombie", "scripts/flow-worktree-claim.sh",
     "FLOW_CLAIM_CONTROL: finding - the claim's owner is gone (stale)"),
    ("flow-worktree-guard-leak", "bad-fresh-leak", "scripts/flow-worktree-guard.sh",
     "FLOW_WORKTREE_GUARD_LEAK_CONTROL: finding - "),
    ("flow-worktree-guard-leak", "good-clean-main", "scripts/flow-worktree-guard.sh",
     "FLOW_WORKTREE_GUARD_LEAK_CONTROL: no-finding - "),
    ("flow-worktree-sweep-apply", "good-merged-and-nothing-left", "scripts/flow-worktree-sweep.sh",
     "FLOW_WORKTREE_SWEEP_APPLY_CONTROL: no-finding - removed; run "),
    ("flow-worktree-sweep-apply", "bad-unpushed-commit-after-the-merge", "scripts/flow-worktree-sweep.sh",
     "FLOW_WORKTREE_SWEEP_APPLY_CONTROL: finding - "),
]

_GIT = ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", "-c", "commit.gpgsign=false",
        "-c", "core.hooksPath=/dev/null"]


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run([*_GIT, *args], cwd=cwd, env=_clean_env(), capture_output=True, text=True,
                          check=True, timeout=60).stdout


def _decoy(tmp_path: Path) -> Path:
    """A repository standing in for the caller's: one commit, one STAGED change
    that a stray `git commit` would sweep up, and one untracked file."""
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    _git(decoy, "init", "-q", "-b", "main", f"--template={tmp_path / 'no-template'}")
    (decoy / "kept.txt").write_text("committed\n")
    _git(decoy, "add", "kept.txt")
    _git(decoy, "commit", "-q", "-m", "the caller's own commit")
    (decoy / "staged.txt").write_text("staged, not committed\n")
    _git(decoy, "add", "staged.txt")
    (decoy / "untracked.txt").write_text("untracked\n")
    return decoy


def _state(decoy: Path) -> dict[str, str]:
    return {
        "head": _git(decoy, "rev-parse", "HEAD"),
        "branches": _git(decoy, "for-each-ref", "--format=%(refname) %(objectname)"),
        "status": _git(decoy, "status", "--porcelain=v1", "--untracked-files=all"),
        "worktrees": _git(decoy, "worktree", "list", "--porcelain"),
        "index": (decoy / ".git" / "index").read_bytes().hex(),
        "files": "\n".join(sorted(p.name for p in decoy.iterdir())),
    }


def _run(control: str, case: str, gate: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    directory = ROOT / "controls" / control
    return subprocess.run(["sh", str(directory / "run-case.sh"), str(directory / "cases" / case), str(ROOT / gate)],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=100, check=False)


@pytest.mark.parametrize(("control", "case", "gate", "expected"), RUNNERS)
def test_a_runner_given_the_callers_git_environment_leaves_the_callers_repository_alone(
        tmp_path: Path, control: str, case: str, gate: str, expected: str) -> None:
    decoy = _decoy(tmp_path)
    before = _state(decoy)
    assert "A  staged.txt" in before["status"], "precondition: the decoy has a staged change to lose"
    env = {**_clean_env(), "GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy),
           "GIT_INDEX_FILE": str(decoy / ".git" / "index"), "GIT_COMMON_DIR": str(decoy / ".git")}
    done = _run(control, case, gate, env)
    assert _state(decoy) == before, "the runner changed the repository its environment pointed at"
    assert expected in done.stdout, done.stdout[-800:] + done.stderr[-400:]


requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git absent")


@requires_git
@pytest.mark.parametrize(("control", "case", "gate", "expected"), RUNNERS)
@pytest.mark.parametrize("route", ["config-count", "config-parameters", "template-dir"])
def test_a_runner_never_runs_an_inherited_hook(
        tmp_path: Path, route: str, control: str, case: str, gate: str, expected: str) -> None:
    """A hook that records every time git runs it, offered by each route an
    environment can offer one. Whatever git operation would have fired it -
    a commit, a checkout, a worktree add - the record stays empty."""
    record = tmp_path / "a-hook-ran.log"
    hooks = tmp_path / "hooks"
    template = tmp_path / "template"
    for directory in (hooks, template / "hooks"):
        directory.mkdir(parents=True)
        for name in ("pre-commit", "post-commit", "post-checkout", "reference-transaction", "prepare-commit-msg"):
            hook = directory / name
            hook.write_text(f'#!/bin/sh\necho "{name}" >> "{record}"\nexit 0\n')
            hook.chmod(0o755)
    env = _clean_env()
    if route == "config-count":
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.hooksPath", GIT_CONFIG_VALUE_0=str(hooks))
    elif route == "config-parameters":
        env["GIT_CONFIG_PARAMETERS"] = f"'core.hooksPath={hooks}'"
    else:
        env["GIT_TEMPLATE_DIR"] = str(template)
    # The hook really does fire when nothing stops it: an ordinary commit here.
    probe = tmp_path / "probe"
    probe.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=probe, env=env, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", "-c", "commit.gpgsign=false",
                    "commit", "-q", "--allow-empty", "-m", "probe"], cwd=probe, env=env, check=True,
                   capture_output=True)
    assert record.exists(), "precondition: this route does make git run the hook"
    record.unlink()
    done = _run(control, case, gate, env)
    assert not record.exists(), f"an inherited hook ran: {record.read_text()}"
    assert expected in done.stdout, done.stdout[-800:] + done.stderr[-400:]


# --- a good case requires ITS answer ------------------------------------------

def _case_good_signal(control: str, case: str) -> re.Pattern[str]:
    manifest = json.loads((ROOT / "controls" / control / "control.json").read_text())
    entry = next(c for c in manifest["cases"] if c["name"] == case)
    assert "good_signal" in entry, f"{control}/{case} relies on the control-wide good signal"
    return re.compile(entry["good_signal"], re.M)


def _stub_gate(tmp_path: Path, body: str) -> Path:
    gate = tmp_path / "stand-in-gate.sh"
    gate.write_text("#!/bin/bash\n" + body)
    gate.chmod(0o755)
    return gate


@pytest.mark.parametrize(("case", "right", "wrong"), [
    ("good-owner-alive", "held", "free"),
    ("good-no-claim", "free", "held"),
])
def test_the_claim_controls_good_cases_each_require_their_own_verdict(
        tmp_path: Path, case: str, right: str, wrong: str) -> None:
    """A helper that answers the other no-finding verdict - `free` for a live
    owner is the dangerous one: it lets a second session take the worktree -
    prints a line the case's own good signal refuses."""
    signal = _case_good_signal("flow-worktree-claim", case)
    for verdict in (right, wrong):
        gate = _stub_gate(tmp_path, f'echo "FLOW_CLAIM: {verdict}"\nexit 0\n')
        directory = ROOT / "controls" / "flow-worktree-claim"
        done = subprocess.run(["sh", str(directory / "run-case.sh"), str(directory / "cases" / case), str(gate)],
                              cwd=ROOT, env=_clean_env(), capture_output=True, text=True, timeout=60, check=False)
        assert done.returncode == 0 and f"no-finding - {verdict}" in done.stdout, done.stdout
        assert bool(signal.search(done.stdout)) is (verdict == right), (verdict, done.stdout)


def test_the_sweep_controls_clean_case_requires_the_removal(tmp_path: Path) -> None:
    """A sweep that skips the merged worktree and leaves it on disk exits 0
    and reads as no finding; the clean case's own good signal refuses it."""
    signal = _case_good_signal("flow-worktree-sweep-apply", "good-merged-and-nothing-left")
    lazy = _stub_gate(
        tmp_path,
        'repo=""\nwhile [ $# -gt 0 ]; do [ "$1" = --repo ] && repo="$2"; shift; done\n'
        'echo "SWEEP_WORKTREE: ${repo}-issue-4242 skip pr-none"\necho "FLOW_WORKTREE_SWEEP: ok"\nexit 0\n')
    directory = ROOT / "controls" / "flow-worktree-sweep-apply"
    case = directory / "cases" / "good-merged-and-nothing-left"
    kept = subprocess.run(["sh", str(directory / "run-case.sh"), str(case), str(lazy)], cwd=ROOT,
                          env=_clean_env(), capture_output=True, text=True, timeout=60, check=False)
    assert kept.returncode == 0 and "no-finding - kept as having no finished PR" in kept.stdout, kept.stdout
    assert not signal.search(kept.stdout), "a sweep that removed nothing satisfied the clean case"
    real = subprocess.run(["sh", str(directory / "run-case.sh"), str(case),
                           str(ROOT / "scripts" / "flow-worktree-sweep.sh")], cwd=ROOT, env=_clean_env(),
                          capture_output=True, text=True, timeout=100, check=False)
    assert real.returncode == 0 and signal.search(real.stdout), real.stdout

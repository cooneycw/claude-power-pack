"""flow-worktree-guard.sh says which of four things happened (#1014).

Before this, "I looked and main is clean" and "I could not look" were
byte-identical on stdout AND exit code: every could-not-look path ended in a
silent `exit 0`, and `/flow:auto` Steps 4 and 6 read exit 0 as "no edit leaked
into main". The marker names the verdict; under --strict the exit follows
gate-lib's gate_map (no-leak 0, leak 3, unknown 4, not-applicable 5), so a
could-not-look answer can never share the good exit.

Every test here was run against 40f771c (pre-fix) and FAILED there, except the
leak control, which passed there too (the guard always caught a real leak).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "flow-worktree-guard.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="builds real git repositories and worktrees",
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True)


def _main_and_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    subprocess.run(["git", "init", "-q", "-b", "main", str(main)], check=True)
    (main / "a.txt").write_text("a\n", encoding="utf-8")
    _git(main, "add", "a.txt")
    _git(main, "commit", "-q", "-m", "base")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "issue-1-x", str(wt))
    return main, wt


def _run(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full = {**os.environ, **(env or {})}
    return subprocess.run(["bash", str(GUARD), *args], cwd=cwd, capture_output=True, text=True, env=full)


def _marker(res: subprocess.CompletedProcess) -> str:
    for line in (res.stdout + res.stderr).splitlines():
        if line.startswith("FLOW_WORKTREE_GUARD:"):
            return line
    return ""


def test_a_clean_main_is_NO_LEAK_exit_0(tmp_path):
    _main, wt = _main_and_worktree(tmp_path)
    res = _run(wt, "--strict")
    assert res.returncode == 0, res.stderr
    assert _marker(res).startswith("FLOW_WORKTREE_GUARD: no-leak"), res.stdout + res.stderr


def test_the_MAIN_CHECKOUT_is_NOT_APPLICABLE_never_a_silent_0(tmp_path):
    """The current-branch lane runs here: there is no separate main tree to leak
    into, which is a different fact from "looked, no leak"."""
    main, _wt = _main_and_worktree(tmp_path)
    res = _run(main, "--strict")
    assert res.returncode == 5, res.stdout + res.stderr
    assert _marker(res).startswith("FLOW_WORKTREE_GUARD: not-applicable"), res.stderr


def test_a_git_that_cannot_answer_is_UNKNOWN(tmp_path):
    """A failing `git rev-parse --git-common-dir` used to fall into the same
    `exit 0 # main checkout (or indeterminate)` as a main checkout."""
    _main, wt = _main_and_worktree(tmp_path)
    stub = tmp_path / "git"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$*" == *"--is-inside-work-tree"* ]]; then exit 0; fi\n'
        "exit 128\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    res = _run(wt, "--strict", env={"FLOW_WORKTREE_GIT": str(stub)})
    assert res.returncode == 4, res.stdout + res.stderr
    assert _marker(res).startswith("FLOW_WORKTREE_GUARD: unknown"), res.stderr


def test_a_FRESH_leak_is_still_LEAK_exit_3(tmp_path):
    """The control: the guard always caught this, and still does."""
    main, wt = _main_and_worktree(tmp_path)
    (wt / "a.txt").write_text("worktree edit\n", encoding="utf-8")
    (main / "a.txt").write_text("leaked edit\n", encoding="utf-8")
    res = _run(wt, "--strict")
    assert res.returncode == 3, res.stderr
    assert _marker(res).startswith("FLOW_WORKTREE_GUARD: leak"), res.stderr


def test_ADVISORY_mode_keeps_exit_0_but_still_names_the_verdict(tmp_path):
    main, _wt = _main_and_worktree(tmp_path)
    res = _run(main)
    assert res.returncode == 0
    assert _marker(res).startswith("FLOW_WORKTREE_GUARD: not-applicable"), res.stderr


# --- counter-model review of #1014 Part 1: each red on the pre-review guard ---

def test_a_git_that_fails_its_FIRST_probe_is_UNKNOWN_not_not_applicable(tmp_path):
    """Only git's own "not a git repository" is not-applicable; a git that
    cannot answer at all is could-not-look."""
    _main, wt = _main_and_worktree(tmp_path)
    stub = tmp_path / "git"
    stub.write_text("#!/usr/bin/env bash\necho 'fatal: detected dubious ownership' >&2\nexit 128\n",
                    encoding="utf-8")
    stub.chmod(0o755)
    res = _run(wt, "--strict", env={"FLOW_WORKTREE_GIT": str(stub)})
    assert res.returncode == 4, res.stdout + res.stderr
    assert _marker(res).startswith("FLOW_WORKTREE_GUARD: unknown"), res.stderr


def test_an_overlap_DELETED_in_main_is_UNKNOWN_not_stale(tmp_path):
    """A path deleted in main has no mtime to read; `find` printed nothing, which
    read as stale, which read as no-leak."""
    main, wt = _main_and_worktree(tmp_path)
    (wt / "a.txt").write_text("worktree edit\n", encoding="utf-8")
    (main / "a.txt").unlink()
    res = _run(wt, "--strict")
    assert res.returncode == 4, res.stdout + res.stderr
    assert _marker(res).startswith("FLOW_WORKTREE_GUARD: unknown"), res.stderr


def test_a_STALE_overlap_gets_the_SAME_verdict_with_and_without_strict(tmp_path):
    main, wt = _main_and_worktree(tmp_path)
    (wt / "a.txt").write_text("worktree edit\n", encoding="utf-8")
    (main / "a.txt").write_text("pre-existing main dirt\n", encoding="utf-8")
    old = 1_600_000_000
    os.utime(main / "a.txt", (old, old))
    strict = _run(wt, "--strict")
    advisory = _run(wt)
    assert strict.returncode == 0 and advisory.returncode == 0
    assert _marker(strict).split(" - ")[0] == _marker(advisory).split(" - ")[0] == \
        "FLOW_WORKTREE_GUARD: no-leak", (_marker(strict), _marker(advisory))


def test_a_leak_verdict_does_not_claim_authorship(tmp_path):
    main, wt = _main_and_worktree(tmp_path)
    (wt / "a.txt").write_text("worktree edit\n", encoding="utf-8")
    (main / "a.txt").write_text("fresh main edit\n", encoding="utf-8")
    res = _run(wt, "--strict")
    assert res.returncode == 3
    assert "signature" in _marker(res) and "writer unverified" in _marker(res)


def test_the_control_runner_does_not_credit_a_CRASHING_gate(tmp_path):
    """A gate that just dies (exit 42, no verdict) must not be scored a finding."""
    crash = tmp_path / "crash.sh"
    crash.write_text("#!/usr/bin/env bash\nexit 42\n", encoding="utf-8")
    crash.chmod(0o755)
    runner = ROOT / "controls" / "flow-worktree-guard" / "run-case.sh"
    case = ROOT / "controls" / "flow-worktree-guard" / "cases" / "bad-main-checkout"
    res = subprocess.run(["sh", str(runner), str(case), str(crash)], capture_output=True, text=True)
    assert "FLOW_WORKTREE_GUARD_CONTROL: finding" not in res.stdout, res.stdout
    assert res.stdout.startswith("FLOW_WORKTREE_GUARD_CONTROL: error"), res.stdout

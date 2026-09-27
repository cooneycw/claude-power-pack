"""The delegated lanes' overrun check compares against a RECORDED base (#1261).

`/codex:auto`, `/qwen:auto` and `/gemma:auto` used to hand-build their worktree
from `origin/main`, which records `origin/main` as the branch's upstream - the
#1221 push hazard. Their post-exec overrun check (`git log @{u}..`, `git reset
@{u}`) and the Step 7 empty-diff backstop (`git rev-list --count @{u}..HEAD`)
only meant "commits since the base" BECAUSE of that upstream. Routing the lanes
through `flow-start-resolve.sh` gives the branch its OWN not-yet-pushed name as
upstream, `@{u}` stops resolving, and `2>/dev/null | wc -l` reads that as zero:
the overrun check goes blind without saying so.

TWO-SIDED, executed against the real blocks in each driver document:

RED   the pre-fix `@{u}` form, in a worktree whose upstream is its own unpushed
      name (the resolver's shape), reports 0 for a commit the model made.
GREEN each driver's current block detects that commit and resets it, and a
      missing recorded base is a STOP, never a zero.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.isolated_env import ISOLATED_PATH

REPO = Path(__file__).resolve().parent.parent
DRIVERS = ("codex", "qwen", "gemma")
CORE = REPO / "templates" / "delegated-driver-core.md"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

# The pre-fix commit check, verbatim in shape, kept here as the control: it is
# what the fixture must blind, or the fixture proves nothing about the fix.
PREFIX_BLOCK = """\
UNEXPECTED_COMMITS=$(git log @{u}.. --oneline 2>/dev/null | wc -l)
echo "UNEXPECTED=$UNEXPECTED_COMMITS"
"""


def _doc(driver: str) -> str:
    return (REPO / ".claude" / "commands" / driver / "auto.md").read_text(encoding="utf-8")


def _snapshot_block(driver: str) -> str:
    """The pre-exec HEAD recording lines from the Step 4 exec block."""
    text = _doc(driver)
    m = re.search(
        r'(PRE_EXEC_HEAD_FILE="\$\(git rev-parse --absolute-git-dir\)/delegated-pre-exec-head"\n'
        r'if ! git rev-parse HEAD > "\$PRE_EXEC_HEAD_FILE"; then\n.*?\nfi\n)',
        text, re.S,
    )
    assert m, f"{driver}: Step 4 no longer records the pre-exec HEAD"
    return m.group(1)


def _overrun_block(driver: str) -> str:
    """Item 1 of the post-execution overrun verification, as the driver ships it."""
    text = _doc(driver)
    m = re.search(
        r"(# 1\. Check for unexpected commits.*?Working-tree changes preserved for review\.\"\nfi\n)",
        text, re.S,
    )
    assert m, f"{driver}: overrun commit check not found"
    return m.group(1)


def _env(home: Path) -> dict[str, str]:
    # negative-fixture: allow PATH is isolation, not an absence
    return {**os.environ, "HOME": str(home), "PATH": ISOLATED_PATH,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}


def _run(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def _resolver_shaped_worktree(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A worktree whose branch tracks its OWN unpushed name, as the resolver makes it."""
    home = tmp_path / "home"
    home.mkdir()
    env = _env(home)
    upstream = tmp_path / "up.git"
    upstream.mkdir()
    _run(["git", "init", "-q", "--bare"], upstream, env)
    work = tmp_path / "work"
    work.mkdir()
    for args in (["init", "-q", "-b", "main"], ["remote", "add", "origin", str(upstream)]):
        _run(["git", *args], work, env)
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    _run(["git", "add", "-A"], work, env)
    _run(["git", "commit", "-qm", "base"], work, env)
    _run(["git", "push", "-q", "origin", "main"], work, env)
    wt = tmp_path / "wt"
    branch = "issue-1-x"
    r = _run(["git", "worktree", "add", "-q", "--no-track", "-b", branch, str(wt), "origin/main"], work, env)
    assert r.returncode == 0, r.stderr
    _run(["git", "config", f"branch.{branch}.remote", "origin"], wt, env)
    _run(["git", "config", f"branch.{branch}.merge", f"refs/heads/{branch}"], wt, env)
    # Precondition of the negative case: @{u} must NOT resolve here.
    assert _run(["git", "rev-parse", "--verify", "-q", "@{u}"], wt, env).returncode != 0
    return wt, env


def _overrun_commit(wt: Path, env: dict[str, str]) -> None:
    (wt / "overrun.txt").write_text("model committed this\n", encoding="utf-8")
    _run(["git", "add", "-A"], wt, env)
    r = _run(["git", "commit", "-qm", "overrun"], wt, env)
    assert r.returncode == 0, r.stderr


@requires_git
def test_the_prefix_upstream_form_is_blind_in_a_resolver_shaped_worktree(tmp_path: Path) -> None:
    """RED: the control. If this ever reports 1, the fixture no longer captures #1261."""
    wt, env = _resolver_shaped_worktree(tmp_path)
    _overrun_commit(wt, env)
    r = _run(["bash", "-c", PREFIX_BLOCK], wt, env)
    assert "UNEXPECTED=0" in r.stdout, r.stdout + r.stderr


@requires_git
@pytest.mark.parametrize("driver", DRIVERS)
def test_the_recorded_base_catches_and_rolls_back_an_overrun_commit(tmp_path: Path, driver: str) -> None:
    """GREEN: same fixture, the driver's own blocks, and the commit is caught."""
    wt, env = _resolver_shaped_worktree(tmp_path)
    before = _run(["git", "rev-parse", "HEAD"], wt, env).stdout.strip()
    r = _run(["bash", "-c", _snapshot_block(driver)], wt, env)
    assert r.returncode == 0, r.stdout + r.stderr
    _overrun_commit(wt, env)
    r = _run(["bash", "-c", _overrun_block(driver)], wt, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OVERRUN DETECTED" in r.stdout and "1 unexpected commit" in r.stdout, r.stdout
    assert _run(["git", "rev-parse", "HEAD"], wt, env).stdout.strip() == before
    assert (wt / "overrun.txt").exists(), "working-tree changes must be preserved"


@requires_git
@pytest.mark.parametrize("driver", DRIVERS)
def test_a_clean_run_reports_no_overrun(tmp_path: Path, driver: str) -> None:
    wt, env = _resolver_shaped_worktree(tmp_path)
    _run(["bash", "-c", _snapshot_block(driver)], wt, env)
    r = _run(["bash", "-c", _overrun_block(driver)], wt, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OVERRUN" not in r.stdout


@requires_git
@pytest.mark.parametrize("driver", DRIVERS)
def test_a_missing_recorded_base_stops_rather_than_reading_zero(tmp_path: Path, driver: str) -> None:
    wt, env = _resolver_shaped_worktree(tmp_path)
    git_dir = Path(_run(["git", "rev-parse", "--absolute-git-dir"], wt, env).stdout.strip())
    assert not (git_dir / "delegated-pre-exec-head").exists()
    _overrun_commit(wt, env)
    r = _run(["bash", "-c", _overrun_block(driver)], wt, env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "OVERRUN CHECK UNAVAILABLE" in r.stdout


def _backstop_block() -> str:
    text = _doc("codex")
    section = text[text.index("### Step 7: Finish"):]
    m = re.search(r"```bash\n(.*?)```", section, re.S)
    assert m
    return m.group(1)


@requires_git
def test_the_step7_backstop_counts_commits_without_an_upstream(tmp_path: Path) -> None:
    """The old `@{u}..HEAD || echo 0` read a committed branch as empty."""
    wt, env = _resolver_shaped_worktree(tmp_path)
    _run(["git", "checkout", "-q", "-B", "issue-1-x"], wt, env)
    _overrun_commit(wt, env)
    ok = _run(["bash", "-c", _backstop_block()], wt, env)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    # A PENDING exact revert (uncommitted) must also stop: it is what Step 7
    # is about to commit (re-review finding).
    (wt / "overrun.txt").unlink()
    pending = _run(["bash", "-c", _backstop_block()], wt, env)
    assert pending.returncode == 1 and "no content change" in pending.stdout, pending.stdout + pending.stderr
    (wt / "overrun.txt").write_text("model committed this\n", encoding="utf-8")
    # A change followed by its exact revert is commits ahead with NO content:
    # the backstop must stop (counter-model finding; a commit count passed it).
    (wt / "overrun.txt").unlink()
    _run(["git", "add", "-A"], wt, env)
    _run(["git", "commit", "-qm", "revert"], wt, env)
    assert _run(["git", "status", "--porcelain"], wt, env).stdout == ""
    reverted = _run(["bash", "-c", _backstop_block()], wt, env)
    assert reverted.returncode == 1 and "no content change" in reverted.stdout, reverted.stdout + reverted.stderr
    # And an unresolvable base is a STOP, not a pass.
    _run(["git", "update-ref", "-d", "refs/remotes/origin/main"], wt, env)
    _run(["git", "remote", "remove", "origin"], wt, env)
    bad = _run(["bash", "-c", _backstop_block()], wt, env)
    assert bad.returncode == 1 and "cannot run" in bad.stdout, bad.stdout + bad.stderr


def test_the_lanes_no_longer_hand_build_a_worktree_from_origin_main() -> None:
    core = CORE.read_text(encoding="utf-8")
    assert "Create fresh from `origin/main`" not in core
    assert "flow-start-resolve.sh 42 --session-cwd" in core
    for driver in DRIVERS:
        text = _doc(driver)
        assert "flow-start-resolve.sh 42 --session-cwd" in text, driver
        code = "\n".join(re.findall(r"```bash\n(.*?)```", text, re.S))
        assert "@{u}" not in re.sub(r"#.*", "", code), f"{driver}: @{{u}} still used in a bash block"


def test_the_approval_gate_names_the_orchestrator_mailbox_route() -> None:
    """Item 4: the route lives next to the prompt, not in whatever brief was written."""
    for driver in DRIVERS:
        text = _doc(driver)
        gate = text[text.index("### Step 3: Approve"):text.index("Report: `Step 3/8")]
        assert "flow-wave-mailbox.sh send --to orchestrator" in gate, driver
        assert "does not bypass it" in gate, driver


@requires_git
def test_the_step7_backstop_finds_origin_master_without_origin_head(tmp_path: Path) -> None:
    """Re-review finding: no origin/HEAD must not mean origin/main."""
    home = tmp_path / "home"
    home.mkdir()
    env = _env(home)
    up = tmp_path / "up.git"
    up.mkdir()
    _run(["git", "init", "-q", "--bare"], up, env)
    work = tmp_path / "w"
    work.mkdir()
    _run(["git", "init", "-q", "-b", "master"], work, env)
    _run(["git", "remote", "add", "origin", str(up)], work, env)
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    _run(["git", "add", "-A"], work, env)
    _run(["git", "commit", "-qm", "base"], work, env)
    _run(["git", "push", "-q", "origin", "master"], work, env)
    _run(["git", "checkout", "-q", "-b", "issue-1-x"], work, env)
    assert _run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"], work, env).returncode != 0
    _overrun_commit(work, env)
    r = _run(["bash", "-c", _backstop_block()], work, env)
    assert r.returncode == 0, r.stdout + r.stderr

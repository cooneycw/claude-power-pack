"""Tests for scripts/flow-start-resolve.sh - the deterministic /flow Step-1
resolver (issue #581).

Contract:
- Resolve mode triages existing work into one LANE
  (``current-branch|fresh|resume|remote-pickup|cross-repo``) and prints a
  key=value contract ending in ``FLOW_START_RESOLVE: ok``.
- The two git-lane creation cases (cross-repo fresh, remote-pickup) run
  ``git worktree add`` themselves (``WT_CREATED=1``); the native fresh lane
  creates nothing (EnterWorktree owns creation).
- A non-OPEN issue blocks creation and sets ``CONFIRM_REQUIRED=1`` unless
  ``--allow-closed`` is passed.
- The resume lane wraps the #503 live-driver guard (``LIVE_DRIVER=``) and the
  shipped-PR hazard check (``PR_HEAD=``); either hazard sets
  ``CONFIRM_REQUIRED=1``.
- ``--verify`` is the post-entry gate: fail on main/master, normalize a
  non-issue-anchored branch to the expected name.
- Hard errors print ``ERROR=`` then ``FLOW_START_RESOLVE: error`` and exit 1.

``gh`` is faked via the ``FLOW_START_RESOLVE_GH`` env hook (canned state /
title / pr-list output driven by ``FAKE_GH_*`` env vars); the tests build REAL
throwaway git repos.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-start-resolve.sh"

# The behaviour tests drive real `git` and `bash` subprocesses. The Woodpecker
# `validate` step runs in `uv:python3.11-bookworm-slim`, which ships bash but
# NOT git, so those tests are skipped there (issue #430). The read-only wiring
# tests below need neither and always run.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)

FAKE_GH = """#!/usr/bin/env bash
[ "${FAKE_GH_FAIL:-0}" = "1" ] && exit 1
case "$*" in
  *"issue view"*"--json state"*) printf '%s\\n' "${FAKE_GH_STATE:-OPEN}" ;;
  *"issue view"*"--json title"*) printf '%s\\n' "${FAKE_GH_TITLE:-Fix the frobnicator}" ;;
  *"pr list"*) printf '%s\\n' "${FAKE_GH_PR:-none}" ;;
  *) exit 1 ;;
esac
"""


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout


def _fake_gh(tmp_path: Path) -> Path:
    gh = tmp_path / "fake-gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    return gh


def _run(
    *args: str,
    cwd: Path,
    gh: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    # A host-level #584 base override must not bleed into the default-path
    # assertions; tests opt in explicitly via extra_env.
    env.pop("FLOW_WORKTREE_BASE", None)
    env["FLOW_START_RESOLVE_GH"] = str(gh)
    env.update(
        {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _contract(res: subprocess.CompletedProcess[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in res.stdout.splitlines():
        if "=" in line and not line.startswith("FLOW_START"):
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _make_origin_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    """An 'origin' repo plus a clone of it, so origin/main and fetch work."""
    origin = tmp_path / "origin-repo"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    (origin / "a.txt").write_text("a0\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "init")
    clone = tmp_path / "clone-repo"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    return origin, clone


# --- read-only wiring (no git/bash needed) ----------------------------------


def test_script_exists_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), "resolver script must be executable"


# --- resolve: fresh + branch derivation -------------------------------------


@requires_git
def test_fresh_lane_in_session_repo(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    assert "FLOW_START_RESOLVE: ok" in res.stdout
    c = _contract(res)
    assert c["LANE"] == "fresh"
    assert c["CROSS_REPO"] == "0"
    assert c["GIT_LANE"] == "0"
    assert c["SESSION_CWD_INFERRED"] == "0"
    assert c["BRANCH"] == "issue-42-fix-the-frobnicator"
    assert c["WT_PATH"].endswith(".claude/worktrees/issue-42-fix-the-frobnicator")
    # The native lane creates nothing - EnterWorktree owns fresh creation.
    assert c["WT_CREATED"] == "0"
    assert not Path(c["WT_PATH"]).exists()
    assert c["ISSUE_STATE"] == "OPEN"
    assert c["CONFIRM_REQUIRED"] == "0"


@requires_git
def test_slug_sanitized_and_truncated(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    title = "Fix: THE (login) redirect/loop!! " + "x" * 80
    res = _run(
        "7",
        cwd=clone,
        gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_TITLE": title},
    )
    c = _contract(res)
    slug = c["BRANCH"].removeprefix("issue-7-")
    assert slug.startswith("fix-the-login-redirect-loop-xxx")
    assert len(slug) <= 50
    assert "--" not in slug and not slug.endswith("-")


# --- resolve: hard errors ----------------------------------------------------


@requires_git
def test_error_outside_repo_without_project(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    res = _run("42", cwd=plain, gh=_fake_gh(tmp_path))
    assert res.returncode == 1
    assert "FLOW_START_RESOLVE: error" in res.stdout
    assert "ERROR=" in res.stdout


@requires_git
def test_error_project_not_a_git_checkout(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    notrepo = tmp_path / "not-a-repo"
    notrepo.mkdir()
    res = _run("42", str(notrepo), cwd=plain, gh=_fake_gh(tmp_path))
    assert res.returncode == 1
    assert "FLOW_START_RESOLVE: error" in res.stdout
    assert "not a git checkout" in res.stdout


@requires_git
def test_error_when_gh_unavailable(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    res = _run("42", cwd=clone, gh=_fake_gh(tmp_path), extra_env={"FAKE_GH_FAIL": "1"})
    assert res.returncode == 1
    assert "FLOW_START_RESOLVE: error" in res.stdout


# --- resolve: session cwd is declared, not inferred (issue #592) -------------
#
# The regression these pin: in Claude Code the Bash tool's cwd persists across
# calls and drifts on any earlier `cd`, while EnterWorktree always acts on the
# session cwd, which never moves. Resolving from `.` therefore decided GIT_LANE
# (and, with no PROJECT, TARGET_REPO itself) against whatever repo the last
# `cd` landed in. Every test below runs the resolver with a process cwd
# DELIBERATELY different from the declared session cwd.


@requires_git
def test_drifted_process_cwd_does_not_win_over_declared_session_cwd(tmp_path: Path):
    """The #592 scenario verbatim: process cwd sits in the target repo while the
    session cwd is elsewhere. GIT_LANE must stay 1 - EnterWorktree would act on
    the session cwd, which is not this repo."""
    _, clone = _make_origin_and_clone(tmp_path)
    session = tmp_path / "session-elsewhere"
    session.mkdir()
    # cwd=clone is the drift; --session-cwd is the truth.
    res = _run("42", str(clone), "--session-cwd", str(session), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["SESSION_CWD"] == str(session.resolve())
    assert c["SESSION_CWD_INFERRED"] == "0"
    assert c["CROSS_REPO"] == "1", "session cwd is not the target repo"
    assert c["GIT_LANE"] == "1", "must not send EnterWorktree at a repo the session is not in"
    assert c["LANE"] == "cross-repo"
    assert c["WT_CREATED"] == "1"


@requires_git
def test_target_repo_comes_from_session_cwd_not_process_cwd(tmp_path: Path):
    """Second facet: with no PROJECT arg, TARGET_REPO itself was resolved from
    the drifted cwd - so a bare `/flow:start 42` could branch in a surprise
    repository."""
    _, session_repo = _make_origin_and_clone(tmp_path)
    other = tmp_path / "other-origin"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    (other / "b.txt").write_text("b\n")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "init")

    res = _run("42", "--session-cwd", str(session_repo), cwd=other, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["TARGET_REPO"] == str(session_repo.resolve()), "resolved the wrong repo"
    assert c["CROSS_REPO"] == "0"
    assert c["GIT_LANE"] == "0"


@requires_git
def test_session_cwd_env_var_is_honored(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    session = tmp_path / "session-elsewhere"
    session.mkdir()
    res = _run(
        "42",
        str(clone),
        cwd=clone,
        gh=_fake_gh(tmp_path),
        extra_env={"FLOW_SESSION_CWD": str(session)},
    )
    c = _contract(res)
    assert c["SESSION_CWD_INFERRED"] == "0"
    assert c["SESSION_CWD"] == str(session.resolve())
    assert c["GIT_LANE"] == "1"


@requires_git
def test_inferred_session_cwd_fails_closed_to_git_lane(tmp_path: Path):
    """No --session-cwd: the resolver must SAY so and pick the safe lane rather
    than silently trusting a cwd it cannot vouch for."""
    _, clone = _make_origin_and_clone(tmp_path)
    res = _run("42", cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["SESSION_CWD_INFERRED"] == "1"
    assert c["CROSS_REPO"] == "0", "the process cwd IS this repo - only its provenance is unverified"
    assert c["GIT_LANE"] == "1", "unverified session cwd never earns the native lane"
    # Failing closed means the git lane must actually be usable: the helper
    # creates the worktree itself, since EnterWorktree will not be called.
    assert c["WT_CREATED"] == "1"
    assert Path(c["WT_PATH"]).is_dir()


@requires_git
def test_session_cwd_must_be_a_directory(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    res = _run("42", "--session-cwd", str(tmp_path / "nope"), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 1
    assert "FLOW_START_RESOLVE: error" in res.stdout
    assert "not a directory" in res.stdout


@requires_git
def test_current_branch_lane_reads_the_session_cwd(tmp_path: Path):
    """The current-branch lane asked `git branch --show-current` of the process
    cwd; on a drifted cwd that reports another checkout's branch."""
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "issue-42-already-here")
    drifted = tmp_path / "drifted"
    drifted.mkdir()
    _git(drifted, "init", "-q", "-b", "main")
    (drifted / "c.txt").write_text("c\n")
    _git(drifted, "add", "-A")
    _git(drifted, "commit", "-q", "-m", "init")
    _git(drifted, "switch", "-q", "-c", "issue-42-decoy-branch")

    res = _run("42", "--session-cwd", str(clone), cwd=drifted, gh=_fake_gh(tmp_path))
    c = _contract(res)
    assert c["LANE"] == "current-branch"
    assert c["BRANCH"] == "issue-42-already-here", "picked up the drifted checkout's branch"
    assert c["WT_PATH"] == str(clone.resolve())


# --- resolve: cross-repo lane (issue #578) -----------------------------------


@requires_git
def test_cross_repo_fresh_creates_worktree(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    plain = tmp_path / "elsewhere"
    plain.mkdir()
    res = _run("42", str(clone), "--session-cwd", str(plain), cwd=plain, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "cross-repo"
    assert c["CROSS_REPO"] == "1"
    assert c["GIT_LANE"] == "1"
    assert c["WT_CREATED"] == "1"
    wt = Path(c["WT_PATH"])
    assert wt.is_dir()
    assert _git(wt, "branch", "--show-current").strip() == c["BRANCH"]


@requires_git
def test_closed_issue_blocks_creation_until_allow_closed(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    plain = tmp_path / "elsewhere"
    plain.mkdir()
    gh = _fake_gh(tmp_path)
    closed = {"FAKE_GH_STATE": "CLOSED"}
    res = _run("42", str(clone), cwd=plain, gh=gh, extra_env=closed)
    c = _contract(res)
    assert c["ISSUE_STATE"] == "CLOSED"
    assert c["CONFIRM_REQUIRED"] == "1"
    assert c["WT_CREATED"] == "0"
    assert not Path(c["WT_PATH"]).exists()
    # After the user confirms, --allow-closed proceeds with creation.
    res2 = _run("42", str(clone), "--allow-closed", cwd=plain, gh=gh, extra_env=closed)
    c2 = _contract(res2)
    assert c2["WT_CREATED"] == "1"
    assert Path(c2["WT_PATH"]).is_dir()


# --- resolve: current-branch + resume lanes ----------------------------------


@requires_git
def test_current_branch_lane(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "issue-42-already-here")
    res = _run("42", cwd=clone, gh=_fake_gh(tmp_path))
    c = _contract(res)
    assert c["LANE"] == "current-branch"
    assert c["BRANCH"] == "issue-42-already-here"
    assert c["WT_PATH"] == str(clone.resolve())


@requires_git
def test_resume_lane_clean_worktree_is_clear(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "worktree", "add", "-q", "-b", "issue-42-earlier-work", ".claude/worktrees/issue-42-earlier-work")
    res = _run("42", cwd=clone, gh=_fake_gh(tmp_path))
    c = _contract(res)
    assert c["LANE"] == "resume"
    assert c["BRANCH"] == "issue-42-earlier-work"
    assert c["WT_PATH"].endswith(".claude/worktrees/issue-42-earlier-work")
    assert c["LIVE_DRIVER"] == "clear"
    assert c["PR_HEAD"] == "none"
    assert c["CONFIRM_REQUIRED"] == "0"


@requires_git
def test_resume_lane_fresh_dirty_file_requires_confirmation(tmp_path: Path):
    import time

    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "worktree", "add", "-q", "-b", "issue-42-earlier-work", ".claude/worktrees/issue-42-earlier-work")
    wt = clone / ".claude" / "worktrees" / "issue-42-earlier-work"
    (wt / "live.py").write_text("# another driver just wrote this\n")
    res = _run(
        "42",
        cwd=clone,
        gh=_fake_gh(tmp_path),
        extra_env={"FLOW_LIVE_DRIVER_NOW": str(int(time.time()))},
    )
    c = _contract(res)
    assert c["LANE"] == "resume"
    assert c["LIVE_DRIVER"] == "suspected"
    assert c["CONFIRM_REQUIRED"] == "1"


@requires_git
def test_resume_lane_existing_pr_requires_confirmation(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "worktree", "add", "-q", "-b", "issue-42-earlier-work", ".claude/worktrees/issue-42-earlier-work")
    res = _run(
        "42",
        cwd=clone,
        gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_PR": "7:OPEN"},
    )
    c = _contract(res)
    assert c["LANE"] == "resume"
    assert c["PR_HEAD"] == "7:OPEN"
    assert c["CONFIRM_REQUIRED"] == "1"


# --- resolve: remote-pickup lane ---------------------------------------------


@requires_git
def test_remote_pickup_creates_tracking_worktree(tmp_path: Path):
    origin, clone = _make_origin_and_clone(tmp_path)
    _git(origin, "switch", "-q", "-c", "issue-42-remote-work")
    (origin / "b.txt").write_text("remote work\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "remote work")
    res = _run("42", cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "remote-pickup"
    assert c["REMOTE_BRANCH"] == "origin/issue-42-remote-work"
    assert c["BRANCH"] == "issue-42-remote-work"
    assert c["WT_CREATED"] == "1"
    wt = Path(c["WT_PATH"])
    assert (wt / "b.txt").exists()
    assert _git(wt, "branch", "--show-current").strip() == "issue-42-remote-work"


# --- resolve: FLOW_WORKTREE_BASE override (issue #584) -----------------------


@requires_git
def test_base_override_fresh_same_repo_rides_git_lane(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    base = tmp_path / "wt-base"
    res = _run(
        "42",
        "--session-cwd",
        str(clone),
        cwd=clone,
        gh=_fake_gh(tmp_path),
        extra_env={"FLOW_WORKTREE_BASE": str(base)},
    )
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "fresh"
    assert c["CROSS_REPO"] == "0"
    assert c["GIT_LANE"] == "1"
    # Interleaved layout: $FLOW_WORKTREE_BASE/<repo>-<branch>, created by the
    # helper (EnterWorktree cannot reach an out-of-repo base).
    assert c["WT_CREATED"] == "1"
    assert c["WT_PATH"] == str(base / f"{clone.name}-{c['BRANCH']}")
    wt = Path(c["WT_PATH"])
    assert wt.is_dir()
    assert _git(wt, "branch", "--show-current").strip() == c["BRANCH"]


@requires_git
def test_resume_of_out_of_repo_worktree_forces_git_lane(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    outside = tmp_path / "wt-base" / f"{clone.name}-issue-42-earlier-work"
    outside.parent.mkdir()
    _git(clone, "worktree", "add", "-q", "-b", "issue-42-earlier-work", str(outside))
    # No FLOW_WORKTREE_BASE this run - the prior run's base-override worktree
    # still must not be entered via EnterWorktree(path=...).
    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    c = _contract(res)
    assert c["LANE"] == "resume"
    assert c["GIT_LANE"] == "1"
    assert c["SESSION_CWD_INFERRED"] == "0"
    assert c["WT_PATH"] == str(outside)


# --- verify mode -------------------------------------------------------------


@requires_git
def test_verify_ok_on_issue_branch(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "issue-42-good-branch")
    res = _run("--verify", "42", cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0
    assert "FLOW_START_VERIFY: ok" in res.stdout
    c = _contract(res)
    assert c["BRANCH"] == "issue-42-good-branch"
    assert c["WT_ROOT"] == str(clone.resolve())


@requires_git
def test_verify_fails_on_main(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    res = _run("--verify", "42", "issue-42-x", cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 1
    assert "FLOW_START_VERIFY: fail" in res.stdout


@requires_git
def test_verify_normalizes_branch_name(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "some-other-name")
    res = _run("--verify", "42", "issue-42-right-name", cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    assert "FLOW_START_VERIFY: ok" in res.stdout
    assert _git(clone, "branch", "--show-current").strip() == "issue-42-right-name"


@requires_git
def test_verify_fails_without_expected_branch_to_normalize_to(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "some-other-name")
    res = _run("--verify", "42", cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 1
    assert "FLOW_START_VERIFY: fail" in res.stdout

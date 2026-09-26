"""Tests for scripts/flow-start-resolve.sh - the deterministic /flow Step-1
resolver (issue #581).

Contract:
- Resolve mode triages existing work into one LANE
  (``current-branch|fresh|resume|remote-pickup|cross-repo``) and prints a
  key=value contract ending in ``FLOW_START_RESOLVE: ok``.
- Worktrees are created outside the repo by default (issue #627), so GIT_LANE is
  always 1 and every creating lane (fresh, cross-repo, remote-pickup) runs
  ``git worktree add`` itself (``WT_CREATED=1``); the native EnterWorktree fresh
  lane is retired.
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
  *"pr list"*)
    # FAKE_GH_PR_MAP="<branch>=<answer> ..." answers per --head branch, so a
    # test can hold one shipped branch and one live one (issue #1258).
    head=""; prev=""
    for a in "$@"; do [ "$prev" = "--head" ] && head="$a"; prev="$a"; done
    for kv in ${FAKE_GH_PR_MAP:-}; do
      [ "${kv%%=*}" = "$head" ] && { printf '%s\\n' "${kv#*=}"; exit 0; }
    done
    printf '%s\\n' "${FAKE_GH_PR:-none}" ;;
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
    # Worktrees are created outside the repo now (issue #627), so every run rides
    # the git lane - even a fresh start in the session repo.
    assert c["GIT_LANE"] == "1"
    assert c["SESSION_CWD_INFERRED"] == "0"
    assert c["BRANCH"] == "issue-42-fix-the-frobnicator"
    # Visible sibling of the repo (in its parent dir), NOT hidden in-repo.
    assert ".claude/worktrees" not in c["WT_PATH"]
    assert c["WT_PATH"].endswith("-issue-42-fix-the-frobnicator")
    assert Path(c["WT_PATH"]).parent == clone.resolve().parent
    # The helper creates the worktree itself (the native fresh lane is retired).
    assert c["WT_CREATED"] == "1"
    assert Path(c["WT_PATH"]).is_dir()
    assert c["ISSUE_STATE"] == "OPEN"
    assert c["CONFIRM_REQUIRED"] == "0"


# --- resolve: compose-project pin (issue #626) ------------------------------


@requires_git
def test_compose_project_name_defaults_to_canonical_basename(tmp_path: Path):
    """The contract carries a COMPOSE_PROJECT_NAME so every compose call in the
    flow worktree inherits a stable name instead of forking a parallel stack off
    the worktree basename. Default = the canonical primary-checkout basename,
    lowercased - never the worktree dir."""
    _, clone = _make_origin_and_clone(tmp_path)  # clone dir basename == "clone-repo"
    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["COMPOSE_PROJECT_NAME"] == "clone-repo"
    # It must be the repo name, not the worktree basename it would otherwise pick.
    assert "issue-42" not in c["COMPOSE_PROJECT_NAME"]


@requires_git
def test_compose_project_name_honors_deploy_yaml_override(tmp_path: Path):
    """An explicit .claude/deploy.yaml compose_project_name: wins, matching the
    Step-9 (#535) precedence so a run that reaches deploy keeps one project name
    end to end."""
    _, clone = _make_origin_and_clone(tmp_path)
    (clone / ".claude").mkdir(parents=True, exist_ok=True)
    (clone / ".claude" / "deploy.yaml").write_text("compose_project_name: pinned-prod\n")
    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["COMPOSE_PROJECT_NAME"] == "pinned-prod"


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
    # GIT_LANE is always 1 now (worktrees are out-of-repo, issue #627).
    assert c["GIT_LANE"] == "1"


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
    # No PR on the pushed branch: the #742 probe ran and found nothing.
    assert c["PR_HEAD"] == "none"
    assert c["CONFIRM_REQUIRED"] == "0"
    wt = Path(c["WT_PATH"])
    assert (wt / "b.txt").exists()
    assert _git(wt, "branch", "--show-current").strip() == "issue-42-remote-work"


@requires_git
def test_remote_pickup_existing_pr_requires_confirmation(tmp_path: Path):
    """Regression for issue #742, cross-repo shape: a remote branch with an OPEN
    PR, picked up from a session cwd OUTSIDE the target repo, must surface the
    shipped-PR hazard (PR_HEAD + CONFIRM_REQUIRED=1). The probe used to run only
    on the resume lane, so this exact shape reported PR_HEAD=none."""
    origin, clone = _make_origin_and_clone(tmp_path)
    _git(origin, "switch", "-q", "-c", "issue-42-remote-work")
    (origin / "b.txt").write_text("remote work\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "remote work")
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    res = _run(
        "42",
        str(clone),
        "--session-cwd",
        str(plain),
        cwd=plain,
        gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_PR": "211:OPEN"},
    )
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "remote-pickup"
    assert c["CROSS_REPO"] == "1"
    assert c["PR_HEAD"] == "211:OPEN"
    assert c["CONFIRM_REQUIRED"] == "1"
    assert "already has PR 211:OPEN" in res.stderr


# --- resolve: existing-branch reuse guard (issue #793) -----------------------
#
# `create_worktree` used to reuse a pre-existing local branch of the derived
# name UNCONDITIONALLY, silently discarding the base ref it was told to branch
# from, while still reporting LANE=fresh. These pin the ancestor-of-base guard
# and the broadened local-branch probe that closes that hole.


@requires_git
def test_fresh_lane_refuses_diverged_existing_local_branch(tmp_path: Path):
    """The exact #793 regression: a local branch matching the DERIVED slug
    already exists and carries unmerged commits (not an ancestor of the base).
    The resolver must refuse - not silently check it out - and must not print
    LANE=fresh (or any LANE at all, since this is a hard error)."""
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "issue-42-fix-the-frobnicator")
    (clone / "wip.txt").write_text("someone else's unmerged work\n")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "wip, never merged")
    _git(clone, "switch", "-q", "main")

    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 1
    assert "FLOW_START_RESOLVE: error" in res.stdout
    assert "LANE=" not in res.stdout, "must not report any LANE on refusal"
    assert "issue-42-fix-the-frobnicator" in res.stdout, "must name the branch"
    assert "unmerged" in res.stdout, "must say the branch is unmerged"
    tip = _git(clone, "rev-parse", "--short", "issue-42-fix-the-frobnicator").strip()
    assert tip in res.stdout, "must name the branch's tip"
    # The worktree must not have been created.
    assert not any(p.name.endswith("-issue-42-fix-the-frobnicator") for p in tmp_path.iterdir())


@requires_git
def test_fresh_lane_reuses_ancestor_existing_local_branch_without_lying(tmp_path: Path):
    """A pre-existing local branch of the derived name whose tip IS an ancestor
    of the base (here: identical to it) is safe to reuse - but the contract
    must not claim LANE=fresh for a checkout that did not freshly branch from
    the base; WT_BASE must say what actually happened instead."""
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "branch", "issue-42-fix-the-frobnicator")  # at the same tip as main

    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["WT_CREATED"] == "1"
    assert c["LANE"] != "fresh", "reused an existing branch - not a fresh branch-off"
    assert "issue-42-fix-the-frobnicator" in c["WT_BASE"]
    assert Path(c["WT_PATH"]).is_dir()


@requires_git
def test_local_pickup_lane_finds_differently_slugged_branch(tmp_path: Path):
    """Issue #793 item 3: the pickup probe used to look only at remote-tracking
    refs, so a LOCAL leftover branch whose slug no longer matches the CURRENT
    issue title (it was renamed since the branch was cut) was invisible to it
    and fell through to the fresh lane under a brand-new branch name, leaving
    two branches for one issue. Matching by issue-number pattern catches it."""
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "issue-42-old-slug-before-rename")
    (clone / "wip.txt").write_text("in-progress work\n")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "wip")
    _git(clone, "switch", "-q", "main")

    res = _run(
        "42",
        "--session-cwd",
        str(clone),
        cwd=clone,
        gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_TITLE": "Brand new title after rename"},
    )
    # The found branch is unmerged relative to the base, so create_worktree's
    # own guard refuses it rather than silently entering someone's WIP - this
    # proves the probe SAW it (as local-pickup would have) instead of missing
    # it and quietly branching a second, differently-named branch off main.
    assert res.returncode == 1
    assert "issue-42-old-slug-before-rename" in res.stdout
    assert "unmerged" in res.stdout


@requires_git
def test_local_pickup_lane_reuses_ancestor_local_branch(tmp_path: Path):
    """The positive path for the same probe: a local branch matching the issue
    number (but not the current title's slug) whose tip IS an ancestor of the
    base is picked up cleanly under LANE=local-pickup - not silently entered
    under a lie of LANE=fresh, and not left an orphan either."""
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "branch", "issue-42-old-slug-before-rename")  # at main's tip

    res = _run(
        "42",
        "--session-cwd",
        str(clone),
        cwd=clone,
        gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_TITLE": "Brand new title after rename"},
    )
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "local-pickup"
    assert c["BRANCH"] == "issue-42-old-slug-before-rename"
    assert "REMOTE_BRANCH" not in c, "this branch was never remote-tracked"
    assert c["WT_CREATED"] == "1"
    assert Path(c["WT_PATH"]).is_dir()
    assert c["CONFIRM_REQUIRED"] == "0"


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
def test_verify_arms_the_shared_stash_guard(tmp_path: Path):
    """The verify gate installs the #1056 guard - ON BY DEFAULT (owner, 2026-09-19).

    Creating a linked worktree is the moment `refs/stash` becomes shared across
    checkouts, and this gate is the one hook point that runs inside the checkout
    on every lane - the same reason the #597 claim is staked here.
    """
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "issue-42-good-branch")

    res = _run("--verify", "42", cwd=clone, gh=_fake_gh(tmp_path))

    assert "FLOW_START_VERIFY: ok" in res.stdout
    assert _contract(res)["STASH_GUARD"] in {"installed", "current"}
    hook = clone / ".git" / "hooks" / "reference-transaction"
    assert hook.exists() and os.access(hook, os.X_OK)


@requires_git
def test_verify_honours_the_stash_guard_optout(tmp_path: Path):
    """A recorded opt-out must survive the flow lane, which runs on every worktree.

    This is the half that makes the opt-out real: without it, the next
    `/flow:auto` silently reinstalls what the user turned off.
    """
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "issue-42-good-branch")
    _git(clone, "config", "cpp.stashGuard", "false")

    res = _run("--verify", "42", cwd=clone, gh=_fake_gh(tmp_path))

    assert "FLOW_START_VERIFY: ok" in res.stdout
    assert _contract(res)["STASH_GUARD"] == "disabled"
    assert not (clone / ".git" / "hooks" / "reference-transaction").exists()


@requires_git
def test_verify_still_passes_when_the_guard_helper_is_absent(tmp_path: Path):
    """ADVISORY and FAIL-OPEN: an unavailable guard must never fail the gate.

    The gate's job is to prove we are on the right branch. Run from a copy of
    the resolver with no sibling helper, verify must still report ok - and must
    report the guard as `unknown` rather than implying it is armed.
    """
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "switch", "-q", "-c", "issue-42-good-branch")
    lonely_dir = tmp_path / "lonely"
    lonely_dir.mkdir()
    lonely = lonely_dir / "flow-start-resolve.sh"
    lonely.write_text(SCRIPT.read_text())
    lonely.chmod(0o755)

    env = os.environ.copy()
    env.pop("FLOW_WORKTREE_BASE", None)
    env["FLOW_START_RESOLVE_GH"] = str(_fake_gh(tmp_path))
    res = subprocess.run(
        ["bash", str(lonely), "--verify", "42"],
        cwd=clone, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )

    assert res.returncode == 0, res.stderr
    assert "FLOW_START_VERIFY: ok" in res.stdout
    assert _contract(res)["STASH_GUARD"] == "unknown"


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


# --- upstream: a flow branch tracks ITSELF, never the base (issue #1221) -----
#
# `git worktree add -b <branch> <path> origin/main` sets the new branch's
# upstream to origin/main (branch.autoSetupMerge). A bare `git push` then exits
# 128, and git's FIRST suggested remedy is `git push origin HEAD:main` - which
# ships the feature branch onto the default branch past every review gate. The
# resolver must leave the branch tracking origin/<its own name>.


def _fresh_worktree(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    origin, clone = _make_origin_and_clone(tmp_path)
    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["WT_CREATED"] == "1"
    return origin, Path(c["WT_PATH"]), c


def _push(wt: Path) -> subprocess.CompletedProcess[str]:
    # A BARE push, exactly as a hurried worker or a wrapper would run it. The
    # host's own push.default must not decide the result, so pin git's default.
    return subprocess.run(
        ["git", "-c", "push.default=simple", "push"],
        cwd=wt,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@requires_git
def test_fresh_worktree_upstream_is_its_own_branch_not_the_base(tmp_path: Path):
    _, wt, c = _fresh_worktree(tmp_path)
    assert _git(wt, "config", f"branch.{c['BRANCH']}.remote").strip() == "origin"
    assert _git(wt, "config", f"branch.{c['BRANCH']}.merge").strip() == f"refs/heads/{c['BRANCH']}"


@requires_git
def test_bare_push_from_fresh_worktree_reaches_the_branchs_own_remote_ref(tmp_path: Path):
    origin, wt, c = _fresh_worktree(tmp_path)
    (wt / "b.txt").write_text("work\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "work")
    main_before = _git(origin, "rev-parse", "main").strip()
    res = _push(wt)
    assert res.returncode == 0, res.stderr
    # Verify the OUTCOME, not the exit code: the ref exists on origin at our tip,
    # and main on origin did not move.
    remote = _git(wt, "ls-remote", "origin", f"refs/heads/{c['BRANCH']}").split()
    assert remote and remote[0] == _git(wt, "rev-parse", "HEAD").strip()
    assert _git(origin, "rev-parse", "main").strip() == main_before


@requires_git
def test_failed_bare_push_never_offers_HEAD_colon_main_as_a_remedy(tmp_path: Path):
    origin, wt, _ = _fresh_worktree(tmp_path)
    # The fixture OWNS its hooks directory: the CI image's git creates repos
    # with no .git/hooks at all, and a host-level core.hooksPath would send the
    # hook somewhere git never reads. The marker assertion below proves it ran.
    hooks = tmp_path / "origin-hooks"
    hooks.mkdir()
    _git(origin, "config", "core.hooksPath", str(hooks))
    hook = hooks / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'rejected by test hook' >&2\nexit 1\n")
    hook.chmod(0o755)
    _git(wt, "commit", "-q", "--allow-empty", "-m", "work")
    res = _push(wt)
    assert res.returncode != 0, "the control must reach the FAILURE path"
    assert "HEAD:main" not in res.stdout + res.stderr
    # ...and it was OUR rejection, not some earlier failure that never reached
    # origin (a missing push destination would also be non-zero without HEAD:main).
    assert "rejected by test hook" in res.stderr


@requires_git
def test_reused_leftover_branch_tracking_the_base_is_repointed_at_itself(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    branch = "issue-42-fix-the-frobnicator"
    _git(clone, "branch", "--track", branch, "origin/main")  # the pre-#1221 shape
    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "local-pickup" and c["BRANCH"] == branch
    assert _git(clone, "config", f"branch.{branch}.merge").strip() == f"refs/heads/{branch}"


# --- issue #1258: decide BEFORE creating, and never pick up shipped history --
#
# The resolver used to run `git worktree add` on a pickup branch and only then
# report PR_HEAD / CONFIRM_REQUIRED, so the question was asked about a checkout
# that already existed (/flow:auto 982, kyle: 127 commits behind main, on a
# branch whose PR had merged). Each case below asserts on the FILESYSTEM and the
# refs, not only on the contract, because the contract was always "correct" -
# it was the side effect before it that was not.


def _worktree_paths(repo: Path) -> list[str]:
    return [
        ln.removeprefix("worktree ")
        for ln in _git(repo, "worktree", "list", "--porcelain").splitlines()
        if ln.startswith("worktree ")
    ]


def _push_issue_branch(origin: Path, name: str) -> None:
    _git(origin, "switch", "-q", "-c", name)
    (origin / f"{name}.txt").write_text("work\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", name)
    _git(origin, "switch", "-q", "main")


@requires_git
def test_remote_branch_with_merged_pr_is_skipped_and_nothing_is_created_on_it(tmp_path: Path):
    origin, clone = _make_origin_and_clone(tmp_path)
    _push_issue_branch(origin, "issue-42-fix-the-frobnicator")
    res = _run(
        "42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_PR": "1056:MERGED"},
    )
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    # Not a pickup of shipped history: fresh, off the base, on a free name -
    # the derived slug IS the shipped branch's name, so it takes a suffix.
    assert c["LANE"] == "fresh"
    assert c["SHIPPED_BRANCH"] == "issue-42-fix-the-frobnicator:1056:MERGED"
    assert c["BRANCH"] == "issue-42-fix-the-frobnicator-2"
    assert c["WT_BASE"] == "origin/main"
    assert c["PR_HEAD"] == "none"
    assert c["CONFIRM_REQUIRED"] == "0"
    wt = Path(c["WT_PATH"])
    assert not (wt / "issue-42-fix-the-frobnicator.txt").exists(), "worktree stands on the shipped branch"
    assert "REMOTE_BRANCH" not in c


@requires_git
def test_remote_branch_with_open_pr_creates_nothing_until_allow_pickup(tmp_path: Path):
    origin, clone = _make_origin_and_clone(tmp_path)
    _push_issue_branch(origin, "issue-42-remote-work")
    before = _worktree_paths(clone)
    res = _run(
        "42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_PR": "211:OPEN"},
    )
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "remote-pickup"
    assert c["PR_HEAD"] == "211:OPEN"
    assert c["CONFIRM_REQUIRED"] == "1"
    # The whole point: asked BEFORE, so nothing exists yet.
    assert c["WT_CREATED"] == "0"
    assert _worktree_paths(clone) == before
    assert not Path(c["WT_PATH"]).exists()
    assert "--allow-pickup" in res.stderr

    res2 = _run(
        "42", "--allow-pickup", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_PR": "211:OPEN"},
    )
    assert res2.returncode == 0, res2.stderr
    c2 = _contract(res2)
    assert c2["WT_CREATED"] == "1"
    assert (Path(c2["WT_PATH"]) / "issue-42-remote-work.txt").exists()
    # --allow-pickup IS the confirmation; a contract still saying STOP over a
    # worktree it just created would be contradictory (counter-model review).
    assert c2["CONFIRM_REQUIRED"] == "0"


@requires_git
def test_shipped_branch_is_skipped_in_favour_of_a_live_one(tmp_path: Path):
    origin, clone = _make_origin_and_clone(tmp_path)
    _push_issue_branch(origin, "issue-42-a-shipped")
    _push_issue_branch(origin, "issue-42-b-live")
    _git(clone, "fetch", "-q", "origin")
    res = _run(
        "42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_PR_MAP": "issue-42-a-shipped=7:MERGED issue-42-b-live=none"},
    )
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "remote-pickup"
    assert c["BRANCH"] == "issue-42-b-live"
    assert c["SHIPPED_BRANCH"] == "issue-42-a-shipped:7:MERGED"
    assert c["CONFIRM_REQUIRED"] == "0"
    assert c["WT_CREATED"] == "1"


@requires_git
def test_local_pickup_of_a_branch_whose_pr_already_merged_starts_fresh(tmp_path: Path):
    # #1221 comment, instance 2: a leftover branch whose PR merged yesterday must
    # not be entered as if it were fresh work. #1258: it is not entered at all.
    _, clone = _make_origin_and_clone(tmp_path)
    _git(clone, "branch", "issue-42-old-slug", "origin/main")
    res = _run(
        "42",
        "--session-cwd",
        str(clone),
        cwd=clone,
        gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_PR_MAP": "issue-42-old-slug=1208:MERGED"},
    )
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "fresh"
    assert c["SHIPPED_BRANCH"] == "issue-42-old-slug:1208:MERGED"
    assert c["BRANCH"] == "issue-42-fix-the-frobnicator"
    assert _git(Path(c["WT_PATH"]), "branch", "--show-current").strip() == c["BRANCH"]


# --- issue #1258: an unwritable sibling base leaves nothing behind -----------


def _unwritable_parent_repo(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin-repo"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    (origin / "a.txt").write_text("a0\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "init")
    parent = tmp_path / "ro"
    parent.mkdir()
    clone = parent / "workspace"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    parent.chmod(0o555)
    return parent, clone


@requires_git
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root writes through 0555")
def test_unwritable_parent_refuses_before_creating_a_branch(tmp_path: Path):
    parent, clone = _unwritable_parent_repo(tmp_path)
    try:
        # Precondition: the negative condition this fixture constructs.
        assert not os.access(parent, os.W_OK)
        res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
        assert res.returncode == 1
        assert "FLOW_START_RESOLVE: error" in res.stdout
        assert "FLOW_WORKTREE_BASE" in res.stdout
        # The stray branch the nit found: none may exist after a refusal.
        assert _git(clone, "branch", "--list", "issue-42-*").strip() == ""
    finally:
        parent.chmod(0o755)


@requires_git
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root writes through 0555")
def test_unwritable_parent_falls_back_to_an_ignored_in_repo_base(tmp_path: Path):
    parent, clone = _unwritable_parent_repo(tmp_path)
    try:
        (clone / ".git" / "info" / "exclude").write_text(".claude/worktrees/\n")
        assert not os.access(parent, os.W_OK)
        res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
        assert res.returncode == 0, res.stdout + res.stderr
        c = _contract(res)
        assert c["WT_PATH"] == str(clone / ".claude" / "worktrees" / "workspace-issue-42-fix-the-frobnicator")
        assert c["WT_CREATED"] == "1"
        assert Path(c["WT_PATH"]).is_dir()
    finally:
        parent.chmod(0o755)


@requires_git
def test_failed_worktree_add_removes_the_branch_it_created(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    # A FILE where the worktree directory must go makes `git worktree add -b`
    # fail after git has already created the branch.
    blocker = tmp_path / "clone-repo-issue-42-fix-the-frobnicator"
    blocker.write_text("in the way\n")
    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 1
    assert _git(clone, "branch", "--list", "issue-42-*").strip() == ""


# --- issue #1258: compose's own `name:` beats the checkout basename -----------


@requires_git
def test_compose_project_name_prefers_the_compose_files_own_name(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    (clone / "docker-compose.yml").write_text('name: "kyle"\nservices: {}\n')
    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert res.returncode == 0, res.stderr
    assert _contract(res)["COMPOSE_PROJECT_NAME"] == "kyle"


@requires_git
def test_compose_name_with_interpolation_falls_back_to_basename(tmp_path: Path):
    _, clone = _make_origin_and_clone(tmp_path)
    (clone / "compose.yaml").write_text("name: ${PROJECT:-x}\nservices: {}\n")
    res = _run("42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path))
    assert _contract(res)["COMPOSE_PROJECT_NAME"] == "clone-repo"


@requires_git
def test_fresh_name_skips_every_taken_suffix(tmp_path: Path):
    origin, clone = _make_origin_and_clone(tmp_path)
    _push_issue_branch(origin, "issue-42-fix-the-frobnicator")
    _push_issue_branch(origin, "issue-42-fix-the-frobnicator-2")
    _git(clone, "fetch", "-q", "origin")
    res = _run(
        "42", "--session-cwd", str(clone), cwd=clone, gh=_fake_gh(tmp_path),
        extra_env={"FAKE_GH_PR": "9:MERGED"},
    )
    assert res.returncode == 0, res.stderr
    c = _contract(res)
    assert c["LANE"] == "fresh"
    assert c["BRANCH"] == "issue-42-fix-the-frobnicator-3"

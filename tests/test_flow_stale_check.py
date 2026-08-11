"""Tests for scripts/flow-stale-check.sh - early stale-base detection (issue #473).

Contract:
- When ``origin/main`` (the base ref) has not moved past HEAD, the verdict is
  ``current`` and exit is 0.
- When the base moved but none of the files this branch touched changed upstream,
  the verdict is ``moved-clean``.
- When the base moved AND a file this branch edited also changed upstream, the
  verdict is ``collision`` and the colliding file(s) are NAMED in the output.
- When a ``.claude/commands/flow/*.md`` file changed upstream, the output reminds
  the user to regenerate the packaged copies (``plugin-sync.sh``) so they do not drift.
- The check is advisory (exit 0) by default; ``--exit-code`` returns 1 on a
  collision so a caller can gate on it.

The tests build REAL throwaway git repos so the diff/intersection logic is
exercised for real; ``--no-fetch`` keeps them offline (no remote).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-stale-check.sh"

FLOW_CMD = ".claude/commands/flow/auto.md"

# The behaviour tests drive real `git` and `bash` subprocesses. The Woodpecker
# `validate` step runs in `uv:python3.11-bookworm-slim`, which ships bash but NOT
# git, so those tests are skipped there (issue #430). The read-only wiring tests
# below need neither and always run.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)


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


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _make_repo(tmp_path: Path) -> Path:
    """A repo on ``main`` with a couple of files, then a feature branch cut off it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _write(repo, "a.txt", "a0\n")
    _write(repo, "shared.txt", "s0\n")
    _write(repo, FLOW_CMD, "flow0\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    return repo


def _advance_main(repo: Path, rel: str, content: str) -> None:
    """Simulate a sibling PR landing on ``main`` while ``feature`` is checked out."""
    _git(repo, "checkout", "-q", "main")
    _write(repo, rel, content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"upstream change to {rel}")
    _git(repo, "checkout", "-q", "feature")


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args, "--no-fetch"],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _verdict(out: str) -> str:
    for line in out.splitlines():
        if line.startswith("FLOW_STALE_BASE:"):
            return line.split(":", 1)[1].strip()
    return ""


def test_script_is_executable():
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK), "flow-stale-check.sh must be executable"


@requires_git
def test_base_current_when_not_behind(tmp_path: Path):
    repo = _make_repo(tmp_path)  # feature == main, nothing moved
    result = _run(repo, "main")
    assert result.returncode == 0, result.stderr
    assert _verdict(result.stdout) == "current"


@requires_git
def test_moved_clean_when_no_overlap(tmp_path: Path):
    repo = _make_repo(tmp_path)
    # Feature edits a.txt; main advances a DIFFERENT file.
    _write(repo, "a.txt", "a-mine\n")
    _git(repo, "commit", "-qam", "my edit")
    _advance_main(repo, "shared.txt", "s-upstream\n")
    result = _run(repo, "main")
    assert result.returncode == 0, result.stderr
    assert _verdict(result.stdout) == "moved-clean"
    assert "No overlap" in result.stdout
    assert "COLLISION" not in result.stdout


@requires_git
def test_collision_is_named(tmp_path: Path):
    repo = _make_repo(tmp_path)
    # Both feature and main touch shared.txt -> collision.
    _write(repo, "shared.txt", "s-mine\n")
    _git(repo, "commit", "-qam", "my edit to shared")
    _advance_main(repo, "shared.txt", "s-upstream\n")
    result = _run(repo, "main")
    assert result.returncode == 0, result.stderr  # advisory: still 0 by default
    assert _verdict(result.stdout) == "collision"
    assert "COLLISION" in result.stdout
    assert "shared.txt" in result.stdout, "the colliding file must be named"
    assert "git merge --no-edit main" in result.stdout


@requires_git
def test_collision_from_uncommitted_worktree_edit(tmp_path: Path):
    repo = _make_repo(tmp_path)
    _advance_main(repo, "shared.txt", "s-upstream\n")
    # Dirty the work tree without committing - still counts as "touched".
    _write(repo, "shared.txt", "s-dirty\n")
    result = _run(repo, "main")
    assert _verdict(result.stdout) == "collision"
    assert "shared.txt" in result.stdout


@requires_git
def test_exit_code_flag_fails_on_collision(tmp_path: Path):
    repo = _make_repo(tmp_path)
    _write(repo, "shared.txt", "s-mine\n")
    _git(repo, "commit", "-qam", "my edit")
    _advance_main(repo, "shared.txt", "s-upstream\n")
    result = _run(repo, "main", "--exit-code")
    assert result.returncode == 1, "collision + --exit-code must return non-zero"
    assert _verdict(result.stdout) == "collision"


@requires_git
def test_exit_code_flag_passes_when_clean(tmp_path: Path):
    repo = _make_repo(tmp_path)
    _write(repo, "a.txt", "a-mine\n")
    _git(repo, "commit", "-qam", "my edit")
    _advance_main(repo, "shared.txt", "s-upstream\n")
    result = _run(repo, "main", "--exit-code")
    assert result.returncode == 0, result.stderr


@requires_git
def test_flow_command_change_reminds_to_resync(tmp_path: Path):
    repo = _make_repo(tmp_path)
    _advance_main(repo, FLOW_CMD, "flow-upstream\n")
    result = _run(repo, "main")
    assert "plugin-sync.sh" in result.stdout, (
        "a flow command change upstream must remind to regenerate the packaged copies"
    )
    assert FLOW_CMD in result.stdout


@requires_git
def test_fail_open_outside_git_repo(tmp_path: Path):
    outside = tmp_path / "plain"
    outside.mkdir()
    result = _run(outside, "main")
    assert result.returncode == 0, "must fail open outside a git repo"
    assert _verdict(result.stdout) == "unknown"


@requires_git
def test_fail_open_when_base_ref_missing(tmp_path: Path):
    repo = _make_repo(tmp_path)
    result = _run(repo, "origin/does-not-exist")
    assert result.returncode == 0
    assert _verdict(result.stdout) == "unknown"


# --- Fetch-failure messaging (issue #536) -----------------------------------
# These run WITHOUT --no-fetch so the fetch path is exercised. The "remote" is an
# empty bare repo, so `git fetch origin main` deterministically fails ("couldn't
# find remote ref main") without contacting the network.


def _run_online(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wire_failing_remote(repo: Path, tmp_path: Path) -> str:
    """Point origin at an empty bare repo (fetch of `main` fails) and seed an
    on-disk origin/main == HEAD so the base ref exists. Returns HEAD sha."""
    remote = tmp_path / "remote.git"
    _git(repo, "init", "-q", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    sha = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "update-ref", "refs/remotes/origin/main", sha)
    return sha


@requires_git
def test_fetch_failure_suppressed_when_fetch_head_fresh(tmp_path: Path):
    repo = _make_repo(tmp_path)
    sha = _wire_failing_remote(repo, tmp_path)
    # A fresh FETCH_HEAD stands in for "a fetch already succeeded this run".
    (repo / ".git" / "FETCH_HEAD").write_text(f"{sha}\t\tbranch 'main'\n")
    result = _run_online(repo, "origin/main")
    assert result.returncode == 0
    assert "failed - using on-disk ref" not in result.stderr, (
        "a fresh FETCH_HEAD must suppress the alarming generic failure line (#536)"
    )
    assert _verdict(result.stdout) == "current"


@requires_git
def test_fetch_failure_surfaces_real_git_error(tmp_path: Path):
    repo = _make_repo(tmp_path)
    _wire_failing_remote(repo, tmp_path)
    fh = repo / ".git" / "FETCH_HEAD"
    if fh.exists():
        fh.unlink()  # not fresh -> the real failure must be surfaced
    result = _run_online(repo, "origin/main")
    assert result.returncode == 0, "still fail-open (advisory) on a fetch failure"
    assert "failed - using on-disk ref" in result.stderr
    assert "git:" in result.stderr, (
        "the ACTUAL git error must be surfaced, not just the generic line (#536)"
    )
    assert _verdict(result.stdout) == "current"


# --- Wiring: the flow surfaces must call the early check / re-sync ----------


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_auto_wires_early_check_at_step4_and_step6():
    text = _read(".claude/commands/flow/auto.md")
    # Referenced at least twice: Step 4 (early) and Step 6 (pre-commit).
    assert text.count("flow-stale-check.sh") >= 2, (
        "auto.md must run the early stale-base check at both Step 4 and Step 6"
    )
    # Step-7 #462 backstop is preserved.
    assert "git merge --no-edit origin/main" in text


def test_finish_wires_early_check():
    text = _read(".claude/commands/flow/finish.md")
    assert "flow-stale-check.sh" in text, "finish.md must run the early stale-base check"


@pytest.mark.parametrize(
    "rel",
    [".claude/commands/flow/auto.md", ".claude/commands/flow/finish.md"],
    ids=["auto", "finish"],
)
def test_stale_base_precheck_commits_dirty_tree_before_merge(rel: str):
    # Issue #521 established the order (secure the uncommitted work FIRST, then
    # merge); issue #635 replaced its stash mechanism with a branch-local WIP
    # commit after the shared stash stack silently swapped work between
    # concurrent worktrees. This pin asserts the CURRENT contract: the wip
    # snapshot commit precedes the stale-base merge in source order. (The old
    # form of this test asserted `git stash push` presence and survived the
    # #635 removal only because the replacement COMMENT text mentions the
    # forbidden commands - a substring pin inverted in meaning without failing.
    # The executable-stash ABSENCE half lives in test_flow_docs_no_shared_stash.)
    text = _read(rel)
    assert 'git commit -m "wip(flow): pre-merge snapshot"' in text, (
        f"{rel} must WIP-commit uncommitted work before the stale-base merge "
        f"(issues #521 order, #635 mechanism)"
    )
    commit_idx = text.find('git commit -m "wip(flow): pre-merge snapshot"')
    merge_after = text.find("git merge --no-edit origin/main", commit_idx)
    assert merge_after != -1, (
        f"{rel}: `git merge origin/main` must follow the WIP commit in the "
        f"stale-base pre-check (issue #635)"
    )
    # The old STOP text mislabeled a dirty-tree refusal (no merge started) as a
    # set of conflicts to resolve - that wording must be gone.
    assert "resolve the listed conflicts" not in text, (
        f"{rel}: the pre-check STOP must not mislabel a dirty-tree refusal as "
        f"conflicts (issue #521)"
    )


class TestDeclaredCheckoutPath:
    """Issue #614: the checkout is declared by the caller, never inferred from
    the drifting process cwd, and every verdict names the tree it inspected."""

    @staticmethod
    def _run_at(cwd, *args):
        import subprocess

        return subprocess.run(
            ["bash", str(SCRIPT), *args, "--no-fetch"],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    @staticmethod
    def _contract(stdout):
        """Return (path_line, verdict_line, adjacent) from the output."""
        lines = stdout.splitlines()
        path_lines = [(i, ln) for i, ln in enumerate(lines) if ln.startswith("FLOW_STALE_PATH: ")]
        base_lines = [(i, ln) for i, ln in enumerate(lines) if ln.startswith("FLOW_STALE_BASE: ")]
        assert len(path_lines) == 1, stdout
        assert len(base_lines) == 1, stdout
        adjacent = base_lines[0][0] == path_lines[0][0] + 1
        return path_lines[0][1], base_lines[0][1], adjacent

    @requires_git
    def test_positional_path_answers_for_named_tree_not_cwd(self, tmp_path):
        # Run from a cwd that is NOT a repo at all, pointing at a repo whose
        # base moved: the verdict must answer for the NAMED tree. Under the old
        # cwd-trusting behavior this exact call reported `unknown`.
        repo = _make_repo(tmp_path)
        _advance_main(repo, "a.txt", "a1\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        result = self._run_at(elsewhere, "main", str(repo))
        assert result.returncode == 0
        path_line, base_line, adjacent = self._contract(result.stdout)
        assert base_line == "FLOW_STALE_BASE: moved-clean", result.stdout
        assert path_line == f"FLOW_STALE_PATH: {repo.resolve()}"
        assert adjacent, "path line must immediately precede the verdict line"

    @requires_git
    def test_declared_path_wins_over_a_different_repo_cwd(self, tmp_path):
        # The #597 drift shape: the cwd sits in a CURRENT tree while the run's
        # worktree (declared) is behind - the answer must be the declared tree's.
        (tmp_path / "behind").mkdir()
        (tmp_path / "current").mkdir()
        behind = _make_repo(tmp_path / "behind")
        _advance_main(behind, "a.txt", "a1\n")
        current = _make_repo(tmp_path / "current")
        result = self._run_at(current, "main", str(behind))
        _, base_line, _ = self._contract(result.stdout)
        assert base_line == "FLOW_STALE_BASE: moved-clean", result.stdout

    @requires_git
    def test_path_flag_forms(self, tmp_path):
        repo = _make_repo(tmp_path)
        for args in (["main", "--path", str(repo)], ["main", f"--path={repo}"]):
            result = self._run_at(tmp_path, *args)
            path_line, base_line, adjacent = self._contract(result.stdout)
            assert base_line == "FLOW_STALE_BASE: current", result.stdout
            assert path_line == f"FLOW_STALE_PATH: {repo.resolve()}"
            assert adjacent

    @requires_git
    def test_default_cwd_backcompat_and_contract(self, tmp_path):
        repo = _make_repo(tmp_path)
        result = self._run_at(repo, "main")
        path_line, base_line, adjacent = self._contract(result.stdout)
        assert base_line == "FLOW_STALE_BASE: current"
        assert path_line == f"FLOW_STALE_PATH: {repo.resolve()}"
        assert adjacent

    def test_invalid_path_fails_open_with_contract(self, tmp_path):
        import shutil as _shutil

        if _shutil.which("bash") is None:
            import pytest as _pytest

            _pytest.skip("bash unavailable")
        result = self._run_at(tmp_path, "main", str(tmp_path / "missing"))
        assert result.returncode == 0
        path_line, base_line, adjacent = self._contract(result.stdout)
        assert base_line == "FLOW_STALE_BASE: unknown"
        assert str(tmp_path / "missing") in path_line
        assert adjacent

    @requires_git
    def test_collision_verdict_carries_path(self, tmp_path):
        repo = _make_repo(tmp_path)
        _advance_main(repo, "shared.txt", "s1\n")
        _write(repo, "shared.txt", "mine\n")  # dirty AFTER main advanced
        result = self._run_at(tmp_path, "main", str(repo))
        path_line, base_line, adjacent = self._contract(result.stdout)
        assert base_line == "FLOW_STALE_BASE: collision", result.stdout
        assert path_line == f"FLOW_STALE_PATH: {repo.resolve()}"
        assert adjacent

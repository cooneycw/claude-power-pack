"""Tests for scripts/gh-pr-merge.sh - layout-aware PR squash-merge (issue #461).

Contract:
- In a LINKED worktree (cwd's ``.git`` is a file), merge WITHOUT --delete-branch
  and delete the remote branch ourselves, so gh never attempts the local branch
  switch that fails with "fatal: 'main' is already checked out".
- In the PRIMARY repo (cwd's ``.git`` is a directory), keep --delete-branch.
- Verify the PR reached MERGED before returning failure, so a non-zero gh exit on
  a local post-merge step never masks a successful remote merge.
- Return non-zero only when the PR genuinely did not merge.

``gh`` and ``git`` are stubbed via the GH_PR_MERGE_GH / GH_PR_MERGE_GIT env hooks;
each stub appends its argv to a call log the tests assert against.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gh-pr-merge.sh"


def _write_stub(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(0o755)


def _make_stubs(
    tmp_path: Path,
    *,
    merge_exit: int = 0,
    pr_state: str = "MERGED",
    mergeable: str | list[str] = "MERGEABLE",
) -> dict:
    """Create fake gh/git that log their args and honour a scripted outcome.

    ``mergeable`` scripts the ``gh pr view --json mergeable`` poll (issue #485):
    pass a single value, or a sequence consumed one value per poll (staying on
    the last once exhausted) to model a transient UNKNOWN that resolves.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    call_log = tmp_path / "calls.log"

    # Persist the mergeability sequence + a counter the gh stub advances per poll.
    seq_file = tmp_path / "mergeable_seq"
    ctr_file = tmp_path / "mergeable_ctr"
    vals = [mergeable] if isinstance(mergeable, str) else list(mergeable)
    seq_file.write_text("\n".join(vals) + "\n")

    # gh: log argv; `pr merge` exits merge_exit; `pr view --json mergeable` echoes
    # the next scripted mergeable value; any other `pr view` echoes pr_state.
    _write_stub(
        bin_dir / "gh",
        f'echo "gh $*" >> "{call_log}"\n'
        'if [[ "$1 $2" == "pr merge" ]]; then\n'
        f"  exit {merge_exit}\n"
        'elif [[ "$1 $2" == "pr view" ]]; then\n'
        '  if [[ "$*" == *mergeable* ]]; then\n'
        f'    ctr=$(cat "{ctr_file}" 2>/dev/null || echo 0)\n'
        f'    mapfile -t vals < "{seq_file}"\n'
        "    idx=$ctr\n"
        "    if (( idx >= ${#vals[@]} )); then idx=$(( ${#vals[@]} - 1 )); fi\n"
        '    echo "${vals[$idx]}"\n'
        f'    echo $(( ctr + 1 )) > "{ctr_file}"\n'
        "  else\n"
        f'    echo "{pr_state}"\n'
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )
    # git: log argv; everything succeeds.
    _write_stub(bin_dir / "git", f'echo "git $*" >> "{call_log}"\nexit 0\n')

    return {
        "GH_PR_MERGE_GH": str(bin_dir / "gh"),
        "GH_PR_MERGE_GIT": str(bin_dir / "git"),
        "_call_log": call_log,
    }


def _run(cwd: Path, stubs: dict, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GH_PR_MERGE_GH"] = stubs["GH_PR_MERGE_GH"]
    env["GH_PR_MERGE_GIT"] = stubs["GH_PR_MERGE_GIT"]
    env["GH_PR_MERGE_POLL_DELAY"] = "0"  # keep the mergeability poll instant in tests
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        check=False,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _linked_worktree(tmp_path: Path) -> Path:
    """A cwd whose .git is a FILE - what a linked/native worktree looks like."""
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text("gitdir: /repo/.git/worktrees/wt\n")
    return wt


def _primary_repo(tmp_path: Path) -> Path:
    """A cwd whose .git is a DIRECTORY - the primary checkout."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def _calls(stubs: dict) -> list[str]:
    log = stubs["_call_log"]
    return log.read_text().splitlines() if log.exists() else []


def test_script_is_executable():
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK), "gh-pr-merge.sh must be executable"


def test_usage_error_without_args(tmp_path: Path):
    stubs = _make_stubs(tmp_path)
    result = _run(_primary_repo(tmp_path), stubs, "42")  # missing branch
    assert result.returncode == 2
    assert "Usage" in result.stderr


def test_linked_worktree_omits_delete_branch_and_deletes_remote(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 0, result.stderr
    calls = _calls(stubs)
    merge = next(c for c in calls if c.startswith("gh pr merge"))
    assert "--delete-branch" not in merge, "linked worktree must NOT pass --delete-branch"
    assert "--squash" in merge
    # Remote branch deleted by us, not by gh.
    assert any(c == "git push origin --delete issue-461-fix" for c in calls), calls


def test_primary_repo_keeps_delete_branch(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    result = _run(_primary_repo(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 0, result.stderr
    calls = _calls(stubs)
    merge = next(c for c in calls if c.startswith("gh pr merge"))
    assert "--delete-branch" in merge, "primary repo must keep --delete-branch"
    # We must NOT issue a manual remote-branch delete in the primary repo.
    assert not any("push origin --delete" in c for c in calls), calls


def test_nonzero_gh_but_merged_is_success(tmp_path: Path):
    # The exact #461 trap: gh exits non-zero on the local post-merge step, but the
    # remote squash succeeded (PR is MERGED). Must be treated as success.
    stubs = _make_stubs(tmp_path, merge_exit=1, pr_state="MERGED")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout


def test_genuinely_unmerged_returns_failure(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=1, pr_state="OPEN")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 1
    assert "did not merge" in result.stderr


def test_primary_repo_nonzero_but_merged_is_success(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=1, pr_state="MERGED")
    result = _run(_primary_repo(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout


def test_transient_unknown_then_mergeable_proceeds(tmp_path: Path):
    # Issue #485: right after a push, mergeable is UNKNOWN for a beat, then
    # resolves to MERGEABLE. The poll must wait it out and still merge.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        mergeable=["UNKNOWN", "UNKNOWN", "MERGEABLE"],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-485-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    calls = _calls(stubs)
    # Polled mergeability more than once (waited out the transient) ...
    poll_calls = [c for c in calls if c.startswith("gh pr view") and "mergeable" in c]
    assert len(poll_calls) >= 2, calls
    # ... and did go on to attempt the squash-merge.
    assert any(c.startswith("gh pr merge") for c in calls), calls


def test_conflicting_stops_before_merge(tmp_path: Path):
    # A genuinely CONFLICTING PR must stop with a clear message and never attempt
    # the merge.
    stubs = _make_stubs(tmp_path, mergeable="CONFLICTING")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-485-fix")
    assert result.returncode == 1
    assert "CONFLICTING" in result.stderr
    calls = _calls(stubs)
    assert not any(c.startswith("gh pr merge") for c in calls), "must not merge a CONFLICTING PR"


def test_persistent_unknown_fails_open_and_merges(tmp_path: Path):
    # If mergeability never resolves (stays UNKNOWN through every attempt), fail
    # open: attempt the merge anyway and let the post-merge MERGED check decide.
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED", mergeable="UNKNOWN")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-485-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    assert "UNKNOWN" in result.stderr  # surfaced the fail-open note
    calls = _calls(stubs)
    # Exhausted the default 5 attempts, then merged anyway.
    poll_calls = [c for c in calls if c.startswith("gh pr view") and "mergeable" in c]
    assert len(poll_calls) == 5, poll_calls
    assert any(c.startswith("gh pr merge") for c in calls), calls


def test_flow_commands_wire_the_helper():
    # Both merge surfaces must call the guard (helper preferred, inline fallback),
    # not the raw `gh pr merge --squash --delete-branch` that trips #461.
    for rel in (".claude/commands/flow/auto.md", ".claude/commands/flow/merge.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "gh-pr-merge.sh" in text, f"{rel} must reference the merge helper"
        # The inline fallback keeps the linked-worktree guard even without the helper.
        assert "git push origin --delete" in text, f"{rel} missing remote-branch delete fallback"
        assert "MERGED" in text, f"{rel} must verify PR state, not just the exit code"

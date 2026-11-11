"""`/flow:cleanup` Step 4 deletes a gone-upstream branch only on proof it landed (issue #1708).

The step used to treat "the remote branch is gone" as proof the pull request
merged, and force-deleted the local branch. A remote branch also disappears
when it is deleted unmerged or its pull request is closed, and then the local
branch was the only copy of the work.

These tests run the document's OWN block, extracted from the command document,
in a scratch repository with a stub `gh`. They pin the block's text, not what
an agent following the document does; that is the limit every command-document
test has.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude" / "commands" / "flow" / "cleanup.md"

pytestmark = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("git", "bash", "jq")),
    reason="needs git, bash and jq",
)

GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]

STUB_GH = """#!/usr/bin/env bash
# Stub gh: answers `pr list` from $GH_STUB_DIR/<head-branch>, and logs its argv.
printf '%s\\n' "$*" >> "$GH_STUB_DIR/calls.log"
head=""
while [ $# -gt 0 ]; do
    if [ "$1" = "--head" ]; then head="$2"; fi
    shift
done
answer="$GH_STUB_DIR/$head"
[ -f "$answer.fail" ] && exit 1
# A neighbour session commits to the branch while cleanup is classifying it.
[ -f "$answer.advance" ] && git -C "$GH_STUB_REPO" update-ref "refs/heads/$head" "$(cat "$answer.advance")"
[ -f "$answer" ] && cat "$answer"
exit 0
"""


def step4_block() -> str:
    """The fenced bash block of Step 4 that decides gone-upstream branches."""
    text = DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
    matching = [b for b in blocks if "cpp-merged-head" in b]
    assert len(matching) == 1, f"expected one block reading the landed record, found {len(matching)}"
    return matching[0]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run([*GIT, *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def scratch(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "remote", "add", "origin", "https://github.com/acme/widget.git")
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    gh = stub_dir / "gh"
    gh.write_text(STUB_GH, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)

    def branch(name: str) -> str:
        """A local issue branch with one commit whose configured upstream is GONE."""
        _git(repo, "checkout", "-q", "-b", name, "main")
        (repo / f"{name}.txt").write_text(name + "\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", name)
        _git(repo, "config", f"branch.{name}.remote", "origin")
        _git(repo, "config", f"branch.{name}.merge", f"refs/heads/{name}")
        _git(repo, "checkout", "-q", "main")
        # precondition for every case below: the upstream ref does not exist
        gone = subprocess.run(
            [*GIT, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{name}"], cwd=repo, check=False
        )
        assert gone.returncode != 0, "precondition: the upstream ref must be gone"
        return _git(repo, "rev-parse", f"refs/heads/{name}")

    def run() -> dict[str, str]:
        env = dict(os.environ)
        env["PATH"] = str(stub_dir) + os.pathsep + env["PATH"]
        env["GH_STUB_DIR"] = str(stub_dir)
        env["GH_STUB_REPO"] = str(repo)
        script = f'MAIN_REPO={json.dumps(str(repo))}\nWORKTREE_BRANCHES=""\n{step4_block()}'
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, check=False)
        assert proc.returncode == 0, proc.stderr
        verdicts = {}
        for line in proc.stdout.splitlines():
            match = re.match(r"(DELETED|KEPT): (\S+) \((.*)\)$", line)
            assert match, f"unexpected output line: {line!r}"
            verdicts[match.group(2)] = f"{match.group(1)}: {match.group(3)}"
            # the verdict must be what actually happened to the ref
            exists = subprocess.run(
                [*GIT, "show-ref", "--verify", "--quiet", f"refs/heads/{match.group(2)}"], cwd=repo, check=False
            ).returncode == 0
            assert exists == (match.group(1) == "KEPT"), f"{line!r} but branch exists={exists}"
        return verdicts

    return repo, stub_dir, branch, run


def test_a_branch_the_merge_helper_recorded_as_landed_is_deleted(scratch):
    repo, stub_dir, branch, run = scratch
    tip = branch("issue-1-recorded")
    _git(repo, "config", "branch.issue-1-recorded.cpp-merged-head", tip)
    assert run() == {"issue-1-recorded": "DELETED: landed: merge-helper record"}
    assert not (stub_dir / "calls.log").exists(), "the offline record needs no GitHub call"


def test_a_branch_whose_tip_is_a_merged_pr_head_is_deleted(scratch):
    repo, stub_dir, branch, run = scratch
    tip = branch("issue-2-merged")
    (stub_dir / "issue-2-merged").write_text(json.dumps([{"headRefOid": tip}]), encoding="utf-8")
    assert run() == {"issue-2-merged": "DELETED: landed: merged PR head"}
    calls = (stub_dir / "calls.log").read_text(encoding="utf-8")
    assert "-R acme/widget" in calls, f"the query must name MAIN_REPO's repository: {calls!r}"
    assert "--state merged" in calls


def test_a_gone_upstream_with_no_proof_is_kept(scratch):
    """THE RED CASE: the remote was deleted without a merge. Before #1708 this
    branch, the only copy of its work, was named for force-deletion."""
    repo, stub_dir, branch, run = scratch
    branch("issue-3-unmerged")
    (stub_dir / "issue-3-unmerged").write_text("[]", encoding="utf-8")
    assert run() == {"issue-3-unmerged": "KEPT: no merged PR"}


def test_a_tip_past_the_merged_head_is_kept(scratch):
    """Merged, then committed to again locally: the extra commit exists nowhere else."""
    repo, stub_dir, branch, run = scratch
    merged_tip = branch("issue-4-moved")
    _git(repo, "config", "branch.issue-4-moved.cpp-merged-head", merged_tip)
    _git(repo, "checkout", "-q", "issue-4-moved")
    (repo / "later.txt").write_text("later\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "later")
    _git(repo, "checkout", "-q", "main")
    (stub_dir / "issue-4-moved").write_text(json.dumps([{"headRefOid": merged_tip}]), encoding="utf-8")
    assert run() == {"issue-4-moved": "KEPT: tip differs from merged head"}


def test_a_branch_that_moves_after_it_was_proven_is_kept(scratch):
    """The deletion is bound to the PROVEN commit, not to the branch name. A
    neighbour session commits to the branch between the proof and the delete;
    deleting by name would destroy that new commit (counter-model review)."""
    repo, stub_dir, branch, run = scratch
    proven = branch("issue-7-raced")
    _git(repo, "checkout", "-q", "issue-7-raced")
    (repo / "neighbour.txt").write_text("new work\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "neighbour")
    newer = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "update-ref", "refs/heads/issue-7-raced", proven)  # as cleanup first sees it
    (stub_dir / "issue-7-raced").write_text(json.dumps([{"headRefOid": proven}]), encoding="utf-8")
    (stub_dir / "issue-7-raced.advance").write_text(newer, encoding="utf-8")
    assert run() == {"issue-7-raced": "KEPT: tip changed during cleanup"}
    assert _git(repo, "rev-parse", "refs/heads/issue-7-raced") == newer


def test_a_proven_branch_checked_out_in_a_worktree_is_kept(scratch, tmp_path):
    repo, stub_dir, branch, run = scratch
    tip = branch("issue-8-checked-out")
    _git(repo, "config", "branch.issue-8-checked-out.cpp-merged-head", tip)
    _git(repo, "worktree", "add", "-q", str(tmp_path / "wt"), "issue-8-checked-out")
    assert run() == {"issue-8-checked-out": "KEPT: checked out in a worktree"}


@pytest.mark.parametrize(
    "answer",
    ["fail", "empty", "garbage", "object"],
)
def test_an_unusable_github_answer_keeps_the_branch(scratch, answer):
    """A failed, empty or unreadable answer is UNKNOWN, never "no PR"."""
    repo, stub_dir, branch, run = scratch
    branch("issue-5-unknown")
    if answer == "fail":
        (stub_dir / "issue-5-unknown.fail").write_text("", encoding="utf-8")
    elif answer == "garbage":
        (stub_dir / "issue-5-unknown").write_text("<html>502</html>", encoding="utf-8")
    elif answer == "object":
        (stub_dir / "issue-5-unknown").write_text('{"message": "rate limited"}', encoding="utf-8")
    # "empty": the stub exits 0 having printed nothing
    assert run() == {"issue-5-unknown": "KEPT: could not ask GitHub"}


def test_a_branch_with_a_live_upstream_or_a_worktree_is_not_considered(scratch):
    repo, stub_dir, branch, run = scratch
    tip = branch("issue-6-live")
    _git(repo, "update-ref", "refs/remotes/origin/issue-6-live", tip)
    assert run() == {}


def test_no_sentence_gives_a_gone_remote_as_sufficient_reason():
    """The old rule was stated four times in the document; none may survive."""
    text = DOC.read_text(encoding="utf-8")
    for phrase in (
        "Remote deleted:",
        "branch -D` on",
        "safe to delete locally",
        "only for branches whose remote was deleted",
        "remote branch deleted - squash-merged PR",
        "or remote branch deleted)",
    ):
        assert phrase not in text, f"cleanup.md still says: {phrase!r}"


def test_the_command_holds_no_standing_approval_for_gh_api():
    """Orchestrator ruling on #1708: `Bash(gh api:*)` pre-approved any API write."""
    frontmatter = DOC.read_text(encoding="utf-8").split("---", 2)[1]
    assert "Bash(gh api" not in frontmatter
    assert "Bash(gh pr list:*)" in frontmatter

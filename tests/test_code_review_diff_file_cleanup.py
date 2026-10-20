"""`/codex:code_review` leaked its diff temp file on four refusal paths (#1494).

`DIFF_FILE=$(mktemp ...)` is created near the top of the diff-building block,
and four `exit 3` refusals below it (no common ancestor with BASE, a failed
untracked-file enumeration, a failed intent-to-add stage, a failed final diff)
used to leave the file behind - only two LATER refusals, in the next block,
removed it. A `trap 'rm -f "$DIFF_FILE"' EXIT` set right after the mktemp
covers every exit in that block, including ones added later; the trap is
explicitly disarmed (`trap - EXIT`) at the end of a SUCCESSFUL run, because
`$DIFF_FILE` must survive into the later blocks that read and remove it
themselves.

TWO-SIDED, on a real repository:
RED/GREEN  a refusal path (no common ancestor) - the temp file must NOT survive.
GREEN      a normal, successful run - the temp file MUST survive (the trap's
           disarm is the half a leak fix could break silently: an
           unconditional trap would delete the file on every exit, including
           the happy path, and nothing downstream would get a diff to review).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.isolated_env import ISOLATED_PATH

REPO = Path(__file__).resolve().parent.parent
COMMAND = REPO / ".claude" / "commands" / "codex" / "code_review.md"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")


def _extract_diff_block() -> str:
    text = COMMAND.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)\n```", text, re.DOTALL)
    for block in blocks:
        if "mktemp /tmp/codex-review-diff" in block:
            return block
    raise AssertionError("code_review.md no longer carries the DIFF_FILE mktemp block")


def _git(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True,
    )


def _env(home: Path) -> dict[str, str]:
    return {
        "HOME": str(home), "PATH": ISOLATED_PATH,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
    }


def _run_block(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = _extract_diff_block()
    return subprocess.run(
        ["bash", "-c", script], cwd=repo, env=env, capture_output=True, text=True,
    )


def test_the_block_installs_and_disarms_a_trap() -> None:
    text = COMMAND.read_text(encoding="utf-8")
    assert 'trap \'rm -f "$DIFF_FILE"\' EXIT' in text, (
        "code_review.md no longer installs a cleanup trap for $DIFF_FILE"
    )
    assert "trap - EXIT" in text, (
        "code_review.md installs the cleanup trap but never disarms it - "
        "a successful run would delete $DIFF_FILE before the later blocks "
        "that need to read it"
    )


@requires_git
def test_a_refused_review_leaves_no_diff_file_behind(tmp_path: Path) -> None:
    env = _env(tmp_path / "home")
    (tmp_path / "home").mkdir()

    # Two git histories with no common ancestor, so `git merge-base` fails -
    # the FIRST refusal path after the mktemp.
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git("init", "-q", "-b", "main", cwd=repo, env=env).returncode == 0
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    assert _git("add", "-A", cwd=repo, env=env).returncode == 0
    assert _git("commit", "-qm", "unrelated history", cwd=repo, env=env).returncode == 0

    other = tmp_path / "other.git"
    other.mkdir()
    assert _git("init", "-q", "--bare", other, cwd=tmp_path, env=env).returncode == 0
    assert _git("remote", "add", "origin", str(other), cwd=repo, env=env).returncode == 0
    # origin/main does not exist and cannot be fetched (bare repo has nothing) -
    # `git fetch origin --quiet || true` swallows the failure, and the later
    # `git merge-base HEAD "$BASE"` (BASE defaulting to origin/main) then fails
    # for want of any such ref, reproducing the "no common ancestor" refusal.

    before = set((Path("/tmp")).glob("codex-review-diff.*.patch"))
    result = _run_block(repo, env)
    after = set((Path("/tmp")).glob("codex-review-diff.*.patch"))
    leaked = after - before

    assert result.returncode == 3, (
        f"expected the no-common-ancestor refusal (exit 3), got {result.returncode}: "
        f"{result.stderr}"
    )
    assert not leaked, (
        f"a refused review left its diff temp file behind: {leaked} - this is "
        "the exact leak #1494 closes"
    )

    for f in leaked:
        f.unlink(missing_ok=True)


@requires_git
def test_a_successful_review_keeps_its_diff_file(tmp_path: Path) -> None:
    env = _env(tmp_path / "home")
    (tmp_path / "home").mkdir()

    upstream = tmp_path / "upstream.git"
    upstream.mkdir()
    assert _git("init", "-q", "--bare", cwd=upstream, env=env).returncode == 0

    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git("init", "-q", "-b", "main", cwd=repo, env=env).returncode == 0
    assert _git("remote", "add", "origin", str(upstream), cwd=repo, env=env).returncode == 0
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    assert _git("add", "-A", cwd=repo, env=env).returncode == 0
    assert _git("commit", "-qm", "base", cwd=repo, env=env).returncode == 0
    assert _git("push", "-q", "origin", "main", cwd=repo, env=env).returncode == 0
    # The bare repo's own HEAD still points at whatever init.defaultBranch was
    # BEFORE anything was pushed, which need not be "main" - and `git remote
    # show origin` (what the command parses "HEAD branch:" from) reads that
    # symbolic ref. Point it explicitly so BASE resolves to origin/main.
    assert _git(
        "symbolic-ref", "HEAD", "refs/heads/main", cwd=upstream, env=env
    ).returncode == 0

    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    assert _git("add", "-A", cwd=repo, env=env).returncode == 0
    assert _git("commit", "-qm", "my change", cwd=repo, env=env).returncode == 0

    before = set((Path("/tmp")).glob("codex-review-diff.*.patch"))
    result = _run_block(repo, env)
    after = set((Path("/tmp")).glob("codex-review-diff.*.patch"))
    created = after - before

    assert result.returncode == 0, (
        f"expected a clean run of the diff block, got {result.returncode}: "
        f"{result.stderr}"
    )
    assert len(created) == 1, (
        f"a successful run must leave exactly one diff temp file for the later "
        f"blocks to read and remove themselves - saw {created}. If this is "
        "empty, the trap-disarm regressed and the happy path now leaks "
        "nothing because it deletes its own output before anyone reads it."
    )

    for f in created:
        f.unlink(missing_ok=True)

"""`/cpp:update` Step 3.5 must survive a concurrent pull (issue #1263).

Step 3.5 decides whether the in-context copy of `/cpp:update` is stale after the
pull. It used to diff `ORIG_HEAD..HEAD`. `ORIG_HEAD` is per-repository, and in a
shared checkout another session pulls too - measured on 2026-09-23, two foreign
pulls landed while one `/cpp:update` was still running.

THE CASE THAT DISCRIMINATES: our pull A -> B changes update.md; a concurrent
pull B -> C does not, and leaves ORIG_HEAD = B. The old block then diffs B..C,
sees no change, and says the stale in-context steps are current. The block is
extracted from the document and executed, both as it stood before the fix (red)
and as it stands now.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude" / "commands" / "cpp" / "update.md"
SELF = ".claude/commands/cpp/update.md"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="bash and git are required to execute the block",
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, rel: str, body: str, msg: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", msg)
    return _git(repo, "rev-parse", "--short", "HEAD")


def _self_check_block(text: str) -> str:
    start = text.index("## Step 3.5")
    block = re.search(r"```bash\n(.*?)```", text[start:], re.S)
    assert block, "Step 3.5 has no bash block"
    return block.group(1)


def _shared_checkout_after_a_concurrent_pull(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "cpp"
    repo.mkdir()
    _git(repo, "init", "-q")
    a = _commit(repo, SELF, "v1\n", "A")
    b = _commit(repo, SELF, "v2 - our pull changed the command\n", "B")
    _commit(repo, "README.md", "unrelated\n", "C - a concurrent pull")
    # What the concurrent pull leaves behind: ORIG_HEAD names ITS start, B.
    _git(repo, "update-ref", "ORIG_HEAD", b)
    # Precondition: the command DID change since this run's start, A.
    assert _git(repo, "diff", "--name-only", a, "--", SELF) == SELF
    return repo, a


def _run(block: str, repo: Path, pre_pull: str) -> str:
    block = block.replace("<the SHA from Step 2's 'Current:' line>", pre_pull)
    return subprocess.run(
        ["bash", "-c", block + '\necho "SELF_CHANGED=$SELF_CHANGED"'],
        env={"CPP_DIR": str(repo), "PATH": os.environ.get("PATH", ""), "HOME": str(repo)},
        capture_output=True,
        text=True,
    ).stdout


def test_a_concurrent_pull_does_not_hide_a_change_to_the_command(tmp_path: Path) -> None:
    repo, a = _shared_checkout_after_a_concurrent_pull(tmp_path)
    out = _run(_self_check_block(DOC.read_text(encoding="utf-8")), repo, a)
    assert "SELF_CHANGED=yes" in out, out


def test_the_pre_fix_block_is_fooled_by_the_same_checkout(tmp_path: Path) -> None:
    """The red half, kept as a committed case: the ORIG_HEAD form says `no`."""
    pre_fix = _self_check_block(
        subprocess.run(
            ["git", "-C", str(ROOT), "show", "4deccd2:" + SELF],
            capture_output=True,
            text=True,
        ).stdout
        or pytest.skip("pre-fix commit 4deccd2 not available in this clone")
    )
    assert "ORIG_HEAD" in pre_fix
    repo, a = _shared_checkout_after_a_concurrent_pull(tmp_path)
    assert "SELF_CHANGED=no" in _run(pre_fix, repo, a)


def test_an_unchanged_command_still_reads_current(tmp_path: Path) -> None:
    repo = tmp_path / "cpp"
    repo.mkdir()
    _git(repo, "init", "-q")
    a = _commit(repo, SELF, "v1\n", "A")
    _commit(repo, "README.md", "other\n", "B")
    out = _run(_self_check_block(DOC.read_text(encoding="utf-8")), repo, a)
    assert "SELF_CHANGED=no" in out, out

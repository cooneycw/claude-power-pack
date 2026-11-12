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


def _env(home: Path) -> dict[str, str]:  # negative-fixture: allow PATH is isolation, not an absence
    return {
        "HOME": str(home), "PATH": ISOLATED_PATH,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
    }


# The block's temp file lives in /tmp, a directory every session and every
# other test on the host shares, and the template is a literal in the frozen
# command document. Comparing the directory before and after therefore reported
# a NEIGHBOUR's file as this run's leak (issue #1718, row 2). Instead the block
# is prefixed with a `mktemp` function that calls the real one and records the
# path it returned, so each test asserts on the one file its own run created.
_DIFF_FILE_PREFIX = "/tmp/codex-review-diff-patch."
_RECORDING_MKTEMP = (
    'mktemp() {\n'
    '    local _made\n'
    '    _made=$(command mktemp "$@") || return\n'
    '    printf \'%s\\n\' "$_made" >> "$CPP_TEST_MKTEMP_LOG"\n'
    '    printf \'%s\\n\' "$_made"\n'
    '}\n'
)


def _run_block(
    repo: Path, env: dict[str, str], script: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the diff block; returns (proc, the diff temp file THIS run created)."""
    if script is None:
        script = _extract_diff_block()
    log = repo.parent / "mktemp.log"
    log.write_text("", encoding="utf-8")
    proc = subprocess.run(
        ["bash", "-c", _RECORDING_MKTEMP + script], cwd=repo,
        env={**env, "CPP_TEST_MKTEMP_LOG": str(log)}, capture_output=True, text=True,
    )
    own = [ln for ln in log.read_text(encoding="utf-8").splitlines()
           if ln.startswith(_DIFF_FILE_PREFIX)]
    assert len(own) == 1, (
        f"the block was expected to create exactly one diff temp file, recorded {own}: "
        f"{proc.stderr}"
    )
    return proc, Path(own[0])


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


def _refusing_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A repository on which the block takes its FIRST refusal after the mktemp."""
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

    return repo, env


@requires_git
def test_a_refused_review_leaves_no_diff_file_behind(tmp_path: Path) -> None:
    repo, env = _refusing_repo(tmp_path)
    result, own = _run_block(repo, env)
    leaked = own.exists()
    own.unlink(missing_ok=True)

    assert result.returncode == 3, (
        f"expected the no-common-ancestor refusal (exit 3), got {result.returncode}: "
        f"{result.stderr}"
    )
    assert not leaked, (
        f"a refused review left its diff temp file behind: {own} - this is "
        "the exact leak #1494 closes"
    )


@requires_git
def test_the_refusal_check_sees_a_leak_when_the_trap_is_removed(tmp_path: Path) -> None:
    """The red case for the test above: without the trap, ITS file survives.

    The same refusal, run on the block with its `trap ... EXIT` line stripped,
    must leave the recorded file behind - otherwise "not leaked" above could be
    the recorder naming the wrong path rather than the trap doing its job.
    """
    repo, env = _refusing_repo(tmp_path)
    trap_line = "trap 'rm -f \"$DIFF_FILE\"' EXIT\n"
    block = _extract_diff_block()
    assert block.count(trap_line) == 1, "precondition: the block installs the trap once"
    result, own = _run_block(repo, env, block.replace(trap_line, ""))
    leaked = own.exists()
    own.unlink(missing_ok=True)

    assert result.returncode == 3, result.stderr
    assert leaked, f"with the trap stripped, the refused run must leave {own} behind"


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

    result, own = _run_block(repo, env)
    kept = own.exists()
    own.unlink(missing_ok=True)

    assert result.returncode == 0, (
        f"expected a clean run of the diff block, got {result.returncode}: "
        f"{result.stderr}"
    )
    assert kept, (
        f"a successful run must leave its diff temp file ({own}) for the later "
        "blocks to read and remove themselves. It is gone, so the trap-disarm "
        "regressed and the happy path now deletes its own output before anyone "
        "reads it."
    )

"""Issue #1262: ELI5 Section B asked only REMOTE-facing staleness questions.

`git log --since`, `gh pr list` and `gh issue list` cannot see a sibling
worktree on this host whose unpushed commits already touch the issue's paths -
the #597 duplicated-work hazard, arriving before anything reaches GitHub. The
vendored core is byte-identical to cooneycw/eli5-gate and is not edited here, so
the check lives in a CPP-owned section OUTSIDE the markers, like the #859/#965
integration sections. Run against 47ddc6c and FAILED there.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELI5 = ROOT / ".claude" / "commands" / "flow" / "eli5.md"


def _split() -> tuple[str, str]:
    text = ELI5.read_text(encoding="utf-8")
    end = text.index("<!-- eli5-core:end")
    return text[:end], text[end:]


def test_section_B_also_checks_sibling_local_worktrees() -> None:
    _core, after = _split()
    assert "git worktree list" in after, (
        "the local-sibling staleness check is missing from eli5.md's CPP-owned sections"
    )
    assert "--not --remotes" in after, (
        "the check must look for UNPUSHED commits, which no remote-facing query can see"
    )


def test_the_check_is_outside_the_vendored_core() -> None:
    core, _after = _split()
    assert "git worktree list" not in core, (
        "the vendored eli5-gate core must stay byte-identical upstream; add CPP "
        "behaviour in a CPP-owned section, not inside the markers"
    )


import re
import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None,
                    reason="runs the documented snippet against a real repository")
def test_the_documented_scan_FINDS_an_unpushed_sibling_even_with_a_space_in_its_path(
    tmp_path: Path,
) -> None:
    """Counter-model review: `for wt in $(...)` split a path on whitespace, and
    the suppressed errors then read as "no commits". The snippet is run, not
    grepped - a document test can only say the words are present."""
    _core, after = _split()
    block = re.search(r"```bash\n(# Every worktree.*?)```", after, re.S)
    assert block, "the documented scan block is missing"
    script = block.group(1).replace("<relevant/paths>", ".")

    def git(cwd: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t",
                        *args], check=True, capture_output=True)

    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    main = tmp_path / "main"
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    git(main, "commit", "-q", "--allow-empty", "-m", "base")
    git(main, "remote", "add", "origin", str(remote))
    git(main, "push", "-q", "origin", "HEAD:refs/heads/main")
    git(main, "fetch", "-q", "origin")
    sibling = tmp_path / "issue 1262 sibling"
    git(main, "worktree", "add", "-q", "-b", "side", str(sibling))
    (sibling / "work.txt").write_text("unpushed\n", encoding="utf-8")
    git(sibling, "add", "work.txt")
    git(sibling, "commit", "-q", "-m", "only here")

    out = subprocess.run(["bash", "-c", script], cwd=main, capture_output=True, text=True)
    assert f"{sibling}: " in out.stdout and "only here" in out.stdout, out.stdout + out.stderr


@pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None,
                    reason="runs the documented snippet")
def test_the_documented_scan_REPORTS_a_failed_worktree_listing(tmp_path: Path) -> None:
    """Counter-model review pass 2: outside any repository the listing fails, and
    the scan must say so rather than print nothing, which reads as "none"."""
    _core, after = _split()
    block = re.search(r"```bash\n(# Every worktree.*?)```", after, re.S)
    assert block
    script = block.group(1).replace("<relevant/paths>", ".")
    probe = subprocess.run(["git", "-C", str(tmp_path), "rev-parse"], capture_output=True)
    assert probe.returncode != 0, "precondition: tmp_path must not be inside a repository"
    out = subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert "UNREADABLE" in out.stdout, out.stdout + out.stderr

"""`/codex:code_review` measures whether its reviewer can read files (#1261).

In a Kyle session container codex's sandbox cannot start (bubblewrap has no user
namespace), so every tool call the reviewer makes fails - and the review still
succeeds on the diff alone. The prompt offered the repository's files, nothing
reported that the offer was void, and a diff-only review read exactly like a full
one.

Step 3 now probes the sandbox (`codex sandbox`, no model call) and emits
`CODEX_REVIEW_SCOPE: full | diff-only | unverified`, tells the reviewer when it
cannot open files, and takes a caller-supplied `CODEX_REVIEW_SANDBOX` (the #1285
shape) - refusing any value other than read-only or danger-full-access.

TWO-SIDED, by a stub `codex` whose sandbox probe fails or succeeds:
RED   probe fails   -> diff-only, and the reviewer prompt says it cannot open files
GREEN probe works   -> full, and the prompt offers the files
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
COMMAND = REPO / ".claude" / "commands" / "codex" / "code_review.md"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

STUB = """#!/bin/sh
# Stub codex for #1261. `sandbox --help` succeeds unless STUB_NO_SANDBOX is set;
# `sandbox ... -- true` exits STUB_SANDBOX_RC; `exec` records its args and
# writes a clean findings report where --output-last-message points.
if [ "$1" = sandbox ]; then
    if [ "$2" = --help ]; then [ -n "$STUB_NO_SANDBOX" ] && exit 2; exit 0; fi
    # STUB_SANDBOX_RC: the sandbox cannot start. STUB_READ_RC: it starts but a
    # repository read is denied. Otherwise the command after `--` REALLY runs,
    # so a probe that names the wrong path fails exactly as it would for real.
    [ "${STUB_SANDBOX_RC:-0}" != 0 ] && exit "$STUB_SANDBOX_RC"
    for a in "$@"; do [ "$a" = head ] && [ -n "$STUB_READ_RC" ] && exit "$STUB_READ_RC"; done
    while [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done
    [ "$1" = -- ] && shift
    "$@"
    exit $?
fi
if [ "$1" = exec ]; then
    out=""
    prev=""
    for a in "$@"; do
        [ "$prev" = --output-last-message ] && out="$a"
        prev="$a"
    done
    printf '%s\\n' "$@" > "$STUB_ARGS"
    cat > /dev/null
    printf '## Findings\\n\\nNone - no defects found.\\n' > "$out"
    exit 0
fi
exit 1
"""


def _step3_block() -> str:
    text = COMMAND.read_text(encoding="utf-8")
    section = text[text.index("### Step 3: Run the review"):text.index("### Step 4:")]
    m = re.search(r"```bash\n(.*?)```", section, re.S)
    assert m, "no bash block in Step 3"
    return m.group(1)


def _run(tmp_path: Path, tracked: bool = True, subdir: bool = False, delete_first: bool = False,
         **extra: str) -> tuple[subprocess.CompletedProcess[str], str]:
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "codex"
    stub.write_text(STUB, encoding="utf-8")
    stub.chmod(0o755)
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    # negative-fixture: allow PATH is isolation plus the stub, not an absence
    base = {"HOME": str(home), "PATH": f"{stub_dir}:{ISOLATED_PATH}"}
    genv = {**os.environ, **base, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=work, env=genv, check=True, capture_output=True)
    if tracked:
        (work / "a_first.txt").write_text("x\n", encoding="utf-8")
        (work / "sub").mkdir(exist_ok=True)
        (work / "sub" / "inner.txt").write_text("y\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=work, env=genv, check=True, capture_output=True)
        if delete_first:
            (work / "a_first.txt").unlink()
    diff = tmp_path / "d.patch"
    diff.write_text("", encoding="utf-8")
    args_file = tmp_path / "args.txt"
    env = {**os.environ, **base, "DIFF_FILE": str(diff), "STUB_ARGS": str(args_file), **extra}
    for k in ("CODEX_REVIEW_SANDBOX",):
        if k not in extra:
            env.pop(k, None)
    proc = subprocess.run(["bash", "-c", _step3_block() + '\necho "EXIT=$CODEX_EXIT"'],
                          cwd=work / "sub" if subdir else work, env=env, capture_output=True, text=True)
    args = args_file.read_text(encoding="utf-8") if args_file.exists() else ""
    return proc, args


@requires_git
def test_a_sandbox_that_cannot_start_reports_diff_only(tmp_path: Path) -> None:
    proc, args = _run(tmp_path, STUB_SANDBOX_RC="101")
    assert "CODEX_REVIEW_SCOPE: diff-only" in proc.stdout, proc.stdout + proc.stderr
    assert "You CANNOT open files" in args
    assert "--sandbox\nread-only" in args


@requires_git
def test_a_working_sandbox_reports_full(tmp_path: Path) -> None:
    proc, args = _run(tmp_path, STUB_SANDBOX_RC="0")
    assert "CODEX_REVIEW_SCOPE: full" in proc.stdout, proc.stdout + proc.stderr
    assert "You may also open the files" in args
    assert "CANNOT" not in args


@requires_git
def test_a_sandbox_that_starts_but_cannot_read_the_repo_is_not_full(tmp_path: Path) -> None:
    """Counter-model finding: startup alone must not claim repository access."""
    proc, args = _run(tmp_path, STUB_SANDBOX_RC="0", STUB_READ_RC="1")
    assert "CODEX_REVIEW_SCOPE: diff-only" in proc.stdout, proc.stdout + proc.stderr


@requires_git
def test_a_subdirectory_invocation_keeps_the_root_verdict(tmp_path: Path) -> None:
    """Re-review finding: `git ls-files` is cwd-relative; the probe read must not be."""
    proc, _ = _run(tmp_path, subdir=True, STUB_SANDBOX_RC="0")
    assert "CODEX_REVIEW_SCOPE: full" in proc.stdout, proc.stdout + proc.stderr


@requires_git
def test_a_deleted_first_tracked_file_is_not_a_failed_read(tmp_path: Path) -> None:
    proc, _ = _run(tmp_path, delete_first=True, STUB_SANDBOX_RC="0")
    assert "CODEX_REVIEW_SCOPE: full" in proc.stdout, proc.stdout + proc.stderr


@requires_git
def test_nothing_tracked_to_read_is_unverified(tmp_path: Path) -> None:
    proc, _ = _run(tmp_path, tracked=False, STUB_SANDBOX_RC="0")
    assert "CODEX_REVIEW_SCOPE: unverified" in proc.stdout, proc.stdout + proc.stderr


@requires_git
def test_no_probe_available_is_unverified_not_full(tmp_path: Path) -> None:
    proc, args = _run(tmp_path, STUB_NO_SANDBOX="1")
    assert "CODEX_REVIEW_SCOPE: unverified" in proc.stdout, proc.stdout + proc.stderr
    assert "may or may not work" in args


@requires_git
def test_a_caller_supplied_full_access_is_honoured_and_needs_no_probe(tmp_path: Path) -> None:
    proc, args = _run(tmp_path, CODEX_REVIEW_SANDBOX="danger-full-access", STUB_SANDBOX_RC="101")
    assert "CODEX_REVIEW_SCOPE: full" in proc.stdout, proc.stdout + proc.stderr
    assert "--sandbox\ndanger-full-access" in args


@requires_git
def test_any_other_sandbox_value_is_refused_not_defaulted(tmp_path: Path) -> None:
    proc, args = _run(tmp_path, CODEX_REVIEW_SANDBOX="workspace-write")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "CODEX_REVIEW_SANDBOX='workspace-write'" in proc.stderr
    assert args == "", "codex exec must not run on a refused sandbox value"


def test_the_sandbox_flag_is_no_longer_hardcoded() -> None:
    assert "--sandbox read-only \\" not in _step3_block()

"""A patch over Codex's input limit takes a route of its own (issue #1714).

Codex refuses stdin over 1,048,576 characters. The review run then exited 1
with an empty findings file, and the procedure recorded "reviewer unavailable"
for a reviewer that was available. Step 3 now measures the patch first:

- over the limit (less a margin for the prompt) at scope `full`: the patch is
  not piped. stdin carries its stat, the prompt tells the reviewer to read each
  file from the repository and to list what it read, and the list is CHECKED
  against the patch's own file list. A file not listed is named as not read
  and the review is marked partial;
- over the limit at any other scope: `blocked`, exit 1, before any model call.

These tests run the document's own Step 3 block. `codex` is a stub: it records
its prompt and how many bytes arrived on stdin, and writes whatever findings
text the test gives it. So nothing here shows what a real reviewer does when
told to fetch the diff itself; that is one recorded observation, not a test.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.isolated_env import ISOLATED_PATH
from tests.test_code_review_sandbox_scope import _step3_block

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

LIMIT = 1048576
MARGIN = 65536
THRESHOLD = LIMIT - MARGIN  # a patch of exactly this many characters is still piped

STUB = """#!/bin/sh
# Stub codex (#1714). The sandbox probe behaves as in the #1261 stub; `exec`
# records the prompt and the stdin size, and writes $STUB_FINDINGS as its report.
if [ "$1" = sandbox ]; then
    if [ "$2" = --help ]; then [ -n "$STUB_NO_SANDBOX" ] && exit 2; exit 0; fi
    [ "${STUB_SANDBOX_RC:-0}" != 0 ] && exit "$STUB_SANDBOX_RC"
    while [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done
    [ "$1" = -- ] && shift
    "$@"
    exit $?
fi
if [ "$1" = exec ]; then
    out=""; prev=""
    for a in "$@"; do [ "$prev" = --output-last-message ] && out="$a"; prev="$a"; done
    printf '%s\\n' "$@" > "$STUB_ARGS"
    wc -c > "$STUB_STDIN_BYTES"
    cat "$STUB_FINDINGS" > "$out"
    exit 0
fi
exit 1
"""

CLEAN = "## Findings\n\nNone - no defects found.\n\n## Red cases\n\n- none\n"


def _run(tmp_path: Path, patch_chars: int, findings: str = CLEAN, **extra: str) -> dict[str, str]:
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    for name, body in (("codex", STUB), ("curl", "#!/bin/sh\nexit 7\n")):
        (stub_dir / name).write_text(body, encoding="utf-8")
        (stub_dir / name).chmod(0o755)
    work = tmp_path / "work"
    home = tmp_path / "home"
    work.mkdir()
    home.mkdir()
    base = {"HOME": str(home), "PATH": f"{stub_dir}:{ISOLATED_PATH}"}
    genv = {**os.environ, **base, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=work, env=genv, check=True, capture_output=True)
    for name in ("alpha.txt", "beta.txt"):
        (work / name).write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=work, env=genv, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=work, env=genv, check=True, capture_output=True)
    merge_base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=work, env=genv, check=True,
                                capture_output=True, text=True).stdout.strip()
    for name in ("alpha.txt", "beta.txt"):  # the change under review touches exactly these two
        (work / name).write_text("changed\n", encoding="utf-8")
    diff = tmp_path / "d.patch"
    diff.write_text("x" * patch_chars, encoding="utf-8")
    findings_file = tmp_path / "findings.txt"
    findings_file.write_text(findings, encoding="utf-8")
    args_file = tmp_path / "args.txt"
    stdin_file = tmp_path / "stdin-bytes.txt"
    env = {**os.environ, **base, "DIFF_FILE": str(diff), "MERGE_BASE": merge_base, "STUB_ARGS": str(args_file),
           "STUB_STDIN_BYTES": str(stdin_file), "STUB_FINDINGS": str(findings_file), **extra}
    env.pop("CODEX_REVIEW_SANDBOX", None)
    proc = subprocess.run(["bash", "-c", _step3_block() + '\necho "EXIT=$CODEX_EXIT"'],
                          cwd=work, env=env, capture_output=True, text=True)
    return {
        "out": proc.stdout,
        "all": proc.stdout + proc.stderr,
        "rc": str(proc.returncode),
        "prompt": args_file.read_text(encoding="utf-8") if args_file.exists() else "",
        "stdin_bytes": stdin_file.read_text(encoding="utf-8").strip() if stdin_file.exists() else "",
        "diff_exists": "yes" if diff.exists() else "no",
    }


@pytest.mark.parametrize(
    ("patch_chars", "route"),
    [
        (THRESHOLD - 1, "stdin"),
        (THRESHOLD, "stdin"),          # the margin boundary: exactly at it is still piped
        (THRESHOLD + 1, "repository"),
        (LIMIT - 1, "repository"),
        (LIMIT, "repository"),
        (LIMIT + 1, "repository"),
    ],
)
def test_the_route_is_chosen_by_the_measured_size(tmp_path: Path, patch_chars: int, route: str) -> None:
    result = _run(tmp_path, patch_chars)
    assert f"CODEX_REVIEW_INPUT: {route}" in result["out"], result["all"]
    assert "CODEX_REVIEW_SCOPE: full" in result["out"]  # the precondition for the repository route
    if route == "stdin":
        assert int(result["stdin_bytes"]) == patch_chars, "the patch itself was not what was piped"
        assert "The unified diff is provided on stdin." in result["prompt"]
        assert "CODEX_REVIEW_COVERAGE" not in result["out"]
    else:
        assert int(result["stdin_bytes"]) < 4096, "an oversized patch was still piped"
        assert "too large to send" in result["prompt"] and "FILE READ: <path>" in result["prompt"]
        assert "The unified diff is provided on stdin." not in result["prompt"]


def test_a_reviewer_that_lists_every_file_is_complete(tmp_path: Path) -> None:
    findings = CLEAN + "\nFILE READ: alpha.txt\nFILE READ: beta.txt\n"
    result = _run(tmp_path, LIMIT + 1, findings)
    assert "CODEX_REVIEW_COVERAGE: complete" in result["out"], result["all"]
    assert "CODEX_REVIEW_NOT_READ" not in result["out"]


def test_a_reviewer_that_lists_nothing_cannot_return_an_ordinary_clean_review(tmp_path: Path) -> None:
    """The #1015 shape: "no findings" from a reviewer that never fetched the diff."""
    result = _run(tmp_path, LIMIT + 1, CLEAN)
    assert "CODEX_REVIEW_NOT_READ: alpha.txt" in result["out"], result["all"]
    assert "CODEX_REVIEW_NOT_READ: beta.txt" in result["out"]
    assert "CODEX_REVIEW_COVERAGE: PARTIAL - 2 file(s) not read" in result["out"]


def test_a_reviewer_that_skips_one_file_is_partial_and_the_file_is_named(tmp_path: Path) -> None:
    result = _run(tmp_path, LIMIT + 1, CLEAN + "\nFILE READ: alpha.txt\n")
    assert "CODEX_REVIEW_NOT_READ: beta.txt" in result["out"], result["all"]
    assert "CODEX_REVIEW_NOT_READ: alpha.txt" not in result["out"]
    assert "CODEX_REVIEW_COVERAGE: PARTIAL - 1 file(s) not read" in result["out"]


def test_a_near_match_is_not_a_read(tmp_path: Path) -> None:
    """Whole-line match: a longer path, or the name inside a sentence, does not count."""
    findings = CLEAN + "\nFILE READ: alpha.txt.bak\nI considered beta.txt carefully.\n"
    result = _run(tmp_path, LIMIT + 1, findings)
    assert "CODEX_REVIEW_COVERAGE: PARTIAL - 2 file(s) not read" in result["out"], result["all"]


@pytest.mark.parametrize(
    ("scope", "extra"),
    [("diff-only", {"STUB_SANDBOX_RC": "101"}), ("unverified", {"STUB_NO_SANDBOX": "1"})],
)
def test_an_oversized_patch_the_reviewer_cannot_fetch_is_blocked_before_any_model_call(
    tmp_path: Path, scope: str, extra: dict[str, str]
) -> None:
    result = _run(tmp_path, LIMIT + 1, **extra)
    assert f"CODEX_REVIEW_SCOPE: {scope}" in result["out"], result["all"]  # the precondition
    assert result["rc"] == "1"
    assert f"CODEX_REVIEW: blocked (patch too large: {LIMIT + 1} characters; scope {scope}" in result["all"]
    assert result["prompt"] == "", "the reviewer was called for a patch it could not be given"
    assert result["diff_exists"] == "no", "the patch file was left behind by the refusal"


@pytest.mark.parametrize("extra", [{}, {"STUB_SANDBOX_RC": "101"}, {"STUB_NO_SANDBOX": "1"}])
def test_no_over_limit_path_says_unavailable(tmp_path: Path, extra: dict[str, str]) -> None:
    """`unavailable` is the word the flow records as a skipped review. A too-large patch is never that."""
    result = _run(tmp_path, LIMIT + 1, **extra)
    assert "unavailable" not in result["all"].lower(), result["all"]


def test_the_same_scopes_under_the_limit_still_run(tmp_path: Path) -> None:
    """Negative control for the block: it is the SIZE that blocks, not the scope."""
    result = _run(tmp_path, 100, STUB_SANDBOX_RC="101")
    assert "CODEX_REVIEW_SCOPE: diff-only" in result["out"] and "CODEX_REVIEW_INPUT: stdin" in result["out"]
    assert result["prompt"] != ""


def test_the_limit_is_one_named_constant_with_its_source() -> None:
    block = _step3_block()
    assert f"REVIEW_INPUT_LIMIT={LIMIT}" in block and f"REVIEW_INPUT_MARGIN={MARGIN}" in block
    assert block.count(str(LIMIT)) == 1, "the limit is written more than once in the executable block"
    assert "input_too_large" in block and "#1670" in block, "the constant no longer names where it came from"

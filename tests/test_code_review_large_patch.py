"""A patch over Codex's input limit is blocked, never "reviewer unavailable" (issue #1714).

Codex refuses stdin over 1,048,576 characters. The review run then exited 1
with an empty findings file, and the procedure recorded "reviewer unavailable"
for a reviewer that was available: a skipped review the finish gate accepts.

Step 3 now measures the patch FIRST, in bytes, against that limit less a margin
for the prompt. Over it, at every scope, the run is `blocked`: exit 1, before
the sandbox probe and before any model call, with a message naming the size,
the limit and what to do. Nothing is piped and no transcript exists, so the
steps that would record a skip are never reached with a too-large patch.

A first design sent the reviewer to read the diff from the repository at scope
`full` and checked which files it said it read. Review found ten defects in it
(the worst: an empty file list read as full coverage) and it was withdrawn; it
is issue #1769's to build.

These tests run the document's own Step 3 block. `codex` is a stub that records
every call made to it.
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
THRESHOLD = LIMIT - MARGIN  # a patch of exactly this many bytes is still piped

STUB = """#!/bin/sh
# Stub codex (#1714): records EVERY call, then behaves like the #1261 stub.
printf '%s\\n' "$1" >> "$STUB_CALLS"
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
    wc -c > "$STUB_STDIN_BYTES"
    printf '## Findings\\n\\nNone - no defects found.\\n' > "$out"
    exit 0
fi
exit 1
"""

SCOPES = {
    "full": {},
    "diff-only": {"STUB_SANDBOX_RC": "101"},
    "unverified": {"STUB_NO_SANDBOX": "1"},
}


def _run(tmp_path: Path, patch: bytes | None, **extra: str) -> dict[str, str]:
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    for name, text in (("codex", STUB), ("curl", "#!/bin/sh\nexit 7\n")):
        (stub_dir / name).write_text(text, encoding="utf-8")
        (stub_dir / name).chmod(0o755)
    work = tmp_path / "work"
    home = tmp_path / "home"
    work.mkdir()
    home.mkdir()
    # negative-fixture: allow PATH is isolation plus the stub, not an absence
    base = {"HOME": str(home), "PATH": f"{stub_dir}:{ISOLATED_PATH}"}
    genv = {**os.environ, **base}
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=work, env=genv, check=True, capture_output=True)
    (work / "tracked.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=work, env=genv, check=True, capture_output=True)
    diff = tmp_path / "d.patch"
    if patch is not None:
        diff.write_bytes(patch)
    calls = tmp_path / "calls.txt"
    calls.write_text("", encoding="utf-8")
    stdin_file = tmp_path / "stdin-bytes.txt"
    env = {**os.environ, **base, "DIFF_FILE": str(diff), "STUB_CALLS": str(calls),
           "STUB_STDIN_BYTES": str(stdin_file), **extra}
    env.pop("CODEX_REVIEW_SANDBOX", None)
    proc = subprocess.run(["bash", "-c", _step3_block() + '\necho "EXIT=$CODEX_EXIT"'],
                          cwd=work, env=env, capture_output=True, text=True)
    return {
        "out": proc.stdout,
        "all": proc.stdout + proc.stderr,
        "rc": str(proc.returncode),
        "calls": " ".join(calls.read_text(encoding="utf-8").split()),
        "stdin_bytes": stdin_file.read_text(encoding="utf-8").strip() if stdin_file.exists() else "",
        "diff_exists": "yes" if diff.exists() else "no",
    }


@pytest.mark.parametrize("scope", sorted(SCOPES))
@pytest.mark.parametrize("size", [THRESHOLD + 1, LIMIT - 1, LIMIT, LIMIT + 1])
def test_a_patch_over_the_threshold_is_blocked_at_every_scope(tmp_path: Path, scope: str, size: int) -> None:
    result = _run(tmp_path, b"x" * size, **SCOPES[scope])
    assert result["rc"] == "1", result["all"]
    assert f"CODEX_REVIEW: blocked (patch too large: {size} bytes; limit {LIMIT} less {MARGIN}" in result["all"]
    assert "Split the change" in result["all"] and "commit separately" in result["all"]
    assert result["calls"] == "", f"codex was called for a patch that cannot be sent: {result['calls']}"
    assert "CODEX_REVIEW_SCOPE" not in result["all"], "the block came after the sandbox probe, not before it"
    assert result["diff_exists"] == "no", "the patch file was left behind by the refusal"


@pytest.mark.parametrize("scope", sorted(SCOPES))
@pytest.mark.parametrize("size", [0, 100, THRESHOLD - 1, THRESHOLD])
def test_a_patch_at_or_under_the_threshold_is_piped_at_every_scope(tmp_path: Path, scope: str, size: int) -> None:
    """The other verdict: it is the size that blocks, and exactly at the margin boundary is still sent."""
    result = _run(tmp_path, b"x" * size, **SCOPES[scope])
    assert "blocked" not in result["all"], result["all"]
    assert f"CODEX_REVIEW_SCOPE: {scope}" in result["out"]
    assert result["calls"].endswith("exec"), "the review did not run"
    assert int(result["stdin_bytes"]) == size, "the patch itself was not what was piped"


@pytest.mark.parametrize("scope", sorted(SCOPES))
def test_no_blocked_path_says_unavailable_or_skipped(tmp_path: Path, scope: str) -> None:
    """`unavailable` is the word the flow records as a skipped review. A too-large patch is never that."""
    result = _run(tmp_path, b"x" * (LIMIT + 1), **SCOPES[scope])
    lowered = result["all"].lower()
    assert "unavailable" not in lowered and "skipped" not in lowered, result["all"]


def test_the_size_is_measured_in_bytes_not_characters(tmp_path: Path) -> None:
    """Multibyte text: fewer characters than the threshold, more bytes. It errs toward blocking."""
    patch = ("é" * (THRESHOLD // 2 + 10)).encode("utf-8")
    assert len(patch.decode("utf-8")) < THRESHOLD < len(patch)  # the precondition
    result = _run(tmp_path, patch)
    assert result["rc"] == "1" and f"patch too large: {len(patch)} bytes" in result["all"], result["all"]


def test_a_patch_whose_size_cannot_be_read_is_blocked_not_sent(tmp_path: Path) -> None:
    result = _run(tmp_path, None)
    assert result["diff_exists"] == "no"  # the precondition: there is no patch file to measure
    assert result["rc"] == "1" and "patch too large: unknown bytes" in result["all"], result["all"]
    assert result["calls"] == ""


def test_the_limit_is_one_named_constant_with_its_source() -> None:
    block = _step3_block()
    assert f"REVIEW_INPUT_LIMIT={LIMIT}" in block and f"REVIEW_INPUT_MARGIN={MARGIN}" in block
    assert block.count(str(LIMIT)) == 1, "the limit is written more than once in the executable block"
    assert "input_too_large" in block and "#1670" in block and "BYTES" in block


def test_the_withdrawn_repository_route_left_nothing_behind() -> None:
    """No input-route marker, no FILE READ protocol, no coverage check: only the blocked line is new."""
    block = _step3_block()
    for leftover in ("CODEX_REVIEW_INPUT", "FILE READ", "CODEX_REVIEW_COVERAGE", "CODEX_REVIEW_NOT_READ", "INPUT_LINE"):
        assert leftover not in block, f"{leftover} is still in Step 3"
    assert "The unified diff is provided on stdin." in block

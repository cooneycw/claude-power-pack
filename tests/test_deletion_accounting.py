"""Tests for scripts/deletion-accounting.sh - pre-push deletion accounting (issue #1031).

THE SUBJECT IS AN EXTRACTOR, so every test here is written against the rule that
a broken extractor's zeros look exactly like real ones. Three consequences shape
the file:

* The gate's count is measured against ``git diff --numstat`` - a number git
  derives by a different route entirely - rather than against a number this file
  wrote down. A parser checked only against its author's expectations agrees with
  the author, not with git.
* The retired ``^-[^-]`` form is EXECUTED here, not described. Its blindness is
  the reason the gate exists, and a described blindness is a claim about what
  someone believed in 2026-09; an executed one is a claim about the code.
* Both directions are asserted. A gate that reported every diff as deleting
  something would pass every blindness test in this file and be useless, so the
  additions-only and same-count cases are as load-bearing as the blind-spot ones.

The one-liner forms under test, for the reader who meets them in the wild:

    git diff "$BASE" | grep -E '^-[^-]' | sort | uniq -c          # retired: blind
    git diff "$BASE" | grep -E '^-' | grep -v '^---' | sort | uniq -c   # better, still blind to `---`
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deletion-accounting.sh"
ANCHOR = ROOT / "controls" / "deletion-accounting" / "anchors" / "0000000-blind-caret-dash.sh"

# The gate shells out to `git` in its `--base` lane, and every test here reaches
# it through `bash`. The Woodpecker `validate` step runs in
# `uv:python3.11-bookworm-slim`, which ships bash but NOT git.
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=120, check=False
    )


def contract(out: str) -> dict[str, str]:
    found = {}
    for line in out.splitlines():
        match = re.match(r"^(DELETION_ACCOUNTING_[A-Z]+): (.*)$", line)
        if match:
            found[match.group(1)] = match.group(2)
    return found


def write_diff(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


# --- the retired form, executed ------------------------------------------- #

def blind_count(diff_text: str) -> int:
    """The retired check: `grep -E '^-[^-]'`."""
    return sum(1 for line in diff_text.splitlines() if re.match(r"^-[^-]", line))


def one_liner_count(diff_text: str) -> int:
    """The corrected one-liner from the issue: `grep -E '^-' | grep -v '^---'`."""
    return sum(
        1
        for line in diff_text.splitlines()
        if line.startswith("-") and not line.startswith("---")
    )


# A unified diff's CONTEXT LINES BEGIN WITH A SPACE, and a blank context line is
# therefore a line containing exactly one space. Written as a triple-quoted
# literal, that trips ruff's W293 - and "fixing" it would silently change the
# fixture away from what git actually emits. The lines are joined from a list so
# the significant space is explicit and cannot be tidied away by a formatter.
BLANK = " "


def diff(*lines: str) -> str:
    return "\n".join(lines) + "\n"


BLINDSPOT_DIFF = diff(
    "diff --git a/docs/example.md b/docs/example.md",
    "--- a/docs/example.md",
    "+++ b/docs/example.md",
    "@@ -1,5 +1,3 @@",
    " # Example",
    BLANK,
    "-- a deleted guidance bullet",
    "-",
    " Trailing text.",
)

DELETED_RULE_DIFF = diff(
    "diff --git a/docs/rule.md b/docs/rule.md",
    "--- a/docs/rule.md",
    "+++ b/docs/rule.md",
    "@@ -1,4 +1,3 @@",
    " # Rule",
    BLANK,
    "----",
    " After the break.",
)

ORDINARY_DIFF = diff(
    "diff --git a/src/app.py b/src/app.py",
    "--- a/src/app.py",
    "+++ b/src/app.py",
    "@@ -1,4 +1,2 @@",
    " import os",
    "-x = 1",
    "-y = 2",
    " z = 3",
)

ADDITIONS_ONLY_DIFF = diff(
    "diff --git a/docs/example.md b/docs/example.md",
    "--- a/docs/example.md",
    "+++ b/docs/example.md",
    "@@ -1,2 +1,4 @@",
    " # Example",
    "+- a new bullet",
    "+",
    " Trailing text.",
)


def test_the_retired_form_really_is_blind_to_bullets_and_blank_lines(tmp_path: Path) -> None:
    """RED, executed: 2 deletions, and `^-[^-]` sees none of them."""
    assert blind_count(BLINDSPOT_DIFF) == 0, "the premise of this whole change"

    result = run("--diff-file", str(write_diff(tmp_path, "b.diff", BLINDSPOT_DIFF)), "--top", "0")
    found = contract(result.stdout)
    assert result.returncode == 1, result.stdout
    assert found["DELETION_ACCOUNTING_LINES"] == "2"
    assert found["DELETION_ACCOUNTING_BLINDSPOT"] == "2"
    assert "DELETION_ACCOUNTING_FINDING: 2 deleted line" in result.stdout


def test_the_issues_own_corrected_one_liner_still_misses_a_deleted_rule(tmp_path: Path) -> None:
    """The residual measured on this branch, pinned so the fix is not undone.

    A deleted line whose CONTENT is `---` renders as `----`, which `grep -v
    '^---'` throws away with the file headers. Both one-liners report 0; the
    gate reports 1. This is why the gate parses hunks instead of matching text.
    """
    assert blind_count(DELETED_RULE_DIFF) == 0
    assert one_liner_count(DELETED_RULE_DIFF) == 0, (
        "if this ever becomes 1 the one-liner was fixed upstream and the doc should say so"
    )

    result = run("--diff-file", str(write_diff(tmp_path, "r.diff", DELETED_RULE_DIFF)), "--top", "0")
    assert result.returncode == 1, result.stdout
    assert contract(result.stdout)["DELETION_ACCOUNTING_LINES"] == "1"


def test_ordinary_deletions_are_not_over_counted(tmp_path: Path) -> None:
    """GREEN: where the old forms CAN see, the gate agrees with them exactly.

    The issue names this as the second half of its negative control - the fix
    must be shown not to over-count. Without it, a gate that counted every line
    of the diff would pass every blindness test above.
    """
    assert blind_count(ORDINARY_DIFF) == 2
    assert one_liner_count(ORDINARY_DIFF) == 2

    result = run("--diff-file", str(write_diff(tmp_path, "o.diff", ORDINARY_DIFF)), "--top", "0")
    assert result.returncode == 1, result.stdout
    assert contract(result.stdout)["DELETION_ACCOUNTING_LINES"] == "2"
    assert contract(result.stdout)["DELETION_ACCOUNTING_BLINDSPOT"] == "0"


def test_a_diff_that_deletes_nothing_exits_clean(tmp_path: Path) -> None:
    result = run("--diff-file", str(write_diff(tmp_path, "a.diff", ADDITIONS_ONLY_DIFF)), "--top", "0")
    assert result.returncode == 0, result.stdout
    found = contract(result.stdout)
    assert found["DELETION_ACCOUNTING_LINES"] == "0"
    assert found["DELETION_ACCOUNTING_FILES"] == "0"
    assert "DELETION_ACCOUNTING_FINDING" not in result.stdout


# --- the parser, measured against git rather than against this file -------- #

def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=120, check=True
    )
    return out.stdout


def build_repo(tmp_path: Path) -> tuple[Path, str]:
    """A repo whose second commit deletes bullets, blank lines, a `---` and code."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    (repo / "doc.md").write_text(
        "---\ntitle: Doc\n---\n\n# Doc\n\n- rule one\n- rule two\n\n---\n\nEnd.\n", encoding="utf-8"
    )
    (repo / "app.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    (repo / "keep.txt").write_text("untouched\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD").strip()

    (repo / "doc.md").write_text("---\ntitle: Doc\n---\n\n# Doc\n\n- rule one\n\nEnd.\n", encoding="utf-8")
    (repo / "app.py").write_text("a = 1\nc = 3\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "change")
    return repo, base


def numstat_totals(repo: Path, base: str) -> tuple[int, int]:
    deleted = files = 0
    for line in git(repo, "diff", base, "--numstat").splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[1].isdigit() and int(parts[1]) > 0:
            deleted += int(parts[1])
            files += 1
    return deleted, files


def test_the_count_agrees_with_git_numstat(tmp_path: Path) -> None:
    """POSITIVE CONTROL for the extractor: git derives the same number another way.

    `--numstat` is produced by git's own diff machinery, not by reading the
    textual patch, so agreement between the two is evidence about the parser
    rather than about this file's arithmetic. The repo deliberately holds every
    shape the one-liners trip on: front-matter delimiters that must NOT count
    (they survive as context), a deleted `---`, a deleted bullet, a deleted
    blank line, and ordinary code.
    """
    repo, base = build_repo(tmp_path)
    expected_lines, expected_files = numstat_totals(repo, base)
    assert expected_lines > 0 and expected_files > 0, "fixture deletes nothing - it proves nothing"

    result = run("--base", base, "--repo", str(repo), "--top", "0")
    found = contract(result.stdout)
    assert result.returncode == 1, result.stdout
    assert int(found["DELETION_ACCOUNTING_LINES"]) == expected_lines
    assert int(found["DELETION_ACCOUNTING_FILES"]) == expected_files


def test_the_retired_form_undercounts_that_same_real_diff(tmp_path: Path) -> None:
    """The 26% headline, reproduced on a real git diff rather than a fixture string."""
    repo, base = build_repo(tmp_path)
    expected_lines, _ = numstat_totals(repo, base)
    diff_text = git(repo, "diff", base)
    assert blind_count(diff_text) < expected_lines, (
        "the retired form saw everything - the fixture no longer exercises the blind spot"
    )


def test_file_headers_are_never_counted_as_deletions(tmp_path: Path) -> None:
    """A multi-file diff carries one `--- a/<path>` per file; none is a deletion."""
    repo, base = build_repo(tmp_path)
    expected_lines, _ = numstat_totals(repo, base)
    diff_text = git(repo, "diff", base)
    headers = sum(1 for line in diff_text.splitlines() if line.startswith("--- "))
    assert headers >= 2, "fixture must span several files for this to mean anything"

    result = run("--base", base, "--repo", str(repo), "--top", "0")
    assert int(contract(result.stdout)["DELETION_ACCOUNTING_LINES"]) == expected_lines


def test_a_deleted_line_shaped_like_a_header_is_still_counted(tmp_path: Path) -> None:
    """`-- foo` followed by `++ bar` inside a hunk must not end the hunk early.

    The hunk-scoped parser recognises a header by git's `a/` `b/` shape while
    inside a hunk, precisely so content that merely resembles one cannot make it
    stop looking.
    """
    # The a/ and b/ PREFIXES are the point. An earlier cut of the parser
    # recognised a header by its text and narrowed that to git's `a/`/`b/`
    # shape, believing the shape was unfakeable; a deleted `-- a/foo` followed
    # by an added `++ b/bar` renders as exactly that shape, ended the hunk, and
    # reported 0 where git reports 2. Found by the counter-model review, which
    # is why this fixture carries the prefixes and the first one did not.
    tricky = (
        "diff --git a/x.txt b/x.txt\n"
        "--- a/x.txt\n"
        "+++ b/x.txt\n"
        "@@ -1,3 +1,2 @@\n"
        " keep\n"
        "--- a/foo\n"
        "+++ b/bar\n"
        "-also deleted\n"
    )
    result = run("--diff-file", str(write_diff(tmp_path, "t.diff", tricky)), "--top", "0")
    assert result.returncode == 1, result.stdout
    assert contract(result.stdout)["DELETION_ACCOUNTING_LINES"] == "2", result.stdout


# --- UNKNOWN is not clean -------------------------------------------------- #

def test_an_unresolvable_base_is_unknown_not_clean(tmp_path: Path) -> None:
    repo, _ = build_repo(tmp_path)
    result = run("--base", "no-such-ref", "--repo", str(repo))
    assert result.returncode == 2, result.stdout
    assert contract(result.stdout)["DELETION_ACCOUNTING_LINES"] == "unknown"
    assert "DELETION_ACCOUNTING_FINDING" not in result.stdout, (
        "an UNKNOWN run must not emit the detection signal, or it scores as a finding"
    )


def test_a_root_with_no_patches_is_unknown_not_clean(tmp_path: Path) -> None:
    """An empty population and a population with nothing deleted are different facts."""
    empty = tmp_path / "empty"
    empty.mkdir()
    result = run("--root", str(empty))
    assert result.returncode == 2, result.stdout
    assert "UNKNOWN" in result.stdout


def test_no_arguments_is_unknown(tmp_path: Path) -> None:
    result = run()
    assert result.returncode == 2, result.stdout


def test_the_resolved_base_sha_is_printed_not_the_moving_ref(tmp_path: Path) -> None:
    """The hazard is a ref that moves, so the report names the commit it read."""
    repo, base = build_repo(tmp_path)
    result = run("--base", "HEAD~1", "--repo", str(repo), "--top", "0")
    assert contract(result.stdout)["DELETION_ACCOUNTING_SOURCE"] == f"base={base}", result.stdout


# --- the anchor stays blind ------------------------------------------------ #

def test_the_committed_anchor_is_still_blind(tmp_path: Path) -> None:
    """Asserted here as well as by the control harness, and deliberately so.

    `check-negative-controls.py` runs this in CI; this test runs it in the unit
    suite. If someone "fixes" the anchor, the control would go INERT - a verdict
    that needs reading to interpret - while this fails with the reason on it.
    """
    case = ROOT / "controls" / "deletion-accounting" / "cases" / "bad-blindspot-deletions"
    result = subprocess.run(
        ["bash", str(ANCHOR), "--root", str(case), "--top", "0"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, "the anchor caught the known-bad input; it is no longer blind"
    assert "DELETION_ACCOUNTING_FINDING" not in result.stdout


# --- the counter-model review's findings, each as an executed red case ------ #
#
# Every one of these reproduced against the first cut of this instrument, and
# every one was the instrument's own failure class: a confident number over a
# population it had not examined. They are pinned here rather than described.

def test_a_colour_coded_diff_is_unknown_not_clean(tmp_path: Path) -> None:
    """`color.ui=always` turned a 19-deletion diff into exit 0, zero deletions.

    Git wraps every `-` in an escape sequence, so no hunk is recognised at all.
    The parser cannot see through that and must not pretend otherwise - it is
    UNKNOWN, not clean.
    """
    repo, base = build_repo(tmp_path)
    coloured = tmp_path / "colour.diff"
    coloured.write_text(
        git(repo, "-c", "color.ui=always", "diff", "--color=always", base), encoding="utf-8"
    )
    assert "\x1b[" in coloured.read_text(encoding="utf-8"), "fixture is not actually coloured"

    result = run("--diff-file", str(coloured), "--top", "0")
    assert result.returncode == 2, result.stdout
    assert "DELETION_ACCOUNTING_FINDING" not in result.stdout


def test_the_base_lane_is_immune_to_presentation_config(tmp_path: Path) -> None:
    """The lane people actually use asks git for canonical patch output.

    `--base` runs `git diff` itself, so it can - and does - pin `color.ui=false`,
    `--no-color`, `--no-ext-diff` and `--no-textconv`. Setting the hostile config
    in the repo under test proves the pin is load-bearing rather than decorative.
    """
    repo, base = build_repo(tmp_path)
    expected, _files = numstat_totals(repo, base)
    git(repo, "config", "color.ui", "always")

    result = run("--base", base, "--repo", str(repo), "--top", "0")
    assert result.returncode == 1, result.stdout
    assert int(contract(result.stdout)["DELETION_ACCOUNTING_LINES"]) == expected


def test_input_that_is_not_a_diff_is_unknown_not_clean(tmp_path: Path) -> None:
    """`fatal: upstream diff generation failed` reported CLEAN before this."""
    junk = tmp_path / "junk.diff"
    junk.write_text("fatal: upstream diff generation failed\n", encoding="utf-8")
    result = run("--diff-file", str(junk), "--top", "0")
    assert result.returncode == 2, result.stdout
    assert "not a unified diff" in result.stderr


def test_a_directory_given_as_a_patch_is_unknown_not_clean(tmp_path: Path) -> None:
    """`-r` is true for a directory, and the discarded `cat` status hid it."""
    result = run("--diff-file", str(tmp_path), "--top", "0")
    assert result.returncode == 2, result.stdout


def test_a_lying_hunk_header_is_unknown_not_clean(tmp_path: Path) -> None:
    """A truncated patch must not be accounted as if it were whole.

    This one also guards the fixtures: because the parser consumes the declared
    counts, a hand-written case whose header disagrees with its body reports
    UNKNOWN, and a test expecting a finding fails rather than passing on a
    number nobody checked.
    """
    truncated = tmp_path / "short.diff"
    truncated.write_text(
        "diff --git a/x.txt b/x.txt\n--- a/x.txt\n+++ b/x.txt\n@@ -1,9 +1,3 @@\n keep\n-gone\n",
        encoding="utf-8",
    )
    result = run("--diff-file", str(truncated), "--top", "0")
    assert result.returncode == 2, result.stdout
    assert "malformed" in result.stderr or "truncated" in result.stderr


def test_binary_files_are_reported_as_an_unexamined_population(tmp_path: Path) -> None:
    """A line count says nothing about a binary file, so the count is stated.

    And a binary file DELETED outright has no lines at all, yet it is a whole
    file leaving the tree - which is precisely what the file-count tell exists
    to surface, so it must not vanish into a clean verdict.
    """
    repo = tmp_path / "binrepo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    (repo / "blob.bin").write_bytes(bytes(range(256)) * 4)
    (repo / "keep.txt").write_text("untouched\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "blob.bin").unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "drop the binary")

    result = run("--base", base, "--repo", str(repo), "--top", "0")
    found = contract(result.stdout)
    assert found["DELETION_ACCOUNTING_LINES"] == "0", result.stdout
    assert "deleted: 1" in found["DELETION_ACCOUNTING_BINARY"], result.stdout
    assert result.returncode == 1, (
        "a deleted binary file vanished into a clean verdict: " + result.stdout
    )


def test_a_genuinely_empty_git_diff_is_clean_not_unknown(tmp_path: Path) -> None:
    """The other direction, and it is what stops the coverage check overreaching.

    "git looked and there is no change" is a real clean answer. Only an input
    with BYTES we could not parse is UNKNOWN. Without this the new check would
    report UNKNOWN for every unchanged tree, which is the over-correction that
    gets a check switched off.
    """
    repo, _base = build_repo(tmp_path)
    result = run("--base", "HEAD", "--repo", str(repo), "--top", "0")
    assert result.returncode == 0, result.stdout
    assert contract(result.stdout)["DELETION_ACCOUNTING_LINES"] == "0"


# --- the second review pass's findings, likewise executed ------------------- #

@pytest.mark.parametrize(
    ("name", "body"),
    [
        (
            "combined-merge-hunk",
            "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@@ -1,1 -1,1 +1,0 @@@\n--gone\n",
        ),
        (
            "header-only-truncation",
            "diff --git a/x b/x\n--- a/x\n+++ b/x\n",
        ),
        (
            "counter-underflow",
            "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,0 +1,1 @@\n context\n-deleted\n",
        ),
    ],
)
def test_a_section_whose_body_was_never_read_is_unknown(tmp_path: Path, name: str, body: str) -> None:
    """Coverage is per FILE SECTION, not per input.

    Accepting the whole input because SOMETHING in it parsed is how one valid
    patch masks an unreadable neighbour - which is exactly what `--root` does,
    since it concatenates every patch it finds. The underflow case is the
    subtlest: `@@ -1,0 +1,1 @@` spends its counts on the context line, so the
    deletion below falls outside the hunk and the end-of-input check sees
    nothing left over to complain about.
    """
    patch = tmp_path / f"{name}.diff"
    patch.write_text(body, encoding="utf-8")
    result = run("--diff-file", str(patch), "--top", "0")
    assert result.returncode == 2, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("rename-only", "diff --git a/a.txt b/b.txt\nsimilarity index 100%\nrename from a.txt\nrename to b.txt\n"),
        ("mode-only", "diff --git a/x b/x\nold mode 100644\nnew mode 100755\n"),
    ],
)
def test_a_metadata_only_change_stays_clean(tmp_path: Path, name: str, body: str) -> None:
    """THE OVER-CORRECTION GUARD, and it is why the coverage rule is written as it is.

    A rename or a mode change legitimately carries no hunk and no `---`/`+++`
    pair. A coverage check that demanded a hunk per `diff --git` would report
    UNKNOWN for both - failing on ordinary, correct input, which is how a check
    gets switched off inside a week.
    """
    patch = tmp_path / f"{name}.diff"
    patch.write_text(body, encoding="utf-8")
    result = run("--diff-file", str(patch), "--top", "0")
    assert result.returncode == 0, result.stdout + result.stderr


def build_binary_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "binrepo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    for name in ("one.bin", "two.bin"):
        (repo / name).write_bytes(bytes(range(256)) * 4)
    (repo / "keep.txt").write_text("untouched\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "one.bin").unlink()
    (repo / "two.bin").unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "drop the binaries")
    return repo, base


def test_both_binary_representations_surface_a_deleted_file(tmp_path: Path) -> None:
    """`git diff` and `git diff --binary` spell a deleted binary differently.

    The default prints `Binary files a/x and /dev/null differ`; `--binary`
    prints `deleted file mode` plus `GIT binary patch` and never mentions
    /dev/null. Keying on the first alone reported `deleted: 0` and exited CLEAN
    for the second.
    """
    repo, base = build_binary_repo(tmp_path)
    for extra in ([], ["--binary"]):
        patch = tmp_path / f"bin{len(extra)}.diff"
        patch.write_text(git(repo, "diff", *extra, base), encoding="utf-8")
        result = run("--diff-file", str(patch), "--top", "0")
        found = contract(result.stdout)
        assert result.returncode == 1, (extra, result.stdout)
        assert "deleted: 2" in found["DELETION_ACCOUNTING_BINARY"], (extra, result.stdout)
        # Two DISTINCT files, not one: binary notices carry no `---` header, so
        # keying the file set off that header collapsed every deleted binary
        # onto the same empty name.
        assert found["DELETION_ACCOUNTING_FILES"] == "2", (extra, result.stdout)


def test_a_partly_failed_traversal_is_unknown_not_clean(tmp_path: Path) -> None:
    """`find | sort` hands the assignment SORT's status, and pipefail is not set.

    So an unreadable subtree exited 1 from find, sort exited 0 over whatever did
    come through, and a PARTIAL patch population was accounted as a whole one -
    reporting CLEAN when the patches it never saw might hold anything. The stub
    reproduces exactly that shape: real output, then a failure.
    """
    root = tmp_path / "patches"
    root.mkdir()
    (root / "ok.diff").write_text(ADDITIONS_ONLY_DIFF, encoding="utf-8")
    assert run("--root", str(root), "--top", "0").returncode == 0, "baseline must be clean"

    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "find").write_text(
        f'#!/usr/bin/env bash\nprintf "%s\\n" "{root / "ok.diff"}"\nexit 1\n', encoding="utf-8"
    )
    (stub / "find").chmod(0o755)
    # PREPENDED, not replaced: everything else the script needs stays reachable,
    # so a failure here can only come from find's status.
    env = dict(os.environ, PATH=f"{stub}:{os.environ['PATH']}")
    assert shutil.which("find", path=str(stub)) is not None, "fixture must provide the stub find"
    assert shutil.which("sort") is not None, "fixture must not have hidden the rest of PATH"

    result = subprocess.run(
        ["bash", str(SCRIPT), "--root", str(root), "--top", "0"],
        capture_output=True, text=True, timeout=120, check=False, env=env,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "incomplete" in result.stderr, result.stderr

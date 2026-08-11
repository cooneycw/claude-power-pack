"""Regression tests for the speckit issue-sync record parse (issue #700).

`scripts/speckit-tasks-to-issues.sh` reads `gh issue list` records as
`<number><SEP><title>` to dedup tasks that already have issues. It shipped with
SEP=tab, and tab is IFS *whitespace*: shell field splitting collapses a run of it
and an EMPTY field vanishes instead of arriving empty, shifting every later field
up one slot. The same defect class was live in `scripts/flow-wave-registry.sh`
(#698); this site was latent, guarded only by the accident that `.number` is
never empty.

The test that matters therefore uses an EMPTY FIRST FIELD - #698's lesson was
that a fixture with all fields populated passes against the broken code and
proves nothing. `test_populated_record_still_parses` is the control that pins
that the ordinary path is unchanged.

The `gh` stub deliberately derives its output separator from the `--jq` filter
the script asks for, rather than hard-coding one. That makes these tests
sensitive to producer/reader AGREEMENT: reverting either side alone to tab
reproduces the bug and fails the empty-field test.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "speckit-tasks-to-issues.sh"

# These tests drive real `git` and `bash` subprocesses. The Woodpecker `validate`
# step runs in `uv:python3.11-bookworm-slim`, which ships bash but NOT git, so
# without this guard the module errors and turns CI red (core directive; #602).
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH",
)

# A stub `gh` that models the one behaviour under test: whatever separator the
# script's --jq filter asks for between .number and .title is the separator the
# records come back with. `unicode_escape` decodes the unit-separator escape
# and \t exactly as jq does, so the stub cannot silently agree with a drifted reader.
GH_STUB = r'''#!/usr/bin/env python3
import json, os, re, sys

argv = sys.argv[1:]
if argv[:2] != ["issue", "list"]:
    sys.exit(0)

jq_filter = argv[argv.index("--jq") + 1]
match = re.search(r"\\\(\.number\)(.*?)\\\(\.title\)", jq_filter)
if not match:
    sys.stderr.write("stub gh: unrecognised --jq filter: %s\n" % jq_filter)
    sys.exit(1)
sep = match.group(1).encode("utf-8").decode("unicode_escape")

for number, title in json.loads(os.environ["GH_STUB_RECORDS"]):
    sys.stdout.write("%s%s%s\n" % (number, sep, title))
'''


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _project(tmp_path: Path, tasks: str) -> tuple[Path, Path]:
    """A git repo with a GitHub origin, a tasks.md, and a stub `gh` on PATH."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "remote", "add", "origin", "https://github.com/acme/widget.git")

    tasks_file = repo / "tasks.md"
    tasks_file.write_text(tasks, encoding="utf-8")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(GH_STUB, encoding="utf-8")
    gh.chmod(0o755)
    return repo, bindir


def _run(
    repo: Path, bindir: Path, tasks_file: Path, records: list[list[str]]
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HOME": str(repo.parent),
        "GH_STUB_RECORDS": json.dumps(records),
    }
    return subprocess.run(
        ["bash", str(SCRIPT), "--dry-run", "--tasks", str(tasks_file)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


def test_empty_first_field_does_not_shift_the_title(tmp_path: Path) -> None:
    """An empty `.number` must leave the title in field 2, not shift it into field 1.

    This is the #700 fixture. Under the tab spelling the record collapses to a
    single field, the title lands in `number`, the T-ID regex never matches, and
    the already-filed task is offered for creation a second time.
    """
    repo, bindir = _project(tmp_path, "- [ ] T001: Wire the frobnicator\n")
    result = _run(repo, bindir, repo / "tasks.md", [["", "T001: Wire the frobnicator"]])

    assert result.returncode == 0, result.stderr
    assert "skip  T001" in result.stdout, (
        "an empty first field shifted the title out of field 2 - the #700 "
        f"collapse. stdout:\n{result.stdout}"
    )
    assert "would create" not in result.stdout


def test_populated_record_still_parses(tmp_path: Path) -> None:
    """Control: the ordinary all-fields-populated path is unchanged."""
    repo, bindir = _project(tmp_path, "- [ ] T001: Wire the frobnicator\n")
    result = _run(
        repo, bindir, repo / "tasks.md", [["42", "T001: Wire the frobnicator"]]
    )

    assert result.returncode == 0, result.stderr
    assert "skip  T001" in result.stdout
    assert "would create" not in result.stdout


def test_unmatched_task_is_still_created(tmp_path: Path) -> None:
    """A task with no existing issue is still offered for creation."""
    repo, bindir = _project(tmp_path, "- [ ] T007: Not filed anywhere\n")
    result = _run(repo, bindir, repo / "tasks.md", [["42", "T001: Something else"]])

    assert result.returncode == 0, result.stderr
    assert "would create: T007: Not filed anywhere" in result.stdout
    assert "skip  T007" not in result.stdout


def test_title_containing_whitespace_survives(tmp_path: Path) -> None:
    """Control: a title carrying embedded tabs still round-trips.

    Deliberately NOT a discriminator - `read -r number title` assigns the whole
    remainder to the last variable, so embedded tabs survive under either
    separator (verified: this passes against the pre-#700 tab code too). It pins
    that moving to `\\037` did not regress titles that contain whitespace.
    """
    repo, bindir = _project(tmp_path, "- [ ] T001: Wire the frobnicator\n")
    result = _run(
        repo,
        bindir,
        repo / "tasks.md",
        [["42", "T001: Wire\tthe\tfrobnicator"]],
    )

    assert result.returncode == 0, result.stderr
    assert "skip  T001" in result.stdout


def test_no_whitespace_ifs_read_remains_in_scripts() -> None:
    """Class guard: no shell reader in scripts/ splits on an IFS-whitespace delimiter.

    The #700 site was the last one (#698 fixed the rest). A new tab- or
    space-delimited `read` fails silently - shifted fields, never an error - so
    the shape is worth pinning rather than rediscovering.
    """
    # `IFS=<value> read` - captures the value in each of the spellings this repo
    # uses: $'..', "..", '..', or bare.
    ifs_read = re.compile(r"""IFS=(\$'[^']*'|"[^"]*"|'[^']*'|\S*)[ \t]+read\b""")

    offenders: list[str] = []
    for script in sorted((ROOT / "scripts").glob("*.sh")):
        for lineno, line in enumerate(
            script.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = ifs_read.search(line)
            if match is None:
                continue
            value = match.group(1)
            # `IFS= read` - the empty-IFS whole-line idiom, correct and common.
            if value == "":
                continue
            if "\\t" in value or "\t" in value or value in ("' '", '" "', " "):
                offenders.append(
                    f"{script.relative_to(ROOT)}:{lineno}: {line.strip()}"
                )

    assert not offenders, (
        "whitespace-IFS read(s) reintroduced (#698/#700):\n" + "\n".join(offenders)
    )

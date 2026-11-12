"""`worktree-remove.sh --help` prints the header's own help region (issue #1693).

The help text used to be a hand-typed copy of the file header, 65 `echo`
lines, and the two had already drifted (they disagreed on exit 9). It is now
the header itself, cut out by two markers. A line RANGE would break the first
time someone edits the header above it, which is the defect a sibling script
has (`flow-worktree-guard.sh`, recorded on #1713); markers move with the text.

Also pins the one behaviour fix that rode along: the relative-path `cd` no
longer honours an inherited `CDPATH` (joined Nit Store finding 557).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "worktree-remove.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


def _help(script: Path = SCRIPT) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True, check=False)


def test_help_prints_usage_options_exit_codes_and_examples():
    proc = _help()
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    for section in ("Usage:", "Options:", "Exit codes:", "Examples:"):
        assert section in out, f"--help lost its {section!r} section:\n{out[:400]}"
    assert "--finish-partial-removal" in out
    # every refusal exit the header documents is named, 9 among them
    for code in ("4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"):
        assert any(line.split()[:1] == [code] for line in out.splitlines()), f"exit {code} is not named"
    assert "cannot be deleted" in out, "exit 9's meaning is missing"
    # the markers themselves and the comment prefix are not printed
    assert "help:begin" not in out and "help:end" not in out
    assert not any(line.startswith("#") for line in out.splitlines())


def test_help_is_cut_by_markers_not_by_a_line_range(tmp_path):
    """Add lines ABOVE the help region: the output must not move or shrink.
    With a hard-coded range this is the edit that silently cuts the text."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("# help:begin\n") == 1 and text.count("# help:end\n") == 1
    padded = text.replace("# help:begin\n", "#\n" * 40 + "# help:begin\n", 1)
    copy = tmp_path / "worktree-remove.sh"
    copy.write_text(padded, encoding="utf-8")
    assert _help(copy).stdout == _help().stdout


def test_help_without_its_end_marker_is_visibly_broken(tmp_path):
    """The red case for the test above: lose a marker and the output changes,
    so a header edit that removes one cannot pass unnoticed."""
    text = SCRIPT.read_text(encoding="utf-8")
    copy = tmp_path / "worktree-remove.sh"
    copy.write_text(text.replace("# help:end\n", "", 1), encoding="utf-8")
    assert _help(copy).stdout != _help().stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_a_relative_path_is_resolved_against_the_cwd_not_cdpath(tmp_path):
    """With CDPATH set, `cd sub` can land in CDPATH/sub and print it. The script
    would then resolve a relative argument to a directory the caller never named."""
    here = tmp_path / "here"
    elsewhere = tmp_path / "elsewhere"
    (here / "sub").mkdir(parents=True)
    (elsewhere / "sub" / "target").mkdir(parents=True)
    env = dict(os.environ)
    env["CDPATH"] = str(elsewhere)
    # `sub/target` does not exist under `here`; under CDPATH it would resolve
    # into `elsewhere`. The script must report on the path under the cwd.
    proc = subprocess.run(
        ["bash", str(SCRIPT), "sub/target"], cwd=here, capture_output=True, text=True, env=env, check=False
    )
    combined = proc.stdout + proc.stderr
    assert str(elsewhere) not in combined, f"the argument was resolved through CDPATH:\n{combined}"

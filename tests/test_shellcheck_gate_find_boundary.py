"""The `find` fallback does not lint the CI's staged toolchain (#972).

WHY THIS NEEDS A TEST AND NOT A CONTROL CASE. CI's shellcheck image has no git,
so the gate enumerates with `find` there - and CI stages pinned binaries into
`.ci-bin/`, including a whole git tree (`.ci-bin/git-root/usr/lib/git-core/*`)
whose scripts are someone else's code. `.gitignore` already excludes `.ci-bin/`,
so the git path never saw it; the `find` prune list did not name it. At
`severity=error` those vendored scripts happened to be clean, so the gap was
invisible. Raising the default to `style` (#972) turned it into 13 files of
findings on PR #1247's pipeline and nothing on any developer box.

The control harness cannot reach this: every case lives inside this repository,
where `git rev-parse` succeeds and the gate takes the git path. A root OUTSIDE
any repository takes the `find` path on any host, which is what `tmp_path` is.

The pair matters. The skipped case alone would also pass on a gate that lints
nothing; the neighbouring directory proves the same bad file IS caught when it
sits outside the ownership boundary.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "shellcheck-gate.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("shellcheck") is None, reason="shellcheck is not installed"
)

#: Only a style-level note (SC2002), so it is caught at the default severity and
#: at nothing stricter - the severity #972 raised the gate to.
OFFENDER = "#!/bin/sh\ncat /etc/hostname | wc -l\n"
CLEAN = "#!/bin/sh\nprintf 'ok\\n'\n"


def _tree(root: Path, offender_dir: str) -> Path:
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "clean.sh").write_text(CLEAN)
    vendored = root / offender_dir
    vendored.mkdir(parents=True)
    (vendored / "tool").write_text(OFFENDER)
    return root


def _gate(root: Path) -> subprocess.CompletedProcess[str]:
    # Precondition: the root is outside every git repository, or the gate takes
    # the git path and this test measures nothing about `find`.
    probe = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-dir"],
        capture_output=True, text=True, check=False,
    ) if shutil.which("git") else None
    assert probe is None or probe.returncode != 0, "tmp root is inside a git repo"
    return subprocess.run(
        ["sh", str(GATE), "--root", str(root)],
        capture_output=True, text=True, timeout=120, check=False,
    )


def test_find_fallback_skips_the_staged_ci_toolchain(tmp_path: Path) -> None:
    root = _tree(tmp_path / "repo", ".ci-bin/git-root/usr/lib/git-core")
    result = _gate(root)
    assert "(source=find)" in result.stdout + result.stderr
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 file(s) scanned" in result.stdout


def test_the_same_offender_outside_the_boundary_is_caught(tmp_path: Path) -> None:
    root = _tree(tmp_path / "repo", "tools/git-core")
    result = _gate(root)
    assert "(source=find)" in result.stdout + result.stderr
    assert result.returncode == 1, result.stdout + result.stderr
    assert "SC2002" in result.stdout

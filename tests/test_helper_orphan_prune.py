"""The prune half of `/cpp:update` Step 5b (issue #1263).

Step 5b linked every executable in `scripts/` into `~/.claude/scripts/` and
removed nothing, so a helper deleted upstream left a dangling link at the stable
path indefinitely. install-drift NAMED it at every session start; nothing acted
on it. Measured live: `project-next-vendor.py`, dangling from af348f8 (#1144)
until someone deleted it by hand.

THE NEGATIVE CONTROL (ADR 0008, as the issue states it): an upstream-deleted
script whose symlink is still installed must be named AND pruned. The first test
is that case end to end - install-drift's own `--json` orphan list drives the
seam, exactly as Step 5b does - and it fails on the pre-fix seam, which had no
`unlink-orphan` and exited 2 with the link still in place.

The refusal cases are the other verdict. A prune that removed whatever it was
handed would pass the first test and delete a user's tool, a live helper, or a
neighbour project's link, so each of those is pinned as surviving.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEAM = ROOT / "scripts" / "cpp-host-write.sh"
DRIFT = ROOT / "scripts" / "install-drift.sh"
UPDATE_DOC = ROOT / ".claude" / "commands" / "cpp" / "update.md"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash on PATH")


def _checkout(root: Path) -> Path:
    (root / ".claude" / "commands").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "CLAUDE.md").write_text("# fake CPP\n", encoding="utf-8")
    return root


def _script(checkout: Path, name: str) -> Path:
    path = checkout / "scripts" / name
    path.write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _seam(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SEAM), *args],
        env={"HOME": str(home), "PATH": os.environ.get("PATH", "")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )


def _orphans(checkout: Path, home: Path) -> list[str]:
    result = subprocess.run(
        ["bash", str(DRIFT), "--json"],
        env={
            "CPP_INSTALL_DRIFT_CHECKOUT": str(checkout),
            "CPP_INSTALL_DRIFT_HOME": str(home),
            "PATH": os.environ.get("PATH", ""),
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return list(json.loads(result.stdout)["orphaned_helpers"])


def test_an_upstream_deleted_helper_is_named_AND_pruned(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path / "cpp")
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    kept = _script(checkout, "kept.sh")
    gone = _script(checkout, "retired-vendor.py")
    (scripts / "kept.sh").symlink_to(kept)
    (scripts / "retired-vendor.py").symlink_to(gone)
    gone.unlink()  # deleted upstream; the installed link now dangles

    named = _orphans(checkout, home)
    assert named == ["retired-vendor.py"], named

    # Step 5b's prune loop: install-drift's list, one seam call per name.
    for name in named:
        result = _seam(home, "unlink-orphan", str(scripts), name)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "orphan removed" in result.stdout

    assert not (scripts / "retired-vendor.py").is_symlink(), "the orphan must be gone"
    assert (scripts / "kept.sh").resolve() == kept, "a live helper must survive"
    assert _orphans(checkout, home) == []


@pytest.mark.parametrize("case", ["live", "host-file", "neighbour", "not-install-shape"])
def test_anything_that_is_not_our_dangling_link_is_refused(tmp_path: Path, case: str) -> None:
    checkout = _checkout(tmp_path / "cpp")
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    entry = scripts / "tool.sh"
    if case == "live":
        entry.symlink_to(_script(checkout, "tool.sh"))
    elif case == "host-file":
        entry.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    elif case == "neighbour":
        # Same install SHAPE, but the root is not a CPP checkout.
        other = tmp_path / "other-project"
        (other / "scripts").mkdir(parents=True)
        entry.symlink_to(other / "scripts" / "tool.sh")
    else:
        # Dangling, into the CPP checkout, but not `<root>/scripts/<own name>`.
        entry.symlink_to(checkout / "scripts" / "renamed.sh")

    result = _seam(home, "unlink-orphan", str(scripts), "tool.sh")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "REFUSED" in result.stderr
    assert entry.is_symlink() or entry.exists(), f"{case}: the entry must survive"


def test_a_deferred_scripts_dir_is_not_pruned(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path / "cpp")
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "gone.sh").symlink_to(checkout / "scripts" / "gone.sh")

    result = _seam(home, "unlink-orphan", str(scripts), "gone.sh", "--defer", "~/.claude/scripts")

    assert result.returncode == 3, result.stdout + result.stderr
    assert "DEFERRED" in result.stdout
    assert (scripts / "gone.sh").is_symlink()


def test_a_name_with_a_path_separator_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude" / "scripts").mkdir(parents=True)
    result = _seam(home, "unlink-orphan", str(home / ".claude" / "scripts"), "../settings.json")
    assert result.returncode == 1


def test_update_step_5b_wires_the_prune_to_install_drifts_orphan_list() -> None:
    """The seam is only half the fix; the command must call it.

    Red on the pre-fix document, whose Step 5b only ever called `link-into`.
    """
    text = UPDATE_DOC.read_text(encoding="utf-8")
    start = text.index("## Step 5b: Script Symlink Refresh")
    end = text.index("## Step 5b.1:")
    step = text[start:end]
    assert "orphaned_helpers" in step
    assert "cpp-host-write.sh unlink-orphan" in step

"""Tests for scripts/regenerate-blind-anchor.py (issue #1492).

Two committed cases, named so a reviewer searching for this script's own
test coverage can find it:

(a) `test_a_the_real_committed_anchor_matches_the_real_gate` - the REAL
    repo tree's own committed anchor reports `matches` against the REAL
    gate, unmodified. The standing proof that the committed anchor and its
    stored patch are not already drifted against each other, run against
    the actual repository tree, never a copy.

(b) `test_bc_mutated_gate_copy_drifts_then_regenerates_cleanly` - a copy
    of the gate (never the real tree) is mutated outside the patch's own
    hunks; the default mode reports `drift` with a diff, `--write`
    regenerates an anchor equal to gate+patch with its hand-written
    docstring preserved and its recorded `sha256` kept in sync, a second
    identical `--write` is byte-for-byte idempotent, and a mutation INSIDE
    a patched hunk (so the stored patch's own context no longer matches)
    is refused as drift rather than silently misapplied.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "regenerate-blind-anchor.py"


def _run_real(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True, text=True, check=False, timeout=30,
    )


def test_a_the_real_committed_anchor_matches_the_real_gate() -> None:
    """(a) The committed controls/host-surface-observe anchor is not stale
    against the real gate + the real stored patch - run against the actual
    repository tree, never a copy."""
    result = _run_real("host-surface-observe")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "matches:" in result.stdout, result.stdout


def test_bc_mutated_gate_copy_drifts_then_regenerates_cleanly(tmp_path: Path) -> None:
    """(b)+(c), entirely in tmp_path - never touches the real repository:
    drift is reported with a diff, --write regenerates with the docstring
    and digest kept correct and in sync, a repeat write is byte-identical,
    and a mutation inside a patched hunk is refused rather than misapplied.
    """
    root = tmp_path
    (root / "scripts").mkdir()
    tool = root / "scripts/regenerate-blind-anchor.py"
    shutil.copyfile(TOOL, tool)
    gate = root / "scripts/host-surface-observe.py"
    shutil.copyfile(ROOT / "scripts/host-surface-observe.py", gate)
    control = root / "controls/host-surface-observe"
    control.mkdir(parents=True)
    shutil.copyfile(ROOT / "controls/host-surface-observe/control.json", control / "control.json")
    anchors = control / "anchors"
    anchors.mkdir()
    anchor = anchors / "constructed-blind-covered-by.py"
    shutil.copyfile(ROOT / "controls/host-surface-observe/anchors" / anchor.name, anchor)
    shutil.copyfile(ROOT / "controls/host-surface-observe/anchors" / anchor.with_suffix(".patch").name,
                    anchor.with_suffix(".patch"))
    spec_path = control / "control.json"
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes)
    # Baseline sanity: the fixture itself is not already drifted.
    assert spec_bytes == (json.dumps(spec, indent=2) + "\n").encode()
    assert spec["anchors"][0]["sha256"] == hashlib.sha256(anchor.read_bytes()).hexdigest()
    original = anchor.read_text()
    # A non-transformation change must propagate from the current gate.
    gate.write_text(gate.read_text() + "\n# regeneration freshness canary\n")
    assert "regeneration freshness canary" not in original

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(tool), "host-surface-observe", *args],
            capture_output=True, text=True, check=False, timeout=30,
        )

    # (b) drift reported, read-only - the anchor on disk is unchanged.
    drift = run()
    assert drift.returncode == 1 and "drift:" in drift.stdout and "@@" in drift.stdout
    assert anchor.read_text() == original

    # (c) --write regenerates: docstring preserved, new gate content present,
    # the recorded digest updated AND correct.
    assert run("--write").returncode == 0
    regenerated = anchor.read_text()
    assert regenerated.split('"""')[1] == original.split('"""')[1]
    assert "# regeneration freshness canary" in regenerated
    assert "parents[3]" in regenerated
    recorded = json.loads(spec_path.read_text())["anchors"][0]["sha256"]
    assert recorded != spec["anchors"][0]["sha256"]
    assert recorded == hashlib.sha256(anchor.read_bytes()).hexdigest()

    # A second, identical --write is byte-for-byte idempotent (control.json
    # included - no spurious digest churn on an unchanged regeneration).
    written_spec = spec_path.read_bytes()
    assert run("--write").returncode == 0
    assert spec_path.read_bytes() == written_spec
    assert json.loads(written_spec)["anchors"][0]["sha256"] == recorded
    assert run().returncode == 0

    # A mutation INSIDE a patched hunk (the covered_by signature the patch
    # itself rewrites) makes the stored patch's own context fail to match -
    # refused as drift, never silently misapplied onto the wrong text.
    gate.write_text(gate.read_text().replace(
        "def covered_by(appeared: str,", "def covered_by(appeared: bytes,"))
    refused = run()
    assert refused.returncode == 1 and "drift:" in refused.stdout and "@@" in refused.stdout
    assert anchor.read_text() == regenerated

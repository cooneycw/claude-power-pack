"""`--verify-provenance` reaches a verdict for a constructed anchor with no sha (issue #1719).

A constructed anchor has no historical commit to be compared with, so its
digest check is the whole of what provenance can establish, and its verdict is
`unverified`. Forty-seven registrations write the field as `n/a`, `-` or
`no-check`. Thirteen omit the key, and for those the function indexed
`anchor['sha']` and raised KeyError: the flag could not complete over the real
tree at all (issue #1732 is the larger finding; this pins the crash).

The committed cases are the real registrations themselves.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-negative-controls.py"


def _load():
    spec = spec_from_file_location("check_negative_controls_for_1719", SCRIPT)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cnc = _load()


def _anchors_without_a_sha() -> list[tuple[str, dict, Path]]:
    found = []
    for manifest in sorted((ROOT / "controls").glob("*/control.json")):
        for anchor in json.loads(manifest.read_text(encoding="utf-8")).get("anchors", []):
            if anchor.get("kind") != "historical" and "sha" not in anchor:
                found.append((manifest.parent.name, anchor, manifest.parent / anchor["path"]))
    return found


CASES = _anchors_without_a_sha()


def test_the_population_is_the_real_registrations():
    """The scan must find the registrations this is about, or every case below
    is vacuous. Thirteen controls were in this shape when it was written."""
    controls = {name for name, _anchor, _path in CASES}
    assert len(controls) >= 10, f"only {len(controls)} control(s) found - the scan is not reading the tree"
    assert "flow-preflight" in controls


@pytest.mark.skipif(shutil.which("git") is None, reason="requires git")
@pytest.mark.parametrize(("control", "anchor", "path"), CASES, ids=[c[0] for c in CASES])
def test_a_constructed_anchor_without_a_sha_gets_a_verdict(control, anchor, path):
    assert path.is_file(), f"precondition: {control}'s anchor file exists"
    verdict = cnc._provenance(anchor, path, ROOT, True)
    assert verdict == "unverified", f"{control}: {verdict!r}"


def test_a_missing_origin_gets_a_verdict_too(tmp_path):
    anchor_file = tmp_path / "anchor.sh"
    anchor_file.write_text("x\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha256(anchor_file.read_bytes()).hexdigest()
    anchor = {"kind": "constructed", "sha": "1234567", "path": "anchor.sh", "sha256": digest}
    assert cnc._provenance(anchor, anchor_file, ROOT, True) == "unverified"


def test_a_wrong_digest_is_still_a_mismatch(tmp_path):
    """The half that shows `unverified` is not a blanket pass: an anchor whose
    bytes differ from its recorded digest is refused before any of this."""
    anchor_file = tmp_path / "anchor.sh"
    anchor_file.write_text("tampered\n", encoding="utf-8")
    anchor = {"kind": "constructed", "path": "anchor.sh", "sha256": "0" * 64}
    assert cnc._provenance(anchor, anchor_file, ROOT, True) == "MISMATCH"


def test_a_historical_anchor_without_a_sha_is_still_refused():
    """The fix must not loosen the registration rule: a HISTORICAL anchor names
    a commit, and one that does not is refused by name."""
    problem = cnc._anchor_kind_problem({"kind": "historical", "path": "anchors/x.sh", "origin": "scripts/x.sh"})
    assert problem and "is not a commit" in problem
    assert cnc._anchor_kind_problem({"kind": "constructed", "path": "anchors/x.sh"}) is None


@pytest.mark.skipif(shutil.which("git") is None, reason="requires git")
def test_the_flag_runs_end_to_end_on_a_real_control():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--control", "controls/flow-preflight", "--verify-provenance"],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )
    assert "Traceback" not in proc.stderr, proc.stderr[-600:]
    assert "NEGATIVE_CONTROL_PROVENANCE: unverified" in proc.stdout, proc.stdout[-600:]
    assert "NEGATIVE_CONTROL_VERDICT: PASS" in proc.stdout

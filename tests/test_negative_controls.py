"""Tests for scripts/check-negative-controls.py (issue #924).

This file exists under its own subject's rule. The harness is an instrument, so
it may not land on a green run either: every verdict it can emit is exercised
here against a synthetic gate, and the load-bearing test is the real #906
demonstration executed rather than described.

The synthetic gate is a tiny script whose blindness is a flag, so the four
verdicts can be produced deterministically without depending on repo history.
The REAL anchor is exercised separately, against the real gate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "check-negative-controls.py"
REAL_CONTROL = ROOT / "controls" / "check-test-binary-guards"
REAL_GATE = ROOT / "scripts" / "check-test-binary-guards.py"

requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git absent in the CI validate image"
)


def run_harness(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS), "--root", str(root), *args],
        capture_output=True, text=True, timeout=120, check=False,
    )


def verdict_of(out: str) -> str:
    for line in out.splitlines():
        if line.startswith("NEGATIVE_CONTROL_VERDICT: "):
            return line.split(": ", 1)[1]
    return "<none>"


def provenance_of(out: str) -> str:
    for line in out.splitlines():
        if line.startswith("NEGATIVE_CONTROL_PROVENANCE: "):
            return line.split(": ", 1)[1]
    return "<none>"


# --------------------------------------------------------------------------- #
# A synthetic gate whose blindness is switchable, so every verdict is reachable
# without depending on repo history.
# --------------------------------------------------------------------------- #
SEEING_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
sys.exit(1 if (root / "tests" / "BAD").exists() else 0)
"""

BLIND_GATE = """#!/usr/bin/env python3
import sys
#: NEGATIVE-CONTROL: controls/toy
sys.exit(0)
"""

WEDGED_GATE = """#!/usr/bin/env python3
import sys
#: NEGATIVE-CONTROL: controls/toy
sys.exit(1)
"""


def build_tree(
    tmp_path: Path,
    gate_src: str,
    anchor_src: str | None = BLIND_GATE,
    cases: list[dict[str, str]] | None = None,
) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "toy-gate.py").write_text(gate_src, encoding="utf-8")
    ctl = tmp_path / "controls" / "toy"
    (ctl / "cases" / "bad" / "tests").mkdir(parents=True)
    (ctl / "cases" / "good" / "tests").mkdir(parents=True)
    (ctl / "cases" / "bad" / "tests" / "BAD").write_text("x", encoding="utf-8")
    anchors: list[dict[str, str]] = []
    if anchor_src is not None:
        (ctl / "anchors").mkdir()
        anchor = ctl / "anchors" / "deadbee-toy.py"
        anchor.write_text(anchor_src, encoding="utf-8")
        import hashlib
        anchors = [{
            "kind": "historical", "sha": "deadbee", "origin": "scripts/toy-gate.py",
            "path": "anchors/deadbee-toy.py",
            "sha256": hashlib.sha256(anchor.read_bytes()).hexdigest(),
        }]
    (ctl / "control.json").write_text(json.dumps({
        "gate": "scripts/toy-gate.py",
        "invocation": [sys.executable, "{gate}", "--root", "{case}"],
        "good_exit": 0,
        "cases": cases if cases is not None else [
            {"name": "bad", "input": "cases/bad", "expect": "BAD"},
            {"name": "good", "input": "cases/good", "expect": "GOOD"},
        ],
        "anchors": anchors,
    }), encoding="utf-8")
    return tmp_path


def test_a_discriminating_gate_with_a_blind_anchor_passes(tmp_path: Path) -> None:
    root = build_tree(tmp_path, SEEING_GATE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "PASS", result.stdout
    assert result.returncode == 0


def test_a_gate_that_stopped_discriminating_reports_blind(tmp_path: Path) -> None:
    """The regression this whole framework exists to catch."""
    root = build_tree(tmp_path, BLIND_GATE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "BLIND", result.stdout
    assert result.returncode == 1


def test_a_gate_wedged_at_fail_reports_blind_too(tmp_path: Path) -> None:
    """The known-good half is not decoration: a gate stuck at FAIL passes the
    known-bad check on its own, and only the good case separates the two."""
    root = build_tree(tmp_path, WEDGED_GATE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "BLIND", result.stdout
    assert "flagged a known-good input" in result.stdout


def test_a_control_with_no_anchor_is_unproven_and_not_pass(tmp_path: Path) -> None:
    """The load-bearing state. Forgetting to demonstrate that a control can fail
    must produce a RED, not a silence - otherwise this framework is just the
    reviewer's habit relocated into a script nobody runs."""
    root = build_tree(tmp_path, SEEING_GATE, anchor_src=None)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNPROVEN", result.stdout
    assert result.returncode == 1


def test_an_anchor_that_catches_the_bad_input_is_inert(tmp_path: Path) -> None:
    """An anchor that is not actually blind proves nothing: the control would not
    notice the gate regressing, which is a control that cannot fail."""
    root = build_tree(tmp_path, SEEING_GATE, anchor_src=SEEING_GATE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "INERT", result.stdout
    assert result.returncode == 1


def test_an_absent_gate_is_unresolved_not_blind(tmp_path: Path) -> None:
    """UNRESOLVED and BLIND present identically and need opposite responses: one
    says the gate broke, the other says the control is pointed at something that
    is not here. Collapsing them turns every stale checkout into a gate alarm."""
    root = build_tree(tmp_path, SEEING_GATE)
    control = json.loads((root / "controls" / "toy" / "control.json").read_text(encoding="utf-8"))
    control["gate"] = "scripts/not-here.py"
    (root / "controls" / "toy" / "control.json").write_text(json.dumps(control), encoding="utf-8")
    (root / "scripts" / "toy-gate.py").unlink()
    (root / "scripts" / "shim.py").write_text(
        "#: NEGATIVE-CONTROL: controls/toy\n", encoding="utf-8"
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout


def test_a_missing_anchor_file_is_unresolved(tmp_path: Path) -> None:
    root = build_tree(tmp_path, SEEING_GATE)
    (root / "controls" / "toy" / "anchors" / "deadbee-toy.py").unlink()
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout


def test_no_registration_anywhere_is_unchecked_not_clean(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "plain.py").write_text("print(1)\n", encoding="utf-8")
    result = run_harness(tmp_path, "--strict")
    assert "UNCHECKED, not clean" in result.stdout
    assert result.returncode == 1


def test_a_tampered_anchor_reports_mismatch_and_never_ok(tmp_path: Path) -> None:
    """Provenance is a separate axis and may never be softened into ok."""
    root = build_tree(tmp_path, SEEING_GATE)
    anchor = root / "controls" / "toy" / "anchors" / "deadbee-toy.py"
    anchor.write_text(BLIND_GATE + "# tampered\n", encoding="utf-8")
    result = run_harness(root, "--verify-provenance")
    assert provenance_of(result.stdout) == "MISMATCH", result.stdout


def test_provenance_is_unverified_when_not_asked_for(tmp_path: Path) -> None:
    """`unverified` must never print as `ok` - the same rule as unknown is not 0."""
    root = build_tree(tmp_path, SEEING_GATE)
    result = run_harness(root)
    assert provenance_of(result.stdout) == "unverified", result.stdout


# --------------------------------------------------------------------------- #
# A one-sided control tests nothing, and must not be able to say PASS (#924,
# Codex pre-PR review). Both of these produced PASS with exit 0 before the fix:
# the harness required only a NON-EMPTY case list, so its summary line - "N
# control(s) discriminate" - claimed more than its input population supported.
# That is this issue's own defect class occurring inside the tool built for it.
# --------------------------------------------------------------------------- #
def test_a_control_with_no_bad_case_cannot_pass(tmp_path: Path) -> None:
    """A GOOD-only control never exercises the blindness, so it proves nothing.

    The gate here is GENUINELY BLIND and the control still reported PASS.
    """
    root = build_tree(
        tmp_path, BLIND_GATE,
        cases=[{"name": "good", "input": "cases/good", "expect": "GOOD"}],
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "no BAD case" in result.stdout
    assert result.returncode == 1


def test_a_control_with_no_good_case_cannot_pass(tmp_path: Path) -> None:
    """A BAD-only control cannot tell a working gate from one wedged at "fail".

    The gate here is WEDGED AT FAIL and the control still reported PASS.
    """
    root = build_tree(
        tmp_path, WEDGED_GATE,
        cases=[{"name": "bad", "input": "cases/bad", "expect": "BAD"}],
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "no GOOD case" in result.stdout
    assert result.returncode == 1


def test_an_unrunnable_invocation_is_unresolved_not_a_gate_alarm(tmp_path: Path) -> None:
    """"The control could not run" must not present as "the gate is broken".

    A launch failure returned the same sentinel as a real BAD verdict, so an
    unrunnable invocation was scored as detection on the bad case and reported
    BLIND on the good one - an environment failure attributed to the gate, which
    is the precise UNRESOLVED-versus-BLIND collapse this file exists to prevent.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    control = json.loads((root / "controls" / "toy" / "control.json").read_text(encoding="utf-8"))
    control["invocation"] = ["definitely-not-an-interpreter-924", "{gate}", "--root", "{case}"]
    (root / "controls" / "toy" / "control.json").write_text(json.dumps(control), encoding="utf-8")
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "could not be executed" in result.stdout
    assert result.returncode == 1


def test_a_mismatched_anchor_is_not_erased_by_a_later_verified_one(tmp_path: Path) -> None:
    """Provenance may never be SOFTENED, and a second anchor is not a pardon.

    Provenance was assigned per anchor into one field, so the last anchor won and
    a MISMATCH on an earlier one vanished. Reversing the list changed the reported
    provenance on identical evidence.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    ctl = root / "controls" / "toy"
    good_anchor = json.loads((ctl / "control.json").read_text(encoding="utf-8"))["anchors"][0]

    tampered_path = ctl / "anchors" / "c0ffee-toy.py"
    tampered_path.write_text(BLIND_GATE, encoding="utf-8")
    tampered = dict(good_anchor, sha="c0ffee", path="anchors/c0ffee-toy.py",
                    sha256="0" * 64)  # a digest that cannot match

    for order, label in (([tampered, good_anchor], "mismatch first"),
                         ([good_anchor, tampered], "mismatch last")):
        control = json.loads((ctl / "control.json").read_text(encoding="utf-8"))
        control["anchors"] = order
        (ctl / "control.json").write_text(json.dumps(control), encoding="utf-8")
        result = run_harness(root)
        assert provenance_of(result.stdout) == "MISMATCH", f"{label}: {result.stdout}"


def test_a_mismatch_survives_an_early_return_later_in_the_anchor_loop(tmp_path: Path) -> None:
    """The first provenance fix was itself incomplete (#924, Codex re-review).

    Aggregating only on the success path meant that any early exit from the anchor
    loop - a later anchor that is missing, unrunnable, or not actually blind -
    reported the default `unverified` and threw away a MISMATCH already measured
    on an earlier anchor. The verdict and the provenance are separate axes, so a
    failing verdict must not silently downgrade what provenance had established.
    """
    import hashlib

    root = build_tree(tmp_path, SEEING_GATE)
    ctl = root / "controls" / "toy"
    good_anchor = json.loads((ctl / "control.json").read_text(encoding="utf-8"))["anchors"][0]

    (ctl / "anchors" / "c0ffee-toy.py").write_text(BLIND_GATE, encoding="utf-8")
    tampered = dict(good_anchor, sha="c0ffee", path="anchors/c0ffee-toy.py", sha256="0" * 64)

    missing = dict(good_anchor, sha="absent0", path="anchors/absent0-toy.py")

    seeing = ctl / "anchors" / "beefbee-toy.py"
    seeing.write_text(SEEING_GATE, encoding="utf-8")
    not_blind = dict(good_anchor, sha="beefbee", path="anchors/beefbee-toy.py",
                     sha256=hashlib.sha256(seeing.read_bytes()).hexdigest())

    for anchors, expected, label in (
        ([tampered, missing], "UNRESOLVED", "second anchor absent from the checkout"),
        ([tampered, not_blind], "INERT", "second anchor catches the known-bad input"),
    ):
        control = json.loads((ctl / "control.json").read_text(encoding="utf-8"))
        control["anchors"] = anchors
        (ctl / "control.json").write_text(json.dumps(control), encoding="utf-8")
        result = run_harness(root)
        assert verdict_of(result.stdout) == expected, f"{label}: {result.stdout}"
        assert provenance_of(result.stdout) == "MISMATCH", f"{label}: {result.stdout}"


# --------------------------------------------------------------------------- #
# The load-bearing test: the real #906 demonstration, executed.
# --------------------------------------------------------------------------- #
def test_the_real_control_discriminates_and_its_anchor_is_blind() -> None:
    """Issue #924's acceptance, run rather than asserted.

    The real gate must report the known-bad fixture BAD and the known-good
    fixture GOOD, and the vendored c6df826 artifact must MISS the known-bad one -
    which is what makes this control load-bearing rather than decorative.
    """
    result = run_harness(ROOT, "--strict")
    assert verdict_of(result.stdout) == "PASS", result.stdout
    assert "missed the known-bad input" in result.stdout
    assert result.returncode == 0


def test_the_real_anchor_is_blind_to_the_fixture_the_current_gate_catches() -> None:
    """The discrimination itself, measured directly rather than through the harness.

    This is the #906 claim executed: one fixture, both gates, opposite verdicts.
    """
    bad = REAL_CONTROL / "cases" / "bad-direct-invocation"
    anchor = REAL_CONTROL / "anchors" / "c6df826-check-test-binary-guards.py"
    current = subprocess.run(
        [sys.executable, str(REAL_GATE), "--root", str(bad)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    historical = subprocess.run(
        [sys.executable, str(anchor), "--root", str(bad)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert current.returncode == 1, f"current gate should flag the fixture: {current.stdout}"
    assert historical.returncode == 0, f"c6df826 should MISS it: {historical.stdout}"


@requires_git
def test_the_vendored_anchor_is_byte_identical_to_its_recorded_commit() -> None:
    """Provenance, verified rather than asserted - where git exists to verify it."""
    control = json.loads((REAL_CONTROL / "control.json").read_text(encoding="utf-8"))
    anchor_spec = control["anchors"][0]
    out = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{anchor_spec['sha']}:{anchor_spec['origin']}"],
        capture_output=True, timeout=30, check=False,
    )
    if out.returncode != 0:
        pytest.skip("commit not present in this checkout (shallow clone)")
    vendored = (REAL_CONTROL / anchor_spec["path"]).read_bytes()
    assert out.stdout == vendored, "the vendored anchor is not what its recorded sha contains"

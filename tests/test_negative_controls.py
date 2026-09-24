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

import contextlib
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
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


def control_block(out: str, gate: str) -> str:
    """The harness output for ONE control, from its GATE line to its VERDICT.

    Added for the coupling fix: several tests asserted WHOLE-BATTERY PASS as a
    proxy for a claim about one control, so a single absent binary (gitleaks,
    2026-09-15) broke three tests that had nothing to do with it, and the failure
    named the wrong subject. Scoping the assertion to the control under test is
    what stops any future UNSIGNALLED control breaking tests that do not care
    about it.
    """
    block, collecting = [], False
    for line in out.splitlines():
        if line.startswith("NEGATIVE_CONTROL_GATE: "):
            collecting = line.split(": ", 1)[1] == gate
        if collecting:
            block.append(line)
            if line.startswith("NEGATIVE_CONTROL_VERDICT: "):
                break
    return "\n".join(block)


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
#: The pattern the toy manifests declare as the toy gates' detection signal.
#: Since #946 a BAD verdict needs the gate to have SAID something, so the
#: synthetic gates print a finding line rather than only setting an exit code.
TOY_SIGNAL = r"^toy-gate: [0-9]+ finding"

SEEING_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "BAD").exists():
    print("toy-gate: 1 finding(s)")
    sys.exit(1)
sys.exit(0)
"""

BLIND_GATE = """#!/usr/bin/env python3
import sys
#: NEGATIVE-CONTROL: controls/toy
sys.exit(0)
"""

#: The marker the toy manifests declare for a REFUSAL (issue #1129). A gate that
#: could not look says so in its own words, and a case may now register that it
#: must - so the harness has to tell this apart from a finding and from a crash,
#: which is what the gates below are for.
TOY_UNKNOWN = r"^toy-gate: UNKNOWN - "

#: Three branches, like every real gate here: it found something, it found
#: nothing, or the INPUT defeated it. The third fires on a case tree rather than
#: on this machine, which is what makes it registrable at all - contrast
#: UNAVAILABLE_GATE below, whose tool is absent on every input.
#:
#: Chatty on the clean path ON PURPOSE, so a pattern anchored on its ok line is
#: available to the "must not match a clean run" test without a second gate.
REFUSING_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "UNEXAMINABLE").exists():
    print("toy-gate: UNKNOWN - this input cannot be examined; 0 examined is not 0 findings.",
          file=sys.stderr)
    sys.exit(3)
if (root / "tests" / "BAD").exists():
    print("toy-gate: 1 finding(s)")
    sys.exit(1)
print("toy-gate: ok - nothing found")
sys.exit(0)
"""

#: THE FAILURE THE REFUSAL BRANCH EXISTS TO PREVENT: it reports a confident
#: CLEAN about a population it could not examine. Identical to REFUSING_GATE in
#: every other branch, so the pair establishes which one the harness is reading.
FALSE_CLEAN_ON_UNKNOWN_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "UNEXAMINABLE").exists():
    print("toy-gate: ok - nothing found")
    sys.exit(0)
if (root / "tests" / "BAD").exists():
    print("toy-gate: 1 finding(s)")
    sys.exit(1)
print("toy-gate: ok - nothing found")
sys.exit(0)
"""

#: Issue #946 re-created inside the field #1129 adds. It FALLS OVER where it was
#: registered to refuse. A crash and a refusal both exit non-zero and neither
#: prints the detection signal, so a harness scoring a registered UNKNOWN case on
#: the exit code alone calls this gate correct - which is the exact blindness the
#: committed anchor in controls/check-negative-controls-unknown embodies.
CRASH_ON_UNKNOWN_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "UNEXAMINABLE").exists():
    raise ZeroDivisionError("the gate fell over instead of refusing")
if (root / "tests" / "BAD").exists():
    print("toy-gate: 1 finding(s)")
    sys.exit(1)
print("toy-gate: ok - nothing found")
sys.exit(0)
"""

#: An anchor must AGREE on a refusal exactly as it must agree on a clean run, so
#: this one REFUSES the unexaminable input and stays blind to the known-bad one.
#: Blind in one named way and identical in every other.
BLIND_BUT_REFUSING_ANCHOR = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "UNEXAMINABLE").exists():
    print("toy-gate: UNKNOWN - this input cannot be examined.", file=sys.stderr)
    sys.exit(3)
print("toy-gate: ok - nothing found")
sys.exit(0)
"""

#: Blind to the REFUSAL as well as to the finding: it reports clean everywhere.
#: That is a second difference from the current gate, so the demonstration is no
#: longer isolated - INERT, by the same rule a GOOD-case disagreement triggers.
BLIND_TO_REFUSAL_ANCHOR = """#!/usr/bin/env python3
import sys
#: NEGATIVE-CONTROL: controls/toy
print("toy-gate: ok - nothing found")
sys.exit(0)
"""

#: Ambiguous on the refusal: it prints BOTH its refusal marker and its detection
#: line on the unexaminable input. The current gate is refused for exactly this
#: (a refusal and a finding cannot be the same evidence), and an anchor is a
#: DIFFERENT program, so the gate-side check says nothing about it.
AMBIGUOUS_ON_REFUSAL_ANCHOR = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "UNEXAMINABLE").exists():
    print("toy-gate: UNKNOWN - this input cannot be examined.", file=sys.stderr)
    print("toy-gate: 1 finding(s)")
    sys.exit(3)
print("toy-gate: ok - nothing found")
sys.exit(0)
"""

#: IT VALIDATES ITS INPUT BEFORE CHECKING ITS TOOL, which is not a contrivance:
#: `scripts/shellcheck-gate.sh` does exactly this, refusing a non-directory
#: `--root` on line 52 and only testing `command -v shellcheck` on line 53. So on
#: a host without the tool, a case whose input is refused by that first check
#: reports a REFUSAL while every other case reports the tool absent.
REFUSES_BEFORE_CHECKING_ITS_TOOL_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "UNEXAMINABLE").exists():
    print("toy-gate: UNKNOWN - this input cannot be examined; 0 examined is not 0 findings.",
          file=sys.stderr)
    sys.exit(3)
print("toy-gate: UNAVAILABLE - the toy tool is not installed, so nothing was examined.",
      file=sys.stderr)
sys.exit(3)
"""

#: Contradictory on the known-BAD input: it announces a refusal and then exits
#: like a CLEAN run. Neither reading survives - it cannot have examined the input
#: and also have been unable to look at it.
CLEAN_BUT_REFUSING_ON_BAD_ANCHOR = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "UNEXAMINABLE").exists():
    print("toy-gate: UNKNOWN - this input cannot be examined.", file=sys.stderr)
    sys.exit(3)
print("toy-gate: UNKNOWN - this input cannot be examined.", file=sys.stderr)
sys.exit(0)
"""

#: The same contradiction moved to the known-GOOD input, so it is reached in the
#: anchor-SANITY loop rather than the known-bad one. It misses the known-bad
#: input correctly, which is what makes the sanity loop the only thing that can
#: catch it.
CLEAN_BUT_REFUSING_ON_GOOD_ANCHOR = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "UNEXAMINABLE").exists():
    print("toy-gate: UNKNOWN - this input cannot be examined.", file=sys.stderr)
    sys.exit(3)
if (root / "tests" / "BAD").exists():
    print("toy-gate: ok - nothing found")
    sys.exit(0)
print("toy-gate: UNKNOWN - this input cannot be examined.", file=sys.stderr)
sys.exit(0)
"""

#: An anchor that REFUSES the known-bad input. It did not CATCH anything, so
#: calling it INERT would accuse a sound artifact of being load-bearing; the
#: required property is simply not established.
REFUSES_THE_BAD_INPUT_ANCHOR = """#!/usr/bin/env python3
import sys
#: NEGATIVE-CONTROL: controls/toy
print("toy-gate: UNKNOWN - this input cannot be examined.", file=sys.stderr)
sys.exit(3)
"""

#: The registration a gate with a refusal branch carries: GOOD and BAD are still
#: required (a one-sided control tests nothing), and the refusal is ADDITIONAL.
UNKNOWN_CASES = [
    {"name": "bad", "input": "cases/bad", "expect": "BAD"},
    {"name": "good", "input": "cases/good", "expect": "GOOD"},
    {"name": "unknown", "input": "cases/unknown", "expect": "UNKNOWN"},
]

#: Wedged at "fail": it reports a finding on EVERY input, the known-good one
#: included. It prints the signal because that is what a stuck gate does - the
#: good case is what separates it from a working one, not the signal.
WEDGED_GATE = """#!/usr/bin/env python3
import sys
#: NEGATIVE-CONTROL: controls/toy
print("toy-gate: 1 finding(s)")
sys.exit(1)
"""

#: Issue #946, reproduced: it FALLS OVER on the known-bad input instead of
#: reporting it, and Python exits 1 on an uncaught exception - the same code the
#: seeing gate uses for detection. Scored on the exit code alone this is
#: indistinguishable from a working gate, and the harness printed PASS.
CRASHING_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "BAD").exists():
    raise FileNotFoundError("the gate fell over instead of reporting a finding")
sys.exit(0)
"""

#: The other half of the same blindness: it detects correctly, then falls over on
#: the known-GOOD input. On the exit code alone that reads as "flagged a
#: known-good input" - a false-alarm diagnosis for a gate that is crashing.
CRASH_ON_GOOD_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "BAD").exists():
    print("toy-gate: 1 finding(s)")
    sys.exit(1)
raise RuntimeError("the gate fell over on the known-good input")
"""


#: Reports on BOTH runs, as most real gates do - `binary-guards: ok - ...` on a
#: clean tree and `binary-guards: N unguarded test(s)` on a dirty one. A signal
#: anchored on the shared prefix alone matches the clean run too, and therefore
#: identifies nothing.
CHATTY_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "BAD").exists():
    print("toy-gate: 1 finding(s)")
    sys.exit(1)
print("toy-gate: ok - nothing found")
sys.exit(0)
"""


#: Issue #1117. Its tool is not installed, so it says so and exits non-zero on
#: EVERY input - which is what an absent binary does. Before the UNAVAILABLE
#: verdict this scored UNSIGNALLED: an accusation about the gate for a fact about
#: the machine.
TOY_UNAVAILABLE = r"^toy-gate: UNAVAILABLE - the toy tool is not installed"

UNAVAILABLE_GATE = """#!/usr/bin/env python3
import sys
#: NEGATIVE-CONTROL: controls/toy
print("toy-gate: UNAVAILABLE - the toy tool is not installed", file=sys.stderr)
sys.exit(3)
"""

#: The contradiction the cross-case check exists for: unavailable on the known-bad
#: input and CLEAN on the known-good one. No missing binary produces that - it is
#: what a pattern loose enough to match a genuine finding looks like on a host
#: where the tool IS present.
UNAVAILABLE_ON_BAD_ONLY_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "BAD").exists():
    print("toy-gate: UNAVAILABLE - the toy tool is not installed", file=sys.stderr)
    sys.exit(3)
sys.exit(0)
"""

#: THE REAL jq SHAPE, synthesised. `flow-driver-retirement-check.sh` declares
#: `^RETIREMENT: (blocked|unknown)\b` as its detection signal - correctly, since
#: for that gate an `unknown` verdict IS the finding a caller must not delete on
#: - and reports a missing jq as `RETIREMENT: unknown - jq is not installed`. So
#: its unavailability message is a MEMBER of its own detection pattern, and no
#: refinement of the detection pattern separates them. This is the specimen that
#: decides the order the two signals are consulted in.
TOY_OVERLAPPING_DETECT = r"^toy-gate: (finding|unknown)\b"
TOY_OVERLAPPING_UNAVAILABLE = r"^toy-gate: unknown - the toy tool is not installed"

OVERLAPPING_UNAVAILABLE_GATE = """#!/usr/bin/env python3
import sys
#: NEGATIVE-CONTROL: controls/toy
print("toy-gate: unknown - the toy tool is not installed")
sys.exit(3)
"""

#: The counter-model finding, as a fixture: it DETECTS its known-bad input
#: correctly and then claims its tool is absent on the known-good one. The tool
#: was demonstrably present - it just ran and found something - so the
#: unavailability claim cannot be about a missing binary. The first cut of the
#: cross-case check counted only CLEAN runs as proof the gate ran and therefore
#: saw no contradiction here at all.
DETECTS_THEN_UNAVAILABLE_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "BAD").exists():
    print("toy-gate: 1 finding(s)")
    sys.exit(1)
print("toy-gate: UNAVAILABLE - the toy tool is not installed", file=sys.stderr)
sys.exit(3)
"""

#: Prints the unavailability wording on its CLEAN run too, so the declared
#: pattern would report a working gate as unexaminable. The mirror of
#: CHATTY_GATE, one field over.
CHATTY_UNAVAILABLE_GATE = """#!/usr/bin/env python3
import sys
from pathlib import Path
#: NEGATIVE-CONTROL: controls/toy
root = Path(sys.argv[sys.argv.index("--root") + 1])
if (root / "tests" / "BAD").exists():
    print("toy-gate: 1 finding(s)")
    sys.exit(1)
print("toy-gate: UNAVAILABLE - the toy tool is not installed")
sys.exit(0)
"""


def build_tree(
    tmp_path: Path,
    gate_src: str,
    anchor_src: str | None = BLIND_GATE,
    cases: list[dict[str, str]] | None = None,
    detect_signal: str | None = TOY_SIGNAL,
    unavailable_signal: str | None = None,
    unknown_signal: str | None = None,
) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "toy-gate.py").write_text(gate_src, encoding="utf-8")
    ctl = tmp_path / "controls" / "toy"
    (ctl / "cases" / "bad" / "tests").mkdir(parents=True)
    (ctl / "cases" / "good" / "tests").mkdir(parents=True)
    (ctl / "cases" / "bad" / "tests" / "BAD").write_text("x", encoding="utf-8")
    # Always materialised, registered only when a test passes UNKNOWN_CASES
    # (issue #1129). An unregistered directory is never invoked, so this costs
    # the existing tests nothing and keeps the third case tree in one place.
    (ctl / "cases" / "unknown" / "tests").mkdir(parents=True)
    (ctl / "cases" / "unknown" / "tests" / "UNEXAMINABLE").write_text("x", encoding="utf-8")
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
    manifest: dict[str, object] = {
        "gate": "scripts/toy-gate.py",
        "invocation": [sys.executable, "{gate}", "--root", "{case}"],
        "good_exit": 0,
        "cases": cases if cases is not None else [
            {"name": "bad", "input": "cases/bad", "expect": "BAD"},
            {"name": "good", "input": "cases/good", "expect": "GOOD"},
        ],
        "anchors": anchors,
    }
    if detect_signal is not None:
        manifest["detect_signal"] = detect_signal
    if unavailable_signal is not None:
        manifest["unavailable_signal"] = unavailable_signal
    if unknown_signal is not None:
        manifest["unknown_signal"] = unknown_signal
    (ctl / "control.json").write_text(json.dumps(manifest), encoding="utf-8")
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
    known-bad check on its own, and only the good case separates the two.

    This also pins an ownership boundary the #946 signal checks could blur. A
    wedged gate prints its finding line on the known-GOOD input, which is
    exactly what "the declared signal also matches a clean run" looks like - and
    the first cut of that refusal fired here, blaming a correct manifest for a
    broken gate. The gate's CLEAN EXIT is what separates them, and this test is
    what catches the day someone drops that condition.
    """
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
# A CRASH IS NOT A DETECTION (#946). The harness scored a case on the exit code
# alone, so a gate that fell over on the known-bad input was scored identically
# to one that reported it - provided the crash exited with anything but
# `good_exit`. `check-test-binary-guards` exits 1 when it finds something and 1
# when it raises, so for the one control that existed the two were not separable
# at all, and the harness printed PASS plus "1 control(s) discriminate" for a
# gate that discriminated nothing. The first four tests below are the committed
# negative control this instrument owes its own rule.
# --------------------------------------------------------------------------- #
def test_a_gate_that_crashes_on_the_known_bad_input_is_not_a_pass(tmp_path: Path) -> None:
    """The issue's own reproduction, executed.

    Before the fix this printed `NEGATIVE_CONTROL_VERDICT: PASS` and exited 0.
    """
    root = build_tree(tmp_path, CRASHING_GATE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNSIGNALLED", result.stdout
    assert result.returncode == 1
    assert "FileNotFoundError" in result.stdout, result.stdout


def test_a_crash_on_the_known_good_input_is_not_reported_as_a_false_alarm(tmp_path: Path) -> None:
    """A crashing gate must not be diagnosed as one that flagged a good input.

    Both send a reader to the wrong place: "it flagged a known-good input" is a
    hunt through the detection logic, and the gate is simply throwing.
    """
    root = build_tree(tmp_path, CRASH_ON_GOOD_GATE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNSIGNALLED", result.stdout
    assert "flagged a known-good input" not in result.stdout, result.stdout
    assert result.returncode == 1


def test_an_anchor_that_crashes_is_unresolved_not_inert(tmp_path: Path) -> None:
    """The same misscore on the other side of the loop.

    An anchor is required to MISS the known-bad input. One that CRASHES on it
    exits non-zero and was therefore read as having CAUGHT it - INERT, which
    accuses a healthy anchor of not being blind. It is still a red, but it is
    the wrong red: the anchor cannot be confirmed to have missed anything.
    """
    root = build_tree(tmp_path, SEEING_GATE, anchor_src=CRASHING_GATE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "CAUGHT the known-bad input" not in result.stdout, result.stdout
    assert result.returncode == 1


def test_a_control_with_no_detect_signal_cannot_pass(tmp_path: Path) -> None:
    """The field is REQUIRED, and its absence is a red rather than a fallback.

    An optional signal would leave every control that omits it scored exactly as
    it was before the fix, which is the fail-open this issue exists to close.
    The gate here DISCRIMINATES perfectly - the refusal is about the manifest.
    """
    root = build_tree(tmp_path, SEEING_GATE, detect_signal=None)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "detect_signal" in result.stdout, result.stdout
    assert result.returncode == 1


def test_an_unusable_detect_signal_is_unresolved_not_a_silent_never_match(tmp_path: Path) -> None:
    """A regex that does not compile must not degrade into "nothing matched".

    Silently treating it as a pattern that never matches turns every BAD case
    into UNSIGNALLED - a red with an unrelated diagnosis - and an empty string
    matches everything, which restores the exit-code-only scoring wholesale.
    """
    for signal, label in ((r"(unclosed", "uncompilable"), ("", "empty")):
        (tmp_path / label).mkdir()
        root = build_tree(tmp_path / label, SEEING_GATE, detect_signal=signal)
        result = run_harness(root, "--strict")
        assert verdict_of(result.stdout) == "UNRESOLVED", f"{label}: {result.stdout}"
        assert "detect_signal" in result.stdout, f"{label}: {result.stdout}"


def test_a_signal_that_matches_the_empty_string_is_refused(tmp_path: Path) -> None:
    """`.*` and a trailing `|` compile fine and match ANYTHING, silence included.

    Rejecting only the empty STRING left the empty-MATCHING patterns, which make
    every non-zero exit a detection again - the pre-#946 scoring restored
    wholesale, wearing the fix's own field name. Both were measured producing
    `PASS` with a gate that crashed on the known-bad input and said nothing.
    Found by the Codex cross-model review of this change.
    """
    for signal, label in ((r".*", "dot-star"), (r"toy-gate: [0-9]+ finding|", "empty-alternation")):
        (tmp_path / label).mkdir()
        root = build_tree(tmp_path / label, CRASHING_GATE, detect_signal=signal)
        result = run_harness(root, "--strict")
        assert verdict_of(result.stdout) == "UNRESOLVED", f"{label}: {result.stdout}"
        assert "detect_signal" in result.stdout, f"{label}: {result.stdout}"
        assert result.returncode == 1, f"{label}: {result.stdout}"


def test_a_signal_that_also_matches_the_known_good_run_is_refused(tmp_path: Path) -> None:
    """The structural check has a floor; this is the one grounded in real output.

    A pattern can miss the empty string and still identify nothing - `^toy-gate`
    against a gate that prints `toy-gate: ok - nothing found` on a clean run.
    The harness already executes the known-GOOD case, so it can check the signal
    against that output instead of trusting the manifest's author, which is the
    same two-sided property the real control asserts for its own regex.
    """
    root = build_tree(tmp_path, CHATTY_GATE, detect_signal=r"^toy-gate")
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "known-GOOD" in result.stdout, result.stdout
    assert result.returncode == 1


def test_a_chatty_gate_with_a_specific_signal_still_passes(tmp_path: Path) -> None:
    """The positive half: the refusal above must not reject a correct manifest.

    Same gate, same clean-run chatter, a signal that names what only a finding
    prints. Without this, "refuse a loose signal" and "refuse every signal" look
    identical from the outside.
    """
    root = build_tree(tmp_path, CHATTY_GATE, detect_signal=r"^toy-gate: [0-9]+ finding")
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "PASS", result.stdout
    assert result.returncode == 0


def test_the_summary_line_states_the_signal_it_checked(tmp_path: Path) -> None:
    """The green may not claim only what it used to claim (detector contracts).

    The success message asserts what the run established; after #946 that
    includes the gate having reported its declared signal, so the message says
    so rather than leaving a reader to assume the old, weaker check.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "PASS", result.stdout
    assert "signal" in result.stdout.rsplit("negative-controls: ok", 1)[-1], result.stdout


# --------------------------------------------------------------------------- #
# The load-bearing test: the real #906 demonstration, executed.
# --------------------------------------------------------------------------- #
def test_the_real_control_discriminates_and_its_anchor_is_blind() -> None:
    """Issue #924's acceptance, run rather than asserted.

    The real gate must report the known-bad fixture BAD and the known-good
    fixture GOOD, and the vendored c6df826 artifact must MISS the known-bad one -
    which is what makes this control load-bearing rather than decorative.
    """
    # Scoped to THIS control rather than the whole battery (see `control_block`).
    # The docstring's claim is about check-test-binary-guards and its c6df826
    # anchor; asserting battery-wide PASS made an unrelated control's UNSIGNALLED
    # read as a failure of this one. No `--strict`: the exit code is a property of
    # every control, not of this one.
    result = run_harness(ROOT)
    block = control_block(result.stdout, "scripts/check-test-binary-guards.py")
    assert block, f"this control is not in the register at all\n{result.stdout}"
    assert verdict_of(block) == "PASS", block
    assert "missed the known-bad input" in block, block


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


def test_the_real_detect_signal_fires_on_the_bad_fixture_and_not_on_the_good_one() -> None:
    """The declared signal, measured against the real gate on both fixtures.

    One-sided is not enough in either direction. A pattern that never matches
    makes every detection an UNSIGNALLED red; a pattern that matches everything
    (`.`, or an accidental empty alternation) restores the exit-code-only
    scoring while looking like a fix. So the regex is asserted to be present in
    the bad-case output AND absent from the good-case output.
    """
    control = json.loads((REAL_CONTROL / "control.json").read_text(encoding="utf-8"))
    signal = re.compile(control["detect_signal"], re.MULTILINE)

    outputs = {}
    for name in ("bad-direct-invocation", "good-direct-invocation"):
        proc = subprocess.run(
            [sys.executable, str(REAL_GATE), "--root", str(REAL_CONTROL / "cases" / name)],
            capture_output=True, text=True, timeout=120, check=False,
        )
        outputs[name] = proc.stdout + proc.stderr

    assert signal.search(outputs["bad-direct-invocation"]), (
        f"the declared signal never fires: {outputs['bad-direct-invocation']}"
    )
    assert not signal.search(outputs["good-direct-invocation"]), (
        f"the declared signal matches a clean run too: {outputs['good-direct-invocation']}"
    )


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


# --------------------------------------------------------------------------- #
# The harness's own registration (issue #964).
#
# ADR 0008 hands the living list of instruments to the controls/ register, so the
# tool that MAINTAINS the register being absent from it made the register
# unreadable as a coverage map. Registering it closes that, and introduces a
# self-reference whose exact boundary is pinned by the three tests below rather
# than argued in prose.
# --------------------------------------------------------------------------- #

SELF_CONTROL = ROOT / "controls" / "check-negative-controls"
SELF_ANCHOR = SELF_CONTROL / "anchors" / "3a90f96-check-negative-controls.py"



def _verdicts_by_gate(out: str) -> dict[tuple[str, str], str]:
    """Pair each (GATE, CONTROL) with the VERDICT that follows it.

    KEYED ON BOTH, and the second half is not cosmetic (issue #1061). A gate may
    carry several registrations - #986 made discovery see them all and #1117
    added the CONTROL line precisely so two controls on one gate stop being
    byte-identical in their only identifying field. Keyed on the gate alone this
    dict silently OVERWRITES: measured against the real register on 2026-09-21,
    44 rows collapsed to 36, so 8 verdicts were discarded before any assertion
    could read them - and `scripts/check-negative-controls.py`, the row this
    file's own demonstration is about, was one of the gates being collapsed.
    A whole-register claim built on it was a claim about whichever registration
    happened to be printed last.
    """
    pairs: dict[tuple[str, str], str] = {}
    gate = None
    control = ""
    for line in out.splitlines():
        if line.startswith("NEGATIVE_CONTROL_GATE: "):
            gate, control = line.split(": ", 1)[1], ""
        elif line.startswith("NEGATIVE_CONTROL_CONTROL: "):
            control = line.split(": ", 1)[1]
        elif line.startswith("NEGATIVE_CONTROL_VERDICT: ") and gate is not None:
            pairs[(gate, control)] = line.split(": ", 1)[1]
            gate = None
    return pairs


@requires_git
def test_every_file_of_the_self_registration_is_tracked() -> None:
    """The control is only real in a CLEAN CHECKOUT, and .gitignore hides it.

    `.gitignore` carries a blanket `*.json` with a `!controls/*/control.json`
    negation that is ONE level deep. The nested case trees put their manifests
    at `controls/<x>/cases/<y>/controls/toy/control.json`, which that negation
    does not reach, so they were silently untracked and every local run passed
    on files a clean checkout would not have. Codex found it; a clean clone
    reported the self-registration BLIND.

    This asserts every file under the control directory is tracked, so a future
    nested case added and forgotten fails loudly here rather than in CI, or
    worse, passes locally forever.
    """
    tracked = set(subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "controls/check-negative-controls"],
        capture_output=True, text=True, check=True,
    ).stdout.split())
    on_disk = {
        str(p.relative_to(ROOT))
        for p in SELF_CONTROL.rglob("*")
        if p.is_file()
    }
    assert on_disk, "the control directory is empty; this test is vacuous"
    missing = sorted(on_disk - tracked)
    assert not missing, (
        "these files exist locally but are NOT tracked, so a clean checkout "
        f"gets a broken control: {missing}"
    )

def test_discover_is_not_recursive_so_nested_case_trees_are_not_double_discovered() -> None:
    """The self-registration nests whole repos under controls/.

    `discover()` walks `<root>/scripts` with `iterdir()`, which is not
    recursive, so the toy gates inside the nested case trees are never picked up
    by the outer run. #964 asked for this to be asserted rather than assumed,
    because if it were ever made recursive the outer run would start evaluating
    the fixtures as though they were real repository instruments.
    """
    nested_gates = sorted(SELF_CONTROL.glob("cases/*/scripts/toy-gate.sh"))
    assert nested_gates, "the nested fixtures moved; this test is now vacuous"
    for gate in nested_gates:
        assert "#: NEGATIVE-CONTROL:" in gate.read_text(encoding="utf-8"), (
            f"{gate} must carry a directive, or it cannot demonstrate the hazard"
        )

    result = run_harness(ROOT, "--quiet")
    discovered = [
        line.split(": ", 1)[1]
        for line in result.stdout.splitlines()
        if line.startswith("NEGATIVE_CONTROL_GATE: ")
    ]
    assert discovered, result.stdout
    assert "scripts/check-negative-controls.py" in discovered, (
        "the harness is not in its own register - deleting the directive must "
        f"fail this test, not pass it quietly. discovered={discovered}"
    )
    for gate in discovered:
        assert "/cases/" not in gate, (
            f"discover() reached a nested fixture ({gate}); it is no longer "
            "confined to <root>/scripts and the register now contains fixtures"
        )


def test_the_self_registration_anchor_is_blind_rather_than_crashing() -> None:
    """#964 condition: an anchor that CRASHES also differs from the current
    harness, and only one of those two differences is a control.

    A traceback and a blind PASS both produce "not what the current gate says",
    so an anchor that errored on the fixture would satisfy a naive difference
    check while demonstrating nothing. This asserts the anchor's PASS is its
    BLINDNESS: a real verdict, exit 0, no traceback. It is #963's "a crash is
    not a detection" applied to the anchor side.
    """
    bad_case = SELF_CONTROL / "cases" / "bad-crashing-gate"
    anchor_run = subprocess.run(
        [sys.executable, str(SELF_ANCHOR), "--root", str(bad_case), "--strict"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert anchor_run.returncode == 0, (
        "the anchor must MISS the known-bad input cleanly; a non-zero exit means "
        f"it errored rather than being blind:\n{anchor_run.stderr}"
    )
    assert "Traceback" not in anchor_run.stderr, anchor_run.stderr
    assert verdict_of(anchor_run.stdout) == "PASS", anchor_run.stdout

    # and the current harness must NOT agree, or there is no discrimination
    current = run_harness(bad_case, "--strict")
    assert verdict_of(current.stdout) == "UNSIGNALLED", current.stdout
    assert current.returncode == 1



# --------------------------------------------------------------------------- #
# The live controls tree is a SHARED MUTABLE RESOURCE between tests (#1061)
# --------------------------------------------------------------------------- #

#: Keyed on ROOT so two worktrees of this repo do not serialise against each
#: other - they have separate trees and cannot collide.
_LIVE_TREE_LOCK = Path(tempfile.gettempdir()) / (
    "cpp-live-controls-" + hashlib.sha256(str(ROOT).encode()).hexdigest()[:12] + ".lock"
)


#: `errno` values that mean SOMEBODY ELSE HOLDS IT. Everything else is a fault.
_CONTENDED = frozenset({errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK})

#: pyproject sets `timeout = 120` per test, so a lock deadline above that can
#: NEVER fire - pytest kills the test first and the careful diagnostic below is
#: unreachable by construction (#1061 counter-model re-review, MEDIUM). The two
#: callers raise their own budget with `@pytest.mark.timeout` to cover waiting
#: for the lock AND doing the work; this deadline stays comfortably inside that
#: raised budget so the lock's explanation is what the reader gets.
_LOCK_BUDGET = 150.0
_TEST_BUDGET = 300


@contextlib.contextmanager
def live_controls_tree_exclusive(timeout: float = _LOCK_BUDGET) -> Iterator[None]:
    """Hold the live `controls/` tree exclusively for the duration.

    WHY A LOCK AND NOT A MARKER (issue #1061). Two tests in this file use the
    REAL tree and one of them DIRTIES it: `test_an_untracked_control_file_
    refuses_the_green` plants an untracked probe for ~19 seconds because a
    committed one would be tracked and the case would stop reproducing. Anything
    else scanning the tree in that window sees a control that does not exist in
    a clean clone - which is true, and nothing to do with that scanner's
    subject. `Makefile:155` runs `pytest -n` with no `--dist`, so xdist's
    default `load` splits same-file tests across workers and the two overlap.

    `--dist loadfile` or an xdist_group marker would also serialise them, but
    both are suite-wide switches in files this change does not own, and both
    would serialise every same-file pair to fix one. flock is process-level, so
    it works across xdist workers, and the kernel releases it when the holder
    dies - a crashed worker cannot wedge the suite.

    THE TIMEOUT FAILS LOUDLY RATHER THAN PROCEEDING. Waiting forever would turn
    a deadlock into a hung CI job with no diagnosis; proceeding anyway would
    reintroduce exactly the race this exists to remove, silently and only under
    load - the worst of the three outcomes.
    """
    deadline = time.monotonic() + timeout
    fh = os.open(_LIVE_TREE_LOCK, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                # CONTENTION ONLY. Catching every OSError made a LOCKING-SYSTEM
                # failure - ENOLCK, say - report as "another test held the lock
                # too long", blaming a neighbour for a fault that is not theirs
                # and discarding the real errno on the way (#1061 counter-model
                # re-review, LOW). Anything that is not contention propagates
                # with its own cause intact.
                if exc.errno not in _CONTENDED:
                    raise
                if time.monotonic() >= deadline:
                    raise AssertionError(
                        f"could not take the live controls tree lock within {timeout}s "
                        f"({_LIVE_TREE_LOCK}); another test is holding it far longer "
                        "than its ~20s window, which is a defect in that test, not here"
                    ) from None
                time.sleep(0.2)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
    finally:
        os.close(fh)


def _forced_pass_harness(tmp_path: Path) -> Path:
    """The harness with every verdict assignment forced to PASS.

    This is the breakage the self-registration is structurally blind to: not a
    detection failure, but the harness losing the ability to say anything except
    'fine'.
    """
    src = HARNESS.read_text(encoding="utf-8")
    mutated = re.sub(r"res\.verdict = [A-Z_]+", "res.verdict = PASS", src)
    mutated = mutated.replace("verdict=UNRESOLVED", "verdict=PASS")
    assert mutated != src, "the mutation matched nothing; this test is vacuous"
    out = tmp_path / "mutant-check-negative-controls.py"
    out.write_text(mutated, encoding="utf-8")
    return out


def _untracked_gates(out: str) -> dict[tuple[str, str], str]:
    """Gates whose control is UNTRACKED, paired with the detail that names the path.

    The harness prints TRACKING beside every VERDICT, and the two are separate
    axes by design (#978): a control can discriminate perfectly and still not
    exist in a clean clone. This reads the axis the verdict mutation does not
    touch, so a caller can tell the two causes of a non-zero exit apart.
    """
    found: dict[tuple[str, str], str] = {}
    gate = None
    control = ""
    detail = ""
    for line in out.splitlines():
        if line.startswith("NEGATIVE_CONTROL_GATE: "):
            gate, control, detail = line.split(": ", 1)[1], "", ""
        elif line.startswith("NEGATIVE_CONTROL_CONTROL: "):
            control = line.split(": ", 1)[1]
        elif line.startswith("NEGATIVE_CONTROL_DETAIL: ") and "NOT tracked" in line:
            detail = line.split(": ", 1)[1]
        elif line.startswith("NEGATIVE_CONTROL_TRACKING: ") and gate is not None:
            if line.split(": ", 1)[1] == "UNTRACKED":
                found[(gate, control)] = detail
    return found


def _registered_count(out: str) -> int | None:
    """The denominator the harness states for itself, or None if it never said."""
    for line in out.splitlines():
        if line.startswith("NEGATIVE_CONTROL_REGISTERED: "):
            try:
                return int(line.split(": ", 1)[1])
            except ValueError:
                return None
    return None


def _classify_nonzero_exit(
    returncode: int,
    stderr: str,
    by_gate: dict[tuple[str, str], str],
    registered: int | None,
    untracked: dict[tuple[str, str], str],
) -> str:
    """WHY did the harness exit non-zero? Pure, so it is testable.

    A CRASH IS NOT A REFUSAL - the rule gate-lib.sh:399 states for its own probe,
    found here by the #1061 counter-model review (gpt-6-astra, MEDIUM). An
    UNTRACKED row establishes that TRACKING FAILED; it does not establish that
    tracking is what produced the exit. A harness killed by a signal, or dying
    with a traceback, while an untracked file HAPPENS to be present would
    otherwise be classified `tracking` and quietly skipped - a real regression
    hidden by a neighbour's mess, which is the same shape as the defect this
    whole change exists to fix, one level down.

    So completion is established FIRST and independently of the verdicts: the
    strict refusal code is exactly 1 (a signal gives a negative returncode), a
    traceback on stderr is a crash whatever the code says, and a row count short
    of the harness's own stated denominator is truncation - which would also
    make the whole-register claim above a claim about a prefix.
    """
    if returncode != 1:
        return "crash"
    if "Traceback (most recent call last)" in stderr:
        return "crash"
    if registered is None or len(by_gate) != registered:
        return "truncated"
    if any(v != "PASS" for v in by_gate.values()):
        return "verdict"
    if untracked:
        return "tracking"
    return "verdict"


@pytest.mark.timeout(_TEST_BUDGET)
def test_self_registration_is_blind_to_a_verdict_assignment_breakage(tmp_path: Path) -> None:
    """HALF ONE of #964's mutation demonstration, and the uncomfortable half.

    A harness that emits PASS unconditionally reports PASS about its OWN
    control, because the thing doing the reporting is the thing that is broken.
    The register row therefore keeps saying the harness is covered while the
    harness has stopped being able to disagree with anything.

    THE EXIT CODE CARRIES TWO CAUSES AND ONLY ONE OF THEM IS THIS TEST'S
    SUBJECT (issue #1061, found while migrating flow-finish-gate onto
    gate-lib). `main()` returns 1 when `failing` is non-empty, and
    `failing` is `r.verdict != PASS OR r.tracking == "UNTRACKED"`. The forced-
    PASS mutation rewrites the verdict assignments and deliberately does NOT
    touch tracking, so under the mutant the verdict term is empty by
    construction and the tracking term is the only thing that can produce a 1.

    That made this test red for a reason outside its own subject, and it said
    so in the worst available words: it asserted "the self-registration is not
    blind to a forced-PASS mutation", which is FALSE. The true state was "the
    live tree was dirty and I could not evaluate this". The cause was a sibling
    in this very file - `test_an_untracked_control_file_refuses_the_green`
    plants an untracked probe in the REAL tree for ~19 seconds, and
    `Makefile:155` runs `pytest -n` with no `--dist`, so xdist's default `load`
    splits same-file tests across workers. Reproduction was 2 of 2 on the full
    suite; the pair alone under `-n 2` passes, so a green from the pair proves
    nothing.

    THE TWO AXES ARE NOW REPORTED SEPARATELY rather than one being dodged. A
    channel carrying two causes must not report them as one - this wave's own
    rule, applied to a test. Note what is NOT done here: the run is not scoped
    to a single control. Scoping would silently turn the whole-tree claim below
    into a single-row one, which is trivially true and no longer the thing it
    was written to say; and it would work only by an unrecorded fact about
    WHICH control the sibling happens to dirty, so the day someone plants a
    probe elsewhere the race returns and the next person re-derives all of this
    from scratch. Detecting the axis needs neither fact.
    """
    mutant = _forced_pass_harness(tmp_path)
    # HELD FOR THE SCAN. Without this the skip below is not a fallback, it is
    # the outcome: measured on the full suite, this test skipped on EVERY run
    # because the sibling's ~19s dirty window overlaps this ~20s scan. A true
    # UNRESOLVED beats a false red, but an UNRESOLVED every time is a subject
    # that never gets exercised - a green that did not run.
    with live_controls_tree_exclusive():
        run = subprocess.run(
            [sys.executable, str(mutant), "--root", str(ROOT), "--strict"],
            capture_output=True, text=True, timeout=180, check=False,
        )
    by_gate = _verdicts_by_gate(run.stdout)
    assert by_gate, run.stdout
    own = {v for (g, _c), v in by_gate.items() if g == "scripts/check-negative-controls.py"}
    assert own, (
        "the demonstration must be about the harness's OWN row; if the "
        f"self-registration is gone this is vacuous. rows={sorted(by_gate)}"
    )
    assert own == {"PASS"}, f"the harness's own registration(s) did not all read PASS: {own}"
    # THE WHOLE-TREE CLAIM, UNNARROWED - AND WITH ITS DENOMINATOR CHECKED ON
    # EVERY EXIT, not only the non-zero one (#1061 counter-model re-review,
    # MEDIUM). "every row reads PASS" is trivially true of one row, so output
    # declaring 44 registrations while emitting a single self-registration PASS
    # used to satisfy this test on a clean tree - a parser regression that
    # collapses registrations staying green underneath the very claim it broke.
    registered = _registered_count(run.stdout)
    assert registered is not None and registered > 0, (
        f"the harness stated no registration count, so there is no denominator "
        f"for the whole-register claim below.\n{run.stdout}"
    )
    assert len(by_gate) == registered, (
        f"parsed {len(by_gate)} rows but the harness registered {registered}: the "
        "claim below would be about a prefix, not about the register.\n"
        f"{sorted(by_gate)}"
    )
    assert set(by_gate.values()) == {"PASS"}, run.stdout

    untracked = _untracked_gates(run.stdout)
    if run.returncode != 0:
        # THE SUBJECT STILL FAILS LOUDLY, and a CRASH is not a refusal. Only an
        # exit this test can attribute to the tracking axis may become
        # UNRESOLVED; everything else - a signal, a traceback, output that stops
        # short of the harness's own stated denominator, or any non-PASS row -
        # is a failure and says which. This assertion is why the skip below
        # cannot swallow a regression, whether the regression is this test's
        # subject or the harness falling over.
        why = _classify_nonzero_exit(
            run.returncode, run.stderr, by_gate, registered, untracked
        )
        assert why == "tracking", (
            f"the mutant exited {run.returncode} and the cause is {why!r}, not the "
            "#978 tracking axis. 'verdict' means the self-registration is NOT blind "
            "to a forced-PASS mutation; 'crash'/'truncated' mean the run did not "
            f"complete and nothing here can be read as evidence.\n"
            f"stderr:\n{run.stderr}\nstdout:\n{run.stdout}"
        )
        pytest.skip(
            "UNRESOLVED, not a failure of this test's subject: the live tree "
            "carries an untracked control file, so the mutant's exit code "
            "reports the #978 tracking axis rather than the verdict axis this "
            "test is about. Every verdict row read PASS, which is the half "
            f"that IS the subject and did hold. Offending: {sorted(untracked.items())}"
        )
    assert run.returncode == 0, (
        "a harness that cannot say anything but PASS exits 0 under --strict, "
        "including about itself: the self-registration cannot see this"
    )


_ROWS_OK = {("scripts/a.py", "controls/a"): "PASS", ("scripts/b.py", "controls/b"): "PASS"}
_ROWS_BAD = {("scripts/a.py", "controls/a"): "BLIND", ("scripts/b.py", "controls/b"): "PASS"}
_DIRTY = {("scripts/a.py", "controls/a"): "1 file(s) ... are NOT tracked: controls/a/x.sh"}


@pytest.mark.parametrize(
    ("returncode", "stderr", "rows", "registered", "untracked", "expected"),
    [
        # THE THREE THAT MATTER ALL CARRY AN UNTRACKED ROW. Before the #1061
        # counter-model review each of these classified as `tracking` and was
        # quietly skipped: a real harness regression hidden by a neighbour's
        # untracked file, which is this change's own defect one level down.
        (-9, "", _ROWS_OK, 2, _DIRTY, "crash"),
        (1, "Traceback (most recent call last):\n  File ...\nKeyError: 'x'", _ROWS_OK, 2, _DIRTY, "crash"),
        (1, "", _ROWS_OK, 44, _DIRTY, "truncated"),
        # and the ordinary classifications
        (1, "", _ROWS_BAD, 2, _DIRTY, "verdict"),
        (1, "", _ROWS_OK, 2, _DIRTY, "tracking"),
        (1, "", _ROWS_OK, 2, {}, "verdict"),
        (2, "", _ROWS_OK, 2, _DIRTY, "crash"),
        (1, "", _ROWS_OK, None, _DIRTY, "truncated"),
    ],
)
def test_a_nonzero_exit_is_attributed_before_it_is_excused(
    returncode: int, stderr: str, rows: dict, registered: int | None,
    untracked: dict, expected: str,
) -> None:
    """The committed red cases for `_classify_nonzero_exit`.

    `test_self_registration_is_blind_to_a_verdict_assignment_breakage` may turn
    a non-zero exit into UNRESOLVED, and a tolerant path that cannot be shown to
    refuse anything is worse than the confusing red it replaced. These are the
    inputs that make it report the other answer - pure, deterministic, and not
    dependent on the live tree that the test itself cannot control.
    """
    assert _classify_nonzero_exit(returncode, stderr, rows, registered, untracked) == expected


def test_the_denominator_check_catches_a_register_collapsed_to_one_row() -> None:
    """The red case for the completeness half (#1061 re-review, MEDIUM).

    "every parsed row reads PASS" is trivially true of ONE row, so a parser that
    collapsed 44 registrations into 1 would satisfy the whole-register claim on
    a clean tree while having destroyed it. The denominator is what makes the
    claim checkable, so the denominator needs its own red case.
    """
    collapsed = (
        "NEGATIVE_CONTROL_REGISTERED: 44\n"
        "NEGATIVE_CONTROL_GATE: scripts/check-negative-controls.py\n"
        "NEGATIVE_CONTROL_CONTROL: controls/check-negative-controls\n"
        "NEGATIVE_CONTROL_VERDICT: PASS\n"
    )
    rows = _verdicts_by_gate(collapsed)
    assert set(rows.values()) == {"PASS"}, "the claim the old test made, and it holds"
    assert _registered_count(collapsed) == 44
    assert len(rows) != _registered_count(collapsed), (
        "the denominator check must be able to see this: 1 row against a stated 44"
    )

    # ...and the honest shape passes it
    whole = collapsed.replace("REGISTERED: 44", "REGISTERED: 1")
    assert len(_verdicts_by_gate(whole)) == _registered_count(whole)


def test_a_lock_system_failure_is_not_blamed_on_a_neighbouring_test(monkeypatch) -> None:
    """The red case for the errno half (#1061 re-review, LOW).

    ENOLCK is the locking system saying it cannot serve the request. Reported as
    contention it becomes "another test is holding it far longer than its ~20s
    window" - an accusation against a test that did nothing, with the real errno
    discarded. It must propagate instead.
    """
    def _enolck(_fd: int, _op: int) -> None:
        raise OSError(errno.ENOLCK, "no locks available")

    monkeypatch.setattr(fcntl, "flock", _enolck)
    with pytest.raises(OSError) as caught:
        with live_controls_tree_exclusive(timeout=0.1):
            pass
    assert caught.value.errno == errno.ENOLCK, "the original cause must survive"
    assert not isinstance(caught.value, AssertionError)


def test_the_lock_deadline_is_reachable_and_says_who_to_blame() -> None:
    """The red case for the timeout half (#1061 re-review, MEDIUM).

    flock associates a lock with the OPEN FILE DESCRIPTION, so a second open of
    the same path contends even from the same process - which makes contention
    deterministic to exercise without a second worker. The point is that the
    deadline FIRES: at the previous 300s default, pytest's 120s per-test budget
    killed the test first and this diagnostic could never be reached.
    """
    holder = os.open(_LIVE_TREE_LOCK, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(AssertionError, match="could not take the live controls tree lock"):
            with live_controls_tree_exclusive(timeout=0.5):
                pass
    finally:
        fcntl.flock(holder, fcntl.LOCK_UN)
        os.close(holder)

    # and it is genuinely released - the same call now succeeds
    with live_controls_tree_exclusive(timeout=5.0):
        pass


def test_pytest_catches_the_breakage_the_self_registration_cannot(tmp_path: Path) -> None:
    """HALF TWO, and this is the load-bearing one.

    The external control is this file, run by pytest in the `validate` CI step:
    a different process, a different entry point, asserting on exit codes and
    stdout rather than on the harness's judgement of itself.

    Here that independence is exercised directly. On a tree where the real
    harness reports BLIND, the mutant reports PASS - so the assertion in
    `test_a_gate_that_stopped_discriminating_reports_blind` FAILS against the
    mutant while the self-registration above stays green.

    IF THIS TEST EVER STOPS FAILING AGAINST THE MUTANT, the external control has
    become decoration and the self-registration is all that is left, which is
    the state #964's design exists to prevent.
    """
    tree = tmp_path / "tree"
    tree.mkdir()
    root = build_tree(tree, BLIND_GATE)
    real = run_harness(root, "--strict")
    assert verdict_of(real.stdout) == "BLIND", real.stdout
    assert real.returncode == 1

    mutant = _forced_pass_harness(tmp_path)
    mutated_run = subprocess.run(
        [sys.executable, str(mutant), "--root", str(root), "--strict"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert verdict_of(mutated_run.stdout) == "PASS", mutated_run.stdout
    assert mutated_run.returncode == 0
    assert verdict_of(real.stdout) != verdict_of(mutated_run.stdout), (
        "the mutant and the real harness agree, so this control no longer "
        "distinguishes a working harness from one that cannot disagree"
    )


# --------------------------------------------------------------------------- #
# #986 - discover() registers every REGISTRATION, not the first one per gate
# --------------------------------------------------------------------------- #


def test_a_gate_declaring_several_controls_contributes_every_one(tmp_path: Path) -> None:
    """The red case for #986: `.search` returns one, `.finditer` returns all.

    LATENT when fixed - the three registered gates each declare exactly one, so
    the old and new calls agreed on the real tree. This fixture is the input that
    tells them apart, and it is committed because a defect nothing can reproduce
    is a defect that comes back.
    """
    (tmp_path / "scripts").mkdir()
    gate = tmp_path / "scripts" / "two-control-gate.sh"
    gate.write_text(
        "#!/bin/sh\n"
        "#: NEGATIVE-CONTROL: controls/alpha\n"
        "#: NEGATIVE-CONTROL: controls/beta\n"
        "exit 0\n",
        encoding="utf-8",
    )
    out = run_harness(tmp_path)
    declared = [ln for ln in out.stdout.splitlines() if ln.startswith("NEGATIVE_CONTROL_GATE:")]
    assert len(declared) == 2, f"both registrations must be discovered, got {len(declared)}:\n{out.stdout}"
    # Each is EVALUATED, not merely counted: both report their own missing manifest.
    assert "no control.json at controls/alpha" in out.stdout
    assert "no control.json at controls/beta" in out.stdout


# --------------------------------------------------------------------------- #
# #979 - a numerator without its denominator
# --------------------------------------------------------------------------- #


def test_the_summary_states_the_universe_it_is_a_fraction_of() -> None:
    """`2 of 61` and `61 of 61` must not print the identical string."""
    # "enumerated instruments" appears only in the all-PASS summary, so asserting
    # it coupled this test to every control's health - and its subject is the
    # DENOMINATOR (#979), not battery health. The universe line is emitted
    # regardless of any control's verdict, which is what this actually needs.
    out = run_harness(ROOT)
    universe = [
        line for line in out.stdout.splitlines()
        if line.startswith("NEGATIVE_CONTROL_UNIVERSE:")
    ]
    assert universe, out.stdout
    value = universe[0].split(": ", 1)[1].strip()
    assert value.isdigit() and int(value) > 0, (
        f"the universe must be a COUNT, not a word - a bare numerator is what "
        f"#979 removed: {universe[0]!r}"
    )
    registered = [
        line for line in out.stdout.splitlines()
        if line.startswith("NEGATIVE_CONTROL_REGISTERED:")
    ]
    assert registered, f"a numerator with no denominator is the #979 defect\n{out.stdout}"


def test_an_unparseable_adr_reports_UNKNOWN_rather_than_a_bare_numerator(tmp_path: Path) -> None:
    """The red case for #979.

    The failure this guards is not "the number is wrong" - it is a count printed
    with no universe, which reads as coverage. So when the universe cannot be
    established the output must SAY so, and must not fall back to the bare count
    that was the defect.
    """
    (tmp_path / "scripts").mkdir()
    adr = tmp_path / "docs" / "decisions"
    adr.mkdir(parents=True)
    (adr / "0008-instrument-negative-control-bound.md").write_text(
        "a document with no enumerated rows\n", encoding="utf-8"
    )
    out = run_harness(tmp_path)
    assert "NEGATIVE_CONTROL_UNIVERSE: unknown" in out.stdout, out.stdout


# --------------------------------------------------------------------------- #
# #978 - a control whose files are untracked does not exist in a clean clone
# --------------------------------------------------------------------------- #


@requires_git
@pytest.mark.skipif(
    shutil.which("gitleaks") is None,
    reason="needs gitleaks: this test requires a GREEN battery in order to refuse it, "
           "and the secret-scan control cannot run without it",
)
@pytest.mark.timeout(_TEST_BUDGET)
def test_an_untracked_control_file_refuses_the_green() -> None:
    """The red case for #978, run against the REAL register.

    GUARDED, unlike the two above, because the coupling here is INHERENT: the
    precondition is `before.returncode == 0` - it needs a green battery in order
    to prove an untracked file refuses one. Narrowing it is not available; the
    whole battery IS its subject. `tests/conftest.py` names the resulting skip
    (#926), so the lane is visibly unexercised rather than silently so.

    A control is exercised from the working tree, so an untracked case file
    discriminates correctly and reports PASS while the same commit in a clean
    clone has no cases at all. Observed twice on 2026-09-15 (#964, #953).

    The file is created and removed inside the test rather than committed,
    because a committed untracked file is a contradiction: committing it would
    make it tracked and the case would stop reproducing.
    """
    sneaky = REAL_CONTROL / "cases" / "untracked-probe.sh"
    # THE DIRTY WINDOW IS HELD EXCLUSIVELY. This test deliberately makes the
    # shared live tree not-clean for ~19 seconds, and anything else scanning it
    # meanwhile reads a true fact about a state this test created - reported
    # against ITS OWN subject, which is wrong (#1061). The restore is inside the
    # lock too: releasing before `restored` is re-measured would hand over a
    # tree this test has not finished putting back.
    with live_controls_tree_exclusive():
        assert not sneaky.exists(), "fixture would clobber a real file"
        before = run_harness(ROOT, "--strict")
        assert before.returncode == 0, f"precondition: the tree is clean\n{before.stdout}"
        sneaky.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        try:
            tracked = subprocess.run(
                ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", str(sneaky)],
                capture_output=True, check=False,
            )
            assert tracked.returncode != 0, "precondition: the probe must be UNTRACKED"
            after = run_harness(ROOT, "--strict")
            assert after.returncode == 1, f"an untracked control file must refuse the green\n{after.stdout}"
            assert "NEGATIVE_CONTROL_TRACKING: UNTRACKED" in after.stdout, after.stdout
            assert "untracked-probe.sh" in after.stdout, "the offending path must be NAMED"
        finally:
            sneaky.unlink(missing_ok=True)
        restored = run_harness(ROOT, "--strict")
        assert restored.returncode == 0, f"the tree must be clean again\n{restored.stdout}"


# --------------------------------------------------------------------------- #
# A value-taking flag as the FINAL argument (issue #992)
# --------------------------------------------------------------------------- #
# `shift 2` fails when only one positional remains and shifts NOTHING. `${2:-}`
# made the missing value benign, so nothing errored - and `$#` never decreased,
# so `while [ $# -gt 0 ]` spun forever on the same argument. The script did not
# crash, print, or exit; it burned a core until something killed it.
#
# THE `timeout=` BELOW IS THE ASSERTION. On the unfixed script this test does not
# fail, it never returns - so an assertion about the exit STATUS would be
# unfalsifiable there, and "exit is 2" would hang the suite rather than red it.
# A hanging suite is not a red run, it is no run at all.


#: The harness's own known-good and known-bad fixtures.
_TOY_GATES = [
    "controls/check-negative-controls/cases/good-discriminating-gate/scripts/toy-gate.sh",
    "controls/check-negative-controls/cases/bad-crashing-gate/scripts/toy-gate.sh",
]


@pytest.mark.parametrize("rel", _TOY_GATES)
@pytest.mark.parametrize("interpreter", ["sh", "bash"])
@pytest.mark.skipif(
    shutil.which("sh") is None or shutil.which("bash") is None,
    reason="shells out to sh and bash",
)
def test_a_toy_gate_refuses_a_dangling_root_under_either_shell(rel: str, interpreter: str) -> None:
    """These two are the fixtures of the harness that proves gates can fail.

    Invoked with `sh`, not `bash`: the files are `#!/bin/sh` and control.json
    invokes them as `["sh", "{gate}", "--root", "{case}"]`. The exit status of
    `${2:?}` differs between shells (2 under dash, 1 under bash), so this asserts
    NON-ZERO rather than a number - the property is "refuses and returns", and
    pinning a shell-specific code would make the test lie on another host.

    REACH, stated rather than implied: the harness always supplies `{case}` to
    `--root`, so this was never reachable from the control battery. It was a trap
    for a hand-invocation. This file should not be read as evidence that the
    battery was at risk.

    BOTH SHELLS, because the old behaviour was HOST-DEPENDENT and that is worse
    than uniformly broken. Measured on the unfixed fixture: under `bash` the
    parse loop spun forever, while under `dash` - what `/bin/sh` is here, and
    what the shebang declares - `shift 2` with one positional is a fatal error
    and the script exited 2. So on a host whose `/bin/sh` is bash the same file
    hangs, and on this one it does not. Parametrising the interpreter is what
    stops the test agreeing with whichever host happens to run it.
    """
    result = subprocess.run(
        [interpreter, str(ROOT / rel), "--root"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0, f"a dangling --root must refuse: {result!r}"
    assert "--root needs a value" in result.stderr, (
        f"{interpreter}: the refusal must NAME the flag, not merely be non-zero - "
        f"dash's own 'shift: can't shift that many' is also non-zero and says "
        f"nothing a caller can act on: {result.stderr!r}"
    )


@pytest.mark.parametrize("rel", _TOY_GATES)
@pytest.mark.skipif(shutil.which("sh") is None, reason="shells out to sh")
def test_a_toy_gate_still_accepts_a_normal_root(rel: str, tmp_path: Path) -> None:
    """The other side: the guard must not refuse the invocation the harness makes.

    `${2:?}` fires on unset OR NULL, so this is also the case that would catch it
    becoming stricter than intended for a real path.
    """
    result = subprocess.run(
        ["sh", str(ROOT / rel), "--root", str(tmp_path)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, f"a normal --root must be accepted: {result!r}"
    assert "toy-gate: clean" in result.stdout, result.stdout


# --------------------------------------------------------------------------- #
# #1036 - two numbers printed as one ratio, a denominator that does not say
#         what it is made of, and a search scope nothing states
# --------------------------------------------------------------------------- #
#
# THESE ARE PYTEST CASES AND NOT FIXTURE CASES UNDER `controls/`, deliberately.
# The framework scores a case on an EXIT CODE plus a detect_signal, and the
# property here is about OUTPUT: a registered control outside the census is
# REPORTED, not failed, because whether it should fail is a separate decision
# that printing the fact does not pre-empt. A control directory cannot express
# "the exit code is unchanged and the text must differ", so the committed red
# lives where it can actually fail - a different process, asserting on stdout,
# which is the same reason `test_pytest_catches_the_breakage_the_self_
# registration_cannot` exists above.


def write_census(root: Path, subjects: list[str], externals: list[str] | None = None) -> Path:
    """A miniature ADR 0008 with one numbered row per subject.

    Shaped like the real document rather than like the parser: numbered rows
    whose column 2 opens with a backticked subject, an external-subjects marker
    in an HTML comment, and a fenced example that must NOT be counted. The fence
    is not decoration - both readers strip fences, and a fixture without one
    would leave that agreement unexercised here.
    """
    adr = root / "docs" / "decisions"
    adr.mkdir(parents=True, exist_ok=True)
    declared = ", ".join(externals or [])
    rows = "\n".join(
        f"| {index} | `{subject}` | a verdict | a consumer | G |"
        for index, subject in enumerate(subjects, start=1)
    )
    path = adr / "0008-instrument-negative-control-bound.md"
    path.write_text(
        "# Census\n\n"
        f"<!-- instrument-census: external-subjects: {declared} -->\n\n"
        "An illustrative row, which is an EXAMPLE and not the census speaking:\n\n"
        "```\n| 99 | `illustrative-tool.sh` | x | y | G |\n```\n\n"
        "| # | instrument | verdict | consumed by | class |\n"
        "|---|---|---|---|---|\n"
        f"{rows}\n",
        encoding="utf-8",
    )
    return path


def contract(out: str, key: str) -> str | None:
    for line in out.splitlines():
        if line.startswith(f"{key}: "):
            return line.split(": ", 1)[1].strip()
    return None


def test_a_registered_control_outside_the_census_is_NAMED(tmp_path: Path) -> None:
    """THE COMMITTED RED for #1036's headline defect.

    `21 of 89 enumerated instruments carry a control that discriminates` was two
    independently-derived counts printed as a ratio: the numerator counted
    REGISTERED CONTROLS, the denominator ADR 0008 CENSUS ROWS, and nothing
    asserted a registered control's gate appeared in the census at all. A
    registered control whose gate was absent produced the SAME OUTPUT as one
    present, so the line overstated its own coverage in the one sentence every
    consumer quotes.

    The issue's own red case - `check-oscillation`, which registered a control
    under #936 and was never added to the table - was fixed by 967c098 (#1060)
    before this landed, so the live instance is gone. That is the reason this
    case is CONSTRUCTED rather than pointed at the tree: a red that depends on
    someone not yet having fixed something evaporates the moment they do.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    write_census(root, ["some-other-gate.py", "and-another.py"])
    out = run_harness(root)
    assert contract(out.stdout, "NEGATIVE_CONTROL_CENSUS_NONMEMBERS") == "1", out.stdout
    assert "NEGATIVE_CONTROL_CENSUS_NONMEMBER: toy-gate.py" in out.stdout, out.stdout
    assert "toy-gate.py" in out.stdout.split("negative-controls: ok -")[-1], (
        "the headline must NAME the non-member, not merely count it - absorbing "
        f"the exception is the defect\n{out.stdout}"
    )


def test_a_registered_control_inside_the_census_is_not_named(tmp_path: Path) -> None:
    """The other direction, and it is not symmetry for its own sake.

    A membership check that named EVERY control would pass the red case above on
    its own while telling a reader nothing, and it would do so loudly enough to
    look like diligence. This is what separates "resolves gates against the
    census" from "prints a list".
    """
    root = build_tree(tmp_path, SEEING_GATE)
    write_census(root, ["toy-gate.py", "some-other-gate.py"])
    out = run_harness(root)
    assert contract(out.stdout, "NEGATIVE_CONTROL_CENSUS_MEMBERS") == "1", out.stdout
    assert contract(out.stdout, "NEGATIVE_CONTROL_CENSUS_NONMEMBERS") == "0", out.stdout
    assert "NEGATIVE_CONTROL_CENSUS_NONMEMBER:" not in out.stdout, out.stdout


def test_a_census_with_an_external_row_reports_a_non_zero_external_count(tmp_path: Path) -> None:
    """The denominator is not homogeneous, and now it says so (#1036).

    Fourteen of the real census's rows name subjects with no file under
    `scripts/` for a marker to live in - `ruff`, `pytest`, `gitleaks`, `make`,
    the `lib.*` entry points. Nothing reported that, so every row read as
    equally reachable.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    write_census(root, ["toy-gate.py", "ruff", "pytest"], externals=["ruff", "pytest"])
    out = run_harness(root)
    assert contract(out.stdout, "NEGATIVE_CONTROL_UNIVERSE") == "3", out.stdout
    assert contract(out.stdout, "NEGATIVE_CONTROL_UNIVERSE_EXTERNAL") == "2", out.stdout
    assert contract(out.stdout, "NEGATIVE_CONTROL_UNIVERSE_REGISTRABLE") == "1", out.stdout


def test_a_census_of_only_registrable_rows_reports_zero_external(tmp_path: Path) -> None:
    """The half that makes the count above evidence rather than decoration.

    A composition report wedged at "some are external" passes the case above on
    its own. This is the direction where it must NOT fire - and it is the same
    reason the register refuses a control with no GOOD case.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    write_census(root, ["toy-gate.py", "other-gate.py"], externals=["ruff"])
    out = run_harness(root)
    assert contract(out.stdout, "NEGATIVE_CONTROL_UNIVERSE_EXTERNAL") == "0", out.stdout
    assert contract(out.stdout, "NEGATIVE_CONTROL_UNIVERSE_REGISTRABLE") == "2", out.stdout


def test_membership_is_unknown_when_the_two_readers_disagree(tmp_path: Path) -> None:
    """A parser disagreement must not become a confident membership answer.

    This file counts census ROWS; `instrument-census-check.py` extracts census
    SUBJECTS. #1060 recorded that splitting those parsers is how two readers of
    one table drift apart while both keep printing numbers. A row with no
    backticked subject in column 2 makes them disagree - and computing
    membership against the smaller set would report real rows as non-members,
    which is a wrong answer where the honest one is `unknown`.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    census = write_census(root, ["toy-gate.py"])
    census.write_text(
        census.read_text(encoding="utf-8") + "| 2 | an unbackticked subject | v | c | G |\n",
        encoding="utf-8",
    )
    out = run_harness(root)
    assert contract(out.stdout, "NEGATIVE_CONTROL_UNIVERSE") == "2", out.stdout
    assert contract(out.stdout, "NEGATIVE_CONTROL_CENSUS_MEMBERS") == "unknown", out.stdout
    assert contract(out.stdout, "NEGATIVE_CONTROL_CENSUS_NONMEMBERS") == "unknown", out.stdout
    assert "NEGATIVE_CONTROL_CENSUS_UNREAD: " in out.stdout, out.stdout


def test_the_run_states_where_it_looked_for_registrations(tmp_path: Path) -> None:
    """"No control found" and "I did not look there" were the same silence."""
    root = build_tree(tmp_path, SEEING_GATE)
    scope = contract(run_harness(root).stdout, "NEGATIVE_CONTROL_DISCOVERY_SCOPE")
    assert scope and "scripts/" in scope, scope


def test_a_marker_in_a_scripts_subdirectory_is_not_discovered(tmp_path: Path) -> None:
    """The case that PINS the scope line to what `discover` actually does.

    `DISCOVERY_SCOPE` is a claim written in prose beside `iterdir()`, and prose
    does not fail. This is what brings someone back to it: widen discovery to
    `rglob()` and this case goes red, so the sentence cannot go on describing a
    search that changed underneath it.

    Whether to widen is a real question and deliberately not answered here - the
    census population is derived with the same `scripts/`-only rule, so widening
    one reader without the other splits the numerator's population from the
    denominator's, which is the defect this whole line of work is about.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    nested = root / "scripts" / "nested"
    nested.mkdir()
    (nested / "hidden-gate.py").write_text(
        "#: NEGATIVE-CONTROL: controls/nowhere\nprint('x')\n", encoding="utf-8"
    )
    out = run_harness(root)
    assert contract(out.stdout, "NEGATIVE_CONTROL_REGISTERED") == "1", (
        "a marker in a scripts/ SUBDIRECTORY was discovered - discovery widened, "
        f"so DISCOVERY_SCOPE in check-negative-controls.py is now wrong\n{out.stdout}"
    )
    assert "controls/nowhere" not in out.stdout, out.stdout


# #1117 - "its tool is missing" is not "it stopped discriminating"
# --------------------------------------------------------------------------- #


def test_a_gate_whose_own_tool_is_absent_reports_UNAVAILABLE(tmp_path: Path) -> None:
    """The distinction this issue exists for.

    A gate that cannot look is not a gate that looked and missed. Both exit
    non-zero, so before the declared unavailability signal the harness filed the
    first as the second - UNSIGNALLED for two of the three real gates, and BLIND
    for the jq one, whose unavailability line is a legitimate member of its own
    detection pattern. The correct response to either is "install a tool", and
    neither verdict says that.
    """
    root = build_tree(tmp_path, UNAVAILABLE_GATE, unavailable_signal=TOY_UNAVAILABLE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNAVAILABLE", result.stdout
    assert "not installed" in result.stdout, result.stdout


def test_the_SAME_silence_without_a_declared_pattern_stays_UNSIGNALLED(tmp_path: Path) -> None:
    """THE RED CASE FOR THE FIELD'S EXISTENCE, and the half that keeps it honest.

    Same harness, same posture; the only difference is whether the manifest
    declares a pattern the gate's words match. The test above would pass against
    a harness that returned UNAVAILABLE for every non-zero exit carrying no
    detection signal - which is the fail-open
    `controls/check-negative-controls-unavailable` pins as a frozen artifact, and
    it would be an even quieter version of the #946 defect. So a gate that goes
    silent must still be UNSIGNALLED, declaration present or not.
    """
    # Declared, and the gate does not say it: this is the discriminating half.
    root = build_tree(tmp_path, CRASHING_GATE, unavailable_signal=TOY_UNAVAILABLE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNSIGNALLED", result.stdout
    assert result.returncode == 1

    # And with no declaration at all, behaviour is byte-identical to pre-#1117.
    (tmp_path / "nested").mkdir()
    other = build_tree(tmp_path / "nested", CRASHING_GATE)
    assert verdict_of(run_harness(other, "--strict").stdout) == "UNSIGNALLED"


def test_an_unavailable_signal_matching_empty_output_is_refused(tmp_path: Path) -> None:
    """`.*` would excuse every silent non-zero exit, wearing the new field's name.

    Structural, checked before any case runs, and the exact mirror of the
    detect_signal refusal: a pattern that matches nothing-at-all cannot separate
    a missing tool from a crash by construction.
    """
    root = build_tree(tmp_path, CRASHING_GATE, unavailable_signal=".*")
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "matches empty output" in result.stdout, result.stdout
    assert result.returncode == 1


def test_an_unavailable_signal_matching_a_clean_run_is_refused(tmp_path: Path) -> None:
    """A pattern anchored on something the gate prints when it is WORKING.

    That reports a healthy gate as unexaminable, which is the opposite error from
    the one above and just as quiet: the control stops covering anything and the
    run still exits 0 under the local posture.
    """
    root = build_tree(tmp_path, CHATTY_UNAVAILABLE_GATE, unavailable_signal=TOY_UNAVAILABLE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "CLEAN output" in result.stdout, result.stdout


def test_unavailable_on_one_case_while_another_ran_cleanly_is_refused(tmp_path: Path) -> None:
    """The cross-case contradiction, and the reason the ordering is safe.

    `unavailable_signal` is consulted BEFORE `detect_signal`, because the jq
    gate's two messages are not separable in the other direction. That ordering
    would be a silent precedence rule without this: a binary that is absent is
    absent for every case, so "unavailable here, clean there" is not something a
    missing tool produces. It is what a pattern broad enough to swallow a genuine
    finding produces on a machine that HAS the tool - every CI run, where the
    three are pinned into the image on purpose.
    """
    root = build_tree(tmp_path, UNAVAILABLE_ON_BAD_ONLY_GATE, unavailable_signal=TOY_UNAVAILABLE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "A missing binary is missing for every case" in result.stdout, result.stdout


def test_strict_ALONE_still_fails_on_UNAVAILABLE(tmp_path: Path) -> None:
    """THE CI POSTURE, pinned so the local one cannot quietly become it.

    `.woodpecker.yml` stages pinned gitleaks, shellcheck and jq into `.ci-bin`
    and its comment rests on this harness reddening rather than reporting a
    shorter battery if a staging step stops delivering one;
    `tests/test_shellcheck_stage.py` holds the same claim. Both are about `make`-
    free CI, which passes `--strict` and nothing else. If tolerance ever leaks
    into the bare flag, an absent binary in CI becomes a silent shorter battery
    and those guarantees are gone with no edit to either file.
    """
    root = build_tree(tmp_path, UNAVAILABLE_GATE, unavailable_signal=TOY_UNAVAILABLE)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNAVAILABLE", result.stdout
    assert result.returncode == 1, (
        "bare --strict must keep failing on UNAVAILABLE - CI reads it\n" + result.stdout
    )


def test_allow_unavailable_excuses_UNAVAILABLE_and_NOTHING_ELSE(tmp_path: Path) -> None:
    """THE LOCAL POSTURE, two-sided.

    One-sided this would pass against a flag that simply suppressed every
    failure, so the same flag is asserted NOT to rescue a silent gate. That is
    the whole difference between a posture and an off switch.
    """
    for sub in ("a", "b", "c"):
        (tmp_path / sub).mkdir()
    unavailable = build_tree(tmp_path / "a", UNAVAILABLE_GATE, unavailable_signal=TOY_UNAVAILABLE)
    excused = run_harness(unavailable, "--strict", "--allow-unavailable")
    assert excused.returncode == 0, excused.stdout
    assert verdict_of(excused.stdout) == "UNAVAILABLE", excused.stdout

    silent = build_tree(tmp_path / "b", CRASHING_GATE, unavailable_signal=TOY_UNAVAILABLE)
    refused = run_harness(silent, "--strict", "--allow-unavailable")
    assert refused.returncode == 1, (
        "--allow-unavailable must not rescue a gate that went silent\n" + refused.stdout
    )
    assert verdict_of(refused.stdout) == "UNSIGNALLED", refused.stdout

    blind = build_tree(tmp_path / "c", BLIND_GATE, unavailable_signal=TOY_UNAVAILABLE)
    still_blind = run_harness(blind, "--strict", "--allow-unavailable")
    assert still_blind.returncode == 1, still_blind.stdout
    assert verdict_of(still_blind.stdout) == "BLIND", still_blind.stdout


def test_an_excused_control_is_NAMED_and_not_counted_as_discriminating(tmp_path: Path) -> None:
    """What it tolerates it must also say, in both directions.

    A tolerated verdict that is silent is the failure this whole file refuses: a
    developer whose box lacks gitleaks would read a green `make verify` as the
    evidence CI has. Two separate claims, and each can regress without the other:
    the unexamined control is NAMED, and it is not absorbed into the numerator of
    the "N of M ... discriminate" line, which would be a fresh overclaim
    introduced by the very change that exists to stop one.
    """
    root = build_tree(tmp_path, UNAVAILABLE_GATE, unavailable_signal=TOY_UNAVAILABLE)
    # A READABLE CENSUS, so the headline reaches its membership branch (#1036).
    # Without one the universe is unknown and the sentence never states the
    # relation this test is about.
    write_census(root, ["toy-gate.py"])
    result = run_harness(root, "--strict", "--allow-unavailable")
    assert result.returncode == 0, result.stdout
    assert "NEGATIVE_CONTROL_UNAVAILABLE: 1" in result.stdout, result.stdout
    assert "NOT EXAMINED here" in result.stdout, result.stdout
    assert "scripts/toy-gate.py" in result.stdout.rsplit("NOT EXAMINED here", 1)[-1], result.stdout
    assert "0 of 1 enumerated instruments" in result.stdout, (
        "the only control was unexamined, so the count of instruments carrying a "
        "control that discriminates is 0 - counting it would claim coverage "
        "nothing established\n" + result.stdout
    )
    assert "1 registered" in result.stdout, (
        "the registration still exists and that is a separate, true fact - "
        "the run must not hide it to make the coverage number honest\n" + result.stdout
    )


def test_the_unavailable_count_is_printed_even_when_it_is_zero(tmp_path: Path) -> None:
    """A line that appears only when non-zero cannot be told from an absent one.

    A consumer reading for it would learn "unexamined: absent", which is equally
    consistent with "none" and with "an older harness that never emitted this".
    Same rule as the universe line #979 added.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    result = run_harness(root, "--strict")
    assert "NEGATIVE_CONTROL_UNAVAILABLE: 0" in result.stdout, result.stdout


@requires_git
def test_allow_unavailable_does_not_excuse_an_UNTRACKED_control(tmp_path: Path) -> None:
    """The two axes stay independent (#978 x #1117).

    "This machine lacks gitleaks" and "this control does not exist in a clean
    clone" are unrelated facts that happen to meet in one Result. Tolerating the
    first must not swallow the second - an untracked control is a green that does
    not survive a clone, and no amount of missing tooling makes that acceptable.
    """
    root = build_tree(tmp_path, UNAVAILABLE_GATE, unavailable_signal=TOY_UNAVAILABLE)
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=60)
    result = run_harness(root, "--strict", "--allow-unavailable")
    assert "NEGATIVE_CONTROL_TRACKING: UNTRACKED" in result.stdout, (
        "fixture precondition: the control's files must be untracked here\n" + result.stdout
    )
    assert result.returncode == 1, (
        "--allow-unavailable excused a control that does not exist in a clean clone\n"
        + result.stdout
    )


def test_two_registrations_on_one_gate_are_distinguishable_in_the_output() -> None:
    """A block's only identifying field was the gate, and a gate may declare several.

    `scripts/check-negative-controls.py` carries two registrations as of #1117 -
    the first gate in the repository to do so, though discovery has supported it
    since #986. Without the control line, the two blocks are byte-identical in
    everything a reader or a consumer could key on, so a failure in one would be
    diagnosed against the other's fixtures.
    """
    out = run_harness(ROOT).stdout
    controls = [
        line.split(": ", 1)[1]
        for line in out.splitlines()
        if line.startswith("NEGATIVE_CONTROL_CONTROL: ")
    ]
    assert "controls/check-negative-controls" in controls, out
    assert "controls/check-negative-controls-unavailable" in controls, out
    assert len(controls) == len(set(controls)), f"two blocks share an identity: {controls}"


def test_the_real_unavailability_control_discriminates_and_its_anchor_is_blind() -> None:
    """The committed demonstration for #1117, executed rather than asserted.

    Scoped to THIS control (see `control_block`), which is why the #1117 contract
    line exists: both registrations report the same gate, so scoping by gate name
    would silently address the neighbour. No `--strict`: the exit code is a
    property of every control, not of this one.
    """
    out = run_harness(ROOT).stdout
    block, collecting = [], False
    for line in out.splitlines():
        if line.startswith("NEGATIVE_CONTROL_CONTROL: "):
            collecting = line.split(": ", 1)[1] == "controls/check-negative-controls-unavailable"
        if collecting:
            block.append(line)
            if line.startswith("NEGATIVE_CONTROL_VERDICT: "):
                break
    text = "\n".join(block)
    assert text, f"the unavailability control is not in the register at all\n{out}"
    assert verdict_of(text) == "PASS", text
    assert "missed the known-bad input" in text, text


def test_the_real_unavailability_anchor_misses_the_silence_the_gate_catches() -> None:
    """The #1117 claim measured directly: one fixture, both artifacts, opposite answers.

    The harness's own verdict about itself is the weaker half (its control says
    so), so this runs the two programs and compares exit codes rather than
    reading the harness's judgement of the comparison.
    """
    control = ROOT / "controls" / "check-negative-controls-unavailable"
    silent = control / "cases" / "bad-silent-gate"
    anchor = control / "anchors" / "constructed-absence-is-unavailable-check-negative-controls.py"
    flags = ["--root", str(silent), "--strict", "--allow-unavailable"]
    current = subprocess.run(
        [sys.executable, str(HARNESS), *flags], capture_output=True, text=True, timeout=120,
    )
    historical = subprocess.run(
        [sys.executable, str(anchor), *flags], capture_output=True, text=True, timeout=120,
    )
    assert current.returncode == 1, f"the current harness should flag a silent gate: {current.stdout}"
    assert "UNSIGNALLED" in current.stdout, current.stdout
    assert historical.returncode == 0, (
        f"the anchor should MISS it - if it catches it, this control is not "
        f"load-bearing: {historical.stdout}"
    )


def test_unavailability_is_read_BEFORE_detection_when_the_two_patterns_overlap(tmp_path: Path) -> None:
    """The ordering, pinned against the specimen that decides it.

    Every other test here passes under EITHER order, because the toy gates print
    an unavailability line their detection pattern does not match - so this is
    the only one that can fail when the two are swapped. That makes it the whole
    of the ordering's coverage, and the reason it exists as its own case.

    Measured on the real gate, 2026-09-20: with jq removed from an otherwise
    identical PATH, `controls/flow-driver-retirement-check` reported BLIND - "the
    gate did not discriminate", the loudest alarm in this vocabulary - for a
    machine that simply lacked a binary. Detection-first reproduces exactly that
    here, because `toy-gate: unknown - ...` matches a detection pattern whose
    `unknown` branch is deliberately there.
    """
    root = build_tree(
        tmp_path,
        OVERLAPPING_UNAVAILABLE_GATE,
        detect_signal=TOY_OVERLAPPING_DETECT,
        unavailable_signal=TOY_OVERLAPPING_UNAVAILABLE,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNAVAILABLE", (
        "the specific pattern must win over the general one. BLIND here is the "
        "real jq defect reproduced: an environment fact reported as the gate "
        "having stopped discriminating\n" + result.stdout
    )


def test_a_gate_that_DETECTED_cannot_then_claim_its_tool_is_absent(tmp_path: Path) -> None:
    """The counter-model finding on this change (MEDIUM), as a red case.

    A SUCCESSFUL DETECTION IS PROOF THE TOOL WAS THERE, exactly as a clean run
    is. The first cut of the cross-case check recorded only `observed == GOOD`
    as evidence the gate ran, so this shape - detect the known-bad input, then
    report the tool absent on the known-good one - produced no contradiction and
    was excused as UNAVAILABLE, exiting 0 under the local posture. The gate had
    already shown it could work, and its failure on the other input was written
    off as a fact about the machine.

    That is the same excusal the whole cross-case guard exists to refuse,
    reachable through the half the guard was not looking at.
    """
    root = build_tree(
        tmp_path, DETECTS_THEN_UNAVAILABLE_GATE, unavailable_signal=TOY_UNAVAILABLE
    )
    result = run_harness(root, "--strict", "--allow-unavailable")
    assert verdict_of(result.stdout) == "UNRESOLVED", (
        "a gate that detected one input cannot claim a missing tool on another\n"
        + result.stdout
    )
    assert result.returncode == 1, (
        "the local posture must not exit 0 here - this is not an environment fact\n"
        + result.stdout
    )
    assert "produced a real verdict" in result.stdout, result.stdout


def test_the_instrument_numerator_does_not_double_count_one_gate(tmp_path: Path) -> None:
    """The second counter-model finding on #1117 (MEDIUM), as a red case.

    The denominator counts ADR 0008 census rows, which are INSTRUMENTS. Until
    #1117 no gate carried two registrations, so a count of CONTROLS was the same
    number and the difference could not show. It can now: adding a second
    control to an ALREADY-covered gate would otherwise raise the claimed
    coverage while covering no additional instrument - a coverage figure that
    goes up when nothing new is covered.

    WHICH CODE PROVIDES THE PROPERTY, stated because it is not this branch's.
    #1036 landed between the finding and this merge, and its `census_membership`
    already resolves registrations to a SET of gate basenames - so the
    deduplication this test asserts is its work, not #1117's. What #1117
    contributes is the first tree that can tell the difference: this is the only
    test in the file that registers two controls on one gate, so before it the
    dedup was implemented and unexercised. Verified by removing the `set()` from
    `census_membership`, which reddens this test and nothing else.

    Both numbers are asserted, because reporting only the deduplicated one would
    lose a true fact rather than fix a false one.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    # A SECOND registration on the same gate, pointing at its own control dir.
    gate = root / "scripts" / "toy-gate.py"
    gate.write_text(
        gate.read_text(encoding="utf-8").replace(
            "#: NEGATIVE-CONTROL: controls/toy",
            "#: NEGATIVE-CONTROL: controls/toy\n#: NEGATIVE-CONTROL: controls/toy2",
        ),
        encoding="utf-8",
    )
    shutil.copytree(root / "controls" / "toy", root / "controls" / "toy2")

    write_census(root, ["toy-gate.py"])
    result = run_harness(root, "--strict")
    assert result.returncode == 0, result.stdout
    assert "NEGATIVE_CONTROL_REGISTERED: 2" in result.stdout, result.stdout
    assert "1 of 1 enumerated instruments" in result.stdout, (
        "two controls on ONE gate cover one instrument, not two - the coverage "
        "count is being taken in controls\n" + result.stdout
    )
    assert "2 registered" in result.stdout, (
        "the registration count is a true fact about this run and must still be "
        "reported, not dropped to make the instrument count correct\n" + result.stdout
    )


# --------------------------------------------------------------------------- #
# A CASE MAY REGISTER A REFUSAL (issue #1129)
#
# Every gate in this tree answers in three branches - clean, a finding, and "I
# could not look, or could not look completely" - and until #1129 only two of
# them could be registered. The third is the one that exists to stop a gate
# reporting a confident clean about a population it never examined, so it is the
# one whose failure is hardest to notice from outside.
#
# These run under PYTEST, a different process and a different entry point from
# the harness judging itself in controls/check-negative-controls-unknown. That
# separation is the point: a second opinion from the same program is not one.
# --------------------------------------------------------------------------- #


def test_a_gate_that_refuses_an_unexaminable_input_passes(tmp_path: Path) -> None:
    """The registrable half: a case demands a refusal and the gate delivers one."""
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_BUT_REFUSING_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "PASS", result.stdout
    assert result.returncode == 0
    assert "case unknown: expected=UNKNOWN observed=UNKNOWN" in result.stdout, (
        "the refusal must be OBSERVED as one, not merely tolerated\n" + result.stdout
    )


def test_a_false_clean_where_a_refusal_was_registered_is_blind(tmp_path: Path) -> None:
    """The failure the refusal branch exists to prevent, and the reason #1129
    called this half the one most worth controlling: a gate reporting CLEAN
    about a population it could not examine. A blind clean and a real clean are
    the same bytes, so nothing but a registered case catches this."""
    root = build_tree(
        tmp_path, FALSE_CLEAN_ON_UNKNOWN_GATE, anchor_src=BLIND_BUT_REFUSING_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "BLIND", result.stdout
    assert result.returncode == 1
    assert "reported CLEAN on an input it cannot examine" in result.stdout, (
        "a BLIND verdict decides where someone looks, so the sentence must name "
        "the false-clean rather than borrow the known-bad or known-good wording\n"
        + result.stdout
    )


def test_a_crash_where_a_refusal_was_registered_is_not_excused_as_one(tmp_path: Path) -> None:
    """Issue #946, re-created inside the field #1129 adds - and refused.

    A crash and a refusal both exit non-zero and neither prints the detection
    signal. A harness that scored a registered UNKNOWN case on the exit code
    alone would call a gate that FELL OVER correct, which is the pre-#946
    fail-open restored by a third route. This is the single property the
    committed anchor in controls/check-negative-controls-unknown is blind to.
    """
    root = build_tree(
        tmp_path, CRASH_ON_UNKNOWN_GATE, anchor_src=BLIND_BUT_REFUSING_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNSIGNALLED", (
        "a gate that fell over must not be excused as one that refused\n" + result.stdout
    )
    assert result.returncode == 1


def test_an_unknown_case_with_no_unknown_signal_is_refused(tmp_path: Path) -> None:
    """Without a marker to recognise a refusal by, the case can NEVER observe
    one: it falls through to UNSIGNALLED or BAD and reads as a gate alarm, which
    sends a reader into the gate's detection logic for a missing line in the
    manifest. Refused with the sentence that names the real defect."""
    root = build_tree(tmp_path, REFUSING_GATE, anchor_src=BLIND_BUT_REFUSING_ANCHOR,
                      cases=UNKNOWN_CASES)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "declares no unknown_signal" in result.stdout, result.stdout
    assert result.returncode == 1


def test_an_unknown_signal_that_matches_the_empty_string_is_refused(tmp_path: Path) -> None:
    """The structural fail-open: a pattern matching silence turns every
    non-zero exit into "it must have refused", which is scoring on the exit code
    again, wearing a third field's name."""
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_BUT_REFUSING_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=r"^toy-gate: UNKNOWN - |",
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "matches empty output" in result.stdout, result.stdout
    assert result.returncode == 1


def test_an_unknown_signal_that_also_matches_the_clean_run_is_refused(tmp_path: Path) -> None:
    """Checked against REAL output, not against the author's intention: a
    pattern anchored on the gate's ok line reports a gate that examined
    everything and found nothing as one that could not look - and does so on the
    very cases that prove the gate works."""
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_BUT_REFUSING_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=r"^toy-gate: ok",
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "reports a working gate as having refused" in result.stdout, result.stdout
    assert result.returncode == 1


def test_an_unknown_signal_that_also_matches_a_detection_is_refused(tmp_path: Path) -> None:
    """The refusal issue #1129 names in terms: a marker that also identified a
    finding would make a refusal and a detection the same evidence, "which is
    #946 undone".

    Consulting the refusal marker BEFORE the detection one is a precedence rule,
    not a licence for the two to overlap. Where they do, the ordering silently
    decides which of two honest-looking patterns wins, and a gate that started
    REPORTING what it used to REFUSE would keep scoring UNKNOWN and pass.
    """
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_BUT_REFUSING_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_SIGNAL,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "a refusal and a finding are the same evidence" in result.stdout, result.stdout
    assert result.returncode == 1


def test_an_absent_tool_is_still_unavailable_and_never_a_registered_refusal(
    tmp_path: Path,
) -> None:
    """PRECEDENCE, and it is load-bearing rather than tidy (issue #1129).

    This reproduces the real shape of `scripts/shellcheck-gate.sh`, which reports
    BOTH its absent linter and its other refusals through one `UNKNOWN - `
    marker - so the tool-absent line is a strict SUBSET of the refusal marker.
    Consulted in the other order, a host that simply lacks the tool would observe
    UNKNOWN, be scored against an expectation, and turn an environment fact back
    into an accusation about our code: #1117 undone by the change that cites it.
    """
    root = build_tree(
        tmp_path, UNAVAILABLE_GATE,
        unavailable_signal=TOY_UNAVAILABLE,
        unknown_signal=r"^toy-gate: UNAVAILABLE - ",
    )
    result = run_harness(root, "--strict", "--allow-unavailable")
    assert verdict_of(result.stdout) == "UNAVAILABLE", (
        "the more specific unavailability pattern must win over the general "
        "refusal marker that also matches it\n" + result.stdout
    )
    assert result.returncode == 0


def test_an_anchor_that_refuses_the_known_bad_input_is_unresolved_not_inert(
    tmp_path: Path,
) -> None:
    """It did not CATCH anything - it said it could not look. Calling that INERT
    accuses a perfectly blind artifact of being load-bearing and sends someone to
    replace a sound file; the honest claim is that the required property was not
    established. The same narrowing #946 made for a crashing anchor."""
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=REFUSES_THE_BAD_INPUT_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "REFUSED the known-bad input" in result.stdout, result.stdout
    assert result.returncode == 1


# --------------------------------------------------------------------------- #
# #1157 - provenance is COMPUTED, PRINTED, and now actually READ
# --------------------------------------------------------------------------- #

def _retag_anchor(root: Path, **fields: object) -> None:
    """Rewrite the toy control's single anchor entry in place."""
    manifest_path = root / "controls" / "toy" / "control.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["anchors"][0].update(fields)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_a_recorded_digest_that_disagrees_now_fails_the_run(tmp_path: Path) -> None:
    """RED CASE for the axis that was printed and ignored (#1157).

    `_provenance()` returned MISMATCH whenever the bytes on disk disagree with
    the digest the manifest records about them - and `failing` never looked at
    it, so a control printed

        NEGATIVE_CONTROL_PROVENANCE: MISMATCH
        NEGATIVE_CONTROL_VERDICT: PASS

    and the gate stayed green. Observed on a real branch, where a manifest sat
    on a digest two edits old through a full green `make verify`. A reader
    seeing both lines reasonably assumes the verdict accounted for the one
    above it.

    This is not the parser class, and the difference is worth keeping: those
    lose evidence BEFORE the verdict. This had the evidence, correct, on
    screen, and did not consult it.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    _retag_anchor(root, sha256="0" * 64)
    result = run_harness(root, "--strict")
    assert "NEGATIVE_CONTROL_PROVENANCE: MISMATCH" in result.stdout, result.stdout
    assert verdict_of(result.stdout) == "PASS", (
        "the DISCRIMINATION verdict is genuinely PASS - that is the point. The "
        "run must fail on the provenance axis, not by relabelling the verdict\n"
        + result.stdout
    )
    assert result.returncode == 1, (
        "a recorded digest disagreeing with the committed bytes must fail the "
        "run\n" + result.stdout
    )
    assert "PROVENANCE:MISMATCH" in result.stdout, (
        "the failing line must NAME the axis; printing `-> PASS` for a failing "
        "control is a failure announcing a pass\n" + result.stdout
    )


@requires_git
def test_an_empty_historical_blob_is_still_compared(tmp_path: Path) -> None:
    """The second direction of the same defect (#1157 counter-model re-review).

    The first fix for a `git show` that exits 0 printing nothing was "empty
    stdout means unverified". That is wrong the other way round: a ZERO-BYTE
    FILE IS A LEGITIMATE COMMITTED ARTIFACT - this repository tracks several -
    so the rule excused a real historical anchor from verification entirely.
    Replace such an anchor's file with content, update the manifest digest to
    match the new bytes, and provenance read `unverified` instead of MISMATCH:
    an anchor silently exempt from the check that exists to establish it is the
    artifact it claims to be.

    Existence is established separately now, with `git cat-file -e`, so the byte
    comparison can include empty content. Measured on the reference that started
    this: cat-file -e exits 128 where show exits 0.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    origin = "history/empty-at-that-commit"
    (root / "history").mkdir()
    (root / "history" / "empty-at-that-commit").write_text("", encoding="utf-8")
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=60)
    subprocess.run([*git, "add", "-A"], check=True, timeout=60, capture_output=True)
    subprocess.run([*git, "commit", "-qm", "empty"], check=True, timeout=60, capture_output=True)
    sha = subprocess.run([*git, "rev-parse", "HEAD"], check=True, timeout=60,
                         capture_output=True, text=True).stdout.strip()

    # The anchor on disk is NOT empty, and its recorded digest matches its own
    # bytes - so only the historical comparison can catch the disagreement.
    anchor_path = root / "controls" / "toy" / "anchors" / "deadbee-toy.py"
    digest = hashlib.sha256(anchor_path.read_bytes()).hexdigest()
    _retag_anchor(root, kind="historical", sha=sha, origin=origin, sha256=digest)

    result = run_harness(root, "--strict", "--verify-provenance")
    assert "NEGATIVE_CONTROL_PROVENANCE: MISMATCH" in result.stdout, (
        "an empty committed blob must be COMPARED, not treated as unreadable - "
        "otherwise this anchor is exempt from provenance entirely\n" + result.stdout
    )
    assert result.returncode == 1, result.stdout


def test_a_synthetic_anchor_is_not_checked_against_a_commit_it_never_had(tmp_path: Path) -> None:
    """A constructed anchor has no historical artifact, so git can say nothing.

    Its `sha` is `0000000` by construction and its `origin` is a SENTENCE
    describing the design it embodies rather than a path. Verifying that against
    history is meaningless - and it did not merely return nothing useful, it
    returned a WRONG ANSWER: `git show "0000000:<sentence>"` exits 0 and prints
    NOTHING, so the `returncode != 0` guard never fired, sha256 of the empty
    string was compared against a real file, and `controls/deletion-accounting`
    reported MISMATCH against a commit that does not exist.

    A command reporting success while establishing nothing, its emptiness read
    as content - this repository's own subject, inside the tool written for it.
    """
    root = build_tree(tmp_path, SEEING_GATE)
    _retag_anchor(root, kind="synthetic", sha="0000000",
                  origin="the design refuted by this control, not a path")
    result = run_harness(root, "--strict", "--verify-provenance")
    assert "NEGATIVE_CONTROL_PROVENANCE: unverified" in result.stdout, result.stdout
    assert "MISMATCH" not in result.stdout, (
        "a synthetic anchor must not be accused of disagreeing with a commit it "
        "never came from\n" + result.stdout
    )
    assert result.returncode == 0


@requires_git
def test_the_real_synthetic_anchors_are_not_reported_as_mismatched() -> None:
    """The regression this actually fixed, pinned on the real register.

    `controls/deletion-accounting` carries a synthetic anchor and reported
    MISMATCH under `--verify-provenance` before #1157. With provenance now
    FAILING the run, that false alarm would have become a false red on a real
    control - so the two changes are inseparable: switching the axis on without
    this fix would have manufactured exactly the kind of failure the axis exists
    to prevent.
    """
    result = run_harness(ROOT, "--verify-provenance")
    assert "NEGATIVE_CONTROL_PROVENANCE: MISMATCH" not in result.stdout, (
        "a synthetic anchor is being compared against history again\n" + result.stdout
    )


# --------------------------------------------------------------------------- #
# #1157 - a case may DECLARE that its anchor is blind to the refusal
# --------------------------------------------------------------------------- #

#: The same UNKNOWN registration, plus the declaration and the reason the field
#: requires. Everything else is byte-identical to UNKNOWN_CASES, so a difference
#: in outcome between the two is attributable to the declaration alone.
DECLARED_BLIND_CASES = [
    {"name": "bad", "input": "cases/bad", "expect": "BAD"},
    {"name": "good", "input": "cases/good", "expect": "GOOD"},
    {"name": "unknown", "input": "cases/unknown", "expect": "UNKNOWN",
     "anchor_expect": "clean",
     "anchor_expect_reason": "this anchor predates the refusal branch and never derives the "
                             "population, so it answers with a confident clean"},
]


@pytest.mark.parametrize(
    "escaping",
    [
        "../../tests/fixtures/ci-coverage/no-verify-target",
        "../other-control/cases/good",
        "/etc",
    ],
)
def test_a_case_reaching_outside_its_own_control_is_refused(tmp_path: Path, escaping: str) -> None:
    """The red case for the containment rule (#1157).

    This was proposed as a way to register #1146's two trees without moving
    them, and refused: what makes a control a readable unit is that everything
    it needs lives beneath it. Once one case reaches out, the register cannot be
    read one directory at a time, and a directory move silently breaks a
    registration that still looks valid.

    Refused in the schema rather than agreed in prose, because a schema that
    permits a path it never intends to see is one that will eventually see it.
    """
    cases = [dict(c) for c in UNKNOWN_CASES]
    cases[1]["input"] = escaping
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_TO_REFUSAL_ANCHOR,
        cases=cases, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "outside its own control directory" in result.stdout, result.stdout
    assert result.returncode == 1


def test_a_symlink_loop_does_not_take_the_whole_run_down(tmp_path: Path) -> None:
    """One malformed control must not stop every other control being reported.

    `Path.resolve()` raises RuntimeError - not OSError - on a symlink LOOP under
    the supported 3.11/3.12, so the containment check's first handler let it
    escape and abort the harness with a traceback (#1157 counter-model review,
    LOW). A blanket crash is the worst possible answer for a tool whose subject
    is instruments that report confidently about things they did not examine:
    every OTHER control's verdict disappears, and the run says nothing about any
    of them.
    """
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_TO_REFUSAL_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    looped = root / "controls" / "toy" / "cases" / "unknown"
    shutil.rmtree(looped)
    looped.symlink_to(looped, target_is_directory=True)
    result = run_harness(root, "--strict")
    assert "Traceback" not in result.stderr, (
        "a symlink loop must be a verdict, not a crash that deletes every other "
        "control's result\n" + result.stderr
    )
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert result.returncode == 1


def test_a_symlinked_case_cannot_smuggle_the_escape_back_in(tmp_path: Path) -> None:
    """The same escape wearing a different spelling, which is why resolve() is used.

    A relative `../..` is the obvious form and the only one anybody would
    propose. A case directory that IS a symlink pointing outside the control
    satisfies any string-level check perfectly and lands in exactly the same
    place - the registration names a path under the control, and the bytes
    exercised are somewhere else entirely.
    """
    outside = tmp_path / "elsewhere" / "tests"
    outside.mkdir(parents=True)
    (outside / "UNEXAMINABLE").write_text("x", encoding="utf-8")
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_TO_REFUSAL_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    smuggled = root / "controls" / "toy" / "cases" / "unknown"
    shutil.rmtree(smuggled)
    smuggled.symlink_to(outside.parent, target_is_directory=True)
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "outside its own control directory" in result.stdout, result.stdout


def test_a_case_may_declare_that_its_anchor_is_blind_to_the_refusal(tmp_path: Path) -> None:
    """The change #1157 exists to make, on the shape #1146 actually hit.

    Identical inputs to `test_an_anchor_blind_to_the_refusal_too_is_inert`
    below, which is INERT and is the cost that forbade registering a refusal
    case at all. The ONLY difference is the declaration, so the outcome is
    attributable to it and to nothing else.

    THIS TEST'S PASS IS NOT SELF-SUFFICIENT and saying so is the point: a
    sanity loop that silently SKIPPED declared cases would produce exactly this
    PASS, and look identical to one that scored them. What establishes that the
    case was EXERCISED is its partner below, where a wrong declaration must red
    - a skipped case cannot red. Read the two together or neither means much.
    """
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_TO_REFUSAL_ANCHOR,
        cases=DECLARED_BLIND_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "PASS", result.stdout
    assert result.returncode == 0


def test_a_declared_blind_anchor_that_is_not_blind_reds(tmp_path: Path) -> None:
    """RED CASE (i), and the proof that a declared case is scored at all.

    `BLIND_BUT_REFUSING_ANCHOR` misses the known-bad input, so it clears the
    anchor loop - but it REFUSES the unexaminable one, so it can derive the
    population the declaration says it cannot. The declaration is falsified and
    the recorded reason is stale.

    UNRESOLVED RATHER THAN INERT, DELIBERATELY. INERT means "the anchor is not
    blind enough, replace it", which here would send someone to discard an
    artifact just shown to be MORE capable than the manifest records. Nothing is
    wrong with the anchor or the gate; the REGISTRATION is what stopped being
    true, which is UNRESOLVED's own documented meaning - "the manifest is
    incomplete... NOT a failure of the gate".

    A loop that skipped declared cases would return PASS here, so this test is
    also what makes its partner above mean something.
    """
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_BUT_REFUSING_ANCHOR,
        cases=DECLARED_BLIND_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "declared blind" in result.stdout, result.stdout
    assert "correct the registration rather than replacing the anchor" in result.stdout, (
        "the message must send the reader to the manifest, not to the anchor\n" + result.stdout
    )
    assert result.returncode == 1


@pytest.mark.parametrize(
    ("mutate", "expected_phrase"),
    [
        #: A typo would otherwise read as "must agree" while looking deliberate.
        ({"anchor_expect": "cleanish"}, "the only value that changes anything is 'clean'"),
        #: Declared where it is never read. This is the printed-but-never-consulted
        #: shape, and refusing it here is the difference between a schema field and
        #: a decoration that governs nothing.
        #: Declared where the DIAGNOSIS would not fit. On a BAD or GOOD case a
        #: disagreement is an anchor defect that INERT names correctly; saying
        #: "correct the registration" there would blame the manifest for the
        #: anchor's fault (#1157 counter-model review, MEDIUM).
        ({"anchor_expect": "clean", "anchor_expect_reason": "r", "expect": "BAD"},
         "only meaningful on an UNKNOWN case"),
        ({"anchor_expect": "clean", "anchor_expect_reason": "r", "expect": "GOOD"},
         "only meaningful on an UNKNOWN case"),
        #: Without the recorded cost the field is a bypass for any inconvenient
        #: anchor disagreement.
        ({"anchor_expect": "clean", "anchor_expect_reason": "   "},
         "no anchor_expect_reason"),
        #: COUNTERFEIT REASONS. Each of these survives `str(x or "")` non-empty
        #: and records nothing a human wrote (#1157 counter-model review). The
        #: field charges a cost; these are forged coins.
        ({"anchor_expect": "clean", "anchor_expect_reason": True}, "no anchor_expect_reason"),
        ({"anchor_expect": "clean", "anchor_expect_reason": 1}, "no anchor_expect_reason"),
        ({"anchor_expect": "clean", "anchor_expect_reason": [""]}, "no anchor_expect_reason"),
        ({"anchor_expect": "clean", "anchor_expect_reason": {"": ""}}, "no anchor_expect_reason"),
    ],
)
def test_a_malformed_anchor_expect_is_refused(
    tmp_path: Path, mutate: dict, expected_phrase: str
) -> None:
    """The manifest half. Each of these would otherwise be silently inert."""
    cases = [dict(c) for c in DECLARED_BLIND_CASES]
    cases[2].update(mutate)
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_TO_REFUSAL_ANCHOR,
        cases=cases, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert expected_phrase in result.stdout, result.stdout
    assert result.returncode == 1


def test_an_anchor_blind_to_the_refusal_too_is_inert(tmp_path: Path) -> None:
    """Anchor-sanity applies to a refusal exactly as it does to a clean run: an
    anchor that disagrees there differs for reasons beyond the blindness under
    test, so the demonstration isolates nothing.

    This is the rule's real cost, pinned deliberately rather than discovered by
    whoever adds the next case: an anchor frozen from before a gate's refusal
    branch existed reports clean where the gate refuses, and forbids any UNKNOWN
    case on that control while it stands.

    SINCE #1157 THIS IS ALSO RED CASE (ii), AND IT IS THE LOAD-BEARING ONE.
    `anchor_expect` is an OPTIONAL field added to an instrument's case schema,
    which is a WIDENING - and the question a widening has to answer is not "does
    the new field work" but "did every case that does not use it keep its
    meaning". This registration declares nothing, so it must STILL red exactly
    as it did before the field existed. Its inputs are identical to
    `test_a_case_may_declare_that_its_anchor_is_blind_to_the_refusal` above
    except for the declaration, so the pair isolates the field's effect to the
    declaration alone.
    """
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=BLIND_TO_REFUSAL_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "INERT", result.stdout
    assert "known-UNEXAMINABLE" in result.stdout, (
        "the message must name the kind of input that disagreed, or a reader "
        "hunts for a clean-run disagreement that is not there\n" + result.stdout
    )
    assert result.returncode == 1


# --------------------------------------------------------------------------- #
# Counter-model review of the #1129 change (codex/gpt-6-astra), accepted.
# Each of these reproduces a way the new expectation could certify evidence the
# change's own rules reject elsewhere.
# --------------------------------------------------------------------------- #


def test_an_anchor_whose_refusal_is_also_a_detection_is_unresolved(tmp_path: Path) -> None:
    """The refusal/detection overlap check must cover the ANCHOR too.

    It ran only over the CASE loop, so ambiguous output was rejected when the
    current gate produced it and ACCEPTED as agreement when the anchor did - and
    an anchor is a different program, so the gate-side check is no evidence about
    it. The control then reported PASS on exactly the evidence the change
    declares inadmissible one function earlier.
    """
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=AMBIGUOUS_ON_REFUSAL_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", (
        "ambiguous anchor output must not be accepted as agreement\n" + result.stdout
    )
    assert result.returncode == 1


def test_a_refusal_is_not_evidence_that_the_gates_tool_was_present(tmp_path: Path) -> None:
    """A gate may refuse an input BEFORE it checks its own tool - and the real
    `shellcheck-gate.sh` does, testing `[ -d "$ROOT" ]` before `command -v
    shellcheck`.

    So on a host missing the tool, the known-bad and known-good cases report
    UNAVAILABLE while the UNKNOWN case genuinely refuses. Counting that refusal
    as proof the gate RAN produced the #1117 contradiction verdict and the
    sentence "so the tool was present" - a confident false statement about the
    machine, which is the failure class this whole file exists to refuse. The
    honest answer is UNAVAILABLE: the control is unexamined here.
    """
    root = build_tree(
        tmp_path, REFUSES_BEFORE_CHECKING_ITS_TOOL_GATE, cases=UNKNOWN_CASES,
        unavailable_signal=TOY_UNAVAILABLE, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict", "--allow-unavailable")
    assert verdict_of(result.stdout) == "UNAVAILABLE", (
        "a refusal says nothing about whether the gate's TOOL was installed\n"
        + result.stdout
    )
    assert "the tool was present" not in result.stdout, (
        "the harness must not assert the tool was present on the strength of a "
        "refusal\n" + result.stdout
    )
    assert result.returncode == 0


def test_a_recognised_unavailability_is_exempt_from_the_overlap_check(tmp_path: Path) -> None:
    """The overlap check answers "can a refusal be told from a finding". On a run
    already identified as UNAVAILABLE by the most specific declared pattern, that
    question is moot - the case is skipped and never scored - so firing there
    turns an environment fact into a manifest accusation.

    The registration below is the shape that exposes it: both the detection and
    the refusal pattern legitimately include the tool-absent message as one
    alternative, which is the same relationship
    `flow-driver-retirement-check.sh` already has between its unavailability
    line and its detection pattern.
    """
    root = build_tree(
        tmp_path, UNAVAILABLE_GATE,
        detect_signal=r"^toy-gate: (FINDING|UNAVAILABLE) - ",
        unavailable_signal=TOY_UNAVAILABLE,
        unknown_signal=r"^toy-gate: (UNKNOWN|UNAVAILABLE) - ",
    )
    result = run_harness(root, "--strict", "--allow-unavailable")
    assert verdict_of(result.stdout) == "UNAVAILABLE", (
        "an absent tool must stay an environment fact, not become an "
        "UNRESOLVED accusation about the manifest\n" + result.stdout
    )
    assert result.returncode == 0


def test_an_anchor_that_exits_clean_while_announcing_a_refusal_is_unresolved(
    tmp_path: Path,
) -> None:
    """Constraint 2 ("the refusal marker may not match a clean run") has to cover
    the ANCHOR as well, for the same reason constraint 3 does: the anchor is a
    different program.

    Exiting like a clean run while announcing a refusal is not a verdict at all -
    it cannot have examined the input and also have been unable to look at it -
    so reading it as "missed the known-bad input, blind as required" certifies
    incoherent evidence as the demonstration.
    """
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=CLEAN_BUT_REFUSING_ON_BAD_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "exited like a CLEAN run" in result.stdout, result.stdout
    assert result.returncode == 1


def test_the_same_contradiction_on_a_sanity_case_is_also_unresolved(tmp_path: Path) -> None:
    """The anchor-sanity loop needs the check too, not just the known-bad loop:
    an anchor can miss the known-bad input correctly and still be incoherent on
    the inputs that are supposed to establish it differs in nothing else."""
    root = build_tree(
        tmp_path, REFUSING_GATE, anchor_src=CLEAN_BUT_REFUSING_ON_GOOD_ANCHOR,
        cases=UNKNOWN_CASES, unknown_signal=TOY_UNKNOWN,
    )
    result = run_harness(root, "--strict")
    assert verdict_of(result.stdout) == "UNRESOLVED", result.stdout
    assert "exited like a CLEAN run" in result.stdout, result.stdout
    assert result.returncode == 1


# --------------------------------------------------------------------------- #
# The ruff fixture exclusions - a tolerance that must not grow silently (#1180)
# --------------------------------------------------------------------------- #
EXPECTED_RUFF_EXCLUDE = [
    "controls/*/anchors",
    "controls/check-negative-fixture-preconditions/cases/unknown-unparseable-neighbour/tests/test_broken.py",
    "controls/check-negative-fixture-preconditions/cases/unknown-unparseable-with-violation/tests/test_broken.py",
]


def _live_ruff_exclude() -> list[str]:
    """The exclude list AS SHIPPED, not the expectation above.

    The property tests below must read this. An earlier cut iterated
    EXPECTED_RUFF_EXCLUDE and so asserted facts about a literal in this file -
    it stayed green through a mutation that added `controls/*/cases/**` to the
    real config, which is the exact widening it was written to forbid. Caught
    by running the mutation and counting the failures: one, where two were due.
    """
    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return list(config["tool"]["ruff"]["exclude"])


def test_the_ruff_fixture_exclusions_have_not_grown() -> None:
    """The lint exclusion is an instrument change, so it gets a guard (#1180).

    `pyproject.toml` excludes two fixture FILES from ruff because the
    `check-negative-fixture-preconditions` control needs a case whose input does
    not parse, and a fixture that cannot lint cannot coexist with a policy that
    lints every fixture. Taking that exception is correct; letting it SPREAD is
    not. A widened pattern would silently excuse the next unparseable fixture
    somebody adds by accident - removing, for every other fixture in the tree,
    exactly the distinction ruff is there to draw.

    Asserting exact membership rather than "the two are present" is what makes
    this a guard: the failure it must catch is an ADDITION, and a containment
    check cannot see one.
    """
    exclude = _live_ruff_exclude()

    assert sorted(exclude) == sorted(EXPECTED_RUFF_EXCLUDE), (
        "the ruff exclude list changed. Every entry here suppresses linting for "
        "something, so adding one is a deliberate act that belongs in a review: "
        f"added={sorted(set(exclude) - set(EXPECTED_RUFF_EXCLUDE))} "
        f"removed={sorted(set(EXPECTED_RUFF_EXCLUDE) - set(exclude))}"
    )


def test_each_excluded_fixture_is_actually_unparseable_and_actually_present() -> None:
    """A stale exclusion is a silent tolerance for a file that now lints fine.

    The two entries are justified ONLY by the files being unparseable by
    construction. If one is deleted, renamed, or quietly repaired, the exclusion
    stops paying for itself and becomes a standing hole nobody is watching - and
    nothing else in the suite would notice, because an exclusion that covers
    nothing produces no output at all.

    This also pins the direction that matters for the control: the file must
    STILL fail to parse, or `unknown-unparseable-*` silently stops exercising
    the refusal branch and starts testing an ordinary clean tree.
    """
    import ast

    fixtures = [e for e in _live_ruff_exclude() if e.endswith(".py")]
    assert fixtures, "no fixture files are excluded, so this guard is watching nothing"

    for rel in fixtures:
        path = ROOT / rel
        assert path.is_file(), f"excluded fixture {rel} is missing; the exclusion is stale"
        with pytest.raises(SyntaxError):
            ast.parse(path.read_text(encoding="utf-8"))


def test_no_fixture_exclusion_is_a_directory_or_glob() -> None:
    """Only `controls/*/anchors` may be a pattern; a fixture exception is per-file.

    The anchors entry is a directory pattern for a different and settled reason
    (#924: an anchor is a frozen byte-identical copy). The #1180 exceptions are
    not allowed to borrow that shape - a glob is precisely how "two known files"
    becomes "anything under here" without anyone deciding to.
    """
    for entry in _live_ruff_exclude():
        if entry == "controls/*/anchors":
            continue
        assert entry.endswith(".py"), f"fixture exclusion {entry!r} is not a single file"
        assert "*" not in entry and "?" not in entry, (
            f"fixture exclusion {entry!r} is a glob; name the file instead"
        )


# --------------------------------------------------------------------------- #
# `subject_kind` - the reporter relaxation, and the three ways it must not leak
# (issue #1085)
# --------------------------------------------------------------------------- #
SUBJECT_CASES = ROOT / "controls" / "check-negative-controls" / "cases"


def test_a_gate_control_with_no_bad_case_still_reports_unresolved() -> None:
    """THE LEAK GUARD. If this ever passes, the relaxation reached every control.

    `subject_kind: reporter` lets an instrument demonstrate blindness on the
    refusal axis instead of with a BAD case. The whole risk is that the
    exception widens: a GATE control that simply forgot its known-bad input
    must keep being refused exactly as it was before the field existed.

    This cannot be a CASE in `controls/check-negative-controls` because that
    control's anchor is a frozen copy of the harness, and on behaviour this
    change does not alter the anchor behaves identically to the fixed gate and
    scores INERT. It is asserted here instead, over the same committed tree.
    """
    out = run_harness(SUBJECT_CASES / "bad-gate-control-without-a-bad-case", "--strict")
    assert out.returncode != 0
    assert "registers no BAD case" in out.stdout + out.stderr, out.stdout


def test_a_reporter_without_a_qualifying_unknown_case_is_refused() -> None:
    """`reporter` is a SECOND WAY TO PAY, never a waiver.

    Declaring the kind must not by itself discharge the requirement. A reporter
    still has to put up an input it refuses and the anchor answers clean; with
    no such case there is nothing demonstrating the anchor is blind at all.
    """
    out = run_harness(SUBJECT_CASES / "bad-reporter-without-a-qualifying-unknown", "--strict")
    assert out.returncode != 0
    body = out.stdout + out.stderr
    assert "registers no UNKNOWN case carrying `anchor_expect: clean`" in body, body
    assert "never a waiver" in body


def test_a_reporter_demonstrating_blindness_on_the_refusal_axis_passes() -> None:
    """The positive control, without which the two above pass on a harness that
    refuses everything.

    The toy refuses an input it cannot examine (exit 2, UNKNOWN); its anchor has
    no refusal branch and answers the same input with a confident clean. The
    fixed instrument refuses, the blind one does not - that is a discrimination,
    and it is the one a reporter can actually make.
    """
    out = run_harness(SUBJECT_CASES / "good-reporter-on-the-refusal-axis", "--strict")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "-> PASS" in out.stdout or "ok -" in out.stdout, out.stdout


def test_an_unrecognised_subject_kind_is_refused_not_defaulted() -> None:
    """Defaulting on a typo is how a narrow exception becomes a wide one.

    `"Reporter"` is what a real author writes. Silently treating it as `gate`
    would be merely confusing; silently treating it as `reporter` would hand out
    the relaxation to anyone who miscapitalised. Neither: it is refused and the
    value is named.
    """
    out = run_harness(SUBJECT_CASES / "bad-unrecognised-subject-kind", "--strict")
    assert out.returncode != 0
    body = out.stdout + out.stderr
    assert "declares subject_kind 'Reporter'" in body, body
    assert "refused rather than defaulted" in body


def test_absent_cases_key_is_named_differently_from_a_one_sided_case_list(
    tmp_path: Path
) -> None:
    """ABSENT is not EMPTY, and the message must not confuse them.

    `spec.get("cases", [])` turned a manifest declaring no `cases` key into one
    declaring an empty list, so a file with no cases at all was reported as
    "registers no BAD case" - a sentence about cases, to someone whose file has
    none. Both refuse, so this was never a false clean; it named the wrong
    defect and sent the reader looking for a list that does not exist.
    """
    (tmp_path / "scripts").mkdir()
    gate = tmp_path / "scripts" / "toy-gate.sh"
    gate.write_text("#!/bin/sh\n#: NEGATIVE-CONTROL: controls/toy\necho ok\n", encoding="utf-8")
    toy = tmp_path / "controls" / "toy"
    toy.mkdir(parents=True)
    (toy / "control.json").write_text(
        json.dumps({"gate": "scripts/toy-gate.sh",
                    "invocation": ["sh", "{gate}"],
                    "good_exit": 0,
                    "detect_signal": "^toy",
                    "anchors": []}),
        encoding="utf-8",
    )
    out = run_harness(tmp_path, "--strict")
    body = out.stdout + out.stderr
    assert "declares no `cases` key at all" in body, body
    assert "registers no BAD case" not in body, "absent was reported as one-sided"


def test_a_reporter_only_battery_does_not_claim_a_detection_it_never_made() -> None:
    """The success line must be built from the population, not asserted over it.

    FOUND BY COUNTER-MODEL REVIEW. The summary ended "each reporting its
    declared detection signal on the known-bad input" UNIVERSALLY, with the
    kind breakdown appended after. Over a battery of reporters that certifies a
    detection which cannot happen - a reporter has no known-bad input and emits
    no detection signal, by the same structural fact that made `subject_kind`
    necessary. The appended clause EXPLAINED the contradiction rather than
    removing it.

    That is a success message claiming more than its input population supports,
    which is the first question this file makes every other gate answer. Getting
    it wrong here is worse than getting it wrong elsewhere.
    """
    out = run_harness(
        ROOT / "controls" / "check-negative-controls" / "cases"
        / "good-reporter-on-the-refusal-axis", "--strict"
    )
    assert out.returncode == 0, out.stdout + out.stderr
    ok = [ln for ln in out.stdout.splitlines() if ln.startswith("negative-controls: ok")]
    assert len(ok) == 1, out.stdout
    line = ok[0]
    assert "reporter control(s)" in line, line
    assert "each REFUSING an input its anchor answers clean" in line, line
    assert "detection signal on the known-bad input" not in line, (
        "a reporter-only battery claimed a detection it never made: " + line
    )


# --------------------------------------------------------------------------- #
# `detect_signal` optional for a reporter - the requirement RELOCATES (#1085)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("sh") is None, reason="drives a toy gate through sh")
def test_a_reporter_may_omit_detect_signal_when_it_declares_unknown_signal() -> None:
    """THE POSITIVE CONTROL. Without it the three guards below pass on a harness
    that refuses every reporter.

    A reporter has no finding to mark: its only non-zero exit is a refusal, and
    `unknown_signal` is what separates that from a crash. So `detect_signal` has
    nothing to match, and every pattern one could write is dishonest - either it
    matches the ordinary measurement output, or it can never match at all.
    """
    out = run_harness(
        ROOT / "controls" / "check-negative-controls" / "cases"
        / "good-reporter-without-detect-signal", "--strict"
    )
    assert out.returncode == 0, out.stdout + out.stderr


@pytest.mark.skipif(shutil.which("sh") is None, reason="drives a toy gate through sh")
def test_a_reporter_with_neither_marker_is_refused() -> None:
    """THE RELOCATED FAIL-OPEN, and the case that decides whether this ships.

    `detect_signal` is required because a non-zero exit must be tellable from a
    CRASH (#946). Letting a reporter drop it without requiring `unknown_signal`
    would not relax that guarantee, it would DELETE it - the same hole, moved.
    """
    out = run_harness(
        ROOT / "controls" / "check-negative-controls" / "cases"
        / "bad-reporter-with-no-markers", "--strict"
    )
    assert out.returncode != 0
    body = out.stdout + out.stderr
    assert "neither a detect_signal nor an unknown_signal" in body, body
    assert "RELOCATES and does not lapse" in body


@pytest.mark.skipif(shutil.which("sh") is None, reason="drives a toy gate through sh")
def test_a_reporter_declaring_a_dishonest_detect_signal_is_still_refused() -> None:
    """Optional is not unchecked. A reporter that DOES declare one is validated
    exactly as a gate is, so the relaxation cannot be used to smuggle a marker
    that identifies a clean run as readily as a finding.
    """
    out = run_harness(
        ROOT / "controls" / "check-negative-controls" / "cases"
        / "bad-reporter-detect-matches-clean", "--strict"
    )
    assert out.returncode != 0
    assert "also matches this gate's known-GOOD output" in out.stdout + out.stderr


@pytest.mark.skipif(shutil.which("sh") is None, reason="drives a toy gate through sh")
def test_a_gate_with_no_detect_signal_is_still_refused() -> None:
    """THE LEAK GUARD. If this passes, the relaxation escaped its subject kind.

    Same shape as the guard on the BAD-case requirement: the exception is for
    reporters, and a gate that simply forgot its detection marker must keep
    being refused exactly as before the field existed.
    """
    out = run_harness(
        ROOT / "controls" / "check-negative-controls" / "cases"
        / "bad-gate-with-no-detect-signal", "--strict"
    )
    assert out.returncode != 0
    assert "declares no detect_signal" in out.stdout + out.stderr


@pytest.mark.skipif(shutil.which("sh") is None, reason="drives a toy gate through sh")
def test_an_explicitly_invalid_detect_signal_is_refused_not_treated_as_omitted() -> None:
    """OMITTED is not INVALID - the distinction this whole change rests on.

    FOUND BY COUNTER-MODEL REVIEW. The exemption first keyed on "is there a
    usable pattern", which is true of an absent field and equally true of
    `"detect_signal": ""`, `null`, `0` or `[]`. A control that DECLARED a broken
    signal therefore took the reporter branch, had the sentinel substituted, and
    passed with its validations disabled - the author said something and the
    harness silently heard nothing.

    Declaring nothing and declaring something broken are different acts. The
    first is what the exemption is for; the second keeps the old answer.

    The irony is load-bearing rather than decorative: this is the absent-versus-
    empty conflation that the change's own rationale is built on, written into
    the change itself. It is asserted here so the next edit cannot reintroduce
    it quietly.
    """
    import json as _json

    toy = (ROOT / "controls" / "check-negative-controls" / "cases"
           / "good-reporter-without-detect-signal" / "controls" / "toy" / "control.json")
    original = toy.read_text(encoding="utf-8")
    assert "detect_signal" not in _json.loads(original), (
        "the fixture must OMIT detect_signal for this test to mean anything"
    )
    try:
        for bad in ("", " ", None, 0, []):
            doc = _json.loads(original)
            doc["detect_signal"] = bad
            toy.write_text(_json.dumps(doc, indent=2), encoding="utf-8")
            out = run_harness(toy.parents[2], "--strict")
            assert out.returncode != 0, f"detect_signal={bad!r} was treated as omitted"
            assert "declares no detect_signal" in out.stdout + out.stderr, out.stdout
    finally:
        toy.write_text(original, encoding="utf-8")

    # A VALID BUT OVER-BROAD PATTERN IS A THIRD CASE, and it takes a different
    # path: `.*` is a usable regex, so it is NOT an omission and NOT invalid -
    # it goes through normal validation and is refused by the empty-output
    # guard. Pinned here because "declared something broken" and "declared
    # something too wide" fail for different reasons and a reader chasing
    # either should land in the right place.
    try:
        doc = _json.loads(original)
        doc["detect_signal"] = ".*"
        toy.write_text(_json.dumps(doc, indent=2), encoding="utf-8")
        out = run_harness(toy.parents[2], "--strict")
        assert out.returncode != 0
        assert "matches empty output" in out.stdout + out.stderr, out.stdout
    finally:
        toy.write_text(original, encoding="utf-8")

    # ...and omission itself still passes, or the assertions above are vacuous.
    out = run_harness(toy.parents[2], "--strict")
    assert out.returncode == 0, out.stdout + out.stderr


def _load_harness_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_negative_controls_1239", HARNESS)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registered first: the module's dataclasses resolve their own module by name.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _tracking_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real repository carrying this repo's own ignore shape (issue #1239).

    `__pycache__/` and the blanket `*.json` negated one level deep are the two
    rules that matter: the first is what hides derived bytecode, the second is
    the #964/#953 hazard `_tracking()` exists to catch.
    """
    root = tmp_path / "repo"
    case_dir = root / "controls" / "toy" / "cases" / "bad"
    case_dir.mkdir(parents=True)
    (root / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n*.json\n!controls/*/control.json\n", encoding="utf-8"
    )
    (root / "controls" / "toy" / "control.json").write_text("{}\n", encoding="utf-8")
    (case_dir / "subject.py").write_text("X = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=60)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, timeout=60)
    return root, case_dir


@requires_git
def test_ignored_bytecode_under_a_control_does_not_read_as_UNTRACKED(tmp_path: Path) -> None:
    """A case that runs Python writes `__pycache__/*.pyc` beside itself (#1239).

    Before the fix, the SECOND `make verify` in any checkout reported the
    control UNTRACKED on that bytecode alone, although a clean clone has every
    file the control needs. Red on the pre-fix harness: `UNTRACKED` naming the
    `.pyc`.
    """
    root, case_dir = _tracking_repo(tmp_path)
    cache = case_dir / "__pycache__"
    cache.mkdir()
    (cache / "subject.cpython-311.pyc").write_bytes(b"\x00bytecode")
    (case_dir / "stray.pyo").write_bytes(b"\x00bytecode")
    precondition = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "-q", str(cache / "subject.cpython-311.pyc")],
        check=False, timeout=60,
    )
    assert precondition.returncode == 0, "precondition: the bytecode must be gitignored"

    verdict, details = _load_harness_module()._tracking(root / "controls" / "toy", root)
    assert (verdict, details) == ("tracked", []), details


@requires_git
def test_an_ignored_LOAD_BEARING_case_file_still_reads_as_UNTRACKED(tmp_path: Path) -> None:
    """The exclusion for #1239 must stay exactly as wide as derived bytecode.

    `_tracking()` exists for the #964/#953 shape: a nested `case.json` swallowed
    by the blanket `*.json`. Excluding every IGNORED path would have fixed #1239
    and blinded this, so this is the case that fails if the fix widens - with a
    `.pyc` present alongside, so it cannot pass by never meeting bytecode.
    """
    root, case_dir = _tracking_repo(tmp_path)
    (case_dir / "case.json").write_text("{}\n", encoding="utf-8")
    (case_dir / "__pycache__").mkdir()
    (case_dir / "__pycache__" / "subject.cpython-311.pyc").write_bytes(b"\x00bytecode")

    verdict, details = _load_harness_module()._tracking(root / "controls" / "toy", root)
    assert verdict == "UNTRACKED", details
    assert "case.json" in details[0], details
    assert ".pyc" not in details[0], "bytecode must not be named as a missing control file"

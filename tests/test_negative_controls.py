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
import re
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


def build_tree(
    tmp_path: Path,
    gate_src: str,
    anchor_src: str | None = BLIND_GATE,
    cases: list[dict[str, str]] | None = None,
    detect_signal: str | None = TOY_SIGNAL,
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



def _verdicts_by_gate(out: str) -> dict[str, str]:
    """Pair each NEGATIVE_CONTROL_GATE with the VERDICT that follows it."""
    pairs: dict[str, str] = {}
    gate = None
    for line in out.splitlines():
        if line.startswith("NEGATIVE_CONTROL_GATE: "):
            gate = line.split(": ", 1)[1]
        elif line.startswith("NEGATIVE_CONTROL_VERDICT: ") and gate is not None:
            pairs[gate] = line.split(": ", 1)[1]
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


def test_self_registration_is_blind_to_a_verdict_assignment_breakage(tmp_path: Path) -> None:
    """HALF ONE of #964's mutation demonstration, and the uncomfortable half.

    A harness that emits PASS unconditionally reports PASS about its OWN
    control, because the thing doing the reporting is the thing that is broken.
    The register row therefore keeps saying the harness is covered while the
    harness has stopped being able to disagree with anything.
    """
    mutant = _forced_pass_harness(tmp_path)
    run = subprocess.run(
        [sys.executable, str(mutant), "--root", str(ROOT), "--strict"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    by_gate = _verdicts_by_gate(run.stdout)
    assert by_gate, run.stdout
    assert by_gate.get("scripts/check-negative-controls.py") == "PASS", (
        "the demonstration must be about the harness's OWN row; if the "
        f"self-registration is gone this is vacuous. rows={by_gate}"
    )
    assert set(by_gate.values()) == {"PASS"}, run.stdout
    assert run.returncode == 0, (
        "a harness that cannot say anything but PASS exits 0 under --strict, "
        "including about itself: the self-registration cannot see this"
    )


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

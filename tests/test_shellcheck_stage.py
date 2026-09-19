"""`shellcheck-stage` is split out of the gate, and its absence still REDDENS (issue #1086).

WHAT CHANGED AND WHY IT NEEDS A CASE. `validate` used to wait on the `shellcheck`
STEP for one thing: the pinned binary that step copies into `.ci-bin`. The copy
takes about a second; the lint it shared a step with takes thirty, measured
directly (`time sh scripts/shellcheck-gate.sh` -> `real 0m30.381s`). So `pytest`,
84% of the pipeline's wall clock, sat behind a lint whose output it never reads.
#1086 splits the staging into its own step and repoints `validate` and
`negative-controls` at THAT.

Moving a dependency is exactly the kind of edit that looks free and is not. Two
ways it can go wrong, and each has a case below:

  1. A CONSUMER STOPS DEPENDING ON ITS STAGER. Woodpecker runs steps concurrently
     unless `depends_on` orders them, so this does not fail loudly - it races, and
     loses intermittently. `tests/test_verify_wiring.py` owns that invariant and
     #1086 parametrised it over both stagers rather than writing a second copy of
     it here.

  2. THE BINARY IS SIMPLY NOT THERE. This is the acceptance item's own words -
     "a case where `.ci-bin/shellcheck` is absent must make `validate` and
     `negative-controls` report UNKNOWN rather than skip ... a check that the
     existing refusal still fires after the dependency moves."

NO TEST IN THIS REPOSITORY ASSERTED (2) BEFORE #1086. The refusal is real and it
is implemented in two places - `scripts/shellcheck-gate.sh` exits 2 with UNKNOWN
when `command -v shellcheck` fails, and `check-negative-controls.py` scores a gate
it cannot run as UNSIGNALLED rather than skipping it - but "the tool was present
on every run so far" is not evidence about what happens when it is not. Re-reading
the gate checks what it MEANT; only a known-bad input checks what it CAN say.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "shellcheck-gate.sh"
WOODPECKER = ROOT / ".woodpecker.yml"

#: A committed tree of shell files the gate is known to examine and pass. Reusing
#: the control's own GOOD case keeps this test measuring the gate's behaviour
#: rather than a fixture written to suit it.
CASE = ROOT / "controls" / "shellcheck-gate" / "cases" / "good-extensionless"


def _steps() -> dict:
    return yaml.safe_load(WOODPECKER.read_text(encoding="utf-8"))["steps"]


# --------------------------------------------------------------------------- #
# The refusal: absent binary is UNKNOWN, never a pass
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("sh") is None, reason="runs the gate under sh")
def test_the_gate_reports_UNKNOWN_when_the_staged_binary_is_absent(
    tmp_path: Path,
) -> None:
    """With no shellcheck reachable, the gate must exit 2 - not 0, not 1.

    THE PRECONDITION IS ASSERTED FIRST. This constructs an absence by replacing
    PATH wholesale, and a fixture that builds an absence indirectly can build one
    broader or narrower than it intended - so the emptiness is checked against the
    same PATH the child will get before the gate is ever invoked (the CLAUDE.md
    directive `check-negative-fixture-preconditions.py` enforces). Without it, a
    stub directory that happened to contain a shellcheck would make this test
    green for the opposite reason.

    Replacing PATH is safe for this particular gate, and that is a property worth
    stating rather than assuming: `command -v shellcheck` is the SECOND thing it
    does, before any call to git, find, tr or wc, and `unknown()` uses only shell
    builtins. So an empty PATH reaches the intended refusal rather than dying on
    a missing coreutil somewhere else and exiting 2 for an unrelated reason.
    """
    stub_bin = tmp_path / "empty-bin"
    stub_bin.mkdir()

    assert shutil.which("shellcheck", path=str(stub_bin)) is None, (
        "the stub PATH already contains a shellcheck, so this case does not "
        "construct the absence it is about"
    )

    sh = shutil.which("sh")
    assert sh is not None
    result = subprocess.run(
        [sh, str(GATE), "--root", str(CASE)],
        env={"PATH": str(stub_bin)},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 2, (
        f"with shellcheck absent the gate exited {result.returncode}, not 2. "
        f"Exit 0 would mean an unstaged binary reads as a clean lint, which is "
        f"the failure the staging step exists to prevent.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "UNKNOWN" in combined and "this is not a pass" in combined, (
        f"the gate exited 2 without saying UNKNOWN, so a reader (and the control "
        f"harness) cannot tell a refusal from a crash.\n{combined}"
    )


@pytest.mark.skipif(
    shutil.which("shellcheck") is None,
    reason="the positive control needs a real shellcheck (CI stages the pinned one into .ci-bin)",
)
def test_the_same_tree_passes_when_the_binary_IS_present() -> None:
    """THE HALF THAT MATTERS: the refusal above is about the binary, not the tree.

    A gate that exited 2 on everything would satisfy the case above on its own
    and would say nothing about staging. This is what separates them - same gate,
    same tree, one difference.
    """
    result = subprocess.run(
        ["sh", str(GATE), "--root", str(CASE)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"the known-good tree did not pass with shellcheck present, so the "
        f"UNKNOWN above cannot be attributed to the missing binary.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "shellcheck-gate: ok" in result.stdout


# --------------------------------------------------------------------------- #
# The split itself
# --------------------------------------------------------------------------- #
def test_the_staging_step_exists_and_stages_the_pinned_binary() -> None:
    """`shellcheck-stage` copies from the PINNED image, and only copies.

    Pinning is the whole point of staging rather than a detail of it: apt in that
    image supplies shellcheck 0.9.0 while the pipeline pins 0.10.0, and
    `.woodpecker.yml` already states the consequence at this step - running the
    gate under two different linters makes `controls/shellcheck-gate`'s verdict
    depend on which container reached it.
    """
    steps = _steps()
    assert "shellcheck-stage" in steps, (
        "the shellcheck-stage step is gone; `validate` and `negative-controls` "
        "would have no pinned shellcheck and every control needing it reports "
        "UNSIGNALLED"
    )
    stage = steps["shellcheck-stage"]
    # `str(c)`: a YAML command need not be a string - a bare `true` parses as a
    # bool - and the membership test would raise TypeError rather than assert.
    assert any(".ci-bin/shellcheck" in str(c) for c in stage["commands"]), (
        "shellcheck-stage no longer stages the binary into .ci-bin"
    )
    assert "@sha256:" in stage["image"], (
        f"shellcheck-stage runs an unpinned image ({stage['image']}); the staged "
        f"binary's version would then depend on when the step ran"
    )
    assert stage["image"] == steps["shellcheck"]["image"], (
        "the staging step and the gate step run DIFFERENT images, so the binary "
        "staged for the controls is not the one the pipeline's own lint used"
    )


def test_the_gate_step_no_longer_blocks_the_critical_path() -> None:
    """Nothing may depend on the `shellcheck` step - that is the whole change.

    Stated as a property of the graph rather than as a comment, because the
    30 seconds comes back silently: a future step that adds `shellcheck` to its
    `depends_on` for the binary would be correct-looking, green, and would undo
    #1086 without anything saying so.
    """
    steps = _steps()
    dependents = [
        name
        for name, step in steps.items()
        if "shellcheck" in (step.get("depends_on") or [])
    ]
    assert dependents == [], (
        f"{dependents} depend on the `shellcheck` GATE step rather than on "
        f"`shellcheck-stage`, so the 30-second lint is back on the critical path. "
        f"If the binary is what they need, depend on `shellcheck-stage`."
    )
    assert "shellcheck-stage" not in (steps["shellcheck"].get("depends_on") or []), (
        "the gate step now waits for the staging step, which serialises the two "
        "for no reason - they are independent"
    )

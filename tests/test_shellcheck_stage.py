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

import os
import re
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


def test_a_declared_staging_that_did_not_deliver_FAILS_rather_than_skips() -> None:
    """The gap the counter-model review found (#1086, gpt-6-astra, MEDIUM).

    Every other test here survives the binary going missing: the absence case
    builds its own empty PATH and passes regardless, and the positive control
    below SKIPS. So if `shellcheck-stage` silently stopped delivering, the
    `negative-controls` step would redden and `validate` - the pytest run - would
    go GREEN. The acceptance item names both steps, and only one of them was
    covered.

    This is the #1017 shape exactly: `tests/test_flow_driver_retirement.py`
    carried a module-level `skipif(which("jq") is None)` and skipped all 26 of its
    tests in CI while `validate` stayed green - load-bearing on a dev box, inert
    in the one environment a reviewer can re-derive.

    THE DISCRIMINATOR IS `.ci-bin` ON PATH, not a CI environment variable. Both
    consuming steps prepend `$PWD/.ci-bin` to PATH; that prefix is the run
    DECLARING that a staged toolchain is supposed to be there. Where it is
    declared, an absent binary is a broken stage and must fail. Where it is not -
    an ordinary dev box - nothing was promised, and skipping is honest. Keying on
    a CI variable instead would make this inert anywhere that variable is unset,
    which is the same defect one level up.
    """
    on_path = [
        part for part in os.environ.get("PATH", "").split(os.pathsep)
        if part.rstrip("/").endswith(".ci-bin")
    ]
    if not on_path:
        pytest.skip("no .ci-bin on PATH - this run declares no staged toolchain")

    found = shutil.which("shellcheck")
    assert found is not None, (
        f"PATH declares a staged toolchain ({on_path}) but no shellcheck is "
        f"reachable, so `shellcheck-stage` did not deliver. Every control that "
        f"needs it will report UNSIGNALLED and this suite would otherwise have "
        f"passed without noticing."
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


#: A step that EXECUTES the suite or the control battery. These are the only
#: steps whose start time the staging split was about, and scoping to them is
#: pass 2 of the counter-model review (#1086, gpt-6-astra, MEDIUM).
#:
#: Derived from what a step DOES, never a hardcoded name list: a future
#: `validate2` that runs pytest inherits this guard, and a `publish` step that
#: merely reads `.ci-bin` for jq does not. The previous cut keyed on ".ci-bin
#: appears in the commands", which swept in exactly that publish step and failed
#: it under a message claiming the lint was back in front of pytest - a non-zero
#: that could not tell our regression from a neighbour's legitimate edge.
EXECUTORS = re.compile(r"(?<![\w./-])pytest(?![\w./-])|check-negative-controls\.py")


def _ancestors(steps: dict, name: str) -> set:
    """Every step `name` transitively waits on.

    Transitive rather than direct: an intermediate step is how the gate comes
    back onto the critical path without anyone naming `shellcheck` in a consumer.
    """
    seen: set = set()
    stack = list((steps.get(name) or {}).get("depends_on") or [])
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend((steps.get(current) or {}).get("depends_on") or [])
    return seen


def _executors(steps: dict) -> list:
    return [
        name for name, step in steps.items()
        if any(EXECUTORS.search(str(c)) for c in (step.get("commands") or []))
    ]


def test_the_gate_step_no_longer_blocks_the_critical_path() -> None:
    """No step that RUNS the suite may transitively wait on the `shellcheck` gate.

    Stated as a property of the graph rather than as a comment, because the
    30 seconds comes back silently: a future step that adds `shellcheck` to a
    consumer's `depends_on` for the binary would be correct-looking, green, and
    would undo #1086 without anything saying so.
    """
    steps = _steps()
    executors = _executors(steps)
    assert executors, (
        "no step runs pytest or the control battery, so this guard has no subject "
        "and would pass vacuously - the executing steps are gone or renamed"
    )

    offenders = {
        name: sorted(_ancestors(steps, name))
        for name in executors
        if "shellcheck" in _ancestors(steps, name)
    }
    assert not offenders, (
        f"a step that RUNS the suite waits on the `shellcheck` gate: {offenders}. "
        f"That puts the 30-second lint back in front of pytest, which is what "
        f"#1086 removed. If the binary is what it needs, depend on "
        f"`shellcheck-stage`."
    )

    assert "shellcheck-stage" not in (steps["shellcheck"].get("depends_on") or []), (
        "the gate step now waits for the staging step, which serialises the two "
        "for no reason - they are independent"
    )


def test_a_downstream_step_may_depend_on_the_shellcheck_gate() -> None:
    """The accepted case, committed (counter-model review pass 2).

    A publishing step that waits for the lint delays nothing that gates pytest.
    The previous guard rejected it and said the lint was back on the critical
    path, which was false. A guard that cannot tell our regression from a
    neighbour's legitimate dependency gets routed around, and the routing-around
    is what removes the protection.
    """
    graph = {
        "validate": {"depends_on": ["shellcheck-stage"], "commands": ["uv run pytest -n 4"]},
        "shellcheck-stage": {"depends_on": ["secret-scan"], "commands": ["cp /bin/shellcheck .ci-bin/"]},
        "shellcheck": {"depends_on": ["secret-scan"], "commands": ["sh scripts/shellcheck-gate.sh"]},
        "secret-scan": {"commands": ["gitleaks detect"]},
        "publish": {
            "depends_on": ["validate", "shellcheck"],
            "commands": ['PATH="$PWD/.ci-bin:$PATH" jq . release.json'],
        },
    }
    assert _executors(graph) == ["validate"], (
        "the publish step reads .ci-bin but runs no tests - it must not be treated "
        "as an executor, which is precisely the over-reach this case pins"
    )
    assert "shellcheck" not in _ancestors(graph, "validate")
    assert "shellcheck" in _ancestors(graph, "publish")  # allowed, and not our subject


def test_an_INTERMEDIATE_dependency_still_reds() -> None:
    """...and narrowing the guard did not blind it to the real regression.

    `validate -> intermediate -> shellcheck` names `shellcheck` nowhere in
    `validate`, and is exactly how the 30 seconds returns unnoticed.
    """
    graph = {
        "validate": {"depends_on": ["intermediate"], "commands": ["uv run pytest -n 4"]},
        "intermediate": {"depends_on": ["shellcheck"], "commands": ["true"]},
        "shellcheck": {"depends_on": [], "commands": ["sh scripts/shellcheck-gate.sh"]},
    }
    assert "shellcheck" in _ancestors(graph, "validate"), (
        "the transitive walk stopped at the direct dependencies, so an "
        "intermediate step hides the gate from this guard entirely"
    )

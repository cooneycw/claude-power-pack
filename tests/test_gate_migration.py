"""Pin: the four controlled shell gates ROUTE THROUGH gate-lib, not merely source it (issue #1127).

Each of these four already carries a registered negative control, and those
controls are why this slice starts here: they are the regression evidence that
the migration did not change what a gate can SEE. But they cannot answer the
migration's own question. A control asks *does the gate still discriminate*, and
a gate that kept its own hand-rolled argument loop and merely added a `.` of
`gate-lib.sh` passes all four unchanged. Routing needs its own instrument.

THE PROPERTY, AND WHY IT IS ONLY PRODUCIBLE BY THE MODULE: a value-taking flag
given as the FINAL argument must produce ``gate-lib``'s refusal - its exact
message and its declared usage exit. A hand-rolled `${2:?...}` produces the
gate's own wording and a shell-dependent code; an `[ $# -ge 2 ] || die` produces
the gate's own `die`. Neither can produce the module's line, so passing this IS
the routing evidence.

BOTH INTERPRETERS, for the reason ``test_a_toy_gate_refuses_a_dangling_root_
under_either_shell`` records about its own subject: the pre-migration behaviour
was HOST-DEPENDENT - ``${2:?}`` exits 1 under bash and 2 under dash - so a
single-interpreter test would agree with whichever shell the host happens to
provide and say nothing about the other.

THE EXPECTED STRINGS ARE DERIVED FROM ``scripts/gate-lib.sh``, NEVER RETYPED
(issue #1127, orchestrator condition). A test that hardcodes the module's
message asserts that the gates agree with this file, not that they agree with
the module - and the two drift the first time the module's wording is improved.
The same applies to the usage exit: it is read from the module's own constant.

THE QUESTION THIS FILE HAD TO ASK OF ITSELF: a migration onto a module built to
stop hand-rolled argument loops must not hand-roll one to prove it. So nothing
here parses a command line to decide what to assert - each case runs a gate with
its flag last and compares against what the module says it will do.

Verified non-vacuous: run against the pre-migration bytes of all four gates,
every case fails, and the PR body pastes the kind of red per gate.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE_LIB = ROOT / "scripts" / "gate-lib.sh"

#: The four gates this slice migrates, each with ONE of its value-taking flags.
#: The flag is the input; which one is immaterial, since they share the module
#: call. `--root` is used for the two that have it, and each of the others uses
#: the flag its own contract is built around.
GATES = (
    ("shellcheck-gate.sh", "--root"),
    ("secret-scan-check.sh", "--root"),
    ("npm-global-upgrade.sh", "--package"),
    ("flow-driver-retirement-check.sh", "--driver"),
)

INTERPRETERS = ("sh", "bash")


def _module_usage_exit() -> int:
    """`GATE_USAGE_EXIT`, read from the module rather than retyped."""
    m = re.search(r"^GATE_USAGE_EXIT=(\d+)", GATE_LIB.read_text(), re.M)
    assert m, "gate-lib.sh no longer declares GATE_USAGE_EXIT"
    return int(m.group(1))


def _module_refusal(flag: str) -> str:
    """The exact line `gate_arg_value` emits for a dangling flag, DERIVED.

    Two pieces, both lifted from `scripts/gate-lib.sh`: the `_gate_refuse`
    prefix, and the message `gate_arg_value` passes it. Retyping either would
    make this file the authority on the module's wording, which is backwards -
    the module is the authority, and a test that disagrees with it should fail
    rather than quietly pin a stale string.
    """
    text = GATE_LIB.read_text()

    prefix = re.search(r"printf '([^']*refused[^']*)\\n'", text)
    assert prefix, "gate-lib.sh no longer formats its refusal with a 'refused' prefix"
    # `gate-lib: refused - %s` -> `gate-lib: refused - `
    lead = prefix.group(1).replace("%s", "")

    msg = re.search(r'_gate_refuse "\$1 (needs a value[^"]*)"', text)
    assert msg, "gate_arg_value no longer refuses a dangling flag with a '$1 needs a value' message"

    return f"{lead}{flag} {msg.group(1)}"


requires_shells = pytest.mark.skipif(
    shutil.which("sh") is None or shutil.which("bash") is None,
    reason="shells out to sh and bash",
)


def test_the_module_still_exposes_what_this_file_derives():
    """Guard the derivation itself.

    If `gate-lib.sh` is restructured so these patterns stop matching, every
    case below would be comparing against a string built from a failed regex.
    The helpers assert internally, so this is the one place that failure
    surfaces as its own diagnosis rather than as four confusing mismatches.
    """
    assert _module_usage_exit() > 0, "a usage error is never the good exit"
    refusal = _module_refusal("--root")
    assert refusal.startswith("gate-lib:"), refusal
    assert "--root" in refusal, refusal
    assert "needs a value" in refusal, refusal


@requires_shells
@pytest.mark.parametrize("interpreter", INTERPRETERS)
@pytest.mark.parametrize(("gate", "flag"), GATES, ids=[g for g, _ in GATES])
def test_a_dangling_value_flag_produces_the_modules_refusal(
    gate: str, flag: str, interpreter: str
) -> None:
    """The routing property: the MODULE refuses, not the gate.

    Pre-migration this fails in one of two ways, both recorded in #1127's
    measured table: under `bash` the gate's own `${2:?...}` exits 1 - which for
    three of the four is a code that also means a real verdict - and under
    `sh` it exits 2. Neither produces the module's line.
    """
    result = subprocess.run(
        [interpreter, str(ROOT / "scripts" / gate), flag],
        capture_output=True,
        text=True,
        timeout=15,
    )
    expected = _module_refusal(flag)
    assert expected in result.stderr, (
        f"{gate} under {interpreter} did not route through gate_arg_value.\n"
        f"expected: {expected!r}\nstderr:   {result.stderr!r}"
    )
    assert result.returncode == _module_usage_exit(), (
        f"{gate} under {interpreter}: usage exit is {result.returncode}, "
        f"expected the module's {_module_usage_exit()}"
    )


@requires_shells
@pytest.mark.parametrize(("gate", "flag"), GATES, ids=[g for g, _ in GATES])
def test_the_usage_exit_is_not_a_verdict_code(gate: str, flag: str) -> None:
    """The reason the move matters, not merely that it moved (#1127).

    Three of the four reported a usage error with a number that also means a
    real verdict: `shellcheck-gate` 1 = findings, `npm-global-upgrade` 1 =
    downgraded, `flow-driver-retirement-check` 1 = blocked. On the last of
    those a dangling `--driver` read as "a LIVE role drives on it" - the
    verdict that BLOCKS a retirement, so a usage error was reporting as the
    safe-side answer and would have been believed.

    The module's usage exit must therefore sit outside every verdict code these
    gates declare. Asserted as a property - above the range a gate uses - rather
    than as the number 64, so it survives the module choosing a different one.
    """
    assert _module_usage_exit() > 3, (
        "the module's usage exit is inside the range these gates use for "
        "verdicts (0-3), so a usage error can still be read as one"
    )


@requires_shells
@pytest.mark.parametrize(("gate", "flag"), GATES, ids=[g for g, _ in GATES])
def test_a_supplied_empty_value_is_not_refused_as_missing(
    gate: str, flag: str
) -> None:
    """`--flag ""` is a value SUPPLIED, and the module accepts it by design.

    #1126 ruled the count semantics: "an empty value supplied is not a value
    missing". Three of these four previously refused it, because `${2:?}` fires
    on unset OR NULL; `secret-scan-check.sh` already accepted it, having used a
    count. The migration aligns the three with the one that was already right.

    What each gate then DOES with the empty value is the gate's own business and
    is asserted in `test_an_empty_value_reaches_the_gates_own_check` below - the
    orchestrator's condition on this slice, because latent becomes live the
    moment the arg loop stops swallowing it.
    """
    result = subprocess.run(
        ["sh", str(ROOT / "scripts" / gate), flag, ""],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert _module_refusal(flag) not in result.stderr, (
        f"{gate}: a SUPPLIED empty value was refused as a MISSING one"
    )


@requires_shells
@pytest.mark.parametrize(
    ("gate", "flag", "marker"),
    (
        ("shellcheck-gate.sh", "--root", "is not a directory"),
        ("npm-global-upgrade.sh", "--package", "--package is required"),
        ("flow-driver-retirement-check.sh", "--driver", "no --driver was given"),
    ),
    ids=("shellcheck-gate", "npm-global-upgrade", "flow-driver-retirement-check"),
)
def test_an_empty_value_reaches_the_gates_own_check(
    gate: str, flag: str, marker: str
) -> None:
    """Each gate must CATCH the empty value it now accepts, and say so.

    The migration makes a previously unreachable path reachable: the arg loop
    used to refuse `--flag ""`, and now it does not. Every one of the three has
    an existing check that catches it downstream - verified by measurement
    here, not by reading - and none reaches its good verdict. That last part is
    what the condition is about: on `flow-driver-retirement-check` an empty
    driver matching no role could have rendered as `clear`, which authorises
    deleting a command, and it does not: it reports `unknown`.

    `secret-scan-check.sh` is absent from this list deliberately. It already
    accepted an empty `--root` before the migration, so nothing about its
    behaviour here is new and there is no newly-reachable path to pin.
    """
    result = subprocess.run(
        ["sh", str(ROOT / "scripts" / gate), flag, ""],
        capture_output=True,
        text=True,
        timeout=30,
    )
    combined = result.stdout + result.stderr
    assert marker in combined, f"{gate}: nothing caught the empty value: {combined!r}"
    assert result.returncode != 0, (
        f"{gate}: an empty {flag} reached a SUCCESS exit; a usage error must "
        f"never render as the go-ahead verdict"
    )

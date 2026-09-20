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

The usage EXIT is derived per gate, and the first cut got that wrong: it read
the module's default and asserted it of all four, which would have forced
`secret-scan-check.sh` to move a number that was already stable across shells
and collided with none of its verdicts. The module offers `gate_map ... usage=N`
precisely so it need not, and a test that assumed the default was asserting
something the module does not promise.

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
    """`GATE_USAGE_EXIT`, the module's DEFAULT, read rather than retyped."""
    m = re.search(r"^GATE_USAGE_EXIT=(\d+)", GATE_LIB.read_text(), re.M)
    assert m, "gate-lib.sh no longer declares GATE_USAGE_EXIT"
    return int(m.group(1))


def _gate_usage_exit(gate: str) -> int:
    """This GATE's usage exit: its own `usage=` if it declares one, else the default.

    Derived per gate, not globally. The module supports `gate_map ... usage=N`
    precisely so a gate whose usage code is already stable and collision-free
    can keep it, and a test that assumed the default would have forced every
    gate to move a number for no reason - which is the opposite of what a
    migration proving "nothing changed" should do.

    `secret-scan-check.sh` is the case: its usage exit is 2 under BOTH shells
    today and collides with none of its verdicts, so it keeps 2. The other three
    exited 1 under bash - a number each of them also uses for a real verdict -
    and move to the module's default.
    """
    text = (ROOT / "scripts" / gate).read_text()
    m = re.search(r"^\s*gate_map\s+([^\n]*)", text, re.M)
    assert m, f"{gate} does not call gate_map"
    declared = re.search(r"\busage=(\d+)", m.group(1))
    return int(declared.group(1)) if declared else _module_usage_exit()


def _module_refusal(flag: str) -> str:
    """The exact line `gate_arg_value` emits for a dangling flag, RUN not READ.

    Derived by ASKING THE MODULE: source it, declare a map, call
    `gate_arg_value` with a dangling flag, and take what it prints. That is the
    behaviour the gates must reproduce, and it is the only derivation that
    survives the module being reimplemented.

    The first cut read the module's SOURCE with two regexes - the `_gate_refuse`
    format string and the message `gate_arg_value` passes it. That made this
    file sensitive to how the module is WRITTEN rather than to what it DOES:
    replacing the formatter with an equivalent `printf '%s\\n' "gate-lib:
    refused - $1"` preserves the output and the exit code byte for byte and
    still broke the regex, so every migrated gate would have gone red for a
    change that altered nothing about them (counter-model review, #1127).

    A test whose subject is "these four agree with the module" must fail when
    they stop agreeing, and only then.
    """
    probe = f'gate_map ok=0 finding=1\nset -- {flag}\ngate_arg_value {flag} "$#" "${{2-}}"\n'
    result = subprocess.run(
        ["sh", "-c", f'. "{GATE_LIB}"\n{probe}'],
        capture_output=True,
        text=True,
        timeout=15,
    )
    line = result.stderr.strip()
    assert line, (
        "the module did not refuse a dangling flag at all, so there is no "
        f"expected line to compare against: {result!r}"
    )
    return line


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
    # Asserted as PROPERTIES, not as the module's exact sentence: the refusal
    # must name the flag it is about, or a caller cannot act on it - which is
    # the property `test_a_toy_gate_refuses_a_dangling_root_under_either_shell`
    # already requires of its own subject. The wording itself is the module's
    # to change.
    assert "--root" in refusal, refusal
    assert refusal, "the module must say something a caller can read"


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
    expected_exit = _gate_usage_exit(gate)
    assert result.returncode == expected_exit, (
        f"{gate} under {interpreter}: usage exit is {result.returncode}, "
        f"expected {expected_exit} (its own `usage=` if declared, else the "
        f"module's default {_module_usage_exit()})"
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
    # Per gate, because the answer differs per gate and the reason differs too.
    # secret-scan-check keeps 2, which is its `die` code - an operational error,
    # not a verdict - so a usage error there is already distinguishable from
    # `clean` (0) and `findings` (1). The other three move out of the 0-3 range
    # entirely, because the number they used IS one of their verdicts.
    text = (ROOT / "scripts" / gate).read_text()
    verdicts = re.search(r"^\s*gate_map\s+([^\n]*)", text, re.M)
    assert verdicts, f"{gate} does not call gate_map"
    codes = {
        int(c)
        for name, c in re.findall(r"\b([a-z-]+)=(\d+)", verdicts.group(1))
        if name != "usage"
    }
    assert _gate_usage_exit(gate) not in codes, (
        f"{gate}: its usage exit {_gate_usage_exit(gate)} is also one of its "
        f"verdict codes {sorted(codes)}, so a usage error can be read as a verdict"
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


#: EVERY migrated value-taking flag, not the one per gate the first cut covered.
#: The empty-value claim was "each gate catches what it now accepts", and that
#: was asserted for `--root`, `--package` and `--driver` only - so it was a
#: claim about four flags proven for three, and the reviewer found the gap where
#: it mattered (counter-model review, #1127). `--sudo` and `--skip-install` are
#: absent because they take no value; there is nothing to supply empty.
MIGRATED_FLAGS = (
    ("shellcheck-gate.sh", "--root", ()),
    ("shellcheck-gate.sh", "--severity", ()),
    ("secret-scan-check.sh", "--root", ()),
    ("npm-global-upgrade.sh", "--package", ("--binary", "b", "--skip-install")),
    ("npm-global-upgrade.sh", "--binary", ("--package", "p", "--skip-install")),
    ("npm-global-upgrade.sh", "--label", ("--package", "p", "--binary", "b", "--skip-install")),
    ("npm-global-upgrade.sh", "--npm", ("--package", "p", "--binary", "b", "--skip-install")),
    ("npm-global-upgrade.sh", "--node", ("--package", "p", "--binary", "b", "--skip-install")),
    ("flow-driver-retirement-check.sh", "--driver", ()),
    ("flow-driver-retirement-check.sh", "--wave", ("--driver", "d")),
    ("flow-driver-retirement-check.sh", "--registry-dir", ("--driver", "d")),
    ("flow-driver-retirement-check.sh", "--helper", ("--driver", "d")),
)


@requires_shells
@pytest.mark.parametrize(
    ("gate", "flag", "extra"),
    MIGRATED_FLAGS,
    ids=[f"{g.removesuffix('.sh')}{f}" for g, f, _ in MIGRATED_FLAGS],
)
def test_no_migrated_flag_reaches_a_good_verdict_on_an_empty_value(
    gate: str, flag: str, extra: tuple
) -> None:
    """EVERY migrated flag, because the claim was about all of them.

    `gate_arg_value` accepts `--flag ""` by design (#1126: a value supplied is
    not a value missing), so each gate must handle it. The dangerous shape is
    not a crash - it is an empty value read as "omitted", because a gate then
    resolves a DEFAULT and answers about something the caller never asked
    about.

    Measured before the fix: `flow-driver-retirement-check.sh --registry-dir ""`
    discarded the registry it was given and examined the HOST's - three
    unrelated waves instead of the one named. It reported `unknown` on that run
    only because those waves happened to be unparseable from there; on a
    readable registry the same mistake reaches `clear`, the verdict that
    authorises deleting a command.

    So the assertion is the one that matters regardless of which gate or which
    default: an empty value must never produce the good exit.
    """
    result = subprocess.run(
        ["sh", str(ROOT / "scripts" / gate), *extra, flag, ""],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0, (
        f"{gate} {flag} '' reached the GOOD exit. An empty value read as "
        f"'omitted' makes the gate answer about a default the caller never "
        f"named: {(result.stdout + result.stderr)[:400]!r}"
    )


@requires_shells
@pytest.mark.parametrize(
    "flag", ("--wave", "--registry-dir", "--helper"), ids=lambda f: f.lstrip("-")
)
def test_an_empty_retirement_selector_is_refused_not_defaulted(flag: str) -> None:
    """The HIGH finding, pinned by its cause rather than by its symptom.

    The test above asserts only "not the good exit", which the pre-fix gate
    also satisfied - by luck, on a host whose registry happened to be
    unreadable. This asserts the gate REFUSED the empty selector, naming it,
    rather than resolving a default and answering about another scope.
    """
    result = subprocess.run(
        [
            "sh",
            str(ROOT / "scripts" / "flow-driver-retirement-check.sh"),
            "--driver", "flow:auto_codex",
            flag, "",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    combined = result.stdout + result.stderr
    assert f"{flag} was given an empty value" in combined, combined
    assert "RETIREMENT: unknown" in combined, combined
    assert result.returncode == 3, result.returncode

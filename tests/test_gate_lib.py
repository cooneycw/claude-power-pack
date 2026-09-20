"""The shared argument and verdict module, and its refusals (issue #1126).

`scripts/gate-lib.sh` is the first slice of the #1061 wave: one home for two
conventions that 48 shell gates currently re-implement. Its own negative
control lives at `controls/gate-lib` and is driven by
`scripts/check-negative-controls.py`; what this module adds is the half a
control-case cannot express.

THE LOAD-BEARING TEST HERE IS THE TIMEOUT, not any exit-code assertion.
#992 was six value-taking flags that SPUN FOREVER when passed as the final
argument - `shift 2` with `$# -eq 1` fails and shifts nothing, so `$#` never
decreases and the `while` loop turns on the same argument until something kills
it. A test asserting "exit is 64" says nothing at all about code that never
reaches any exit, so the assertion has to BE the timeout, and it has to run
against a loop written the naive way - which is what
`test_the_naive_loop_this_module_replaces_actually_hangs` constructs.

Every refusal is exercised under BOTH `sh` and `bash`, and the two are required
to agree. That is not thoroughness: `${2:?}` - the guard #992 measured as
"exit 1", and the idiom in four gates in this tree - exits 1 under bash and 2
under dash. `scripts/shellcheck-gate.sh` declares `exit 1 = findings`, so under
bash its usage refusal reports as a FINDING and under sh as UNKNOWN. One file,
one input, two answers. A single-shell test cannot see it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "gate-lib.sh"
CONTROL = ROOT / "controls" / "gate-lib"
ANCHOR = CONTROL / "anchors" / "0000000-naive-gate-lib.sh"

SHELLS = ("sh", "bash")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("sh") is None,
    reason="requires sh and bash on PATH",
)


def _run(shell: str, script: Path, *args: str, timeout: float = 10.0):
    return subprocess.run(
        [shell, str(script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _probe(tmp_path: Path, body: str) -> Path:
    """A script that sources the module and does `body`."""
    path = tmp_path / "probe.sh"
    path.write_text(f'. "{MODULE}"\n{body}\n', encoding="utf-8")
    return path


def _both_shells(tmp_path: Path, body: str, timeout: float = 10.0):
    probe = _probe(tmp_path, body)
    return {shell: _run(shell, probe, timeout=timeout) for shell in SHELLS}


# --------------------------------------------------------------------------- #
# The #992 half: the assertion is the timeout                                  #
# --------------------------------------------------------------------------- #

NAIVE_LOOP = """
ROOT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --root) ROOT="${2:-}"; shift 2 ;;
        *) shift ;;
    esac
done
echo "parsed root=[$ROOT]"
"""


@pytest.mark.parametrize("shell", SHELLS)
def test_the_naive_loop_this_module_replaces_never_reports_the_usage_error(
    tmp_path: Path, shell: str
) -> None:
    """The red run, on the shape the module exists to remove.

    This is the pre-fix code for this module. There is no earlier version of
    `gate-lib.sh` to run against, because #1061's constraint 1 requires the
    control to land BEFORE any caller, so the "code before the fix" is
    constructed here as the idiom #992 measured spinning in six live files.

    IT FAILS DIFFERENTLY IN THE TWO SHELLS, AND THAT IS ITSELF A FINDING.
    Measured, `set -- one; shift 2`:

        bash   `shift` returns 1 and leaves the positional parameters alone,
               so `$#` never decreases and the `while` loop turns on the same
               argument forever - the #992 hang
        dash   `shift: can't shift that many` is FATAL; the shell exits 2 on
               the spot, with no hang at all

    So #992's hang is a BASH defect. Its six subjects are all
    `#!/usr/bin/env bash` and its fix stands, but the general claim does not
    carry to a POSIX-sh gate - and `scripts/shellcheck-gate.sh`, #1127's first
    migration target, is one. Under dash the naive loop does not spin; it dies
    with exit 2, which that gate's own contract reads as UNKNOWN.

    What is true in BOTH is the property this module fixes: the loop never
    reaches its own result, and whatever it says is about the shell's `shift`
    builtin rather than about the flag the caller actually typed.
    """
    naive = tmp_path / "naive.sh"
    naive.write_text(NAIVE_LOOP, encoding="utf-8")

    if shell == "bash":
        with pytest.raises(subprocess.TimeoutExpired):
            _run(shell, naive, "--root", timeout=4.0)
        return

    done = _run(shell, naive, "--root", timeout=4.0)

    assert done.returncode != 0, done.stdout
    assert "parsed root=" not in done.stdout
    # The diagnosis points at the shell, not at the caller's mistake. That is
    # the half a different exit code would not have told you.
    assert "--root" not in done.stderr, done.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_the_module_refuses_a_final_value_taking_flag_instead_of_spinning(
    tmp_path: Path, shell: str
) -> None:
    body = 'gate_map ok=0 finding=1\nset -- --root\ngate_arg_value --root "$#" "${2-}"\necho REACHED'
    probe = _probe(tmp_path, body)

    # No pytest.raises: reaching the assertions at all is half the result.
    done = _run(shell, probe, timeout=4.0)

    assert done.returncode == 64, done.stderr
    assert "gate-lib: refused - --root needs a value" in done.stderr
    assert "REACHED" not in done.stdout


# --------------------------------------------------------------------------- #
# The question the refusal asks is the COUNT, not the emptiness                #
# --------------------------------------------------------------------------- #


def test_an_empty_value_that_was_supplied_is_accepted(tmp_path: Path) -> None:
    """`--root ""` supplies an empty value; `--root` at the end supplies none.

    Two live idioms in this tree decide on `[ -n "$2" ]` and therefore cannot
    tell these apart, rejecting a legitimate empty argument. This test is what
    keeps the decision on the argument count.
    """
    body = (
        'gate_map ok=0 finding=1\n'
        'set -- --root ""\n'
        'gate_arg_value --root "$#" "${2-}"\n'
        'echo "value=[$GATE_VALUE]"'
    )
    for shell, done in _both_shells(tmp_path, body).items():
        assert done.returncode == 0, f"{shell}: {done.stderr}"
        assert "value=[]" in done.stdout, shell


# --------------------------------------------------------------------------- #
# The refusals, and the requirement that both shells agree                     #
# --------------------------------------------------------------------------- #

REFUSALS = [
    ("a second verdict at the good exit", "gate_map ok=0 unknown=0", "both map to the good exit 0"),
    ("usage at the good exit", "gate_map usage=0", "'usage' may not map to the good exit 0"),
    ("no verdict at the good exit", "gate_map finding=1 unknown=2", "no verdict maps to the good exit 0"),
    ("a duplicate verdict", "gate_map ok=0 ok=1", "is declared twice"),
    ("a code above 125", "gate_map ok=0 boom=200", "codes above 125 are the shell's own"),
    ("a non-numeric code", "gate_map ok=0 finding=x", "is not a non-negative integer"),
    ("a malformed pair", "gate_map ok", "is not <verdict>=<code>"),
    ("an unmapped gate_exit", "gate_map ok=0\ngate_exit unknown", "falling through to the good exit"),
    ("an unmapped gate_emit", "gate_map ok=0\ngate_emit PROBE nope", "is not in the declared map"),
    ("gate_emit before gate_map", "gate_emit PROBE ok", "was called before gate_map"),
    ("gate_exit before gate_map", "gate_exit ok", "was called before gate_map"),
    ("gate_arg_value before gate_map", 'gate_arg_value --root 2 x', "was called before gate_map"),
    ("a bad contract key", "gate_map ok=0\ngate_emit 9BAD ok", "must begin with a letter"),
]


@pytest.mark.parametrize(("label", "body", "needle"), REFUSALS, ids=[r[0] for r in REFUSALS])
def test_each_refusal_fires_identically_in_sh_and_bash(
    tmp_path: Path, label: str, body: str, needle: str
) -> None:
    runs = _both_shells(tmp_path, body + "\necho REACHED")

    for shell, done in runs.items():
        assert done.returncode == 64, f"{shell} ({label}): exit {done.returncode}\n{done.stderr}"
        assert needle in done.stderr, f"{shell} ({label}): {done.stderr}"
        assert "REACHED" not in done.stdout, f"{shell} ({label}): execution continued"

    # THE POINT OF RUNNING BOTH. `${2:?}` gives 1 under bash and 2 under dash,
    # which is how a usage error came to report as a finding in shellcheck-gate.
    assert runs["sh"].returncode == runs["bash"].returncode, label


def test_the_good_verdict_goes_to_stdout_and_everything_else_to_stderr(tmp_path: Path) -> None:
    body = (
        "gate_map ok=0 finding=1 unknown=2\n"
        'gate_emit PROBE ok "all clear"\n'
        'gate_emit PROBE finding "one thing"\n'
        'gate_emit PROBE unknown "could not look"'
    )
    for shell, done in _both_shells(tmp_path, body).items():
        assert "PROBE: ok - all clear" in done.stdout, shell
        assert "PROBE: finding - one thing" in done.stderr, shell
        assert "PROBE: unknown - could not look" in done.stderr, shell
        assert "finding" not in done.stdout, shell


@pytest.mark.parametrize("verdict,code", [("ok", 0), ("finding", 1), ("unknown", 3), ("usage", 64)])
def test_gate_exit_uses_the_gates_own_codes_and_never_normalises_them(
    tmp_path: Path, verdict: str, code: int
) -> None:
    """`flow-driver-retirement-check.sh` uses 3 for unknown and two others use 2.

    Consumers read those numbers today, so the module declares per gate and
    unifies nothing. What it enforces is only that no second verdict reaches 0.
    """
    body = f"gate_map ok=0 finding=1 unknown=3\ngate_exit {verdict}"
    for shell, done in _both_shells(tmp_path, body).items():
        assert done.returncode == code, f"{shell}: {done.returncode}"


# --------------------------------------------------------------------------- #
# Sourcing must never run the self-check                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("shell", SHELLS)
def test_sourcing_does_not_dispatch_the_self_check_even_when_argv_says_check(
    tmp_path: Path, shell: str
) -> None:
    """POSIX `.` passes the caller's positional parameters straight through.

    A gate whose own CLI takes `--check` would otherwise run the module's
    self-check instead of its work - a permissive dispatch guard turning every
    caller into this file. The guard is a sentinel comment the module carries
    and a sourcing gate does not.
    """
    caller = tmp_path / "caller.sh"
    caller.write_text(
        f'. "{MODULE}"\ngate_map ok=0 finding=1\ngate_emit CALLER ok "did my own work"\n',
        encoding="utf-8",
    )

    done = _run(shell, caller, "--check", str(CONTROL / "cases" / "bad-final-flag"))

    assert done.returncode == 0, done.stderr
    assert "CALLER: ok - did my own work" in done.stdout
    assert "GATE_LIB:" not in done.stdout + done.stderr


def test_the_anchor_carries_the_sentinel_so_it_is_not_inert_for_the_wrong_reason() -> None:
    """A dispatch guard keyed on the FILENAME would silently break the anchor.

    The anchor is a different file name by construction. Were dispatch keyed on
    `$0`'s basename, the anchor would run nothing, exit 0 on every case, and
    pass the register's "missed the known-bad input" check for a reason that has
    nothing to do with blindness. A vacuous anchor is worse than no anchor,
    because it reads as a demonstration.
    """
    assert "#: GATE-LIB-SENTINEL" in ANCHOR.read_text(encoding="utf-8")


def test_the_anchor_runs_the_gates_own_check_runner_byte_for_byte() -> None:
    """The anchor's claim is that ONLY the four library functions differ.

    If the runner drifts, a verdict difference between the anchor and the gate
    stops isolating the refusals, and the control quietly starts measuring
    something else. The claim is written in the anchor's header and in
    `control.json`; this is what makes it checkable rather than prose.
    """
    marker = "_gate_self_invoked() {"
    gate_text = MODULE.read_text(encoding="utf-8")
    anchor_text = ANCHOR.read_text(encoding="utf-8")

    assert gate_text.count(marker) == 1
    assert anchor_text.count(marker) == 1
    assert gate_text[gate_text.index(marker):] == anchor_text[anchor_text.index(marker):]


# --------------------------------------------------------------------------- #
# The self-check's own verdicts                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("case", "code", "verdict"),
    [
        ("bad-final-flag", 1, "refused"),
        ("bad-unknown-maps-to-good", 1, "refused"),
        ("bad-unmapped-verdict", 1, "refused"),
        ("bad-no-map", 1, "refused"),
        ("good-flag-with-value", 0, "ok"),
        ("good-empty-value", 0, "ok"),
    ],
)
def test_the_self_check_reports_each_registered_case(case: str, code: int, verdict: str) -> None:
    done = _run("sh", MODULE, "--check", str(CONTROL / "cases" / case))
    assert done.returncode == code, done.stderr
    assert f"GATE_LIB: {verdict} - " in done.stdout + done.stderr


def test_a_probe_that_crashes_without_refusing_is_unknown_not_refused(tmp_path: Path) -> None:
    """A CRASH IS NOT A REFUSAL - the #946 rule, inside the tool built for it.

    A probe that falls over also exits non-zero. Scoring that as `refused` is
    how `check-negative-controls.py` once reported PASS for a gate that
    discriminated nothing and died, so the runner requires the module to have
    SAID it refused.
    """
    case = tmp_path / "crashy"
    case.mkdir()
    (case / "probe.sh").write_text('echo "boom" >&2\nexit 9\n', encoding="utf-8")

    done = _run("sh", MODULE, "--check", str(case))

    assert done.returncode == 2, done.stdout + done.stderr
    assert "GATE_LIB: unknown - " in done.stderr
    assert "that is a crash, not a refusal" in done.stderr
    assert "GATE_LIB: refused" not in done.stdout + done.stderr


def test_a_probe_whose_answer_depends_on_the_shell_is_unknown(tmp_path: Path) -> None:
    """The divergence a single-shell control cannot see, made into a verdict.

    `${2:?}` exits 1 under bash and 2 under dash. A runner that consulted one
    shell would report a confident verdict for a gate that has two answers, so
    disagreement is its own state here rather than folded into either one.
    """
    case = tmp_path / "divergent"
    case.mkdir()
    (case / "probe.sh").write_text('set -u\nV="${2:?needs a value}"\n', encoding="utf-8")

    done = _run("sh", MODULE, "--check", str(case))

    assert done.returncode == 2, done.stdout + done.stderr
    assert "GATE_LIB: unknown - " in done.stderr
    assert "sh exited 2 and bash exited 1" in done.stderr


def test_the_self_check_refuses_a_case_directory_it_cannot_read(tmp_path: Path) -> None:
    done = _run("sh", MODULE, "--check", str(tmp_path / "nope"))
    assert done.returncode == 2
    assert "is not a directory" in done.stderr

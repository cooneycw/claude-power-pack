"""Pin: vantage is DERIVED, three-stated, and blind to the count that looks decisive (issue #959).

Every lane decision in CPP was made by an agent reading a paragraph. That is
load-bearing, because the correct answer INVERTS across the container boundary:
past it the mailbox is lane 1 and `SendMessage` addresses a population holding no
fleet peer at all, so a wrong `host` is not a slower send - it is a silent
non-delivery that returns success. `scripts/flow-vantage.sh` makes the answer
available to something other than a reader.

WHAT THIS FILE PINS THAT THE REGISTERED CONTROL CANNOT.
`controls/flow-vantage` proves the gate discriminates between a host, a container
and a signal disagreement, and that a blind variant would miss two of the three.
Its anchor is the MOUNT-shaped blindness. It cannot also be the RECORD-COUNT
blindness - a record-count check answers `container` on a lone host session, so
it would disagree with the real gate on the control's known-GOOD input and score
INERT, demonstrating nothing (`controls/flow-vantage/control.json` records that
reasoning). So the record-count blindness is pinned HERE instead, as behaviour:
vary the count, and the verdict must not move. Two measured blindnesses, two
instruments, neither left unproven.

`test_the_verdict_does_not_move_with_the_record_count` is the one to read first.
It is a NEGATIVE-MEMBERSHIP test: it asserts what must NOT be able to influence
the answer. Deleting the pid-namespace logic would not fail it - the control does
that - but reintroducing `ls ~/.claude/sessions/` as a signal would, and that is
precisely the regression #958 spent a measurement campaign ruling out.

Verified non-vacuous, both mutations run against this file on 2026-09-20:

  * namespace comparison INVERTED in the gate - 9 of 14 fail, and the registered
    control reports BLIND (`--strict` exit 1). Both instruments catch it.
  * a record-COUNT branch added to the gate (`<= 1 record` means container) -
    `test_the_verdict_does_not_move_with_the_record_count[host]` fails and
    NOTHING ELSE DOES, including the registered control, which reports PASS and
    `--strict` exit 0. That asymmetry is the reason this file exists: the
    control's committed cases carry no session records, so the blindness is
    invisible to it by construction. If this test is ever deleted as redundant,
    the record-count regression becomes undetectable again.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VANTAGE = ROOT / "scripts" / "flow-vantage.sh"
CONTROL_CASES = ROOT / "controls" / "flow-vantage" / "cases"

#: The conventional initial pid namespace inode on Linux, and the value measured
#: on the host this was built on (harness 2.1.266, 2026-09-20). Restated here
#: deliberately: if the gate's constant is edited, this file is the second
#: opinion, and a test importing the value from the gate would agree with any
#: edit at all.
INITIAL_NS = "pid:[4026531836]"
#: Measured inside a per-session kyle container, harness 2.1.266, 2026-09-13
#: (issue #947, one container, kyle session 48).
CONTAINER_NS = "pid:[4026533495]"

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)
#: `readlink` on a symlink whose target is not a real path is how the fixture
#: stands in for /proc/self/ns/pid. Windows-style filesystems without symlink
#: support would make every fixture below meaningless rather than failing
#: honestly, so the capability is asserted rather than assumed.
requires_symlinks = pytest.mark.skipif(
    not hasattr(os, "symlink"), reason="requires symlink support"
)


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    # A vantage declaration inherited from the surrounding session would
    # short-circuit every measurement below and turn this file green without
    # measuring anything. Cleared explicitly rather than assumed absent.
    full_env.pop("FLOW_VANTAGE_DECLARE", None)
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", str(VANTAGE), *args],
        capture_output=True,
        text=True,
        env=full_env,
    )


def _contract(stdout: str) -> dict[str, str]:
    """The three contract lines, keyed. Missing keys are the caller's problem."""
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        if line.startswith("FLOW_VANTAGE") and ": " in line:
            key, _, value = line.partition(": ")
            out[key] = value
    return out


def _fixture(
    tmp_path: Path,
    *,
    ns: str | None,
    machine_id: str | None,
    records: int = 0,
) -> Path:
    """A stand-in for the PATHS the gate reads - never for its answer.

    Nothing written here names a verdict. `ns-pid` is a real symlink read by the
    same `readlink` that reads `/proc/self/ns/pid`, and `etc/machine-id` is a
    real file read by the same presence test, so what is exercised is the
    production derivation rather than a belief about it.
    """
    root = tmp_path / "fixture"
    root.mkdir(parents=True, exist_ok=True)
    if ns is not None:
        link = root / "ns-pid"
        if link.is_symlink() or link.exists():
            link.unlink()
        os.symlink(ns, link)
    if machine_id is not None:
        (root / "etc").mkdir(exist_ok=True)
        (root / "etc" / "machine-id").write_text(machine_id, encoding="utf-8")
    if records:
        # Faithful record PAIRS: `<pid>.json` and `<pid>.<hash>.key`. #958
        # measured that `ls ~/.claude/sessions/` emits 2N lines for N records
        # (10 raw lines for 5 records, 2026-09-16), and a fixture carrying only
        # the .json half would quietly make the count half what a reader of that
        # measurement would expect.
        sessions = root / "sessions"
        sessions.mkdir(exist_ok=True)
        for n in range(records):
            pid = 900000 + n
            (sessions / f"{pid}.json").write_text("{}", encoding="utf-8")
            (sessions / f"{pid}.deadbeef.key").write_text("x", encoding="utf-8")
    return root


# --------------------------------------------------------------------------- #
# The contract itself
# --------------------------------------------------------------------------- #


@requires_bash
@requires_symlinks
def test_a_host_fixture_reports_host_with_a_basis_naming_the_signal(tmp_path: Path) -> None:
    f = _fixture(tmp_path, ns=INITIAL_NS, machine_id="0" * 32 + "\n")
    res = _run("--fixture", str(f), "--quiet")
    c = _contract(res.stdout)
    assert c["FLOW_VANTAGE"] == "host"
    assert c["FLOW_VANTAGE_SOURCE"] == "measured"
    assert res.returncode == 0
    # The basis must name the SIGNAL, not count agreements: "2 signals agreed"
    # is a claim a reader cannot check or argue with.
    assert "ns-pid" in c["FLOW_VANTAGE_BASIS"]
    assert INITIAL_NS in c["FLOW_VANTAGE_BASIS"]


@requires_bash
@requires_symlinks
def test_a_container_fixture_reports_container_on_its_own_exit_code(tmp_path: Path) -> None:
    f = _fixture(tmp_path, ns=CONTAINER_NS, machine_id=None)
    res = _run("--fixture", str(f), "--quiet")
    c = _contract(res.stdout)
    assert c["FLOW_VANTAGE"] == "container"
    assert c["FLOW_VANTAGE_SOURCE"] == "measured"
    # One verdict per exit code (#1027). `container` sharing 0 with `host` would
    # leave a caller reading `$?` unable to tell the two apart at all.
    assert res.returncode == 3
    assert "machine-id" in c["FLOW_VANTAGE_BASIS"]


@requires_bash
@requires_symlinks
def test_the_namespace_alone_decides_container_when_machine_id_is_present(tmp_path: Path) -> None:
    """A container from an image that DOES ship /etc/machine-id is still a container.

    The machine-id signal is evidence for the kyle-session image only. A present
    machine-id must therefore never be read as host evidence, or the verdict
    would flip on an unrelated property of somebody's base image.
    """
    f = _fixture(tmp_path, ns=CONTAINER_NS, machine_id="a" * 32 + "\n")
    res = _run("--fixture", str(f), "--quiet")
    assert _contract(res.stdout)["FLOW_VANTAGE"] == "container"
    assert res.returncode == 3


# --------------------------------------------------------------------------- #
# `unknown` - reached, not merely documented
# --------------------------------------------------------------------------- #


@requires_bash
@requires_symlinks
def test_disagreeing_signals_report_unknown_rather_than_picking_a_winner(tmp_path: Path) -> None:
    """Initial namespace, no machine-id: a host shipping none. Several distros do."""
    f = _fixture(tmp_path, ns=INITIAL_NS, machine_id=None)
    res = _run("--fixture", str(f), "--quiet")
    c = _contract(res.stdout)
    assert c["FLOW_VANTAGE"] == "unknown"
    assert c["FLOW_VANTAGE_SOURCE"] == "measured"
    assert res.returncode == 4
    # The basis has to say the signals CONTRADICTED each other, not merely list
    # them: a reader deciding whether to trust `unknown` needs to know it came
    # from disagreement rather than from an absence.
    assert "CONTRADICTED" in c["FLOW_VANTAGE_BASIS"]


@requires_bash
def test_an_unreadable_namespace_reports_unknown_and_never_host(tmp_path: Path) -> None:
    """The general signal is silent, so one-sided corroboration may not speak for it.

    This is the direction that matters: `unknown` and `host` route differently,
    and a gate that fell back to `host` when it could not measure would send a
    containerised session down the lane that reports success and delivers
    nothing.
    """
    f = _fixture(tmp_path, ns=None, machine_id=None)
    assert not (f / "ns-pid").exists(), "fixture must LACK the namespace link"
    res = _run("--fixture", str(f), "--quiet")
    c = _contract(res.stdout)
    assert c["FLOW_VANTAGE"] == "unknown"
    assert res.returncode == 4
    assert "unreadable" in c["FLOW_VANTAGE_BASIS"]


@requires_bash
@requires_symlinks
def test_every_verdict_emits_all_three_contract_lines(tmp_path: Path) -> None:
    """A consumer parses three keys; a verdict that emitted two would read as absent."""
    cases = (
        dict(ns=INITIAL_NS, machine_id="0" * 32),
        dict(ns=CONTAINER_NS, machine_id=None),
        dict(ns=INITIAL_NS, machine_id=None),
        dict(ns=None, machine_id=None),
    )
    for spec in cases:
        f = _fixture(tmp_path / str(hash(str(spec))), **spec)  # type: ignore[arg-type]
        c = _contract(_run("--fixture", str(f), "--quiet").stdout)
        assert set(c) == {
            "FLOW_VANTAGE",
            "FLOW_VANTAGE_SOURCE",
            "FLOW_VANTAGE_BASIS",
        }, f"{spec} emitted {sorted(c)}"


# --------------------------------------------------------------------------- #
# Declared: honoured, reported as declared, never merged into a measurement
# --------------------------------------------------------------------------- #


@requires_bash
@requires_symlinks
@pytest.mark.parametrize(
    ("declared", "code"), (("host", 0), ("container", 3)), ids=("host", "container")
)
def test_a_declared_override_is_honoured_and_reported_as_declared(
    tmp_path: Path, declared: str, code: int
) -> None:
    # The fixture says the OPPOSITE of the declaration in both directions, so a
    # pass cannot come from the two happening to agree.
    opposite = CONTAINER_NS if declared == "host" else INITIAL_NS
    f = _fixture(tmp_path, ns=opposite, machine_id="0" * 32)
    res = _run("--fixture", str(f), "--quiet", env={"FLOW_VANTAGE_DECLARE": declared})
    c = _contract(res.stdout)
    assert c["FLOW_VANTAGE"] == declared
    assert c["FLOW_VANTAGE_SOURCE"] == "declared"
    assert res.returncode == code
    # NEVER MERGED: the basis of a declared verdict must not carry a measured
    # signal name, or `measured` and `declared` stop being separable downstream -
    # which is the whole reason the source field exists.
    assert "ns-pid" not in c["FLOW_VANTAGE_BASIS"]
    assert "machine-id" not in c["FLOW_VANTAGE_BASIS"]
    assert "FLOW_VANTAGE_DECLARE" in c["FLOW_VANTAGE_BASIS"]


@requires_bash
@requires_symlinks
def test_an_unrecognised_declaration_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    """A typo must not silently promote itself to a measurement.

    Falling through to measurement would be the friendlier behaviour and the
    wrong one: the caller believes they pinned the answer, the run measures
    something else, and the two only differ on the machine where it matters.
    """
    f = _fixture(tmp_path, ns=INITIAL_NS, machine_id="0" * 32)
    res = _run("--fixture", str(f), "--quiet", env={"FLOW_VANTAGE_DECLARE": "contaner"})
    c = _contract(res.stdout)
    assert c["FLOW_VANTAGE"] == "unknown"
    assert c["FLOW_VANTAGE_SOURCE"] == "declared"
    assert res.returncode == 4
    # Not reported as `host`, which is what the fixture would have measured.
    assert "ns-pid" not in c["FLOW_VANTAGE_BASIS"]


# --------------------------------------------------------------------------- #
# The blindness the registered control structurally cannot anchor
# --------------------------------------------------------------------------- #


@requires_bash
@requires_symlinks
@pytest.mark.parametrize(
    ("ns", "machine_id", "expected"),
    (
        (INITIAL_NS, "0" * 32, "host"),
        (CONTAINER_NS, None, "container"),
    ),
    ids=("host", "container"),
)
def test_the_verdict_does_not_move_with_the_record_count(
    tmp_path: Path, ns: str, machine_id: str | None, expected: str
) -> None:
    """NEGATIVE MEMBERSHIP: the session record count must not influence the answer.

    `register.md` recommended `ls ~/.claude/sessions/` until 2026-09-16 and #958
    measured why it cannot work: a container holds one record because discovery
    is filesystem-based and container-private, and A LONE HOST SESSION HOLDS ONE
    RECORD TOO. Those are different facts with opposite routing consequences. The
    count is not even stable on one vantage - 6 records on 2026-09-15, 5 on
    2026-09-16, 7 on 2026-09-20, with no fleet change between.

    So this varies the count across the range that spans both readings and
    asserts the verdict is identical. It fails the moment anyone reintroduces the
    signal, which is the regression worth guarding: it is the first thing
    somebody reaches for, and the failure it produces is silent.
    """
    verdicts = set()
    for records in (1, 9):
        f = _fixture(
            tmp_path / f"n{records}", ns=ns, machine_id=machine_id, records=records
        )
        sessions = f / "sessions"
        # Precondition: the fixture really does differ in the way under test.
        # Without this the two runs could agree because neither had any records
        # at all, and the invariance would be asserted over nothing.
        assert len(list(sessions.glob("*.json"))) == records
        c = _contract(_run("--fixture", str(f), "--quiet").stdout)
        verdicts.add(c["FLOW_VANTAGE"])
    assert verdicts == {expected}, (
        f"the verdict moved with the record count: {sorted(verdicts)} - the #958 "
        "blindness has been reintroduced"
    )


# --------------------------------------------------------------------------- #
# The committed control's own fixtures, exercised by the suite too
# --------------------------------------------------------------------------- #


@requires_bash
@pytest.mark.parametrize(
    ("case", "expected", "code"),
    (
        ("good-host", "host", 0),
        ("bad-container", "container", 3),
        ("bad-unknown-disagreement", "unknown", 4),
    ),
)
def test_the_committed_control_cases_still_say_what_the_manifest_claims(
    case: str, expected: str, code: int
) -> None:
    """A second reader of the control fixtures, from a different entry point.

    `check-negative-controls.py` runs these too, and its own verdict-assignment
    is what `controls/check-negative-controls` calls structurally blind about
    itself. A separate process asserting on the raw contract lines is the second
    opinion that a single program cannot give itself.
    """
    case_dir = CONTROL_CASES / case
    assert case_dir.is_dir(), f"control case missing from the checkout: {case}"
    res = _run("--fixture", str(case_dir), "--quiet")
    assert _contract(res.stdout)["FLOW_VANTAGE"] == expected
    assert res.returncode == code


# --------------------------------------------------------------------------- #
# Counter-model review findings (codex/gpt-6-astra, 2026-09-20)
# --------------------------------------------------------------------------- #


@requires_bash
@requires_symlinks
def test_a_rejected_declaration_cannot_inject_a_contract_line(tmp_path: Path) -> None:
    """A refused input must not be able to write the answer it was refused.

    stdout here IS a line protocol, and the rejected value was interpolated into
    it verbatim. `FLOW_VANTAGE_DECLARE=$'x\\nFLOW_VANTAGE: host'` therefore
    emitted a forged verdict line ABOVE the real one; a consumer taking the
    first match stored `host` for an input this branch exists to refuse. The
    refusal was working perfectly and the report carried the caller's answer -
    reproduced through `flow-wave-registry.sh register` before the fix.
    """
    f = _fixture(tmp_path, ns=INITIAL_NS, machine_id="0" * 32)
    res = _run(
        "--fixture",
        str(f),
        "--quiet",
        env={"FLOW_VANTAGE_DECLARE": "bogus\nFLOW_VANTAGE: host"},
    )
    verdict_lines = [
        line for line in res.stdout.splitlines() if line.startswith("FLOW_VANTAGE: ")
    ]
    assert verdict_lines == ["FLOW_VANTAGE: unknown"], (
        f"the rejected value put {len(verdict_lines)} verdict line(s) on stdout: "
        f"{verdict_lines}"
    )
    assert res.returncode == 4


@requires_bash
@requires_symlinks
def test_the_sanitiser_keeps_a_readable_value_readable(tmp_path: Path) -> None:
    """The escape must not be a blanket redaction.

    A caller who mistyped needs to SEE what they typed, or the refusal stops
    being actionable and they retry the same typo. Only characters outside the
    conservative set are replaced.
    """
    f = _fixture(tmp_path, ns=INITIAL_NS, machine_id="0" * 32)
    res = _run("--fixture", str(f), "--quiet", env={"FLOW_VANTAGE_DECLARE": "contaner"})
    assert "contaner" in _contract(res.stdout)["FLOW_VANTAGE_BASIS"]


def test_the_registered_control_unsets_the_declaration(tmp_path: Path) -> None:
    """The control's invocation must clear `FLOW_VANTAGE_DECLARE`.

    The gate reads it FIRST and short-circuits, so a control inheriting the
    caller's environment never reaches its fixtures: measured 2026-09-20, PASS
    with the variable absent and BLIND with `host` exported. Its red would then
    be a fact about whoever ran it. The invocation is DATA, so unlike the suite
    it cannot clear the variable per run - it has to carry the `env -u`, and
    this is what notices if someone tidies it away.
    """
    import json

    manifest = json.loads(
        (ROOT / "controls" / "flow-vantage" / "control.json").read_text()
    )
    invocation = manifest["invocation"]
    # The EMPTY form (`env FLOW_VANTAGE_DECLARE= ...`), not `env -u`:
    # `check-control-ci-deps.py` reads the token after `env` as a command unless
    # it is a `VAR=value` assignment, so `-u` made the whole battery red. The
    # gate treats an empty value as undeclared, which the behavioural test below
    # checks rather than assuming.
    assert "FLOW_VANTAGE_DECLARE=" in invocation, invocation
    assert invocation.index("FLOW_VANTAGE_DECLARE=") < invocation.index("bash"), invocation


@requires_bash
def test_the_control_invocation_really_ignores_an_exported_declaration() -> None:
    """The manifest guard above, checked as behaviour rather than as a string.

    A test that only reads the manifest asserts the shape of a list. This runs
    the gate THROUGH that list with the variable exported and requires the
    measured answer - so a future `env -u` that is present but ineffective
    (wrong position, wrong spelling) is still caught.
    """
    import json

    manifest = json.loads(
        (ROOT / "controls" / "flow-vantage" / "control.json").read_text()
    )
    case = CONTROL_CASES / "bad-container"
    argv = [
        part.replace("{gate}", str(VANTAGE)).replace("{case}", str(case))
        for part in manifest["invocation"]
    ]
    env = dict(os.environ)
    env["FLOW_VANTAGE_DECLARE"] = "host"
    res = subprocess.run(argv, capture_output=True, text=True, env=env)
    assert _contract(res.stdout)["FLOW_VANTAGE"] == "container"
    assert _contract(res.stdout)["FLOW_VANTAGE_SOURCE"] == "measured"


@requires_bash
@pytest.mark.parametrize("flag", ("--help", "-h"))
def test_help_actually_prints_the_usage_it_claims_to(flag: str) -> None:
    """A help screen that prints nothing and exits 0 reads as "nothing to say".

    The extraction used a fixed `sed -n '1,140p'` window and the header grew
    past it, so both spellings returned empty at exit 0 - the failure looked
    exactly like a deliberately terse tool. The range is derived from the text
    now, so the header can grow again without silently emptying this.
    """
    res = _run(flag)
    assert res.returncode == 0
    assert "--fixture" in res.stdout, res.stdout
    assert "FLOW_VANTAGE_DECLARE" in res.stdout, res.stdout


@requires_bash
def test_the_constructed_anchor_is_blind_by_input_not_by_being_a_stub(
    tmp_path: Path,
) -> None:
    """The anchor must be a real implementation of the check it reconstructs.

    It answers `host` on every committed case, and a reader could reasonably
    wonder whether that is because the mount signal never fires or because the
    anchor is a constant function - the two look identical from the control's
    output, and only one of them is an honest reconstruction. Feeding it a
    mountinfo that DOES carry `claude/sessions` makes it say `container`, so its
    blindness is a property of the world (the line never appears on either side,
    measured 0 matches) rather than of the artifact.

    Raised as a red case by the counter-model review (codex/gpt-6-astra) and not
    previously covered.
    """
    anchor = (
        ROOT
        / "controls"
        / "flow-vantage"
        / "anchors"
        / "constructed-mountinfo-blind-flow-vantage.sh"
    )
    fixture = tmp_path / "mounted"
    fixture.mkdir()
    real = (CONTROL_CASES / "good-host" / "proc-mountinfo").read_text()
    (fixture / "proc-mountinfo").write_text(
        real + "999 30 0:99 / /home/u/.claude/sessions rw,relatime shared:99 - tmpfs t rw\n"
    )
    res = subprocess.run(
        ["bash", str(anchor), "--fixture", str(fixture)],
        capture_output=True,
        text=True,
    )
    assert _contract(res.stdout)["FLOW_VANTAGE"] == "container"
    assert res.returncode == 3
    # And the committed cases really do lack that line, which is what makes the
    # anchor blind on them - asserted rather than assumed.
    for case in ("good-host", "bad-container", "bad-unknown-disagreement"):
        assert "claude/sessions" not in (
            CONTROL_CASES / case / "proc-mountinfo"
        ).read_text()

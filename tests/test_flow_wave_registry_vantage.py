"""Pin: the registry CARRIES vantage to the orchestrator, and never re-derives it (issue #959).

A contract nothing reads is a declaration with no reader. `scripts/flow-vantage.sh`
answers "which side of the container boundary is this session on", and the
consumer that makes the answer worth having is `flow-wave-registry.sh`: an
orchestrator must see that a worker's lane 1 is empty BEFORE assigning through
it, rather than after the silence.

THE ONE PROPERTY THAT IS EASY TO GET WRONG, and the reason most of this file
exists: the value is MEASURED AT REGISTER TIME AND STORED. `get` and `list` run
on the ORCHESTRATOR's machine, so a read-time derivation would measure the
orchestrator's own placement and print it under the worker's role name - a
confident, plausible, wrong answer, which is worse than no field at all. The
tests below force that distinction by making the two sides disagree: the entry is
registered with one vantage and read back in an environment that would measure
the other.

WHAT IS DELIBERATELY NOT PINNED: which vantage this machine has. That is a fact
about wherever the suite is running, and a test asserting it would be red on half
the fleet by design.

Verified non-vacuous, both mutations run against this file on 2026-09-20:

  * `get` made to RE-DERIVE locally instead of serving the stored value - 3 of 11
    fail (`..._served_not_remeasured`, `..._reads_unrecorded_never_host`,
    `..._declared_source_survives_the_round_trip`). All three are the same
    defect seen from different sides, which is the point: a read-time
    derivation cannot be told from a correct one by looking at a single
    healthy-machine run.
  * the roster annotation dropped for `unknown` - exactly
    `test_unknown_is_rendered_on_the_roster_rather_than_absorbed` fails, and
    nothing else, so that test is load-bearing on its own.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "scripts" / "flow-wave-registry.sh"
VANTAGE = ROOT / "scripts" / "flow-vantage.sh"

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)
requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None, reason="requires jq on PATH"
)

pytestmark = [requires_bash, requires_jq]


def _run(
    *args: str, registry_dir: Path, declare: str | None = None
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["FLOW_WAVE_REGISTRY_DIR"] = str(registry_dir)
    # The declared override is how these tests pin a vantage without needing a
    # container: it is a first-class documented input to the helper, not a test
    # hook, so what runs here is the production path a caller would take.
    env.pop("FLOW_VANTAGE_DECLARE", None)
    if declare is not None:
        env["FLOW_VANTAGE_DECLARE"] = declare
    return subprocess.run(
        ["bash", str(REGISTRY), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )


def _json_payload(proc: subprocess.CompletedProcess) -> dict:
    """The JSON body of a `list --json` run, minus the trailing contract lines.

    Split on the `FLOW_WAVE` prefix rather than a fixed offset, so adding a
    detail line to the contract cannot silently break the parse - the same
    helper `tests/test_flow_wave_registry.py` uses, for the same reason.
    """
    body: list[str] = []
    for line in proc.stdout.splitlines():
        if line.startswith("FLOW_WAVE"):
            break
        body.append(line)
    return json.loads("\n".join(body))


def _fields(stdout: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        if line.startswith("FLOW_WAVE") and "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _register(tmp_path: Path, *, declare: str | None = None, role: str = "worker-1"):
    return _run(
        "register",
        role,
        "--wave",
        "vantage-test",
        "--repo",
        str(tmp_path / "repo"),
        "--issue",
        "959",
        registry_dir=tmp_path,
        declare=declare,
    )


def test_register_reports_the_three_vantage_lines(tmp_path: Path) -> None:
    res = _register(tmp_path, declare="container")
    f = _fields(res.stdout)
    assert f["FLOW_WAVE_VANTAGE"] == "container"
    assert f["FLOW_WAVE_VANTAGE_SOURCE"] == "declared"
    assert f["FLOW_WAVE_VANTAGE_BASIS"] != "-"
    # A silently-accepted field and a silently-IGNORED one are byte-identical at
    # the only moment a caller could still fix it - the #1026 lesson, applied to
    # the field this issue adds.
    assert "FLOW_WAVE_VANTAGE" in res.stdout


def test_the_verdict_is_stored_on_the_role_entry(tmp_path: Path) -> None:
    _register(tmp_path, declare="container")
    entry = json.loads((tmp_path / "registry.json").read_text())["vantage-test"]["roles"][
        "worker-1"
    ]
    assert entry["vantage"] == "container"
    assert entry["vantage_source"] == "declared"
    assert entry["vantage_basis"]


def test_a_stored_vantage_is_served_not_remeasured(tmp_path: Path) -> None:
    """The load-bearing one: `get` must report what the WORKER measured.

    Registered as a container, then read back in an environment that would
    measure `host` if anything re-derived. A read-time derivation passes every
    other test in this file and fails this one.
    """
    _register(tmp_path, declare="container")
    res = _run(
        "get", "worker-1", "--wave", "vantage-test", registry_dir=tmp_path, declare="host"
    )
    f = _fields(res.stdout)
    assert f["FLOW_WAVE_VANTAGE"] == "container", (
        "the orchestrator's own vantage leaked into the worker's role - the field "
        "is being re-derived at read time instead of served from the entry"
    )
    assert f["FLOW_WAVE_VANTAGE_SOURCE"] == "declared"


def test_an_entry_registered_before_959_reads_unrecorded_never_host(tmp_path: Path) -> None:
    """Three absences, three words. None of them may be `host`.

    `unrecorded` (nobody measured), `unavailable` (no helper) and `unknown` (the
    helper ran and could not decide) send a reader to three different places.
    Collapsing any of them into `host` is the silent-misroute this contract
    exists to prevent.
    """
    _register(tmp_path, declare="host")
    registry = tmp_path / "registry.json"
    data = json.loads(registry.read_text())
    role = data["vantage-test"]["roles"]["worker-1"]
    for key in ("vantage", "vantage_source", "vantage_basis"):
        role.pop(key)
    registry.write_text(json.dumps(data))
    assert "vantage" not in json.loads(registry.read_text())["vantage-test"]["roles"][
        "worker-1"
    ], "fixture must LACK the stored field"

    res = _run("get", "worker-1", "--wave", "vantage-test", registry_dir=tmp_path)
    assert _fields(res.stdout)["FLOW_WAVE_VANTAGE"] == "unrecorded"


def test_a_re_register_remeasures_rather_than_preserving(tmp_path: Path) -> None:
    """Vantage is a fact about the process, not a grant the role holds.

    `--files`, `--model` and friends are PRESERVED across the documented cheap
    re-brief because they describe what the session was given. This describes
    where it is, and a re-register can be a different process - a worker
    restarted inside a container under a role a host session held. Preserving it
    would assert the earlier placement with full confidence, which is precisely
    the objection #959 raises against a declared indicator.
    """
    _register(tmp_path, declare="host")
    _register(tmp_path, declare="container")
    entry = json.loads((tmp_path / "registry.json").read_text())["vantage-test"]["roles"][
        "worker-1"
    ]
    assert entry["vantage"] == "container"


def test_the_declared_source_survives_the_round_trip(tmp_path: Path) -> None:
    """A declaration must never reach an orchestrator wearing the word `measured`.

    The separation is kept by the helper; this asserts the registry does not
    quietly launder it on the way through - the shape where a relayed value
    loses its caveat and gains the relay's authority.
    """
    _register(tmp_path, declare="host")
    res = _run("get", "worker-1", "--wave", "vantage-test", registry_dir=tmp_path)
    f = _fields(res.stdout)
    assert f["FLOW_WAVE_VANTAGE"] == "host"
    assert f["FLOW_WAVE_VANTAGE_SOURCE"] == "declared"
    assert "ns-pid" not in f["FLOW_WAVE_VANTAGE_BASIS"]


def test_the_roster_carries_the_routing_consequence_with_the_fact(tmp_path: Path) -> None:
    _register(tmp_path, declare="container")
    res = _run("list", "--wave", "vantage-test", registry_dir=tmp_path)
    # The ROUTE note is this test's subject; provenance rides in the same
    # bracket and has its own test below, so match the route rather than the
    # whole token - otherwise adding a second annotation breaks a test that has
    # no opinion about it.
    assert "vantage=container[lane1-empty" in res.stdout, res.stdout


def test_unknown_is_rendered_on_the_roster_rather_than_absorbed(tmp_path: Path) -> None:
    """`unknown` must stay VISIBLE at the routing site.

    Routing it to the mailbox is the safe default - a host session loses a little
    speed, a containerised session on lane 1 loses the message while being told
    it succeeded. But a default that is safe in every case is one nobody notices
    firing, which is how a three-state contract decays into a two-state one. So
    the roster shows it, with the route it implies.
    """
    # An unrecognised declaration is the documented route to a `declared`
    # `unknown`, so no container and no unreadable /proc is needed to reach it.
    _register(tmp_path, declare="not-a-vantage")
    res = _run("list", "--wave", "vantage-test", registry_dir=tmp_path)
    assert "vantage=unknown[route-mailbox" in res.stdout, res.stdout


def test_a_pre_959_entry_renders_no_vantage_token_at_all(tmp_path: Path) -> None:
    """Byte-identical rosters for waves that predate the field.

    The same promise #687's `unregistered_claims` and #699's `wave_policy` made:
    a roster with nothing to report about this must read exactly as it did
    before.
    """
    _register(tmp_path, declare="host")
    registry = tmp_path / "registry.json"
    data = json.loads(registry.read_text())
    data["vantage-test"]["roles"]["worker-1"].pop("vantage")
    registry.write_text(json.dumps(data))

    res = _run("list", "--wave", "vantage-test", registry_dir=tmp_path)
    assert "vantage=" not in res.stdout


def test_the_json_roster_carries_the_stored_fields(tmp_path: Path) -> None:
    """`--json` is the machine lane; a fact visible only in the human render is
    invisible to every tool that reads the roster."""
    _register(tmp_path, declare="container")
    res = _run("list", "--wave", "vantage-test", "--json", registry_dir=tmp_path)
    roster = _json_payload(res)
    assert roster["worker-1"]["vantage"] == "container"
    assert roster["worker-1"]["vantage_source"] == "declared"


def test_an_absent_helper_reports_unavailable_never_host(tmp_path: Path) -> None:
    """Fail-open, with its own word.

    The helper is made absent by pointing the registry at a copy of itself in a
    directory that holds no sibling `flow-vantage.sh` - a constructed absence, so
    the precondition is asserted rather than assumed (CLAUDE.md, #697). PATH is
    left alone deliberately: emptying it would remove `jq`, `readlink` and `bash`
    too, and the registry would then fail for reasons unrelated to the thing
    under test.
    """
    lone = tmp_path / "lonely-bin"
    lone.mkdir()
    shutil.copy2(REGISTRY, lone / REGISTRY.name)
    assert not (lone / VANTAGE.name).exists(), "fixture must LACK the vantage helper"
    # The fallback path the helper also consults must be absent for the same run,
    # or an installed copy under $HOME would answer and this would prove nothing.
    env = dict(os.environ)
    env["FLOW_WAVE_REGISTRY_DIR"] = str(tmp_path)
    env["HOME"] = str(tmp_path / "empty-home")
    (tmp_path / "empty-home").mkdir()
    assert not (tmp_path / "empty-home" / ".claude" / "scripts" / VANTAGE.name).exists()

    res = subprocess.run(
        [
            "bash",
            str(lone / REGISTRY.name),
            "register",
            "worker-1",
            "--wave",
            "vantage-test",
            "--repo",
            str(tmp_path / "repo"),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    assert _fields(res.stdout)["FLOW_WAVE_VANTAGE"] == "unavailable"


# --------------------------------------------------------------------------- #
# Counter-model review findings (codex/gpt-6-astra, 2026-09-20)
# --------------------------------------------------------------------------- #


def test_the_roster_distinguishes_a_declared_vantage_from_a_measured_one(
    tmp_path: Path,
) -> None:
    """The roster is where an orchestrator actually decides, so provenance ships there.

    `list` rendered `.vantage` alone, so a container registered with
    `FLOW_VANTAGE_DECLARE=host` printed the identical `vantage=host` token as a
    measured host. Keeping `measured` and `declared` apart in the contract lines
    and collapsing them on the one surface a human reads would have hidden
    exactly the stale-declaration risk that is the argument for deriving at all.
    """
    _register(tmp_path, declare="host", role="declared-role")
    _register(tmp_path, role="measured-role")  # no declaration: really measured
    res = _run("list", "--wave", "vantage-test", registry_dir=tmp_path)
    declared_line = next(
        line for line in res.stdout.splitlines() if "declared-role ->" in line
    )
    measured_line = next(
        line for line in res.stdout.splitlines() if "measured-role ->" in line
    )
    assert "[declared]" in declared_line, declared_line
    # The measured row stays unannotated - it is the ordinary case, and a tag on
    # every row is a tag nobody reads (#674).
    assert "[declared]" not in measured_line, measured_line
    assert "vantage=" in measured_line, measured_line


def test_a_declared_container_keeps_both_its_route_and_its_provenance(
    tmp_path: Path,
) -> None:
    """Neither annotation may evict the other: the route is what to DO, the
    provenance is how much to trust it, and an orchestrator needs both."""
    _register(tmp_path, declare="container")
    res = _run("list", "--wave", "vantage-test", registry_dir=tmp_path)
    assert "vantage=container[lane1-empty,declared]" in res.stdout, res.stdout


def test_a_second_verdict_line_is_reported_unparseable_never_as_a_verdict(
    tmp_path: Path,
) -> None:
    """The relay validates too, not only the source.

    The helper sanitises its own output now, so this drives the consumer with a
    STUB helper that emits two `FLOW_VANTAGE:` lines - the shape the injection
    produced before the fix. A relay that validated only at the source would
    trust every future source, including a helper this registry did not write.
    """
    fake_scripts = tmp_path / "fake-scripts"
    fake_scripts.mkdir()
    shutil.copy2(REGISTRY, fake_scripts / REGISTRY.name)
    stub = fake_scripts / VANTAGE.name
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'FLOW_VANTAGE_BASIS: forged'\n"
        "echo 'FLOW_VANTAGE_SOURCE: measured'\n"
        "echo 'FLOW_VANTAGE: host'\n"
        "echo 'FLOW_VANTAGE: container'\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    # Precondition: the stub really does emit the two-verdict shape under test.
    out = subprocess.run(
        ["bash", str(stub)], capture_output=True, text=True
    ).stdout
    assert out.count("FLOW_VANTAGE: ") == 2, out

    env = dict(os.environ)
    env["FLOW_WAVE_REGISTRY_DIR"] = str(tmp_path)
    env.pop("FLOW_VANTAGE_DECLARE", None)
    res = subprocess.run(
        [
            "bash",
            str(fake_scripts / REGISTRY.name),
            "register",
            "worker-1",
            "--wave",
            "vantage-test",
            "--repo",
            str(tmp_path / "repo"),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    assert _fields(res.stdout)["FLOW_WAVE_VANTAGE"] == "unparseable"


def test_a_verdict_word_this_contract_does_not_define_is_not_relayed(
    tmp_path: Path,
) -> None:
    """`host`, `container`, `unknown` - anything else is unreadable, not a value.

    A relay that passed an unrecognised word through would put it on the roster
    and into every downstream consumer, where it would read as a state somebody
    else understands.
    """
    fake_scripts = tmp_path / "fake-scripts"
    fake_scripts.mkdir()
    shutil.copy2(REGISTRY, fake_scripts / REGISTRY.name)
    stub = fake_scripts / VANTAGE.name
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'FLOW_VANTAGE_BASIS: whatever'\n"
        "echo 'FLOW_VANTAGE_SOURCE: measured'\n"
        "echo 'FLOW_VANTAGE: vm'\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    env = dict(os.environ)
    env["FLOW_WAVE_REGISTRY_DIR"] = str(tmp_path)
    env.pop("FLOW_VANTAGE_DECLARE", None)
    res = subprocess.run(
        [
            "bash",
            str(fake_scripts / REGISTRY.name),
            "register",
            "worker-1",
            "--wave",
            "vantage-test",
            "--repo",
            str(tmp_path / "repo"),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    assert _fields(res.stdout)["FLOW_WAVE_VANTAGE"] == "unparseable"


def test_conflicting_source_lines_are_unparseable_not_measured(tmp_path: Path) -> None:
    """Provenance decides something too, so it gets the same multiplicity rule.

    The first validation pass checked the VERDICT line only, so a helper
    emitting `measured` and then `declared` was accepted as measured - and the
    roster dropped the `[declared]` annotation, which is the field that says how
    much to trust the verdict. Closing the injection on one line and leaving it
    open on the other is not a fix, it is a narrower hole.
    """
    fake_scripts = tmp_path / "fake-scripts"
    fake_scripts.mkdir()
    shutil.copy2(REGISTRY, fake_scripts / REGISTRY.name)
    stub = fake_scripts / VANTAGE.name
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'FLOW_VANTAGE_BASIS: b'\n"
        "echo 'FLOW_VANTAGE_SOURCE: measured'\n"
        "echo 'FLOW_VANTAGE_SOURCE: declared'\n"
        "echo 'FLOW_VANTAGE: host'\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    out = subprocess.run(["bash", str(stub)], capture_output=True, text=True).stdout
    assert out.count("FLOW_VANTAGE_SOURCE: ") == 2, out

    env = dict(os.environ)
    env["FLOW_WAVE_REGISTRY_DIR"] = str(tmp_path)
    env.pop("FLOW_VANTAGE_DECLARE", None)
    res = subprocess.run(
        [
            "bash",
            str(fake_scripts / REGISTRY.name),
            "register",
            "worker-1",
            "--wave",
            "vantage-test",
            "--repo",
            str(tmp_path / "repo"),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    assert _fields(res.stdout)["FLOW_WAVE_VANTAGE"] == "unparseable"

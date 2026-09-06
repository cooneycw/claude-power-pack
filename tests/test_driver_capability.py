"""Pin: driver capability is declared data, checked before assignment (issue #783).

CPP has four drivers that carry a GitHub issue end to end. The ELI5 gate (#775)
and the delegated drivers' Step 3 gate (#774/#784) both answer "should this work
be done, and is this the right plan?". Nothing answered "can this driver do this
work AT ALL?" - and for three of the four the answer is structurally no for whole
classes of issue: they wrap their model in an IMPLEMENTATION-ONLY execution fence
(so the deliverable can only be a source diff), and none can reach a live source.

Observed twice in one evening on the `kyle-completion` wave (2026-09-05), by two
different workers on two different drivers, and caught both times only because
the worker read its own fence and refused. That is discipline, not mechanism.

This suite is the mechanism, and it is deliberately built the harder way round:
the expected matrix is DERIVED FROM THE DRIVER DOCUMENTS rather than restated
from the helper. A test that copied `flow-driver-capability.sh`'s own table would
pass forever while the table drifted from the fences it describes - the exact
decoration failure #701 named about its own lexicon, and the reason the helper
publishes its data to three readers instead of merely existing. So:

- if a delegated driver loses its IMPLEMENTATION-ONLY fence, `scope` becomes a
  lie and this file goes red;
- if `codex/auto.md` stops specifying `--sandbox workspace-write`, the basis for
  `web: no` is gone and this file goes red;
- if `templates/opencode-gemma.json` stops denying `webfetch`/`websearch`, the
  hardest of the three web claims is gone and this file goes red.

The registry half is pinned by behaviour rather than by text: the roster
annotation must be DERIVED from the helper, so a run with the helper removed must
render no fence at all rather than a remembered one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "scripts" / "flow-driver-capability.sh"
REGISTRY = ROOT / "scripts" / "flow-wave-registry.sh"
COMMANDS = ROOT / ".claude" / "commands"
GEMMA_PROFILE = ROOT / "templates" / "opencode-gemma.json"

# Drives a real `bash` subprocess; the CI validate container may not ship one,
# so skip there (CPP core directive, same shape as the other flow suites).
requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)
requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None, reason="requires jq on PATH"
)

#: The three drivers that delegate implementation to another model. Each wraps it
#: in the execution fence #735 introduced, which is what makes them
#: implementation-only, and none of the three can consult a live source.
DELEGATED = ("codex", "qwen", "gemma")

FENCE_SENTENCE = (
    "You are an IMPLEMENTATION-ONLY agent. Your SOLE job is to write and modify"
)


def _driver_doc(family: str) -> str:
    return (COMMANDS / family / "auto.md").read_text(encoding="utf-8")


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", str(CAP), *args],
        capture_output=True,
        text=True,
        env=full_env,
    )


def _fields(stdout: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line and line.startswith("FLOW_DRIVER"):
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _verdict(stdout: str, prefix: str) -> str:
    for line in reversed(stdout.splitlines()):
        if line.startswith(f"{prefix}: "):
            return line.split(": ", 1)[1]
    raise AssertionError(f"no {prefix} verdict line in:\n{stdout}")


# ---------------------------------------------------------------------------
# The matrix must match the tree it describes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", DELEGATED, ids=DELEGATED)
def test_delegated_drivers_still_carry_the_implementation_only_fence(family: str) -> None:
    """`scope: implementation-only` is only true while the fence is really there.

    This is the precondition for the helper's claim, asserted against the driver
    document rather than against the helper - a negative-condition fixture must
    assert its own precondition (the #697 convention), and here the precondition
    IS the evidence.
    """
    assert FENCE_SENTENCE in _driver_doc(family), (
        f"{family}/auto.md no longer carries the IMPLEMENTATION-ONLY execution fence, "
        "so flow-driver-capability.sh's `scope: implementation-only` for it is now a "
        "false claim (issue #783). Either restore the fence or change the declared data."
    )


@requires_bash
@pytest.mark.parametrize("family", DELEGATED, ids=DELEGATED)
def test_declared_scope_matches_the_fence(family: str) -> None:
    proc = _run("show", f"{family}:auto")
    assert proc.returncode == 0, proc.stderr
    fields = _fields(proc.stdout)
    assert fields["FLOW_DRIVER_SCOPE"] == "implementation-only"
    assert "research" in fields["FLOW_DRIVER_CANNOT"], (
        "an implementation-only driver cannot produce a finding, so `research` must "
        "appear in what it cannot take"
    )


@requires_bash
def test_flow_auto_is_the_declared_general_driver() -> None:
    """The matrix needs a positive case, or `cannot` is unfalsifiable.

    If every driver were implementation-only and web-less, "route it elsewhere"
    would name nowhere - and a check that can only ever say `mismatch` teaches a
    reader to stop reading it.
    """
    proc = _run("show", "flow:auto")
    assert proc.returncode == 0, proc.stderr
    fields = _fields(proc.stdout)
    assert fields["FLOW_DRIVER_SCOPE"] == "general"
    assert fields["FLOW_DRIVER_WEB"] == "yes"
    assert fields["FLOW_DRIVER_CANNOT"] == "-"
    assert FENCE_SENTENCE not in _driver_doc("flow"), (
        "flow/auto.md must NOT carry an implementation-only fence - Claude implements "
        "directly there, which is the whole basis for `scope: general`"
    )


def test_codex_web_basis_is_still_the_sandbox_flag() -> None:
    """`web: no` for codex rests on one flag in one document. Pin the flag.

    Nothing else stops Codex reaching the network, so if #735's downgrade were
    ever reverted the declared data would silently overstate the block.
    """
    doc = _driver_doc("codex")
    assert "--sandbox workspace-write" in doc, (
        "codex/auto.md no longer specifies `--sandbox workspace-write`, which is the "
        "sole basis for flow-driver-capability.sh declaring `web: no` for codex:auto "
        "(issue #783/#735)"
    )


@requires_bash
def test_codex_web_basis_names_the_sandbox() -> None:
    fields = _fields(_run("show", "codex:auto").stdout)
    assert fields["FLOW_DRIVER_WEB"] == "no"
    assert "sandbox" in fields["FLOW_DRIVER_WEB_BASIS"], (
        "the recorded basis must name the mechanism, so a reader who doubts the claim "
        "has something to check"
    )


def test_gemma_web_basis_is_still_the_profile_denial() -> None:
    """The hardest of the three web claims - a named tool denial in the profile."""
    profile = json.loads(GEMMA_PROFILE.read_text(encoding="utf-8"))
    blob = json.dumps(profile)
    assert '"webfetch": "deny"' in blob.replace("\\", ""), (
        "templates/opencode-gemma.json no longer denies `webfetch`; gemma:auto's "
        "`web: no` was the one MECHANICAL denial of the three (issue #783/#752)"
    )
    assert '"websearch": "deny"' in blob.replace("\\", "")


@requires_bash
def test_qwen_web_basis_does_not_overstate_the_block() -> None:
    """Honesty check, and the one this suite exists to keep honest.

    Qwen Code CLI has web tools upstream; the CPP lane configures none, and the
    Docker sandbox is skipped entirely for a remote endpoint (#749) - qwen/auto.md
    says in as many words that network from model-run shell commands is NOT
    blocked. So the verdict is right but the BASIS is an absence of provision, and
    recording it as a denial would be the kind of overstatement that gets a whole
    matrix disbelieved.
    """
    fields = _fields(_run("show", "qwen:auto").stdout)
    assert fields["FLOW_DRIVER_WEB"] == "no"
    basis = fields["FLOW_DRIVER_WEB_BASIS"]
    assert "unconfigured" in basis, f"expected an absence-of-provision basis, got {basis!r}"
    assert "denied" not in basis and "blocked" not in basis, (
        "qwen's web basis must not claim a mechanical denial it does not have"
    )


# ---------------------------------------------------------------------------
# The helper's own contract
# ---------------------------------------------------------------------------


@requires_bash
def test_check_reports_fit_for_work_the_driver_can_do() -> None:
    proc = _run("check", "codex:auto", "--needs", "implementation")
    assert proc.returncode == 0, proc.stderr
    assert _verdict(proc.stdout, "FLOW_DRIVER_CHECK") == "fit"


@requires_bash
@pytest.mark.parametrize(
    ("driver", "need"),
    [(f"{family}:auto", need) for family in DELEGATED for need in ("research", "web")],
)
def test_check_refuses_the_two_observed_mis_routes(driver: str, need: str) -> None:
    """The two failures the issue was filed about, one case each, all three drivers."""
    proc = _run("check", driver, "--needs", need)
    assert proc.returncode == 1, (
        f"{driver} --needs {need} must be a mismatch and exit 1; got "
        f"{proc.returncode}\n{proc.stdout}"
    )
    assert _verdict(proc.stdout, "FLOW_DRIVER_CHECK") == "mismatch"
    assert need in _fields(proc.stdout)["FLOW_DRIVER_UNMET"]
    assert f"FLOW_DRIVER_BLOCKED: {need} - " in proc.stdout, (
        "a mismatch must say WHY, naming the need; a bare verdict is the kind of "
        "refusal a reader routes around"
    )


@requires_bash
def test_flow_auto_can_take_both_classes() -> None:
    proc = _run("check", "flow:auto", "--needs", "research,web")
    assert proc.returncode == 0, proc.stdout
    assert _verdict(proc.stdout, "FLOW_DRIVER_CHECK") == "fit"


@requires_bash
def test_an_unknown_need_is_a_usage_error_not_a_silent_fit() -> None:
    """A typo that reads as `fit` is the decoration failure in miniature."""
    proc = _run("check", "codex:auto", "--needs", "reserch")
    assert proc.returncode == 2, proc.stdout
    assert "unknown need" in proc.stderr


@requires_bash
def test_an_unknown_driver_is_unanswered_and_fails_open() -> None:
    """Failing closed on a downstream driver would block a wave over a name.

    `unknown` is a STATE, not a failure - the same rule #674 records for the
    registry: a new verdict must never become a new exit code.
    """
    proc = _run("check", "somebody-elses:auto", "--needs", "web")
    assert proc.returncode == 0, proc.stdout
    assert _verdict(proc.stdout, "FLOW_DRIVER_CHECK") == "unknown"
    assert _fields(proc.stdout)["FLOW_DRIVER_SCOPE"] == "-", (
        "an unknown driver must assert nothing; a '-' is the only honest answer"
    )


@requires_bash
@pytest.mark.parametrize("spelling", ["codex:auto", "/codex:auto", "codex", "codex:auto (gpt-5.5)"])
def test_driver_names_are_accepted_as_actually_written(spelling: str) -> None:
    """`--driver` is free text (#699) and is written four different ways in practice.

    Downgrading `flow:auto (Opus 5)` to `unknown` on a parenthesis would make the
    roster annotation vanish exactly when a wave bothered to be specific.
    """
    fields = _fields(_run("show", spelling).stdout)
    assert fields["FLOW_DRIVER"] == "codex:auto", f"{spelling!r} did not resolve"


@requires_bash
def test_list_covers_every_declared_driver() -> None:
    proc = _run("list", "--json")
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(proc.stdout)
    assert {row["driver"] for row in rows} == {
        "flow:auto",
        "codex:auto",
        "qwen:auto",
        "gemma:auto",
    }


# ---------------------------------------------------------------------------
# The roster reads it back - the anti-decoration half
# ---------------------------------------------------------------------------


@requires_bash
@requires_jq
def test_roster_annotates_a_role_with_its_driver_fence(tmp_path: Path) -> None:
    """The feature, end to end: the mismatch is visible at ASSIGNMENT time.

    `worker-2 -> ... driver=gemma:auto[impl-only,no-web]` is what an orchestrator
    reads before routing a research ticket, instead of learning it when the worker
    refuses.
    """
    env = {
        "FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "reg"),
        "FLOW_WAVE_SOCK_DIR": str(tmp_path / "socks"),
    }
    reg = lambda *a: subprocess.run(  # noqa: E731 - a local alias keeps the cases readable
        ["bash", str(REGISTRY), *a],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
    )

    reg("register", "worker-2", "--wave", "w", "--driver", "gemma:auto")
    listing = reg("list", "--wave", "w").stdout
    assert "driver=gemma:auto[impl-only,no-web]" in listing, listing

    got = reg("get", "worker-2", "--wave", "w").stdout
    fields = dict(
        line.split("=", 1) for line in got.splitlines() if line.startswith("FLOW_WAVE_DRIVER")
    )
    assert fields["FLOW_WAVE_DRIVER"] == "gemma:auto"
    assert fields["FLOW_WAVE_DRIVER_SCOPE"] == "implementation-only"
    assert fields["FLOW_WAVE_DRIVER_WEB"] == "no"
    assert "research" in fields["FLOW_WAVE_DRIVER_CANNOT"]


@requires_bash
@requires_jq
def test_the_roster_annotation_is_derived_not_remembered(tmp_path: Path) -> None:
    """Mutation check: with the helper gone, the fence must vanish, not persist.

    This is what distinguishes deriving from restating. If the registry carried
    its own copy of "gemma:auto is impl-only", this test would still see the
    annotation - and the copy would be free to drift from the fences it describes
    while every reader believed it.
    """
    env = {
        "FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "reg"),
        "FLOW_WAVE_SOCK_DIR": str(tmp_path / "socks"),
    }
    # A registry copy whose sibling capability helper does not exist.
    stripped = tmp_path / "scripts"
    stripped.mkdir()
    (stripped / "flow-wave-registry.sh").write_text(
        REGISTRY.read_text(encoding="utf-8"), encoding="utf-8"
    )

    def reg(script: Path, *a: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(script), *a],
            capture_output=True,
            text=True,
            env={**os.environ, **env},
        )

    reg(stripped / "flow-wave-registry.sh", "register", "w1", "--wave", "w", "--driver", "gemma:auto")
    listing = reg(stripped / "flow-wave-registry.sh", "list", "--wave", "w").stdout
    assert "driver=gemma:auto" in listing, "the declared driver itself is still recorded"
    assert "impl-only" not in listing, (
        "with flow-driver-capability.sh absent the roster must render NO fence - a "
        "surviving annotation would mean the registry keeps its own copy of the "
        "capability claim, which is free to drift (issue #783)"
    )

    got = reg(stripped / "flow-wave-registry.sh", "get", "w1", "--wave", "w").stdout
    assert "FLOW_WAVE_DRIVER_SCOPE=-" in got, (
        "a missing fence must read as '-', never as a capability claim"
    )


@requires_bash
@requires_jq
def test_a_role_that_declares_no_driver_reads_exactly_as_before(tmp_path: Path) -> None:
    """#783 must be invisible to a wave that never used it (the #699 rule)."""
    env = {
        "FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "reg"),
        "FLOW_WAVE_SOCK_DIR": str(tmp_path / "socks"),
    }
    reg = lambda *a: subprocess.run(  # noqa: E731
        ["bash", str(REGISTRY), *a],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
    )
    reg("register", "worker-1", "--wave", "w")
    assert "driver=" not in reg("list", "--wave", "w").stdout
    assert "FLOW_WAVE_DRIVER=-" in reg("get", "worker-1", "--wave", "w").stdout


@requires_bash
@requires_jq
def test_the_driver_survives_the_omit_everything_re_brief(tmp_path: Path) -> None:
    """Re-registering is the documented cheap re-brief (#670/#699).

    A worker that `/clear`ed and re-registered to re-read the protocol must not
    thereby erase which driver it is running - the roster would then route work to
    it on no information at all.
    """
    env = {
        "FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "reg"),
        "FLOW_WAVE_SOCK_DIR": str(tmp_path / "socks"),
    }
    reg = lambda *a: subprocess.run(  # noqa: E731
        ["bash", str(REGISTRY), *a],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
    )
    reg("register", "worker-1", "--wave", "w", "--driver", "codex:auto")
    reg("register", "worker-1", "--wave", "w")
    assert "FLOW_WAVE_DRIVER=codex:auto" in reg("get", "worker-1", "--wave", "w").stdout


# ---------------------------------------------------------------------------
# Each driver states its own contract (the issue's third bullet)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", DELEGATED, ids=DELEGATED)
def test_each_delegated_driver_states_what_it_cannot_take(family: str) -> None:
    doc = _driver_doc(family)
    assert "## Capability contract" in doc, (
        f"{family}/auto.md must state its capability contract (issue #783) - the point "
        "is that a worker reads a STATED contract rather than inferring one from an "
        "execution fence written for a different purpose"
    )
    assert "research" in doc and "live source" in doc
    assert "/flow:auto" in doc, (
        "naming what it cannot do without naming where the work goes instead leaves the "
        "worker exactly as stuck as before"
    )


@pytest.mark.parametrize("family", DELEGATED, ids=DELEGATED)
def test_step_2_runs_the_capability_pre_flight(family: str) -> None:
    """The check must sit BEFORE the prompt is built, or it saves nothing."""
    doc = _driver_doc(family)
    lines = doc.splitlines()
    step2 = next(i for i, line in enumerate(lines) if line.startswith("### Step 2: Analyze"))
    step3 = next(i for i, line in enumerate(lines) if line.startswith("### Step 3: Approve"))
    section = "\n".join(lines[step2:step3])
    assert "flow-driver-capability.sh check" in section, (
        f"{family}/auto.md Step 2 must run the capability check before building the "
        "prompt (issue #783)"
    )
    assert "FLOW_DRIVER_CHECK: fit" in section
    build = section.index("flow-driver-capability.sh check")
    prompt = section.index("Build the")
    assert build < prompt, (
        f"{family}: the capability check must precede prompt construction - a check "
        "after the work is built is a report, not a gate"
    )


def test_flow_auto_declares_the_positive_contract() -> None:
    doc = _driver_doc("flow")
    assert "## Capability contract" in doc
    assert "general" in doc and "research" in doc


@pytest.mark.parametrize("family", DELEGATED, ids=DELEGATED)
def test_help_pages_separate_capability_from_precondition(family: str) -> None:
    """#758 documented whether the driver can START; this is what it can PRODUCE.

    Both live in the same Quick Start block, so the split has to be explicit or a
    reader merges them and concludes an existing repo plus a filed issue is the
    whole test.
    """
    doc = (COMMANDS / family / "help.md").read_text(encoding="utf-8")
    assert "#783" in doc, f"{family}/help.md must carry the capability note"
    assert "precondition" in doc, f"{family}/help.md must still carry the #758 split"
    assert doc.index("precondition") < doc.index("#783"), (
        "capability follows precondition: a driver that cannot start is not reached by "
        "the question of what it can produce"
    )


def test_wave_routes_on_declared_capability() -> None:
    doc = (COMMANDS / "flow" / "wave.md").read_text(encoding="utf-8")
    assign = doc.index("### 2. Assign")
    judge = doc.index("### 3. Judge")
    section = doc[assign:judge]
    assert "flow-driver-capability.sh" in section, (
        "flow/wave.md's Assign step must check driver capability - assignment is the "
        "moment #783 exists to move the discovery to"
    )
    assert "impl-only" in section and "no-web" in section, (
        "the roster annotation the orchestrator actually reads must appear where it "
        "is read"
    )

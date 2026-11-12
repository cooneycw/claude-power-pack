"""Tests for scripts/flow-finish-gate.sh - the deterministic quality-gate
invocation as one audited, allowlistable helper (issue #613, the #581 pattern).

Contract:
- With a CPP checkout and ``uv`` available, the helper invokes the runner as
  ``uv run --project <CPP_DIR> python -m lib.cicd run --plan <name>`` with
  ``PYTHONPATH`` naming the PARENT of ``lib/`` (the #430 contract), passing
  ``--plan`` through (default ``finish``). Verdict ``ok`` (exit 0) or ``fail``
  (exit 1) mirrors the runner's exit.
- With no runner (no checkout, or no uv), it degrades to ``make lint`` +
  ``make test`` when those targets exist; with neither, verdict ``skipped``
  (exit 4) with a loud warning.
- ``--check-summary`` runs ``lib.cicd check --summary`` as an ADVISORY: verdict
  ``ok`` (exit 0), ``warn`` (exit 3) or ``skipped`` (exit 4).
- Every verdict carries its OWN exit code (issue #1027): ``ok`` 0, ``fail`` 1,
  usage error 2, ``warn`` 3, ``skipped`` 4. Before that, ``ok``/``warn``/
  ``skipped`` all exited 0, so the documented ``if gate; then proceed; fi``
  grading shape could not see a gate that proved nothing or did not run.
- A gate that RAN but examined nothing reports ``warn (zero coverage: ...)``
  (issue #1027): a stage with no input produces a green that is not evidence.
- The flow command docs invoke the helper BARE at the stable path and no longer
  carry the inline ``PYTHONPATH=... uv run ...`` gate shape that could never
  match a permission prefix rule.

The behaviour tests stub ``uv`` and ``make`` with PATH shims that record their
argv, so no real runner is needed; ``FLOW_GATE_CPP_DIR`` pins (or empties) the
checkout resolution.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# coordination-admission.sh is exercised through each real caller, including
# its false/missing signal path; no second signal classifier is used in tests.
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-finish-gate.sh"

requires_git = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="the finish gate derives counter-model enrolment from git (issue #1171)",
)

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="requires bash on PATH",
)


def _make_stub(
    bindir: Path, name: str, exit_code: int = 0, stdout: str = ""
) -> Path:
    """An executable PATH shim that logs its argv and exits ``exit_code``.

    ``stdout`` lets a stub emit a payload the helper then parses - the runner
    path reads the runner's JSON from STDOUT via ``tee``, so a test that writes
    a JSON file somewhere is testing nothing (issue #812).
    """
    log = bindir / f"{name}.log"
    stub = bindir / name
    payload = ""
    if stdout:
        out_file = bindir / f"{name}.stdout"
        out_file.write_text(stdout)
        payload = f'cat "{out_file}"\n'
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{log}"\n'
        f"{payload}"
        f"exit {exit_code}\n"
    )
    stub.chmod(0o755)
    return log


def _assert_single_marker(proc: subprocess.CompletedProcess[str]) -> None:
    """At most ONE verdict marker per run, over every fixture in this file.

    `verdict()` prints; a call site that does not exit falls through to a
    second verdict, and a consumer reading the FIRST marker then reads the
    wrong one (Nit Store, found during #1147; issue #1258). The terminality
    test pins the script's text; this pins every exercised run's OUTPUT.
    """
    markers = [ln for ln in (proc.stdout or "").splitlines() if ln.startswith("FLOW_FINISH_GATE: ")]
    assert len(markers) <= 1, f"more than one verdict marker: {markers}"


def _run(
    tmp_path: Path,
    *args: str,
    cpp_dir: str | None = None,
    uv_exit: int | None = 0,
    make_exit: int | None = None,
    cwd: Path | None = None,
    uv_stdout: str = "",
    inject_gates: bool = True,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the helper with stubbed uv/make; returns (proc, stub bin dir)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    if uv_exit is not None:
        if uv_stdout and inject_gates:
            uv_stdout = _with_gates(uv_stdout)
        _make_stub(bindir, "uv", uv_exit, stdout=uv_stdout)
    if make_exit is not None:
        _make_stub(bindir, "make", make_exit)
    env = os.environ.copy()
    for key in ("CPP_KYLE_COORDINATION_ADMISSION", "CPP_KYLE_FULL_SUITE_ACTIVE", "CPP_KYLE_LOCK_BIN",
                "CPP_FLOW_FINISH_GATE_STATUS_FILE"):
        env.pop(key, None)
    env.pop("CPP_COORDINATION_ADMISSION_FILE", None)
    extras = dict(extra_env or {})
    signal = extras.pop("CPP_KYLE_COORDINATION_ADMISSION", None)
    flag = tmp_path / "coordination-flag"
    if signal is not None:
        flag.write_text("on\n" if signal == "1" else signal)
    env["CPP_COORDINATION_ADMISSION_FILE"] = str(flag)
    env.update(extras)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    if cpp_dir is not None:
        env["FLOW_GATE_CPP_DIR"] = cpp_dir
    proc = subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd or tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _assert_single_marker(proc)
    return proc, bindir


# A TRANSCRIPT of the `gates` array a post-#1147 runner emits, not a second
# declaration of it. The shell reads which step ids are quality gates out of
# the runner JSON (issue #1147); a synthetic payload without the field is not
# a runner payload, and the gate now fails closed on one - so every fixture
# below that is about something ELSE has to carry it, or it would silently
# become a test of the fail-closed branch.
#
# Written literally, and deliberately NOT derived from lib.cicd.steps: a
# fixture that imports the set under discussion would make the shell-side
# assertions circular. What PRODUCTION emits is pinned separately, against the
# runner itself, by test_runner_json_carries_the_derived_gate_set.
_FIXTURE_GATES = ("lint", "test", "typecheck", "security_scan", "verify")

# The smallest thing a runner actually prints. A `uv` stub that exits 0 and
# prints NOTHING is not a runner that succeeded - it is a runner whose
# output could not be read, and the gate fails closed on that by design.
_MINIMAL_RUNNER_JSON = '{\n  "success": true\n}'


def _with_gates(payload: str) -> str:
    """Make a synthetic payload a COHERENT runner payload, not just a partial one.

    Three fields are injected together because the gate reads them together: the
    `gates` array (which ids are quality gates), `dropped_gates` (whether the
    manifest left a declared gate out of the plan, #1155 - injected as `[]`,
    reconciled and clean) and, when the payload has no per-step record of its
    own, a `step_details` entry so every declared gate is ACCOUNTED FOR - it
    ran, or it is in `skipped`. A real runner always emits
    both; a fixture declaring five gates and recording none of them is not a
    runner payload, and since #1147 the gate correctly warns about it.

    So the declared set is derived from what the payload already accounts for
    rather than stated: gates the fixture reports skipped, plus gates it records
    as run. A payload that accounts for no gate at all gets the minimal coherent
    pair - one gate, declared and run - which keeps fixtures whose subject is
    something else (reruns, timeouts, carried results) saying what they always
    said.

    Inserted after the opening brace so it survives payloads ending in a nested
    object or array. A payload that already names its own gate set is returned
    untouched: those are the tests whose subject IS the field, and they pass
    inject_gates=False to reach this function not at all.
    """
    if '"gates"' in payload:
        return payload

    accounted = set(re.findall(r'"id": "([a-z_]+)"', payload))
    for block in re.findall(r'"skipped": \[(.*?)\]', payload, re.S):
        accounted.update(re.findall(r'"([a-z_]+)"', block))
    declared = [g for g in _FIXTURE_GATES if g in accounted]

    add_details = ""
    if not declared:
        declared = ["lint"]
        if '"step_details"' not in payload:
            add_details = (
                '\n  "step_details": [\n    {\n      "id": "lint",\n'
                '      "status": "success"\n    }\n  ],'
            )

    gates = ",\n".join(f'    "{g}"' for g in declared)
    # `dropped_gates` only when the payload does not state its own: a fixture
    # whose subject IS reconciliation builds it explicitly and never comes here.
    dropped = "" if '"dropped_gates"' in payload else '\n  "dropped_gates": [],'
    head, sep, tail = payload.partition("{")
    assert sep, f"not a JSON object payload: {payload!r}"
    return f'{head}{{\n  "gates": [\n{gates}\n  ],{dropped}{add_details}{tail}'


def _fake_cpp(tmp_path: Path) -> Path:
    cpp = tmp_path / "cpp"
    cpp.mkdir()
    (cpp / "CLAUDE.md").write_text("# fake\n")
    return cpp


_UNKNOWN_WARNING = (
    "test: exited 0 but NO test summary could be parsed from stdout or stderr "
    "- this gate's result is UNKNOWN, not clean"
)
_NO_TESTS_WARNING = (
    "test: exited 0 but executed NO tests (0 passed, 66 skipped) - this gate "
    "proved nothing about the change (issue #621)"
)

# Claims the gate's own QUALIFIED line must never make on its own authority.
# Asserted as a FORBIDDEN SET rather than by pinning the sentence: a reword is
# free, reintroducing the false claim is not (issue #939).
_UNESTABLISHED_CLAIMS = (
    "without executing any tests",
    "executed no tests",
    "no tests ran",
)


def _qualified_line(output: str) -> str:
    """The gate's OWN warning line, not the runner JSON it tee'd through.

    Scoping matters: the runner's warnings are echoed in the tee'd JSON, and a
    #621 warning legitimately contains "executed NO tests". Asserting over the
    whole output would read the runner's honest sentence as the gate's
    unestablished one and fail for the wrong reason.
    """
    return next(
        line
        for line in output.splitlines()
        if "the gate passed but the runner QUALIFIED it" in line
    )


def _runner_json(warning: str) -> str:
    return (
        '{\n  "success": true,\n  "plan": "finish",\n'
        '  "warnings": [\n    "' + warning + '"\n  ]\n}\n'
    )


@requires_bash
@requires_git
def test_qualified_gate_does_not_assert_a_cause_it_did_not_establish(
    tmp_path: Path,
) -> None:
    """The gate must not convert ANY warning into "no tests executed" (issue #939).

    `QUALIFIED` is set by the mere presence of a "warnings" key, and that
    collection carries three findings of which only #621 means no tests ran.
    For unparseable output the suite may have executed thousands: failing to
    RECOGNIZE a summary establishes nothing about what ran.

    THE PROPERTY, NOT THE PROSE. This asserts a forbidden set rather than the
    replacement wording, so a later reword stays green and a reintroduced false
    claim - or a FOURTH warning kind flattened into the #621 sentence - goes
    red. The reason this went unnoticed for the whole life of #838, which had
    already falsified the old sentence, is that no test asserted anything about
    it at all.
    """
    cpp = _fake_cpp(tmp_path)
    proc, _ = _run(
        tmp_path,
        cpp_dir=str(cpp),
        uv_exit=0,
        uv_stdout=_runner_json(_UNKNOWN_WARNING),
    )

    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn" in proc.stdout

    line = _qualified_line(proc.stdout)
    for claim in _UNESTABLISHED_CLAIMS:
        assert claim not in line, (
            f"the gate asserted {claim!r} from a warning that says the result "
            "is UNKNOWN - it did not establish that"
        )


@requires_bash
@requires_git
def test_the_qualified_line_still_fires_for_a_real_no_tests_warning(
    tmp_path: Path,
) -> None:
    """The negative half: the guard above must not be satisfied by silence.

    A gate that stopped emitting the QUALIFIED line entirely would pass the
    forbidden-claim assertion perfectly while losing the warning that matters.
    Both warning kinds must still reach `warn`, so the property under test is
    "does not overclaim", never "says less".
    """
    cpp = _fake_cpp(tmp_path)
    proc, _ = _run(
        tmp_path,
        cpp_dir=str(cpp),
        uv_exit=0,
        uv_stdout=_runner_json(_NO_TESTS_WARNING),
    )

    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    # The line is emitted; the CAUSE is carried by the runner's own warning,
    # which is tee'd through and does say it executed no tests.
    assert _qualified_line(proc.stdout)
    assert "executed NO tests" in proc.stdout


# --- Runner path -------------------------------------------------------------


@requires_bash
@requires_git
def test_runner_ok(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    proc, bindir = _run(
        tmp_path, cpp_dir=str(cpp), uv_exit=0, uv_stdout=_MINIMAL_RUNNER_JSON
    )
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    argv = (bindir / "uv.log").read_text()
    assert f"run --python 3.11 --no-python-downloads --project {cpp} python -m lib.cicd run --plan finish" in argv


@requires_bash
@requires_git
def test_runner_fail(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    proc, _ = _run(tmp_path, cpp_dir=str(cpp), uv_exit=1)
    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout


@requires_bash
@requires_git
def test_plan_passthrough(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    proc, bindir = _run(
        tmp_path,
        "--plan",
        "check",
        cpp_dir=str(cpp),
        uv_exit=0,
        uv_stdout=_MINIMAL_RUNNER_JSON,
    )
    assert proc.returncode == 0
    assert "--plan check" in (bindir / "uv.log").read_text()


# --- Makefile fallback -------------------------------------------------------


@requires_bash
@requires_git
def test_fallback_all_gate_targets_is_ok(tmp_path: Path) -> None:
    """Every gate the finish plan declares has a target here, `verify` included
    (issue #1147) - so the fallback runs all four and reports a bare `ok`."""
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\ntest:\n\ttrue\ntypecheck:\n\ttrue\nverify:\n\ttrue\n"
    )
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "Makefile fallback" in proc.stdout
    argv = (bindir / "make.log").read_text().splitlines()
    assert argv == ["lint", "test", "typecheck", "verify"]


@requires_bash
@requires_git
def test_fallback_missing_verify_target_reports_warn_named(tmp_path: Path) -> None:
    """The red case for the fallback half of #1147.

    A repo with lint/test/typecheck but no `verify:` target: three gates ran,
    the fourth could not, and #628 says a gate that did not run is never a bare
    `ok`. Before this issue the fallback did not know `verify` was a gate at
    all and this fixture reported `ok` - a green over a gate nobody ran.

    This is the change with the widest blast radius in #1147: every repository
    with no `verify` target now ends the fallback lane at `warn`, exactly as
    one with no typecheck route already did.
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\ntest:\n\ttrue\ntypecheck:\n\ttrue\n"
    )
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (skipped gates: verify)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    # The three that CAN run still ran - this is a reporting change.
    argv = (bindir / "make.log").read_text().splitlines()
    assert argv == ["lint", "test", "typecheck"]


@requires_bash
@requires_git
def test_fallback_missing_gate_reports_warn_named(tmp_path: Path) -> None:
    """A repo with lint+test targets but no typecheck target and no configured
    mypy: the gate did not run, so the marker is `warn (skipped gates: ...)` and
    names it - never a bare `ok` (#628)."""
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\ntest:\n\ttrue\n")
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    assert "typecheck" in proc.stdout
    # lint + test still actually ran.
    argv = (bindir / "make.log").read_text().splitlines()
    assert argv == ["lint", "test"]


@requires_bash
@requires_git
def test_fallback_uses_uv_when_no_makefile_but_pyproject(tmp_path: Path) -> None:
    """No Makefile at all, but pyproject configures ruff/pytest/mypy and uv is
    available: the fallback runs each gate via `uv run --extra dev <tool>`
    instead of skipping (#628)."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\n[tool.pytest.ini_options]\n[tool.mypy]\n"
    )
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=0)
    argv = (bindir / "uv.log").read_text()
    assert "run --extra dev ruff check ." in argv
    assert "run --extra dev pytest" in argv
    assert "run --extra dev mypy ." in argv
    # `verify` is a Makefile aggregate with no `uv run` equivalent, so with no
    # Makefile at all it cannot run by either route and is named as skipped
    # (#1147). The three tool-backed gates above still ran, which is what this
    # test is about; `uv run --extra dev` with an EMPTY command must never be
    # one of the invocations.
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (skipped gates: verify)" in proc.stdout
    assert "run --extra dev\n" not in argv


@requires_bash
@requires_git
def test_fallback_fail(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\ntest:\n\ttrue\n")
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=1)
    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout


@requires_bash
@requires_git
def test_skipped_when_no_runner_and_no_makefile(tmp_path: Path) -> None:
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None)
    assert proc.returncode == 4
    assert "FLOW_FINISH_GATE: skipped" in proc.stdout
    assert "SKIPPED" in proc.stdout


# --- --check-summary (advisory) ---------------------------------------------


@requires_bash
@requires_git
def test_check_summary_ok(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\n")
    proc, bindir = _run(tmp_path, "--check-summary", cpp_dir=str(cpp), uv_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "lib.cicd check --summary" in (bindir / "uv.log").read_text()


@requires_bash
@requires_git
def test_check_summary_warn_is_exit_three(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\n")
    proc, _ = _run(tmp_path, "--check-summary", cpp_dir=str(cpp), uv_exit=3)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn" in proc.stdout


@requires_bash
@requires_git
def test_check_summary_skipped_without_runner(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\n")
    proc, _ = _run(tmp_path, "--check-summary", cpp_dir="", uv_exit=None)
    assert proc.returncode == 4
    assert "FLOW_FINISH_GATE: skipped" in proc.stdout


@requires_bash
@requires_git
def test_check_summary_skipped_without_makefile(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    proc, _ = _run(tmp_path, "--check-summary", cpp_dir=str(cpp), uv_exit=0)
    assert proc.returncode == 4
    assert "FLOW_FINISH_GATE: skipped" in proc.stdout


@requires_bash
@requires_git
def test_unknown_argument_is_usage_error(tmp_path: Path) -> None:
    proc, _ = _run(tmp_path, "--bogus", cpp_dir="")
    assert proc.returncode == 2


# --- Wiring (read-only, always run) ------------------------------------------


def test_helper_is_in_install_family() -> None:
    text = (ROOT / "scripts" / "flow-helpers-install.sh").read_text()
    assert "flow-finish-gate.sh" in text


def test_helper_is_bundled_in_codex_skill() -> None:
    bundled = ROOT / "codex" / "skills" / "flow-finish" / "scripts" / "flow-finish-gate.sh"
    assert bundled.read_text() == (ROOT / "scripts" / "flow-finish-gate.sh").read_text()


def test_helper_is_allowlisted() -> None:
    text = (ROOT / "templates" / "claude-settings-permissions.json").read_text()
    assert "Bash(~/.claude/scripts/flow-finish-gate.sh:*)" in text


@pytest.mark.parametrize(
    "doc", ["auto.md", "finish.md", "merge.md", "check.md"]
)
def test_command_docs_invoke_the_helper_not_inline_bash(doc: str) -> None:
    text = (ROOT / ".claude" / "commands" / "flow" / doc).read_text()
    assert "~/.claude/scripts/flow-finish-gate.sh" in text
    # The un-allowlistable inline gate shape must not ride these docs anymore.
    # (auto.md Step 9 deploy VERIFICATION legitimately keeps `lib.cicd verify`
    # lines - only the quality-GATE `run --plan` shape is extracted, #613.)
    assert "python -m lib.cicd run --plan" not in text


# --- #621: a green gate whose test step executed nothing ---------------------


def _uv_stub_printing(bindir: Path, stdout_payload: str, exit_code: int = 0) -> None:
    """A `uv` shim that prints a canned runner JSON payload on stdout."""
    stub = bindir / "uv"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{bindir / "uv.log"}"\n'
        f'echo "CPP_GATE_RERUN_FAILED=${{CPP_GATE_RERUN_FAILED-UNSET}}" '
        f'>> "{bindir / "uv.env.log"}"\n'
        f"cat <<'JSON'\n{stdout_payload}\nJSON\n"
        f"exit {exit_code}\n"
    )
    stub.chmod(0o755)


def _run_with_uv_stub(
    tmp_path: Path,
    cpp: Path,
    payload: str,
    exit_code: int = 0,
    flow_gate_rerun: str | None = None,
    inject_gates: bool = True,
    tmpdir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    _uv_stub_printing(
        bindir, _with_gates(payload) if inject_gates else payload, exit_code
    )
    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FLOW_GATE_CPP_DIR"] = str(cpp)
    if flow_gate_rerun is not None:
        env["FLOW_GATE_RERUN"] = flow_gate_rerun
    if tmpdir is not None:
        env["TMPDIR"] = str(tmpdir)
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _assert_single_marker(proc)
    return proc


@requires_bash
@requires_git
def test_qualified_run_reports_warn_not_ok(tmp_path: Path) -> None:
    """The runner qualifies an all-skipped test step; this helper is the layer
    the flow commands read, so flattening that back to a bare `ok` would re-hide
    the #621 false green one level up. Exit status is 3 (issue #1027) - a
    signal, not a failure, but distinct from a clean `ok`."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 3,\n'
        '  "tests": {"test": {"passed": 0, "skipped": 66, "executed": 0}},\n'
        # Matches what the runner ACTUALLY emits (issue #939): the "(issue
        # #621)" tag now rides on the specific warning rather than on the
        # gate's generic QUALIFIED line, which no longer names a cause because
        # three different findings reach it. The assertion below is unchanged -
        # the reader must still be able to see this is the #621 case - only the
        # fixture is brought back in line with its real producer.
        '  "warnings": ["test: exited 0 but executed NO tests (0 passed, 66 '
        'skipped) - this gate proved nothing about the change (issue #621)"]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    assert "issue #621" in proc.stdout
    # The runner's own JSON still reaches the caller (tee, not swallow).
    assert '"warnings"' in proc.stdout


@requires_bash
@requires_git
def test_unqualified_run_still_reports_ok(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = '{\n  "success": true,\n  "steps_completed": 3,\n  "steps_total": 3\n}'
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "warn" not in proc.stdout


@requires_bash
@requires_git
def test_failed_run_is_fail_even_with_warnings(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = '{\n  "success": false,\n  "warnings": ["test: exited 0 but executed NO tests"]\n}'
    proc = _run_with_uv_stub(tmp_path, cpp, payload, exit_code=1)
    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout


# --- #769: one targeted re-run of pytest's failed ids -----------------------


@requires_bash
@requires_git
def test_runner_rerun_passed_reports_warn_and_ids(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = """{
  "success": true,
  "steps_completed": 3,
  "steps_total": 3,
  "reruns": [
    {
      "step": "test",
      "ids": [
        "tests/a.py::t1"
      ],
      "outcome": "passed-in-isolation",
      "first_attempt": null,
      "rerun": null
    }
  ]
}"""
    proc = _run_with_uv_stub(tmp_path, cpp, payload)

    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    assert "RERUN_PASSED: tests/a.py::t1" in proc.stdout
    assert "issue #769" in proc.stdout


@requires_bash
# `new-failures` and `failed-unattributed` are #915's two new verdicts. The gate
# clears ONLY on an exact `passed-in-isolation` match, so neither can produce a
# RERUN_PASSED line - but that is a property of the awk pattern rather than of
# these names, and a future edit could widen it. Pinned here so it cannot.
@pytest.mark.parametrize(
    "rerun_outcome",
    ["failed", "inconclusive", "new-failures", "failed-unattributed"],
)
@requires_git
def test_uncleared_rerun_has_no_rerun_passed_line(
    tmp_path: Path, rerun_outcome: str
) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = """{
  "success": false,
  "reruns": [
    {
      "step": "test",
      "ids": [
        "tests/a.py::t1"
      ],
      "outcome": "%s",
      "first_attempt": null,
      "rerun": null
    }
  ]
}""" % rerun_outcome
    proc = _run_with_uv_stub(tmp_path, cpp, payload, exit_code=1)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout
    assert "RERUN_PASSED:" not in proc.stdout


@requires_bash
@requires_git
def test_gate_enables_runner_rerun_by_default(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = '{\n  "success": true\n}'
    proc = _run_with_uv_stub(tmp_path, cpp, payload)

    assert proc.returncode == 0
    assert (tmp_path / "bin" / "uv.env.log").read_text().strip() == (
        "CPP_GATE_RERUN_FAILED=1"
    )


@requires_bash
@requires_git
def test_gate_can_disable_runner_rerun(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = '{\n  "success": true\n}'
    proc = _run_with_uv_stub(tmp_path, cpp, payload, flow_gate_rerun="0")

    assert proc.returncode == 0
    assert (tmp_path / "bin" / "uv.env.log").read_text().strip() == (
        "CPP_GATE_RERUN_FAILED=0"
    )


@requires_bash
@requires_git
def test_disabled_rerun_overrides_an_inherited_opt_in(tmp_path: Path) -> None:
    """FLOW_GATE_RERUN=0 must OVERRIDE an inherited CPP_GATE_RERUN_FAILED=1, not
    merely decline to set it. A nested gate is the normal case - CPP's own suite
    runs under an outer gate that already exported the opt-in - so an opt-out
    that only omits the assignment disables nothing where it matters most."""
    cpp = _fake_cpp(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    _uv_stub_printing(bindir, _with_gates(_MINIMAL_RUNNER_JSON), 0)
    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FLOW_GATE_CPP_DIR"] = str(cpp)
    env["FLOW_GATE_RERUN"] = "0"
    env["CPP_GATE_RERUN_FAILED"] = "1"
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert proc.returncode == 0
    assert (bindir / "uv.env.log").read_text().strip() == "CPP_GATE_RERUN_FAILED=0"


@requires_bash
@requires_git
def test_runner_rerun_reports_multiple_ids(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = """{
  "success": true,
  "reruns": [
    {
      "step": "test",
      "ids": [
        "tests/a.py::t1",
        "tests/b.py::TestB::t2[param]"
      ],
      "outcome": "passed-in-isolation",
      "first_attempt": null,
      "rerun": null
    }
  ]
}"""
    proc = _run_with_uv_stub(tmp_path, cpp, payload)

    assert proc.returncode == 3
    assert (
        "RERUN_PASSED: tests/a.py::t1 tests/b.py::TestB::t2[param]"
        in proc.stdout
    )


def _fallback_make_stub(
    bindir: Path, rerun_passes: bool, fail_target: str | None = None
) -> None:
    stub = bindir / "make"
    second_exit = (
        "printf 'PYTEST_ADDOPTS=%s\\n' \"${PYTEST_ADDOPTS:-}\"; "
        "printf '=== 1 passed in 0.01s ===\\n'; exit 0"
        if rerun_passes
        else (
            "printf '=== 1 failed in 0.01s ===\\n'; "
            "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; exit 1"
        )
    )
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f"if [[ \"$1\" == \"{fail_target}\" ]]; then exit 1; fi\n"
        "if [[ \"$1\" != \"test\" ]]; then exit 0; fi\n"
        f"printf x >> \"{bindir / 'test-attempts'}\"\n"
        f"if [[ -f \"{bindir / 'test-marker'}\" ]]; then {second_exit}; fi\n"
        f": > \"{bindir / 'test-marker'}\"\n"
        "printf '=== 1 failed in 0.01s ===\\n'\n"
        "printf 'FAILED tests/a.py::t1 - AssertionError\\n'\n"
        "exit 1\n"
    )
    stub.chmod(0o755)


@requires_bash
@requires_git
def test_fallback_rerun_passes_and_warns(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text(
        "lint:\n\ntest:\n\ntypecheck:\n\nverify:\n"
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fallback_make_stub(bindir, rerun_passes=True)

    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, cwd=tmp_path)

    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "RERUN_PASSED: tests/a.py::t1" in proc.stdout
    assert "issue #769" in proc.stdout
    assert (bindir / "test-attempts").read_text() == "xx"
    assert "--last-failed --last-failed-no-failures none" in proc.stdout


@requires_bash
@requires_git
def test_fallback_rerun_failure_stays_failed(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text(
        "lint:\n\ntest:\n\ntypecheck:\n\nverify:\n"
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fallback_make_stub(bindir, rerun_passes=False)

    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, cwd=tmp_path)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout
    assert "RERUN_PASSED:" not in proc.stdout
    assert (bindir / "test-attempts").read_text() == "xx"


@requires_bash
@requires_git
def test_skipped_gates_win_but_rerun_ids_are_still_printed(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = """{
  "success": true,
  "reruns": [
    {
      "step": "test",
      "ids": [
        "tests/a.py::t1"
      ],
      "outcome": "passed-in-isolation",
      "first_attempt": null,
      "rerun": null
    }
  ],
  "skipped": [
    "typecheck"
  ]
}"""
    proc = _run_with_uv_stub(tmp_path, cpp, payload)

    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (skipped gates: typecheck)" in proc.stdout
    assert "RERUN_PASSED: tests/a.py::t1" in proc.stdout


@requires_bash
@requires_git
def test_fallback_prints_rerun_ids_even_when_a_later_gate_fails(
    tmp_path: Path,
) -> None:
    """The runner path prints RERUN_PASSED before verdict precedence is applied;
    the fallback must too. Emitting it only after the `fail` branch dropped the
    ids on exactly the red-and-flaky run that is hardest to read - a test cleared
    by its re-run, then a genuinely failing typecheck - which is the fallback
    silently diverging from the runner, the #617/#621/#628 trap."""
    (tmp_path / "Makefile").write_text(
        "lint:\n\ntest:\n\ntypecheck:\n\nverify:\n"
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fallback_make_stub(bindir, rerun_passes=True, fail_target="typecheck")

    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, cwd=tmp_path)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout
    # The genuine failure still wins the verdict, but the flake is not erased.
    assert "RERUN_PASSED: tests/a.py::t1" in proc.stdout


@requires_bash
@requires_git
def test_fallback_rerun_appends_to_host_pytest_addopts(tmp_path: Path) -> None:
    """The runner's rerun_env APPENDS to any host PYTEST_ADDOPTS; the fallback
    must not replace it, or the two attempts are not the same invocation and the
    caller's own pytest options silently vanish on the re-run only."""
    (tmp_path / "Makefile").write_text(
        "lint:\n\ntest:\n\ntypecheck:\n\nverify:\n"
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fallback_make_stub(bindir, rerun_passes=True)

    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FLOW_GATE_CPP_DIR"] = ""
    env["PYTEST_ADDOPTS"] = "-p no:randomly"
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert proc.returncode == 3
    assert "PYTEST_ADDOPTS=-p no:randomly --last-failed" in proc.stdout


def test_rerun_id_cap_matches_the_runner() -> None:
    """The shell fallback and the Python runner each carry their own copy of the
    #769 cap. They gate the same decision, so a drift between them would make the
    two local-gate paths disagree about what counts as a flake."""
    from lib.cicd.runner import MAX_RERUN_IDS

    shell = SCRIPT.read_text()
    assert f"MAX_RERUN_IDS={MAX_RERUN_IDS}\n" in shell


# --- #628: a green run whose quality gates were SKIPPED ----------------------


@requires_bash
@requires_git
def test_runner_skipped_gates_report_warn_named(tmp_path: Path) -> None:
    """The runner emits a "skipped": [...] array for skip_if-skipped gates. This
    helper is the layer the flow commands read, so it must report `warn` and NAME
    the skipped gates rather than flatten the run to a bare `ok` - the exact
    false green of #628. Exit is 3 (issue #1027) - it is a signal."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 4,\n  "steps_total": 4,\n'
        '  "skipped": [\n    "lint",\n    "test",\n    "typecheck"\n  ]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    for gate in ("lint", "test", "typecheck"):
        assert gate in proc.stdout
    assert "issue #628" in proc.stdout


@requires_bash
@requires_git
def test_runner_skipped_non_gate_still_ok(tmp_path: Path) -> None:
    """A skipped NON-gate step is a legitimate skip - the marker stays `ok`.

    THE EXEMPLAR CHANGED HERE, AND WHY IS THE POINT (#628 -> #890). This test
    used `security_scan` as its non-gate, on #628's categorical reading that a
    gate is one of the three #617 quality gates. #890 reversed that: the question
    is what a SKIP MEANS, and `security_scan` skips exactly when the scanner is
    not installed - so it is a gate, and a skipped one must warn.

    `stale_commit_check` is the non-gate now. Its skip_if is "not on main, or
    offline", so the skip reports a situation rather than an unverified
    dimension. The assertion this test makes - that a non-gate skip does not
    manufacture a warning - is unchanged and still worth having: an over-correction
    that warned on every skip would be the everyday-blocker failure, and is what
    the widened filter in flow-finish-gate.sh could have caused.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 4,\n  "steps_total": 4,\n'
        '  "skipped": [\n    "stale_commit_check"\n  ]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "warn" not in proc.stdout


def test_runner_json_carries_the_derived_gate_set() -> None:
    """The producer half of #1147: the runner SAYS which ids are quality gates.

    This replaces test_gate_filter_matches_GATE_STEP_IDS, whose subject - a
    `grep -oE` alternation duplicating GATE_STEP_IDS into the shell - no longer
    exists. That test kept two lists equal; the fix removed the second list, so
    what needs pinning now is the channel that carries the one remaining
    declaration across the language boundary.

    Emitted UNCONDITIONALLY, which is the load-bearing half. A conditional
    emit would make "this plan has no gates" and "this runner is too old to
    say" the same bytes, and the shell fails closed on absence - so a runner
    that dropped the field on an empty set would hard-fail every such run.
    `deploy` is exactly that plan, so this is not a theoretical shape.

    The set is PLAN-SCOPED, not the global GATE_STEP_IDS - see
    test_the_emitted_gate_set_never_exceeds_the_plan_that_ran for why
    publishing the union broke every non-finish plan.
    """
    from lib.cicd.runner import RunResult
    from lib.cicd.steps import get_plan_steps, plan_gate_ids

    steps = get_plan_steps("finish", project_root=str(ROOT))
    d = RunResult(
        success=True,
        run_id="r",
        plan_name="finish",
        gates=plan_gate_ids("finish", steps),
    ).to_dict()
    assert "gates" in d, (
        "the runner JSON carries no 'gates' field - scripts/flow-finish-gate.sh "
        "reads which steps are quality gates out of it and fails closed without "
        "it, so this is a hard failure of every gate run (issue #1147)"
    )
    assert d["gates"] == sorted(plan_gate_ids("finish", steps))
    assert d["gates"], "an empty gate set means the derivation found nothing"

    # The field survives a result carrying NOTHING else optional. Every
    # neighbour in to_dict() is conditional on its own truthiness, and this one
    # sitting among them is exactly where a later edit would make it match.
    assert "skipped" not in d and "warnings" not in d


@requires_bash
@requires_git
def test_the_shell_reads_the_gate_set_from_the_json_not_a_list(
    tmp_path: Path,
) -> None:
    """The consumer half, with an id NO hardcoded list could contain.

    `quux_check` is not a step in any plan and never was. A JSON declaring it a
    gate and reporting it skipped therefore distinguishes the two possible
    shells: one that filters `skipped` against the JSON's own set names it, and
    one filtering against an internal list - the pre-#1147 alternation - drops
    it and reports a bare `ok`.

    Run against the pre-fix script this fails, which is the point: that script
    prints `FLOW_FINISH_GATE: ok` for a run with an unexamined gate.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 2,\n  "steps_total": 2,\n'
        '  "gates": [\n    "lint",\n    "quux_check"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "skipped": [\n    "quux_check"\n  ],\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (skipped gates: quux_check)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout


@requires_bash
@requires_git
def test_a_non_gate_skip_is_still_ok_when_the_json_says_so(
    tmp_path: Path,
) -> None:
    """The other side of the same read, so "name everything skipped" does not
    satisfy the test above.

    Same payload shape, but the skipped id is absent from the declared gate
    set. A shell that simply reported every skipped step would warn here, and
    that over-correction is what makes the #628 warning noise nobody reads.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 2,\n  "steps_total": 2,\n'
        '  "gates": [\n    "lint",\n    "quux_check"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "skipped": [\n    "stale_commit_check"\n  ],\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    },\n'
        '    {\n      "id": "quux_check",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout


def test_the_resolved_finish_plan_runs_every_gate_the_builtin_plan_declares() -> None:
    """The manifest WINS over BUILTIN_PLANS, so a gate added to the built-in
    plan and not listed in `.claude/cicd_tasks.yml` is dead config (#617, #1147).

    This is the pin for a trap the repository has now fallen into twice. #617
    hit it with `typecheck` and wrote the warning as a comment INSIDE the
    manifest - where a reader editing lib/cicd/steps.py never sees it. #1147 hit
    it with `verify` anyway: the built-in finish plan grew a fifth gate, the
    manifest still listed four, and the runner declared five gates in its JSON
    while executing four and reporting `ok`.

    Measured, not reasoned about. The gate ran in 163.68s - the same figure as
    before a 229.8s step was supposedly added - and that is what gave it away.

    Asserted against the RESOLVED plan rather than by reading the YAML, so it
    holds however the manifest expresses the step.
    """
    from lib.cicd.steps import BUILTIN_PLANS, get_plan_steps

    declared = {s.id for s in BUILTIN_PLANS["finish"] if s.gate}
    resolved = {s.id for s in get_plan_steps("finish", project_root=str(ROOT))}
    missing = sorted(declared - resolved)
    assert not missing, (
        f"the finish plan this repository actually runs omits declared gate(s) "
        f"{missing}. `.claude/cicd_tasks.yml` takes precedence over "
        f"BUILTIN_PLANS, so a gate defined in steps.py and not listed under "
        f"plans.finish.steps is never executed - and GATE_STEP_IDS still "
        f"declares it, so the JSON claims a gate the run never had (#617, #1147)"
    )


def test_the_emitted_gate_set_never_exceeds_the_plan_that_ran() -> None:
    """A plan is only answerable for ITS OWN gates (counter-model review, #1147).

    `GATE_STEP_IDS` is the union across every plan. Publishing that to a
    consumer which requires every member to be accounted for turns two
    perfectly good runs into failures: `--plan check` executes lint/test/
    typecheck and has no security_scan or verify in it, and `--plan deploy`
    shares none of the five. Measured before the fix: check reported
    `fail (declared but never ran: security_scan verify)` and deploy reported
    all five.

    The invariant is containment, asserted for EVERY built-in plan rather than
    for the one that broke - the defect was not specific to `check`, it was
    that the published set had nothing to do with the plan.
    """
    from lib.cicd.steps import BUILTIN_PLANS, get_plan_steps, plan_gate_ids

    for plan in sorted(BUILTIN_PLANS):
        resolved = [d.id for d in get_plan_steps(plan, project_root=str(ROOT))]
        gates = plan_gate_ids(plan, get_plan_steps(plan, project_root=str(ROOT)))
        extra = sorted(set(gates) - set(resolved))
        assert not extra, (
            f"the '{plan}' plan publishes gate(s) {extra} that its resolved "
            f"steps {resolved} do not contain. flow-finish-gate.sh requires "
            f"every published gate to appear in step_details or skipped, so "
            f"this makes a successful run report `fail (declared but never "
            f"ran: ...)` (#1147)"
        )


def test_the_finish_plan_still_publishes_its_gates() -> None:
    """The guard rail for the containment test above.

    Containment is satisfiable by publishing nothing at all, which would make
    the accountability check inert and take #1147's own guard with it. The
    finish plan - the one the gate runs by default - must still name its gates.
    """
    from lib.cicd.steps import get_plan_steps, plan_gate_ids

    steps = get_plan_steps("finish", project_root=str(ROOT))
    gates = set(plan_gate_ids("finish", steps))
    assert {"lint", "test", "typecheck", "verify"} <= gates, (
        f"the finish plan publishes {sorted(gates)}, which is missing one of "
        f"the gates it runs - the accountability check cannot see a gate that "
        f"is not published (#1147)"
    )


def test_a_generated_manifest_runs_the_verify_gate() -> None:
    """A manifest CPP generates must run the gate CPP's own plan declares.

    Counter-model review finding: `BUILTIN_PLANS` and this repository's
    checked-in manifest both gained `verify`, while `generate_manifest` still
    produced a four-step finish plan and skipped `verify` by name in its
    extra-targets loop. Every project scaffolded by CPP would therefore have a
    finish gate that never ran the project's own verification - #1147's defect,
    shipped to every new repository instead of this one.
    """
    from lib.cicd.manifest import generate_manifest

    manifest = generate_manifest(str(ROOT))
    assert "verify" in manifest.steps, "generated manifest defines no verify step"
    assert "verify" in manifest.plans["finish"].steps, (
        "the generated finish plan does not REFERENCE verify. A step defined "
        "and never referenced is dead config - the #617/#1147 precedence trap"
    )
    # The budget matters: `make verify` measured 229.8s here and grows with the
    # suite, and the extra-targets loop's default is 600.
    assert manifest.steps["verify"].timeout >= 1800


@requires_bash
@requires_git
def test_an_empty_gate_set_is_not_an_unreadable_one(tmp_path: Path) -> None:
    """`"gates": []` is an ANSWER; an absent field is not (#1147).

    A plan can legitimately have no quality gate - `deploy` resolves to
    bootstrap/drift/deploy steps and publishes an empty set. The fail-closed
    branch therefore has to test the field's PRESENCE, not whether the parsed
    set came back empty; testing emptiness would fail every run of such a plan
    while claiming the runner was too old to report.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "plan": "deploy",\n'
        '  "steps_completed": 1,\n  "steps_total": 1,\n'
        '  "gates": [],\n'
        '  "dropped_gates": [],\n'
        '  "step_details": [\n'
        '    {\n      "id": "deploy",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "gate set unreadable" not in proc.stdout


@requires_bash
@requires_git
def test_an_aggregate_prerequisite_run_by_verify_is_not_called_unrun(
    tmp_path: Path,
) -> None:
    """Counter-model review, #1147: running an aggregate ran its prerequisites.

    `verify` and `check-all` name the same prerequisites. This lane runs
    `make verify`, which executes `extra-check`; the #808 detector excluded the
    target it ran but not that target's PREREQUISITES, so it went on to report
    `check-all`'s `extra-check` as unrun. Adding a second aggregate that names
    the same prerequisites changed the verdict without changing one thing about
    what was verified.
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\n"
        "test:\n\ttrue\n"
        "typecheck:\n\ttrue\n"
        "extra-check:\n\ttrue\n"
        "verify: lint test typecheck extra-check\n"
        "check-all: lint test typecheck extra-check\n"
    )
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "not run by fallback" not in proc.stdout


@requires_bash
@requires_git
def test_a_prerequisite_nothing_ran_is_still_reported(tmp_path: Path) -> None:
    """The guard rail: the expansion must not silence #808 generally.

    `check-all` names `lonely-check`, which no target this lane ran depends on.
    That is still an aggregate whose prerequisites went unexamined, and it must
    still warn - otherwise "cover prerequisites of what we ran" would have been
    implemented as "stop asking".
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\n"
        "test:\n\ttrue\n"
        "typecheck:\n\ttrue\n"
        "verify:\n\ttrue\n"
        "lonely-check:\n\ttrue\n"
        "check-all: lint test typecheck lonely-check\n"
    )
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (not run by fallback: lonely-check)" in proc.stdout


@requires_bash
@requires_git
def test_subsumption_is_reported_by_name(tmp_path: Path) -> None:
    """A gate absent from the executed list because an aggregate ran it must
    SAY so (issue #1152).

    `subsumed` is the one status in this vocabulary that means a gate RAN.
    Leaving it unreported would make a deduplicated run look exactly like the
    silent omissions #1147 and #1155 exist to refuse - three gates missing from
    the executed list with nothing saying why - and a reader would have to
    re-derive the Makefile prerequisite list to find out.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "plan": "finish",\n'
        '  "gates": [\n    "lint",\n    "verify"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "subsumed_gates": {\n    "lint": "verify"\n  },\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "subsumed"\n    },\n'
        '    {\n      "id": "verify",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 0
    assert "SUBSUMED: lint" in proc.stdout
    assert "make verify" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    # A subsumed gate RAN, so it must not be reported as skipped - #628's warn
    # would be false, and a false warn is how a true one stops being read.
    assert "skipped gates" not in proc.stdout


@requires_bash
@requires_git
def test_subsumption_refusal_is_reported(tmp_path: Path) -> None:
    """WHY nothing was subsumed, said rather than left to silence (issue #1192).

    The gate printed a SUBSUMED line when dedup happened and NOTHING when it
    was refused, so "your makefile is outside the grammar and every gate ran
    twice" and "there was nothing to deduplicate" were the same output - to the
    only reader who pays the difference.

    The refusal that motivated this is an `-include` of an optional env file:
    ordinary configuration, neither of the two hazards the grammar is written
    for, and refused all the same.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "plan": "finish",\n'
        '  "gates": [\n    "lint",\n    "verify"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "subsumed_gates": {},\n'
        '  "subsumption_refusals": [\n'
        '    "the makefile is outside the grammar subsumption requires '
        '(line 1: an include), so nothing is subsumed and every gate runs"\n'
        "  ],\n"
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    },\n'
        '    {\n      "id": "verify",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    # THE DIAGNOSTIC LINES, not raw stdout (counter-model review). The gate
    # TEES the runner JSON to stdout, so `"an include" in proc.stdout` is
    # satisfied by the echoed payload alone - it would pass with the diagnostic
    # printing WRONG REASON, or printing no reason at all. Select the lines the
    # gate itself emits and assert on those.
    reported = [
        line for line in proc.stdout.splitlines()
        if line.startswith("flow-finish-gate: SUBSUMPTION REFUSED:")
    ]
    assert proc.returncode == 0
    assert reported, proc.stdout
    assert any("an include" in line for line in reported), reported
    assert any("outside the grammar" in line for line in reported), reported
    assert "FLOW_FINISH_GATE: ok" in proc.stdout


@requires_bash
@requires_git
def test_the_refusal_survives_a_FAILING_run(tmp_path: Path) -> None:
    """The refusal is a fact about the DERIVATION, not about the verdict.

    The diagnostic sat inside the success branch, so a repository outside the
    grammar whose gates then failed learned nothing about why it had ALSO paid
    for every gate twice (counter-model review, issue #1192) - and that is the
    run where the duplicate cost hurts most, because the failure is about to be
    re-run.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": false,\n  "plan": "finish",\n'
        '  "gates": [\n    "lint",\n    "verify"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "subsumed_gates": {},\n'
        '  "subsumption_refusals": [\n'
        '    "the makefile is outside the grammar subsumption requires '
        '(line 1: an include), so nothing is subsumed and every gate runs"\n'
        "  ],\n"
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "failed"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, exit_code=1, inject_gates=False)

    reported = [
        line for line in proc.stdout.splitlines()
        if line.startswith("flow-finish-gate: SUBSUMPTION REFUSED:")
    ]
    assert proc.returncode != 0, "the run failed; the verdict must still say so"
    assert reported, proc.stdout
    assert any("an include" in line for line in reported), reported


@requires_bash
@requires_git
def test_no_refusal_prints_NOTHING(tmp_path: Path) -> None:
    """THE SILENCE HALF, and it is as load-bearing as the printed line.

    A gate that announced a refusal unconditionally would satisfy the test
    above while telling every ordinary run it had been refused - and a line
    that appears on every run is one nobody reads, which is the state this
    change exists to leave.

    Both no-refusal shapes are covered: `[]` (derived, nothing refused) and
    `null` (not derived at all, the resume-on-finished-run path). Neither is a
    refusal, so neither prints.
    """
    cpp = _fake_cpp(tmp_path)
    for refusals in ('  "subsumption_refusals": [],\n', '  "subsumption_refusals": null,\n'):
        payload = (
            '{\n  "success": true,\n  "plan": "finish",\n'
            '  "gates": [\n    "lint",\n    "verify"\n  ],\n'
            '  "dropped_gates": [],\n'
            '  "subsumed_gates": {},\n'
            + refusals
            + '  "step_details": [\n'
            '    {\n      "id": "lint",\n      "status": "success"\n    },\n'
            '    {\n      "id": "verify",\n      "status": "success"\n    }\n'
            "  ]\n}"
        )
        proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

        reported = [
            line for line in proc.stdout.splitlines()
            if line.startswith("flow-finish-gate: SUBSUMPTION REFUSED:")
        ]
        assert proc.returncode == 0, refusals
        assert reported == [], (refusals, reported)


@requires_bash
@requires_git
def test_a_not_run_record_cannot_coexist_with_a_pass(tmp_path: Path) -> None:
    """The shell-reachable half of #1152's standing question.

    `not-run` means a gate was deferred to an aggregate that FAILED, so make
    stopped before reaching it. A runner reporting overall success while
    carrying such a record has two disagreeing accounts of one run, and the
    reading that lets work through is the one saying quality gates never
    executed. The gate believes the per-step record.

    Run against the gate at 529d470 this reports `ok` and exits 0 - it has no
    notion of a not-run record, reads the top-level `success`, and stops. That
    is `controls/flow-finish-gate-subsumption`'s known-bad input.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "plan": "finish",\n'
        '  "gates": [\n    "lint",\n    "verify"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "subsumed_gates": {},\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "not-run"\n    },\n'
        '    {\n      "id": "verify",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail (recorded not-run: lint)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout


@requires_bash
@requires_git
def test_an_aggregate_failure_names_the_prerequisite(tmp_path: Path) -> None:
    """`verify` has 29 direct prerequisites in this repository, so `fail` alone
    asks a reader to search all of them (issue #1152).

    make names the one it stopped at. The gate carries that name rather than
    discarding it - and reports the aggregate alone when make said nothing
    matchable, because a WRONG prerequisite name sends the reader somewhere
    specific and innocent.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": false,\n  "plan": "finish",\n'
        '  "gates": [\n    "lint",\n    "verify"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "subsumed_gates": {},\n'
        '  "failed_step": "verify",\n'
        '  "failed_prerequisite": "lint",\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "not-run"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, exit_code=1, inject_gates=False)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail (at prerequisite lint)" in proc.stdout


@requires_bash
@requires_git
def test_the_fallback_lane_says_it_does_not_deduplicate(tmp_path: Path) -> None:
    """Stated, never silent (issue #1152).

    The fallback cannot import the Python Makefile reader the runner lane
    derives subsumption with, and a second reader here would be the
    duplicate-parser defect this repository keeps removing. So it runs every
    gate - correct, just slower - and a reader comparing the two lanes' timings
    is owed the reason rather than left to infer it.
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\ntest:\n\ttrue\ntypecheck:\n\ttrue\nverify:\n\ttrue\n"
    )
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)

    assert proc.returncode == 0
    assert "subsumption: not derived in the fallback lane; all gates run" in proc.stdout
    # and it really did run all four
    argv = (bindir / "make.log").read_text().splitlines()
    assert argv == ["lint", "test", "typecheck", "verify"]


@requires_bash
@requires_git
def test_a_manifest_that_drops_a_declared_gate_fails_by_name(
    tmp_path: Path,
) -> None:
    """#1155's subject at the layer that prints the verdict.

    `.claude/cicd_tasks.yml` wins over BUILTIN_PLANS, so a manifest can leave a
    declared gate out of a plan entirely. It then never runs AND is never
    recorded as skipped, so every other check here sees nothing: the skipped
    filter matches nothing, the accountability check is satisfied because the
    published gate set came from the resolved plan too. The marker reads `ok`.

    That is how #1147 shipped a green over four of five gates, and
    codex-power-pack is carrying the same defect for `typecheck` and `verify`
    today (cooneycw/codex-power-pack#290).

    FAIL, not warn, and the contrast is the reason: a gate that is PRESENT and
    skips reports #628's `warn (skipped gates: ...)` WITH its reason. A dropped
    gate has no reason because nothing recorded it at all. Dropping is silent;
    skipping is loud.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "plan": "finish",\n'
        '  "gates": [\n    "lint"\n  ],\n'
        '  "dropped_gates": [\n    "typecheck",\n    "verify"\n  ],\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 1
    assert (
        "FLOW_FINISH_GATE: fail (gate dropped from the plan: typecheck verify)"
        in proc.stdout
    )
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout


@requires_bash
@requires_git
def test_a_reconciled_plan_with_nothing_dropped_stays_ok(tmp_path: Path) -> None:
    """The guard rail. "Fail when a gate is dropped" is satisfiable by failing
    always, which would take the whole gate down; an empty `dropped_gates` is
    the ordinary case and must stay a bare `ok`."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "plan": "finish",\n'
        '  "gates": [\n    "lint"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "dropped from the plan" not in proc.stdout


@requires_bash
@requires_git
def test_a_plan_with_no_builtin_declaration_says_not_applicable(
    tmp_path: Path,
) -> None:
    """`null` is NOT `[]`, and the difference is the point (#1155).

    A manifest may define a plan the built-ins know nothing about. There is then
    no declaration to reconcile against - which is a different fact from
    "reconciled, nothing missing". Rendering both as zero-dropped would let a
    plan nobody can check report exactly what a clean plan reports: unscanned
    reading as clean.

    So the reader says so BY NAME, naming the plan, and does not fail - there is
    no finding here, only an absence of one to make.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "plan": "bespoke",\n'
        '  "gates": [\n    "lint"\n  ],\n'
        '  "dropped_gates": null,\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 0
    assert "not applicable" in proc.stdout
    assert "no builtin plan named 'bespoke'" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    # It must not borrow the clean case's silence.
    assert "dropped from the plan" not in proc.stdout


@requires_bash
@requires_git
def test_a_runner_that_cannot_reconcile_is_not_a_pass(tmp_path: Path) -> None:
    """A runner carrying #1147 but not #1155 publishes `gates` and no
    `dropped_gates`. Reconciliation did not happen, and NOT CHECKED must not
    read as clean - the same fail-closed rule the gate-set field already gets."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "plan": "finish",\n'
        '  "gates": [\n    "lint"\n  ],\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail (reconciliation unavailable)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout


@requires_bash
@requires_git
def test_a_declared_gate_that_never_ran_is_not_ok(tmp_path: Path) -> None:
    """The guard for the defect above, at the layer that prints the verdict.

    A gate dropped from the executed plan is in NEITHER list: it did not run, and
    nothing recorded it as skipped. The skipped-gate filter therefore finds
    nothing and the marker reads `ok` - which is how #1147's own fix shipped a
    green over four gates while declaring five.

    FAIL, not warn. #628's `warn (skipped gates: X)` means the gate could not run
    and RECORDS WHY - a consistent runner reporting a fact about the repository.
    Here the runner declared the gate and both of its own records of what became
    of it omit it, so the accounting itself is inconsistent and there is no
    reason to report. The gate fails closed rather than degrading to a softer
    verdict (wave orchestrator ruling, 2026-09-20).

    The payload is the REAL runner JSON shape from that run, reduced: `gates`
    names verify, `step_details` does not, and there is no `skipped` array at
    all. Replayed through the pre-fix script it prints `FLOW_FINISH_GATE: ok`
    and exits 0.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 2,\n  "steps_total": 2,\n'
        '  "gates": [\n    "lint",\n    "verify"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    },\n'
        '    {\n      "id": "stale_commit_check",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail (declared but never ran: verify)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout


@requires_bash
@requires_git
def test_gates_that_all_ran_stay_ok(tmp_path: Path) -> None:
    """The guard rail for the test above.

    "Warn when a declared gate is unaccounted for" is satisfiable by warning on
    every run, which would make the warning noise and cost it its readers. A
    payload whose every declared gate appears in `step_details` must stay a bare
    `ok`, and a non-gate step running alongside them must not change that.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 3,\n  "steps_total": 3,\n'
        '  "gates": [\n    "lint",\n    "verify"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    },\n'
        '    {\n      "id": "verify",\n      "status": "success"\n    },\n'
        '    {\n      "id": "stale_commit_check",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "declared but never ran" not in proc.stdout


@requires_bash
@requires_git
def test_a_declared_gate_recorded_as_skipped_is_accounted_for(
    tmp_path: Path,
) -> None:
    """A skipped gate IS accounted for - it keeps #628's own wording.

    Without this the two checks would collide: every skipped gate is also absent
    from `step_details`, so a guard reading only that list would relabel every
    #628 skip as "declared but never ran" and the distinction between "this repo
    has no such target" and "the plan silently dropped it" would be lost.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 1,\n  "steps_total": 2,\n'
        '  "gates": [\n    "lint",\n    "verify"\n  ],\n'
        '  "dropped_gates": [],\n'
        '  "skipped": [\n    "verify"\n  ],\n'
        '  "step_details": [\n'
        '    {\n      "id": "lint",\n      "status": "success"\n    }\n'
        "  ]\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (skipped gates: verify)" in proc.stdout
    assert "declared but never ran" not in proc.stdout


@requires_bash
@requires_git
def test_a_runner_json_without_a_gate_set_fails_closed(tmp_path: Path) -> None:
    """The absence case, and it is NEVER a pass.

    A runner too old to emit `gates`, or a JSON this parse cannot read, leaves
    the shell unable to tell which skipped steps were gates. An empty set
    filters everything away, so the silent outcome is `ok` - #1147's own defect,
    arriving through the fix for it.

    The single-marker assertion is not decoration. `verdict` PRINTS and does not
    exit; the first cut of this guard omitted the exit, so the script emitted
    `fail (gate set unreadable)` and then carried on to `verdict ok; exit 0`.
    Both markers were in the output and a test asserting only the first
    substring would have passed over an exit-0 false green.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 2,\n  "steps_total": 2,\n'
        '  "skipped": [\n    "typecheck"\n  ]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload, inject_gates=False)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail (gate set unreadable)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    markers = [
        line
        for line in proc.stdout.splitlines()
        if line.startswith("FLOW_FINISH_GATE: ")
    ]
    assert len(markers) == 1, (
        f"the gate emitted {len(markers)} verdict markers, {markers} - a caller "
        f"reads one. `verdict` prints without exiting, so a branch that forgets "
        f"its exit falls through to the next verdict (issue #1147)"
    )


# --- #804: a resumed run carrying an unverified stale result -----------------
#
# The runner emits a top-level "carried_from_previous_run" array whenever a
# resumed run kept a step's result rather than re-running it (issue #838
# follow-up), and, since #804, a "tree_verified" flag saying whether that
# carry was backed by a tree_signature match. This helper must warn on the
# first WITHOUT the second - and stay silent when both are present, or every
# ordinary crash-resume in this fleet would warn and train readers to stop
# reading the line.


@requires_bash
@requires_git
def test_carried_unverified_is_warn(tmp_path: Path) -> None:
    """No tree_verified key at all - e.g. a runner too old to set it, or one
    that could not compute a signature (no git). The helper cannot prove the
    carried step still describes the tree, so it must not say `ok`."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 3,\n  "steps_total": 3,\n'
        '  "carried_from_previous_run": [\n    "lint"\n  ]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (carried, unverified: lint)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    assert "issue #804" in proc.stdout


@requires_bash
@requires_git
def test_carried_verified_stays_ok(tmp_path: Path) -> None:
    """tree_verified: true means the runner hashed the tree at persist time
    and again at resume time and they matched - a proven crash-resume, not an
    assumption. This must NOT warn: it is the case option 3 exists to make
    silent, and warning on it anyway would fire on every ordinary
    killed-and-resumed run."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 3,\n  "steps_total": 3,\n'
        '  "carried_from_previous_run": [\n    "lint"\n  ],\n'
        '  "tree_verified": true\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "warn" not in proc.stdout


@requires_bash
@requires_git
def test_multiple_carried_steps_are_all_named(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 3,\n  "steps_total": 3,\n'
        '  "carried_from_previous_run": [\n    "lint",\n    "typecheck"\n  ]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (carried, unverified: lint typecheck)" in proc.stdout


@requires_bash
@requires_git
def test_skipped_gates_still_win_over_unverified_carry(tmp_path: Path) -> None:
    """Same precedence question #769 answered against #628: two true things can
    be wrong about a run at once, and the verdict has to pick the more serious
    one rather than let either erase the other. A gate that never ran at all
    is more serious than a step whose result merely lacks proof, so skipped
    wins - matching test_skipped_gates_win_but_rerun_ids_are_still_printed."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 3,\n  "steps_total": 4,\n'
        '  "carried_from_previous_run": [\n    "lint"\n  ],\n'
        '  "skipped": [\n    "typecheck"\n  ]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (skipped gates: typecheck)" in proc.stdout


# ── Naming what ran, and seeing a larger gate (issue #808) ──────────────────
#
# The fallback runs lint/test/typecheck. A repo whose real gate is a larger
# aggregate target - this repository's own `make verify` is nine - gets three
# of nine run and reported `ok`: a true statement about a fraction of the gate,
# presented as a verdict on the tree. That is the same shape as the `skipped`
# case above, one level in, and it sits inside the instrument everything else
# trusts.
#
# The THRESHOLD is deliberately unchanged: a repo where the fallback IS the
# gate still reports `ok`, and this issue does not touch when `skipped` fires.
# What changed (issue #1027) is `skipped`'s own exit code, not this threshold;
# what #808 changed is that the report now says which targets ran and which
# the repo expected.


@requires_bash
@requires_git
def test_fallback_names_the_gates_it_ran(tmp_path: Path) -> None:
    """Coverage should be readable, not inferred from an absence of complaint."""
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\ntest:\n\ttrue\ntypecheck:\n\ttrue\nverify:\n\ttrue\n"
    )
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 0
    assert (
        "gates executed: make lint make test make typecheck make verify"
        in proc.stdout
    )


@requires_bash
@requires_git
def test_an_aggregate_gate_the_fallback_cannot_run_is_a_warn(tmp_path: Path) -> None:
    """#808 holds for an aggregate this lane does NOT run.

    The aggregate here is `check-all`, not `verify`: since #1147 `verify` is a
    gate this lane runs itself, so it is no longer an example of a target
    whose prerequisites went unexamined. Repos name their aggregate all sorts
    of things, and for every name but the one we run, #808 is unchanged.
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\n"
        "test:\n\ttrue\n"
        "typecheck:\n\ttrue\n"
        "verify:\n\ttrue\n"
        "extra-check:\n\ttrue\n"
        "check-all: lint test typecheck extra-check\n"
    )
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (not run by fallback: extra-check)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    assert "make check-all" in proc.stdout
    # The gates it knows still ran - this is a reporting change, not a refusal.
    argv = (bindir / "make.log").read_text().splitlines()
    assert argv == ["lint", "test", "typecheck", "verify"]


@requires_bash
@requires_git
def test_an_aggregate_this_lane_runs_is_not_reported_as_unrun(
    tmp_path: Path,
) -> None:
    """The red case for #1147 against #808.

    `verify: lint test typecheck extra-check` with every target present. This
    lane now RUNS `make verify`, so extra-check ran - as a prerequisite of the
    command we issued. #808's warning says the aggregate's prerequisites "did
    NOT run here", and emitting it would be the gate asserting a fact its own
    previous line falsified.

    Before the detector was taught to skip a target this lane ran, this
    fixture reported `warn (not run by fallback: extra-check)` over a run that
    had just executed extra-check.
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\n"
        "test:\n\ttrue\n"
        "typecheck:\n\ttrue\n"
        "extra-check:\n\ttrue\n"
        "verify: lint test typecheck extra-check\n"
    )
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "not run by fallback" not in proc.stdout
    argv = (bindir / "make.log").read_text().splitlines()
    assert argv == ["lint", "test", "typecheck", "verify"]


@requires_bash
@requires_git
def test_a_repo_where_the_fallback_is_the_gate_is_still_ok(tmp_path: Path) -> None:
    """The guard rail. Without it, "warn on an aggregate" is satisfiable by
    warning on everything, which would train readers to ignore the warning -
    strictly worse than not having it."""
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\ntest:\n\ttrue\ntypecheck:\n\ttrue\nverify:\n\ttrue\n"
    )
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "not run by fallback" not in proc.stdout


@requires_bash
@requires_git
def test_a_phony_declaration_is_not_mistaken_for_an_aggregate(tmp_path: Path) -> None:
    """.PHONY lists gate names as DATA, not as prerequisites.

    Found by running the detector against this repository rather than a
    fixture: .PHONY names every phony target, so it trivially 'depends on'
    lint, test and typecheck and matched before `verify` did. A synthetic
    Makefile without a .PHONY line would never have shown it.
    """
    (tmp_path / "Makefile").write_text(
        ".PHONY: lint test typecheck verify docs clean\n"
        "lint:\n\ttrue\ntest:\n\ttrue\ntypecheck:\n\ttrue\nverify:\n\ttrue\n"
    )
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "docs" not in proc.stdout
    assert "clean" not in proc.stdout


@requires_bash
@requires_git
def test_a_multi_line_aggregate_is_detected(tmp_path: Path) -> None:
    """A real aggregate spans continuation lines, so a line-at-a-time scan
    would see one prerequisite and miss five.

    Named `check-all` rather than `verify` for the same reason as the test
    above: `verify` is now a gate this lane runs, so it is excluded from the
    unrun-aggregate question by construction and would test nothing here.
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\n"
        "test:\n\ttrue\n"
        "typecheck:\n\ttrue\n"
        "verify:\n\ttrue\n"
        "alpha-check:\n\ttrue\n"
        "beta-check:\n\ttrue\n"
        "check-all: lint test typecheck \\\n\talpha-check \\\n\tbeta-check\n"
    )
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "alpha-check" in proc.stdout
    assert "beta-check" in proc.stdout


@requires_bash
@requires_git
def test_the_skipped_threshold_is_unchanged(tmp_path: Path) -> None:
    """Pinned by #808/#809, which explicitly excluded exit-code changes from
    its own scope: a repo with no gate targets reports `skipped`. #1027 is the
    ticket that DOES change the exit code (0 -> 4, so a caller reading only
    `$?` can tell "did not run" from a clean `ok`) - see the header table. The
    THRESHOLD this test's name refers to - when `skipped` fires, not what it
    exits - is what stays unchanged; a later reader should see the new code
    asserted rather than assume either half drifted."""
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=None)
    assert proc.returncode == 4
    assert "FLOW_FINISH_GATE: skipped" in proc.stdout


# ── A timeout is reported as a timeout (issue #812) ─────────────────────────
#
# The runner emits `timed_out_step` / `timed_out_after` at the top level of its
# JSON; the gate must surface that rather than flattening it into a bare
# `fail`. Still exit 1 - an unfinished gate has not shown the tree is good -
# but the reader has to be able to tell "ran out of budget" from "the tree is
# broken", because only one of those is worth triaging.


@requires_bash
@requires_git
def test_a_runner_timeout_is_surfaced_as_a_timeout(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    runner_json = (
        '{\n'
        '  "success": false,\n'
        '  "failed_step": "test",\n'
        '  "timed_out_step": "test",\n'
        '  "timed_out_after": 600\n'
        '}\n'
    )
    proc, _ = _run(tmp_path, cpp_dir=str(cpp), uv_exit=1, uv_stdout=runner_json)
    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail (timeout: test after 600s)" in proc.stdout
    assert "did NOT fail, it did not finish" in proc.stdout
    assert "CPP_GATE_TEST_TIMEOUT" in proc.stdout, (
        "the message must say how to raise the budget - the number will be "
        "wrong again as the suite grows, and a reader mid-incident should not "
        "have to find that out from the source"
    )


@requires_bash
@requires_git
def test_an_ordinary_failure_is_still_a_bare_fail(tmp_path: Path) -> None:
    """The guard rail: a change that called every failure a timeout would pass
    the test above while destroying the distinction it exists for."""
    cpp = _fake_cpp(tmp_path)
    runner_json = '{\n  "success": false,\n  "failed_step": "test"\n}\n'
    proc, _ = _run(tmp_path, cpp_dir=str(cpp), uv_exit=1, uv_stdout=runner_json)
    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout
    assert "timeout" not in proc.stdout.lower()


@requires_bash
@requires_git
def test_runner_zero_coverage_reports_warn_named(tmp_path: Path) -> None:
    """A gate that RAN and examined NOTHING must not read as a clean pass (#1027).

    The #628 array above answers "did the gate run?". This answers the question
    one step further in, which had no channel at all: the gate ran, exited 0,
    and had no input. `ruff check .` on a tree with no Python files warns on
    stderr, prints "All checks passed!" on stdout and exits 0 - so before this,
    a stage with nothing to examine and a stage that examined the whole tree
    produced byte-identical step details and the same `ok`.

    Demonstrated end to end before this test was written: the same tree against
    origin/main 967c098 exits 0 with `FLOW_FINISH_GATE: ok`, and against this
    branch exits 3 with `warn (zero coverage: security_scan)`.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 4,\n  "steps_total": 4,\n'
        '  "coverage": {\n'
        '    "security_scan": {\n'
        '      "state": "zero",\n'
        '      "units": 0,\n'
        '      "tool": "security-gate"\n'
        "    }\n"
        "  }\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (zero coverage: security_scan)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    assert "issue #1027" in proc.stdout


@requires_bash
@requires_git
def test_runner_covered_stage_stays_ok(tmp_path: Path) -> None:
    """The other half of the control, and the one that catches a blind gate.

    A parser that reported `zero` for everything would satisfy the test above
    and be strictly worse than no parser: every run would warn, and the warning
    would stop being read. A stage that states real coverage must stay `ok`.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 4,\n  "steps_total": 4,\n'
        '  "coverage": {\n'
        '    "typecheck": {\n'
        '      "state": "covered",\n'
        '      "units": 47,\n'
        '      "tool": "mypy"\n'
        "    }\n"
        "  }\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "zero coverage" not in proc.stdout


@requires_bash
@requires_git
def test_runner_unknown_coverage_stays_ok(tmp_path: Path) -> None:
    """`unknown` is RECORDED but never graded on - the deliberate bound (#1027).

    It is the state of every lint harness CPP cannot parse (Go, Rust, a shell
    wrapper) and of ruff on its clean path, so warning on it would fire on every
    run of those repos. Recording it still fixes the reported defect - the
    reader sees an unproven stage rather than a bare `status: "success"` - which
    is why the field is present in the JSON this test feeds in and the verdict
    is still `ok`.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 4,\n  "steps_total": 4,\n'
        '  "coverage": {\n'
        '    "lint": {\n'
        '      "state": "unknown",\n'
        '      "units": null,\n'
        '      "tool": "unknown"\n'
        "    }\n"
        "  }\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "zero coverage" not in proc.stdout


@requires_bash
@requires_git
def test_skipped_gates_win_over_zero_coverage(tmp_path: Path) -> None:
    """Precedence, asserted rather than left to source order.

    A gate that did not run at all is the more fundamental fact than one that
    ran with no input, so `skipped gates` is reported first. Both are exit 3, so
    only the NAMED verdict distinguishes them - which is exactly the reader-
    facing distinction #1027 is about.
    """
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 4,\n  "steps_total": 4,\n'
        '  "skipped": [\n    "typecheck"\n  ],\n'
        '  "coverage": {\n'
        '    "security_scan": {\n'
        '      "state": "zero",\n'
        '      "units": 0,\n'
        '      "tool": "security-gate"\n'
        "    }\n"
        "  }\n}"
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (skipped gates: typecheck)" in proc.stdout


def _zero_coverage_make_stub(bindir: Path, lint_output: str) -> None:
    """A `make` shim whose lint target emits REAL tool output on stderr."""
    stub = bindir / "make"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'case "$1" in\n'
        f'  lint) printf %s\\\\n "{lint_output}" >&2; echo "All checks passed!";;\n'
        '  test) echo "3 passed in 0.01s";;\n'
        '  typecheck) echo "Success: no issues found in 12 source files";;\n'
        "esac\n"
        "exit 0\n"
    )
    stub.chmod(0o755)


@requires_bash
@requires_git
def test_fallback_lane_detects_a_gate_that_examined_nothing(tmp_path: Path) -> None:
    """The FALLBACK lane needs this too, and needs it more (#1027).

    The runner lane reads the coverage object out of the runner's JSON. The
    fallback has no runner and no step_details - and in a container, where
    there is no CPP checkout, the fallback IS the ordinary path rather than the
    degraded one. That is precisely where #1027 measured `skipped` and `passed`
    sharing an exit code, so a runner-only fix would have left the measured
    case blind.
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\ntest:\n\ntypecheck:\n\nverify:\n"
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _zero_coverage_make_stub(
        bindir, "warning: No Python files found under the given path(s)"
    )

    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FLOW_GATE_CPP_DIR"] = ""
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn (zero coverage: lint)" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout


@requires_bash
@requires_git
def test_fallback_lane_stays_ok_when_the_gates_examined_something(
    tmp_path: Path,
) -> None:
    """The half that catches a fallback detector matching everything."""
    (tmp_path / "Makefile").write_text(
        "lint:\n\ntest:\n\ntypecheck:\n\nverify:\n"
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _zero_coverage_make_stub(bindir, "checked 40 files")

    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FLOW_GATE_CPP_DIR"] = ""
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "zero coverage" not in proc.stdout


@requires_bash
@requires_git
def test_fallback_lane_still_reports_a_failing_gate(tmp_path: Path) -> None:
    """The `tee` capture must not swallow the command's exit status.

    The non-test fallback lanes now pipe through `tee` so their output can be
    inspected, which means a bare `||` would read the TEE's status and record
    success for every failing gate. They grade on `PIPESTATUS[0]` instead; this
    is the test that fails if that ever regresses to `$?`.
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\ntest:\n\ntypecheck:\n\nverify:\n"
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "make"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'case "$1" in\n'
        '  lint) echo "E501 line too long"; exit 1;;\n'
        '  test) echo "3 passed in 0.01s";;\n'
        '  typecheck) echo "Success: no issues found in 12 source files";;\n'
        "esac\n"
        "exit 0\n"
    )
    stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FLOW_GATE_CPP_DIR"] = ""
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout


# --- Counter-model enrolment (issue #1171) ----------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _enrolled_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master", ".")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "docs" / "measurements" / "counter-model").mkdir(parents=True)
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _write_receipt(repo: Path, head: str, status: str = "ran", reason: str | None = None) -> None:
    import json

    r = {
        "schema": 1, "recorded_at": "2026-09-21T12:00:00Z", "issue": "1171",
        "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": head, "status": status,
        "reviewer": None if status == "skipped" else "codex/gpt-6-astra",
        "implementer": "claude/claude-opus-5",
    }
    if reason:
        r["skip_reason"] = reason
    (repo / "docs/measurements/counter-model/receipt.json").write_text(json.dumps(r, indent=2))


def _gate(repo: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["FLOW_GATE_CPP_DIR"] = ""
    env["CM_RECEIPT_HELPER"] = str(ROOT / "scripts" / "counter-model-receipt.py")
    return subprocess.run(
        ["bash", str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True,
    )


def test_every_verdict_call_is_terminal() -> None:
    """The enrolment enforcement in `verdict()` relies on this (#1171), and #1061 widened it.

    `verdict()` downgrades a PASS verdict to `fail` by printing and EXITING. That
    is only safe because every call site already exits immediately afterwards, so
    the exit it pre-empts was coming anyway. A later edit that adds a `verdict`
    call which FALLS THROUGH would silently acquire an early exit it never asked
    for - so the invariant is pinned here rather than trusted, in the file that
    depends on it.

    THE TERMINAL SET IS ENUMERATED, NEVER A WILDCARD. #1061 migrated the 25
    hand-rolled `exit N` successors onto `gate_exit`, so the idiom moved while the
    property did not. `gate_exit` is admitted because it is UNCONDITIONALLY
    TERMINAL - measured, not assumed: all four paths out of gate-lib.sh:308-318 end
    in `exit` (:309 and :310 and :312 via `_gate_refuse`, :317 on the mapped
    verdict), and the `return 1` inside `_gate_code_for` is consumed by the `if !`
    at :312 rather than returned to the caller. A loose alternation matching any `gate_`-prefixed helper
    would admit a future helper that returns, which is the fall-through this test
    exists to catch.

    AND IT NOW CHECKS AGREEMENT, which the old `exit N` form could not express
    without duplicating gate_map here: a `gate_exit` successor's verdict word must
    EQUAL the verdict call's leading word. `verdict "ok"` followed by
    `gate_exit fail` is a gate that says one thing and exits another, and under the
    old idiom only a second copy of the map could have caught it.
    """
    lines = SCRIPT.read_text().splitlines()
    calls = [i for i, ln in enumerate(lines) if re.match(r"^\s*verdict\s", ln)]
    assert calls, "no verdict calls found - this test is not measuring anything"
    non_terminal = [
        (i + 1, lines[i].strip())
        for i in calls
        if i + 1 >= len(lines)
        or not re.match(r"^\s*(?:exit\s+\d+|gate_exit\s+[a-z-]+)\s*(?:#.*)?$", lines[i + 1])
    ]
    assert non_terminal == [], (
        "verdict() exits when it downgrades a pass verdict, which is only safe "
        f"while every call is terminal; these are not: {non_terminal}"
    )

    disagreeing = []
    for i in calls:
        successor = lines[i + 1] if i + 1 < len(lines) else ""
        if not re.match(r"^\s*gate_exit\b", successor):
            continue
        # NOT `if not got: continue`. A spelling this pattern cannot read -
        # `gate_exit "fail"`, or a trailing comment - would then be SKIPPED by the
        # agreement check, and a skipped line and a conforming line are the same
        # colour. The whole-successor match above already refuses those shapes as
        # non-terminal, so reaching here with an unreadable one is a contradiction
        # worth failing on rather than passing over (counter-model review, #1061).
        got = re.match(r"^\s*gate_exit\s+([a-z-]+)\s*(?:#.*)?$", successor)
        assert got, f"line {i + 2}: gate_exit successor is not in a readable form: {successor.strip()}"
        said = re.match(r'^\s*verdict\s+"?([a-z-]+)', lines[i])
        assert said, f"line {i + 1} calls verdict with no readable verdict word: {lines[i].strip()}"
        if said.group(1) != got.group(1):
            disagreeing.append((i + 1, said.group(1), got.group(1)))
    assert disagreeing == [], (
        "a gate that prints one verdict and exits with another is indistinguishable "
        "from one that agrees, to every caller reading only $?; these disagree "
        f"(line, printed, exited): {disagreeing}"
    )


@requires_git
def test_missing_counter_model_line_reds_a_run_that_would_otherwise_pass(tmp_path: Path) -> None:
    repo = _enrolled_repo(tmp_path)
    got = _gate(repo)
    assert "FLOW_FINISH_GATE: fail (counter-model line missing)" in got.stdout
    assert got.returncode == 1


@requires_git
def test_a_receipt_at_an_ancestor_commit_still_satisfies(tmp_path: Path) -> None:
    """The ancestry rule, and the reason strict head equality was rejected.

    auto.md writes the receipt at :940, runs this gate at :1021, COMMITS at :1097
    and runs the gate again at :1240 after merging origin/main. Under strict head
    equality the second run reds while holding a perfectly valid review.
    """
    repo = _enrolled_repo(tmp_path)
    reviewed = _git(repo, "rev-parse", "HEAD")
    _write_receipt(repo, reviewed)
    (repo / "later.txt").write_text("later\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "commit after the review")
    assert _git(repo, "rev-parse", "HEAD") != reviewed
    got = _gate(repo)
    assert "FLOW_FINISH_GATE: fail" not in got.stdout
    assert "FLOW_FINISH_GATE_COUNTER_MODEL: receipt:" in got.stdout


@requires_git
def test_a_skip_reason_outside_the_committed_set_reds(tmp_path: Path) -> None:
    """`explicit-opt-out` was removed deliberately; it must not come back by the side door."""
    repo = _enrolled_repo(tmp_path)
    _write_receipt(repo, _git(repo, "rev-parse", "HEAD"), "skipped", "explicit-opt-out")
    got = _gate(repo)
    assert "FLOW_FINISH_GATE: fail (counter-model line unknown)" in got.stdout
    assert got.returncode == 1


@requires_git
def test_a_committed_skip_reason_passes_with_the_skip_named(tmp_path: Path) -> None:
    repo = _enrolled_repo(tmp_path)
    _write_receipt(repo, _git(repo, "rev-parse", "HEAD"), "skipped", "codex-absent")
    got = _gate(repo)
    assert "FLOW_FINISH_GATE_COUNTER_MODEL: skipped: codex-absent" in got.stdout
    assert "FLOW_FINISH_GATE: fail" not in got.stdout


@requires_git
def test_a_repository_that_does_not_participate_is_not_red(tmp_path: Path) -> None:
    """This helper is installed globally and runs in repositories that have no receipts at all."""
    repo = tmp_path / "other"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master", ".")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "f.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    got = _gate(repo)
    assert "FLOW_FINISH_GATE: fail" not in got.stdout
    assert "not-enrolled" in got.stdout


@requires_git
def test_main_side_after_a_squash_merge_would_red_which_is_why_this_is_branch_side(
    tmp_path: Path,
) -> None:
    """The squash-merge hazard, as an executed fact rather than a comment.

    CPP squash-merges, so a branch's commits never land on main. `--is-ancestor`
    then answers NO for every one of them, and a main-side copy of this check
    would red every merged PR in the repository. The gate is invoked branch-side
    only (auto.md Steps 6 and 7), where the branch commits are still reachable.
    This reproduces the squash and asserts the red, so the reason for that
    scoping is committed rather than described.
    """
    repo = _enrolled_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "work.txt").write_text("work\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "the work")
    reviewed = _git(repo, "rev-parse", "HEAD")
    _write_receipt(repo, reviewed)
    branch_receipt = (repo / "docs/measurements/counter-model/receipt.json").read_text()

    # Squash the branch onto main exactly as gh pr merge --squash does: the
    # content lands, the commits do not.
    _git(repo, "checkout", "-q", "master")
    _git(repo, "merge", "--squash", "feature")
    (repo / "docs/measurements/counter-model/receipt.json").write_text(branch_receipt)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "squashed (#1171)")

    assert subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", reviewed, "HEAD"],
    ).returncode != 0, "the reviewed commit is reachable after a squash - premise of this test is gone"

    got = _gate(repo)
    assert "FLOW_FINISH_GATE: fail (counter-model line missing)" in got.stdout, (
        "a main-side run after a squash reds - which is the finding this test records, "
        "and the reason the check must stay branch-side"
    )


@requires_git
def test_a_receipt_whose_status_says_nothing_is_unknown_not_a_review(tmp_path: Path) -> None:
    """Found by the counter-model review of this change (HIGH).

    The first cut accepted every matching receipt whose status was not exactly
    `skipped`, so a receipt with `"status": "garbage"` - or none at all - satisfied
    the gate while recording neither a review nor an allowed skip. Status is checked
    positively now: only `ran` is a review.
    """
    repo = _enrolled_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    for bad in ("garbage", None):
        import json as _json
        r = {"schema": 1, "recorded_at": "2026-09-21T12:00:00Z", "issue": "1171",
             "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
             "head": head, "reviewer": "codex/gpt-6-astra", "implementer": "claude/claude-opus-5"}
        if bad is not None:
            r["status"] = bad
        (repo / "docs/measurements/counter-model/receipt.json").write_text(_json.dumps(r, indent=2))
        got = _gate(repo)
        assert "FLOW_FINISH_GATE: fail (counter-model line unknown)" in got.stdout, bad
        assert got.returncode == 1


@requires_git
def test_a_skip_reason_shaped_like_a_grep_option_is_refused(tmp_path: Path) -> None:
    """Found by the counter-model review of this change, pass 2 (MEDIUM).

    `grep -qxF "$reason"` without `--` reads `-ecodex-absent` as the option
    `-e codex-absent` and matches, so a reason outside the committed set passed the
    allowlist. An allowlist addressable with its own matcher's flags is not one.
    """
    repo = _enrolled_repo(tmp_path)
    _write_receipt(repo, _git(repo, "rev-parse", "HEAD"), "skipped", "-ecodex-absent")
    got = _gate(repo)
    assert "FLOW_FINISH_GATE: fail (counter-model line unknown)" in got.stdout
    assert got.returncode == 1


@requires_bash
def test_a_missing_gate_lib_is_fatal_not_advisory(tmp_path: Path) -> None:
    """The accident that produced this test, committed as its case (issue #1061).

    `set -e` is not in force in this gate, so a bare `. "$missing"` PRINTS and
    CONTINUES, and every `gate_exit` downstream then becomes `command not found` -
    also non-fatal. Constructed by accident while reproducing the distribution gap,
    the observed output was:

        scripts/flow-finish-gate.sh: line 1333: gate_exit: command not found
        FLOW_FINISH_GATE: ok
        EXIT=127

    A green verdict over a broken instrument: the fall-through-to-the-good-exit this
    migration exists to REMOVE, reintroduced by its own dependency going missing. It
    matters because this gate is bundled into four generated Codex skills while
    gate-lib is bundled into none, so the distributed copies are exactly where it
    would bite and exactly where nobody runs this suite.
    """
    lone = tmp_path / "scripts"
    lone.mkdir()
    shutil.copy(SCRIPT, lone / SCRIPT.name)
    env = dict(os.environ)
    env.update(HOME=str(tmp_path / "nohome"), CLAUDE_PLUGIN_ROOT="", FLOW_GATE_CPP_DIR="")
    got = subprocess.run(
        ["bash", str(lone / SCRIPT.name)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120,
    )
    assert got.returncode == 2, (
        f"a gate that cannot find its library must refuse, not proceed; got {got.returncode}\n"
        f"{got.stdout}\n{got.stderr}"
    )
    assert "cannot find gate-lib.sh" in got.stderr
    assert "FLOW_FINISH_GATE: ok" not in got.stdout, (
        "the pre-fix failure mode: a clean verdict printed after gate_exit was unavailable"
    )


@requires_git
def test_the_receipt_line_separates_the_filename_from_the_branch(tmp_path: Path) -> None:
    """Found by worker-A while merging main; two sites, and the obvious fix is wrong.

    The line's only job is to say WHICH receipt satisfied the gate, and it rendered
    `receipt: 2026-...-issue-1080.jsonissue-1080-commit-...` - the filename running
    straight into the branch with no separator, so the filename's boundary is
    unfindable. The construct was `${branch:+}${branch:-  (detached ...)}`: the `:+`
    word is EMPTY, so it expands to nothing in BOTH cases, and the `:-` then emits
    the branch NAME in the set case.

    Substituting text into the `:+` half does not fix it - `${branch:+ for branch
    '$branch'}${branch:-  (...)}` renders `for branch 'x'x`, which reads plausibly
    enough to pass review. Hence one computed suffix behind an explicit if/else, and
    hence this test asserts BOTH renderings rather than just the one that was
    reported.
    """
    repo = _enrolled_repo(tmp_path)
    _git(repo, "checkout", "-q", "-B", "feat-x")
    head = _git(repo, "rev-parse", "HEAD")
    _write_receipt(repo, head)

    on_branch = _gate(repo).stdout
    assert "receipt: receipt.json for branch 'feat-x'" in on_branch, on_branch
    assert "'feat-x'feat-x" not in on_branch, "the obvious-but-wrong fix"
    assert "receipt.jsonfeat-x" not in on_branch, "the original defect"

    _git(repo, "checkout", "-q", "--detach", "HEAD")
    detached = _gate(repo).stdout
    assert "receipt: receipt.json  (detached HEAD:" in detached, detached
    assert "for branch" not in detached.split("COUNTER_MODEL:")[1].split("\n")[0]


# --- The control runner's isolation (attachment coupling, 2026-09-22) -------
#
# The six controls/flow-finish-gate* registrations used to `cd` into their case
# IN PLACE, inside this repository, so the gate read the ENCLOSING repository's
# git state - a fact the fixture never chose. Measured at one sha: attached to a
# branch -> fail, DETACHED at the same sha -> ok, attached to main -> fail. So
# ATTACHMENT was the variable, main failed permanently, and CI - always detached
# - could never see any of it.

RUNNER = ROOT / "controls" / "flow-finish-gate" / "run-case.sh"
REAL_REPO_MARKER = "RUN-ON-THE-REAL-REPO-PATH"


def _run_case(case_dir: Path, cpp_mode: str = "empty") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(RUNNER), str(case_dir), str(SCRIPT), cpp_mode],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )


def _control_path(proc: subprocess.CompletedProcess[str]) -> str:
    hits = re.findall(r"^FLOW_FINISH_GATE_CONTROL_PATH: (\S+)", proc.stdout, re.M)
    assert hits, f"the runner reported no path:\n{proc.stdout}\n{proc.stderr}"
    return hits[-1]


@requires_git
def test_the_runner_isolates_outside_every_git_repository(tmp_path: Path):
    """The isolation IS the location, so pin the location.

    A copy that landed anywhere inside a checkout would silently restore the
    coupling and the case would go green while measuring the wrong repository -
    worse than the red it replaced, because nothing would say so.
    """
    case = tmp_path / "case"
    case.mkdir()
    (case / "Makefile").write_text("lint:\n\t@echo ok\n", encoding="utf-8")
    proc = _run_case(case)
    assert _control_path(proc) == "isolated"
    assert "FLOW_FINISH_GATE_CONTROL: unavailable" not in proc.stdout


@requires_git
def test_the_real_repo_marker_is_LOAD_BEARING(tmp_path: Path):
    """The marker must change behaviour, or the case that names it is a costume.

    A BAD case reds on EITHER path, so the verdict alone cannot show which path
    ran. Without the runner saying so, a marker that silently stopped working
    would leave a case named for the real path quietly running isolated - the
    exact drift that case exists to catch, wearing the costume of the guard.
    """
    case = tmp_path / "case"
    case.mkdir()
    (case / "Makefile").write_text("lint:\n\t@echo ok\n", encoding="utf-8")
    assert _control_path(_run_case(case)) == "isolated"
    (case / REAL_REPO_MARKER).write_text("deliberate\n", encoding="utf-8")
    assert _control_path(_run_case(case)) == "real-repo"


@requires_git
def test_the_committed_real_repo_case_still_takes_the_real_path():
    """Condition from the approving review: one case stays on the real path.

    Asserted against the COMMITTED case rather than a fixture, because the
    condition is about what ships.
    """
    case = ROOT / "controls" / "flow-finish-gate" / "cases" / "bad-verify-reds-ON-THE-REAL-REPO-PATH"
    assert (case / REAL_REPO_MARKER).is_file(), "the committed case lost its marker"
    assert _control_path(_run_case(case)) == "real-repo"


@requires_git
def test_a_CRASHING_gate_still_does_not_read_as_detection():
    """The other half of the discriminating pair, and the reason `\\b` is safe.

    THE FIRST VERSION OF THIS TEST PASSED WHEN THE GATE NEVER STARTED
    (counter-model review, codex, MEDIUM). It asserted only "non-zero AND no
    verdict line on stdout", and `TMPDIR=/dev/null/not-a-directory` satisfies
    both: the runner exits 2 with `unavailable` having never run the gate.
    Reproduced before fixing. A test that reports success over nothing
    exercised is the failure this whole branch is about, one level in.

    So: require the CRASH status specifically, reject an unavailable run by
    name, prove the crash fixture actually executed, and read BOTH streams -
    the harness matches detection signals against stdout and stderr together,
    so checking one is a narrower question than the one being asked.
    """
    case = ROOT / "controls" / "flow-finish-gate" / "cases" / "probe-crash-must-not-read-as-detected"
    proc = _run_case(case)
    combined = proc.stdout + proc.stderr

    assert "FLOW_FINISH_GATE_CONTROL: unavailable" not in combined, (
        "the runner never reached the gate, so this run says nothing about a crash:\n"
        + combined
    )
    assert _control_path(proc) == "isolated", "the crash fixture must have been run"
    # SIGKILL. Not merely non-zero: a refusal is non-zero too, and the whole
    # point of the pair is that those two are different things.
    assert proc.returncode == 137, f"expected a signal death (137), got {proc.returncode}"
    verdicts = re.findall(r"^FLOW_FINISH_GATE: .*$", combined, re.M)
    assert verdicts == [], f"a crash must emit NO verdict line, got {verdicts}:\n{combined}"


@requires_git
def test_the_real_repo_path_case_is_owned_by_its_planted_defect(tmp_path: Path):
    """Why the real-repo path is pinned HERE and not by a control case.

    A control case on the real path was written and WITHDRAWN: `detect_signal`
    is control-level, so no case can say "only my planted defect counts", and
    measurement showed the case was satisfied by its neighbour. With every gate
    passing - the planted defect entirely removed - it still emitted
    `FLOW_FINISH_GATE: fail`, because the ENCLOSING repository has no
    counter-model receipt for the current branch.

    A test can assert what a case cannot: that the real path runs in place, AND
    that the failure belongs to the planted defect rather than to the
    repository the fixture happens to sit in.
    """
    case = ROOT / "controls" / "flow-finish-gate" / "cases" / "bad-verify-reds-ON-THE-REAL-REPO-PATH"
    assert (case / REAL_REPO_MARKER).is_file(), "the fixture lost its marker"
    proc = _run_case(case)
    assert _control_path(proc) == "real-repo", "this fixture must NOT be isolated"

    # OWNERSHIP: the planted defect must be what redded. The fixture's own
    # verify target is the subject; a failure attributable only to enrolment
    # would be the neighbour's, and is the reason the case was withdrawn.
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, combined
    assert "verify" in combined, (
        "the planted verify defect left no trace, so this run cannot claim the "
        "real path exercised its own subject:\n" + combined
    )


@requires_git
def test_the_runner_reports_UNAVAILABLE_rather_than_clean_when_it_cannot_isolate(
    tmp_path: Path,
):
    """A battery that silently runs fewer cases is unscanned-reads-as-clean.

    TMPDIR pointed at a path that cannot be created is the reachable form: the
    runner must say so in its own words and exit non-zero, never fall through to
    the gate and report whatever the enclosing repository happens to produce.
    """
    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_path / "does" / "not" / "exist")
    case = tmp_path / "case"
    case.mkdir()
    (case / "Makefile").write_text("lint:\n\t@echo ok\n", encoding="utf-8")
    proc = subprocess.run(
        ["sh", str(RUNNER), str(case), str(SCRIPT), "empty"],
        capture_output=True, text=True, check=False, cwd=ROOT, env=env,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "FLOW_FINISH_GATE_CONTROL: unavailable" in proc.stdout, proc.stdout
    assert "FLOW_FINISH_GATE: " not in proc.stdout, (
        "an unavailable run must not also emit a gate verdict"
    )



# --- issue #1258: name the failing test; leave no temp file ------------------

_FAILED_PAYLOAD = (
    '{\n  "success": false,\n  "failed_step": "test",\n  "steps_completed": 1,\n'
    '  "tests": {\n    "test": {\n      "passed": 5847,\n      "failed": 1,\n'
    '      "executed": 5848,\n      "failed_ids": [\n'
    '        "tests/test_a.py::test_one"\n      ]\n    }\n  }\n}'
)


@requires_bash
@requires_git
def test_a_failed_gate_names_the_failing_test(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    proc = _run_with_uv_stub(tmp_path, cpp, _FAILED_PAYLOAD, exit_code=1)
    assert proc.returncode == 1
    assert "FAILED_IDS: tests/test_a.py::test_one" in proc.stdout
    # Relayed ABOVE the verdict, which stays the last marker.
    lines = proc.stdout.splitlines()
    ids_at = next(i for i, ln in enumerate(lines) if ln.startswith("FAILED_IDS:"))
    verdict_at = next(i for i, ln in enumerate(lines) if ln.startswith("FLOW_FINISH_GATE: "))
    assert ids_at < verdict_at


@requires_bash
@requires_git
def test_an_unnamed_failure_is_said_out_loud(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = _FAILED_PAYLOAD.replace(
        '"failed_ids": [\n        "tests/test_a.py::test_one"\n      ]', '"failed_ids": []'
    )
    assert '"failed_ids": []' in payload  # precondition: the fixture really is empty
    proc = _run_with_uv_stub(tmp_path, cpp, payload, exit_code=1)
    assert proc.returncode == 1
    assert "FAILED_IDS: none readable" in proc.stdout


@requires_bash
@requires_git
def test_an_interrupted_gate_leaves_no_runner_json_behind(tmp_path: Path) -> None:
    """The leak the nit measured (twelve zero-byte files on one host): a gate
    killed between `mktemp` and the parse never reached its straight-line `rm`.
    The runner stub here SIGTERMs the gate itself mid-run."""
    cpp = _fake_cpp(tmp_path)
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "uv"
    # $PPID of a pipeline member is the gate's own shell.
    stub.write_text("#!/usr/bin/env bash\nkill -TERM \"$PPID\"\nsleep 5\n")
    stub.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FLOW_GATE_CPP_DIR"] = str(cpp)
    env["TMPDIR"] = str(tmpdir)
    proc = subprocess.run(
        ["bash", str(SCRIPT)], cwd=tmp_path, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60,
    )
    # Precondition: it really was interrupted, before any verdict.
    assert "FLOW_FINISH_GATE: " not in proc.stdout, proc.stdout
    assert "running deterministic gate" in proc.stdout
    assert sorted(p.name for p in tmpdir.iterdir()) == []



@requires_bash
@requires_git
@pytest.mark.skipif(
    not Path("/proc/self/stat").exists(),
    reason="the late tee is released on the gate's death, read from /proc; without "
    "procfs that synchronisation cannot be established and the case would prove nothing",
)
def test_a_late_tee_cannot_recreate_the_runner_json_after_the_trap(tmp_path: Path) -> None:
    """THE #1313 REGRESSION: the leak the test above catches only under load.

    `tee` is a pipeline member that outlives the killed gate. If it opens the
    runner JSON by NAME after the EXIT trap's `rm`, it re-creates the file and
    nothing removes it again - pipeline 2811's `['flow-finish-gate.9OcbCl']`,
    first mislabelled a timing flake. A loaded host is what makes `tee` late;
    here a PATH stub makes it late on purpose - by an EVENT, not a delay
    (counter-model review): it holds the real `tee` until the gate shell has
    DIED, i.e. until its EXIT trap has already run. A fixed sleep could lose to
    a slow gate and pass on the unfixed code without exercising the race.

    The GATE's pid is handed to the stub by this test (written the moment Popen
    returns), never read from the stub's `$PPID`: a stub that starts after the
    gate is killed has already been reparented, and would watch the wrong
    process (counter-model review, pass 2). The gate counts as dead once it is a
    zombie - it stays one until this test reaps it, after EOF on stdout, which
    `tee` holds, so waiting for the pid to vanish would deadlock.

    No sleep in the assertion: communicate() returns at EOF on the gate's
    stdout, which `tee` holds, so every straggler has exited when TMPDIR is read.
    """
    cpp = _fake_cpp(tmp_path)
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "uv"
    stub.write_text("#!/usr/bin/env bash\nkill -TERM \"$PPID\"\nsleep 5\n")
    stub.chmod(0o755)
    real_tee = shutil.which("tee")
    assert real_tee, "precondition: a real tee to delay"
    gate_pid_file = tmp_path / "gate.pid"
    released = tmp_path / "tee-released"
    late_tee = bindir / "tee"
    late_tee.write_text(
        "#!/usr/bin/env bash\n"
        "deadline=$((SECONDS + 30))\n"
        f'until [ -s "{gate_pid_file}" ]; do\n'
        '  [ "$SECONDS" -lt "$deadline" ] || { echo "late-tee: no gate pid" >&2; exit 97; }\n'
        "  sleep 0.05\n"
        "done\n"
        f'gate=$(cat "{gate_pid_file}")\n'
        # Alive = a /proc entry that is not a zombie.
        'while [ -r "/proc/$gate/stat" ] && [ "$(cut -d")" -f2 "/proc/$gate/stat" | cut -d" " -f2)" != Z ]; do\n'
        '  [ "$SECONDS" -lt "$deadline" ] || { echo "late-tee: the gate never exited" >&2; exit 97; }\n'
        "  sleep 0.05\n"
        "done\n"
        f': > "{released}"\n'
        f'exec {real_tee} "$@"\n'
    )
    late_tee.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FLOW_GATE_CPP_DIR"] = str(cpp)
    env["TMPDIR"] = str(tmpdir)
    gate = subprocess.Popen(
        ["bash", str(SCRIPT)], cwd=tmp_path, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    gate_pid_file.write_text(str(gate.pid))
    try:
        stdout, _ = gate.communicate(timeout=60)
    finally:
        if gate.poll() is None:
            gate.kill()
            gate.wait(timeout=10)
    assert "FLOW_FINISH_GATE: " not in stdout, "precondition: interrupted before a verdict"
    assert "running deterministic gate" in stdout
    assert released.exists(), f"precondition: tee was released only after the gate died\n{stdout}"
    assert sorted(p.name for p in tmpdir.iterdir()) == []


@requires_bash
@requires_git
def test_an_uninterrupted_run_reads_the_complete_runner_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of #1313: writing through fd 9 must not change what is read.

    Every verdict below is derived from PATH reads of the runner JSON after the
    pipeline, so they prove the file held the whole payload; the payload is also
    tee'd to stdout verbatim, and the file is still removed at the end.
    """
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    cpp = _fake_cpp(tmp_path)
    payload = _runner_json(_NO_TESTS_WARNING)
    proc, _ = _run(tmp_path, cpp_dir=str(cpp), uv_exit=0, uv_stdout=payload)
    assert proc.returncode == 3
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert _qualified_line(proc.stdout)
    assert '"warnings"' in proc.stdout and "executed NO tests" in proc.stdout
    assert sorted(p.name for p in tmpdir.iterdir()) == []

@requires_bash
@requires_git
def test_runner_unavailable_fallback_honours_a_declared_mypy_scope(tmp_path: Path) -> None:
    """counter-model review, pass 2: the runner-unavailable lane still ran
    `mypy .`, so the scope a repo declared depended on which lane ran."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ruff]\n[tool.pytest.ini_options]\n[tool.mypy]  # scope\nfiles = ["pkg"]\n'
    )
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=0)
    invocations = (bindir / "uv.log").read_text().splitlines()
    assert "run --extra dev mypy" in invocations
    assert "run --extra dev mypy ." not in invocations


@requires_git
@requires_bash
@pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
@pytest.mark.parametrize("plan, expect_fail", [("check", False), ("finish", True)])
def test_fallback_runs_verify_only_for_plans_that_declare_it(tmp_path: Path, plan: str, expect_fail: bool) -> None:
    """Issue #1366 (counter-model review): `--plan check` is lint/test/typecheck.

    The runner-less fallback ran `verify` unconditionally, so a failing `verify` -
    a gate /flow:check never asked for - turned /flow:check red. The finish plan
    still runs it: the same tree is the red case for that plan.
    """
    (tmp_path / "Makefile").write_text(
        "lint:\n\t@true\ntest:\n\t@echo '1 passed in 0.01s'\ntypecheck:\n\t@true\nverify:\n\t@false\n"
    )
    assert "verify:\n\t@false" in (tmp_path / "Makefile").read_text(), "precondition: verify fails"
    env = dict(os.environ)
    env.update(FLOW_GATE_CPP_DIR="", CLAUDE_PLUGIN_ROOT="")
    got = subprocess.run(
        ["bash", str(SCRIPT), "--plan", plan],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120,
    )
    out = got.stdout + got.stderr
    assert "deterministic runner unavailable" in out, "precondition: the fallback lane ran"
    if expect_fail:
        assert got.returncode == 1, out
    else:
        assert got.returncode != 1, out
        assert "make verify" not in out, out


# --------------------------------------------------------------------------- #
# The CI pull_request step (issue #1452). The mode's verdicts are scored by
# controls/counter-model-enrolment-ci; these pin the step's three load-bearing
# properties, each of which the mode cannot see from inside.
# --------------------------------------------------------------------------- #

def _enrolment_step() -> dict:
    yaml = pytest.importorskip("yaml")
    pipeline = yaml.safe_load((ROOT / ".woodpecker.yml").read_text(encoding="utf-8"))
    return pipeline["steps"]["counter-model-enrolment"]


def test_ci_enrolment_step_runs_on_pull_requests_only() -> None:
    """A main push would red every merged PR: squash-merging removes the
    branch commits, so ancestry answers no for every receipt."""
    assert _enrolment_step()["when"] == [{"event": "pull_request"}]


def test_ci_enrolment_step_deepens_history_before_deciding() -> None:
    """On the depth-1 clone the mode answers undecidable (exit 5), so a step that
    skipped the fetch could never pass - and one that tolerated exit 5 could
    never fail. The fetch must come first, and nothing may swallow the gate's
    exit."""
    commands = _enrolment_step()["commands"]
    fetch = next(i for i, c in enumerate(commands) if "--unshallow" in c)
    gate = next(i for i, c in enumerate(commands) if "--enrolment-only" in c)
    assert fetch < gate
    assert "|| true" not in commands[gate] and ";" not in commands[gate]


def test_ci_enrolment_step_names_the_source_branch() -> None:
    """Without --branch, a detached checkout matches by ancestry alone and a
    receipt recorded for another branch satisfies this PR."""
    gate = next(c for c in _enrolment_step()["commands"] if "--enrolment-only" in c)
    assert '--branch "$CI_COMMIT_SOURCE_BRANCH"' in gate


@requires_git
@requires_bash
def test_branch_without_enrolment_only_is_a_usage_error(tmp_path: Path) -> None:
    proc = subprocess.run(["bash", str(SCRIPT), "--branch", "x"], cwd=tmp_path,
                          capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "--branch is only meaningful with --enrolment-only" in proc.stderr


@requires_git
@requires_bash
@pytest.mark.parametrize("args", [["--enrolment-only", "--branch="], ["--enrolment-only", "--branch", ""]])
def test_an_empty_branch_is_refused_not_ignored(tmp_path: Path, args: list[str]) -> None:
    """Counter-model review: an empty override used to be dropped silently, so an
    unset $CI_COMMIT_SOURCE_BRANCH turned the CI step into ancestry-only."""
    proc = subprocess.run(["bash", str(SCRIPT), *args], cwd=tmp_path,
                          capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "--branch was given an empty value" in proc.stderr


@requires_git
@requires_bash
def test_plan_check_does_not_exempt_enrolment_only(tmp_path: Path) -> None:
    """Counter-model red case: `--plan check` exempts a FINISH run (it produces no
    PR), but the CI mode is asked about a PR and must still decide."""
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=tmp_path, env=env, check=True)
    (tmp_path / "docs" / "measurements" / "counter-model").mkdir(parents=True)
    (tmp_path / "docs" / "measurements" / "counter-model" / ".keep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, env=env, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, env=env, check=True)
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--plan", "check", "--enrolment-only", "--branch", "issue-9-pr"],
        cwd=tmp_path, env=env, capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "FLOW_FINISH_GATE: fail (counter-model line missing)" in proc.stdout


@requires_bash
@requires_git
@pytest.mark.skipif(shutil.which("python3") is None, reason="requires python3 on PATH")
@pytest.mark.parametrize("case", ["good-fail-fix-resume", "bad-makefile-changed-between-runs"])
@pytest.mark.parametrize("state_count", [0, 1, 2])
def test_resume_stub_requires_exactly_one_state_file(
    tmp_path: Path, case: str, state_count: int,
) -> None:
    """Hardening: fresh case runs do not currently produce ambiguous state.

    A scratch phase-one driver plants state files just before the real stub
    reads them. Two files must refuse; one must reach the resume.
    """
    source = ROOT / "controls/flow-finish-gate-resume/cases" / case
    scratch = tmp_path / "case"
    shutil.copytree(source, scratch)
    # A controlled git shim selects the non-repository state location even if
    # the pytest temporary directory happens to sit below a checkout.
    bindir = tmp_path / "bin"
    bindir.mkdir()
    git = bindir / "git"
    git.write_text("#!/bin/sh\nexit 1\n")
    git.chmod(0o755)
    phase_one = scratch / "phase_one.py"
    phase_one.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "state = Path('.claude/runs')\n"
        "state.mkdir(parents=True, exist_ok=True)\n"
        f"for index in range({state_count}):\n"
        "    (state / f'{index}.json').write_text('{\"status\": \"not-run\"}')\n"
        "print('phase-driver-ran')\n"
        "sys.exit(1)\n"
    )
    assert not (scratch / ".phase1-done").exists()
    assert not list(scratch.glob(".claude/runs/*.json"))
    result = subprocess.run(
        ["bash", str(scratch / "bin/uv"), "--project", str(ROOT), "python3", str(phase_one)],
        cwd=scratch, env=dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}"),
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert len(list(scratch.glob(".claude/runs/*.json"))) == state_count
    if state_count == 2:
        assert result.returncode == 9, result.stderr
        assert "holds 2 state\n  files; this case cannot tell which one phase 1 produced." in result.stderr
    elif state_count == 0:
        assert result.returncode == 9, result.stderr
        assert "*.json state file, so phase 2 would be a FRESH run, not a resume." in result.stderr
    else:
        assert result.returncode == 1, result.stderr
        assert "precondition ok" in result.stderr
        assert "PHASE 2" in result.stderr
        assert "PRECONDITION FAILED" not in result.stderr


@requires_git
@requires_bash
@pytest.mark.parametrize("signal", [None, "", "0", "unknown", "true", "1"])
def test_coordination_supervises_full_gate_once_only_when_enabled(tmp_path: Path, signal: str | None):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    supervisor = bindir / "supervisor"
    supervisor.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$(dirname "$0")/supervisor.log"\n'
        '[[ "$1" == run && "$2" == full-suite && "$3" == --wait && "$4" == 3600 && "$5" == -- ]] || exit 92\n'
        'shift 5\nexec "$@"\n'
    )
    supervisor.chmod(0o755)
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    extra = {"CPP_KYLE_LOCK_BIN": str(supervisor)}
    if signal is not None:
        extra["CPP_KYLE_COORDINATION_ADMISSION"] = signal
    proc, _ = _run(tmp_path, cpp_dir="", make_exit=0, extra_env=extra)
    assert proc.returncode == 0, proc.stdout
    log = bindir / "supervisor.log"
    assert (len(log.read_text().splitlines()) if log.exists() else 0) == (1 if signal == "1" else 0)
    assert (bindir / "make.log").read_text().splitlines() == ["lint", "test", "typecheck", "verify"]
    assert proc.stdout.count("FLOW_FINISH_GATE_EXIT=0") == 1


@requires_git
@requires_bash
@pytest.mark.parametrize("supervisor_exit", [75, 3, 2, 10, 11, 0])
def test_coordination_refusal_starts_no_gate_work(tmp_path: Path, supervisor_exit: int):
    # kyle-lock's own codes overlap the gate's: refused 3 would read as warn and
    # usage 2 as usage. A supervisor that never ran the gate - whatever it exits,
    # 0 included - must be one fail with one exit line, and no gate work.
    supervisor = tmp_path / "refuse"
    supervisor.write_text(f"#!/usr/bin/env bash\nexit {supervisor_exit}\n")
    supervisor.chmod(0o755)
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    proc, bindir = _run(tmp_path, cpp_dir="", make_exit=0, extra_env={
        "CPP_KYLE_COORDINATION_ADMISSION": "1", "CPP_KYLE_LOCK_BIN": str(supervisor)})
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not (bindir / "make.log").exists()
    if supervisor_exit == 75:
        assert "FLOW_FINISH_GATE: fail (coordination unavailable: exit 75; " in proc.stdout
    else:
        assert f"FLOW_FINISH_GATE: fail (coordination supervisor exited {supervisor_exit} " in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    exit_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLOW_FINISH_GATE_EXIT=")]
    assert exit_lines == ["FLOW_FINISH_GATE_EXIT=1"], proc.stdout
    assert proc.stdout.splitlines()[-1] == "FLOW_FINISH_GATE_EXIT=1"


def _bounded_authority(path: Path, state: str) -> None:
    """A fake kyle-lock that behaves like the real one around --wait (#1678).

    Unavailable with no --wait never returns, as the real client does; with
    --wait it gives up at the bound, prints its last answer and exits 75.
    """
    path.write_text(
        "#!/usr/bin/env bash\n"
        '[[ "$1" == run && "$2" == full-suite ]] || exit 92\n'
        "shift 2\nwait=\n"
        'if [[ "$1" == --wait ]]; then wait="$2"; shift 2; fi\n'
        '[[ "$1" == -- ]] || exit 92\nshift\n'
        + ('exec "$@"\n' if state == "held" else
           '[[ -n "$wait" ]] || exec sleep 600\n'
           'sleep "$wait"\n'
           'printf \'{"state": "unavailable", "code": "authority_down", "reason": "refused"}\\n\'\n'
           "exit 75\n")
    )
    path.chmod(0o755)


@requires_git
@requires_bash
def test_coordination_unavailable_authority_ends_within_the_bound_by_name(tmp_path: Path):
    # Regression for #1678: without a bounded --wait this fake never returns and
    # the run dies on the subprocess timeout instead of printing a verdict.
    supervisor = tmp_path / "authority"
    _bounded_authority(supervisor, "unavailable")
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    flag = tmp_path / "coordination-flag"
    flag.write_text("on\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _make_stub(bindir, "make", 0)
    env = os.environ.copy()
    for key in ("CPP_KYLE_FULL_SUITE_ACTIVE", "CPP_FLOW_FINISH_GATE_STATUS_FILE"):
        env.pop(key, None)
    env.update({"CPP_COORDINATION_ADMISSION_FILE": str(flag), "CPP_KYLE_LOCK_BIN": str(supervisor),
                "CPP_KYLE_LOCK_WAIT_SECONDS": "1", "FLOW_GATE_CPP_DIR": "",
                "PATH": f"{bindir}:{env['PATH']}"})
    proc = subprocess.run(["bash", str(SCRIPT)], cwd=tmp_path, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, timeout=20)
    assert proc.returncode == 1, proc.stdout
    assert ("FLOW_FINISH_GATE: fail (coordination unavailable: authority_down; "
            "no grant within 1s, no gate work started)") in proc.stdout
    assert not (bindir / "make.log").exists()
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout and "skipped" not in proc.stdout
    assert proc.stdout.splitlines()[-1] == "FLOW_FINISH_GATE_EXIT=1"


@requires_git
@requires_bash
def test_coordination_held_authority_runs_the_gate_under_the_bound(tmp_path: Path):
    supervisor = tmp_path / "authority"
    _bounded_authority(supervisor, "held")
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    proc, bindir = _run(tmp_path, cpp_dir="", make_exit=0, extra_env={
        "CPP_KYLE_COORDINATION_ADMISSION": "1", "CPP_KYLE_LOCK_BIN": str(supervisor),
        "CPP_KYLE_LOCK_WAIT_SECONDS": "1"})
    assert proc.returncode == 0, proc.stdout
    assert (bindir / "make.log").read_text().splitlines() == ["lint", "test", "typecheck", "verify"]


@requires_git
@requires_bash
@pytest.mark.parametrize("bound", ["0", "-5", "forever", "1.5", ""])
def test_coordination_wait_bound_is_validated_only_when_admission_is_on(tmp_path: Path, bound: str):
    supervisor = tmp_path / "authority"
    _bounded_authority(supervisor, "held")
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    extra = {"CPP_KYLE_LOCK_BIN": str(supervisor), "CPP_KYLE_LOCK_WAIT_SECONDS": bound}
    off, bindir = _run(tmp_path, cpp_dir="", make_exit=0, extra_env=dict(extra))
    assert off.returncode == 0, off.stdout  # admission off: the variable is inert
    (bindir / "make.log").unlink()
    on, _ = _run(tmp_path, cpp_dir="", make_exit=0,
                 extra_env={**extra, "CPP_KYLE_COORDINATION_ADMISSION": "1"})
    if bound == "":  # empty means unset: the default applies
        assert on.returncode == 0, on.stdout
        return
    assert on.returncode == 1, on.stdout
    assert "FLOW_FINISH_GATE: fail (coordination wait bound invalid: " in on.stdout
    assert not (bindir / "make.log").exists()


@requires_git
@requires_bash
def test_coordination_interrupted_parent_removes_its_temp_files(tmp_path: Path):
    import signal
    import time

    bindir = tmp_path / "bin"
    bindir.mkdir()
    started = tmp_path / "supervisor-started"
    supervisor = bindir / "supervisor"
    supervisor.write_text(f'#!/usr/bin/env bash\ntouch "{started}"\nexec sleep 60\n')
    supervisor.chmod(0o755)
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    flag = tmp_path / "coordination-flag"
    flag.write_text("on\n")
    env = os.environ.copy()
    for key in ("CPP_KYLE_FULL_SUITE_ACTIVE", "CPP_FLOW_FINISH_GATE_STATUS_FILE"):
        env.pop(key, None)
    env.update({"CPP_COORDINATION_ADMISSION_FILE": str(flag), "CPP_KYLE_LOCK_BIN": str(supervisor),
                "TMPDIR": str(scratch), "FLOW_GATE_CPP_DIR": "", "PATH": f"{bindir}:{env['PATH']}"})
    proc = subprocess.Popen(["bash", str(SCRIPT)], cwd=tmp_path, env=env, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 15
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert started.exists(), "the supervisor never started"
        created = sorted(f.name for f in scratch.iterdir())
        assert any(n.startswith("flow-finish-gate-coordination.") for n in created), created
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=15)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    assert sorted(f.name for f in scratch.iterdir()) == []


@requires_git
@requires_bash
def test_coordination_writers_outliving_the_parent_cannot_recreate_its_files(tmp_path: Path):
    # Only the parent is stopped; the supervisor and the continued gate run on
    # and finish afterwards. Their late status and verdict writes must not
    # recreate anything the parent's cleanup removed.
    import signal
    import time

    bindir = tmp_path / "bin"
    bindir.mkdir()
    _make_stub(bindir, "make", 0)
    started, go, done = tmp_path / "started", tmp_path / "go", tmp_path / "done"
    supervisor = bindir / "supervisor"
    supervisor.write_text(
        "#!/usr/bin/env bash\n"
        f'touch "{started}"\n'
        f'while [[ ! -e "{go}" ]]; do sleep 0.05; done\n'
        'shift 5\n"$@"\n'
        f'touch "{done}"\n'
    )
    supervisor.chmod(0o755)
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    flag = tmp_path / "coordination-flag"
    flag.write_text("on\n")
    env = os.environ.copy()
    for key in ("CPP_KYLE_FULL_SUITE_ACTIVE", "CPP_FLOW_FINISH_GATE_STATUS_FILE"):
        env.pop(key, None)
    env.update({"CPP_COORDINATION_ADMISSION_FILE": str(flag), "CPP_KYLE_LOCK_BIN": str(supervisor),
                "TMPDIR": str(scratch), "FLOW_GATE_CPP_DIR": "", "PATH": f"{bindir}:{env['PATH']}"})
    proc = subprocess.Popen(["bash", str(SCRIPT)], cwd=tmp_path, env=env, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 15
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert started.exists(), "the supervisor never started"
        assert any(n.startswith("flow-finish-gate-coordination.") for n in (f.name for f in scratch.iterdir()))
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=15)
        assert sorted(f.name for f in scratch.iterdir()) == [], "the parent did not clean up"
        go.touch()
        deadline = time.monotonic() + 30
        while not done.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert done.exists(), "the continued gate never finished"
        time.sleep(0.5)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    assert sorted(str(f.relative_to(scratch)) for f in scratch.rglob("*")) == []


@requires_git
@requires_bash
@pytest.mark.parametrize(("supervisor_tail", "gate_exit", "expected"), [
    ("exit $rc", 0, 0), ("exit $rc", 1, 1), ("exit 12", 0, 1), ("exit 13", 0, 1)])
def test_coordination_passes_the_gate_verdict_only_when_the_supervisor_agrees(
    tmp_path: Path, supervisor_tail: str, gate_exit: int, expected: int
):
    # A lease lost (12) or an unconfirmed stop (13) after a green gate is not a
    # green gate. Either way there is exactly one exit line, from the parent.
    supervisor = tmp_path / "supervisor"
    supervisor.write_text(
        "#!/usr/bin/env bash\n"
        '[[ "$1 $2 $3 $5" == "run full-suite --wait --" ]] || exit 92\n'
        f'shift 5\n"$@"\nrc=$?\n{supervisor_tail}\n'
    )
    supervisor.chmod(0o755)
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    proc, bindir = _run(tmp_path, cpp_dir="", make_exit=gate_exit, extra_env={
        "CPP_KYLE_COORDINATION_ADMISSION": "1", "CPP_KYLE_LOCK_BIN": str(supervisor)})
    assert (bindir / "make.log").exists(), "the gate must have run under the supervisor"
    assert proc.returncode == expected, proc.stdout + proc.stderr
    if supervisor_tail != "exit $rc":
        assert "lease lost or stop unconfirmed" in proc.stdout
    exit_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLOW_FINISH_GATE_EXIT=")]
    assert exit_lines == [f"FLOW_FINISH_GATE_EXIT={expected}"], proc.stdout
    verdicts = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLOW_FINISH_GATE: ")]
    want = "FLOW_FINISH_GATE: ok" if expected == 0 else "FLOW_FINISH_GATE: fail"
    assert len(verdicts) == 1 and verdicts[0].startswith(want), verdicts


@requires_git
@requires_bash
@pytest.mark.parametrize("mode", ["--enrolment-only", "--check-summary", "--help"])
def test_coordination_metadata_never_acquires(tmp_path: Path, mode: str):
    supervisor = tmp_path / "unexpected-supervisor"
    proc, _ = _run(tmp_path, mode, cpp_dir="", extra_env={
        "CPP_KYLE_COORDINATION_ADMISSION": "1", "CPP_KYLE_LOCK_BIN": str(supervisor)})
    assert str(supervisor) not in proc.stdout


@requires_git
@requires_bash
def test_coordination_missing_supervisor_refuses_before_work(tmp_path: Path):
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    proc, bindir = _run(tmp_path, cpp_dir="", make_exit=0, extra_env={
        "CPP_KYLE_COORDINATION_ADMISSION": "1", "CPP_KYLE_LOCK_BIN": str(tmp_path / "absent")})
    assert proc.returncode != 0
    assert not (bindir / "make.log").exists()


@requires_git
@requires_bash
def test_coordination_continuation_keeps_one_lease_and_hides_authority_credentials(tmp_path: Path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    supervisor = bindir / "supervisor"
    supervisor.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$(dirname "$0")/supervisor.log"\n'
        '[[ "$KYLE_LOCK_TOKEN" == synthetic-supervisor-only ]] || exit 93\n'
        'shift 5\nexec "$@"\n'
    )
    supervisor.chmod(0o755)
    make = bindir / "make"
    make.write_text(
        "#!/usr/bin/env bash\n"
        '[[ ! -v KYLE_LOCK_URL && ! -v KYLE_LOCK_TOKEN && ! -v KYLE_LOCK_TOKEN_FILE ]] || exit 94\n'
        'printf "%s\\n" "$1" >> "$(dirname "$0")/make.log"\n'
        'if [[ "$1" == test && "${CPP_NESTED_PROBE:-}" != 1 ]]; then\n'
        f'  CPP_NESTED_PROBE=1 bash "{SCRIPT}" --plan check\n'
        'fi\n'
    )
    make.chmod(0o755)
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    # Run directly: _run's one-marker assertion deliberately excludes a nested
    # invocation, which has its own distinct verdict in this test transcript.
    env = os.environ.copy()
    env.update({"PATH": f"{bindir}:{env['PATH']}", "FLOW_GATE_CPP_DIR": "",
                "CPP_KYLE_COORDINATION_ADMISSION": "1", "CPP_KYLE_LOCK_BIN": str(supervisor),
                "KYLE_LOCK_TOKEN": "synthetic-supervisor-only", "KYLE_LOCK_URL": "http://invalid.example",
                "KYLE_LOCK_TOKEN_FILE": "synthetic-file"})
    env.pop("CPP_KYLE_FULL_SUITE_ACTIVE", None)
    flag = tmp_path / "coordination-flag"
    flag.write_text("on\n")
    env["CPP_COORDINATION_ADMISSION_FILE"] = str(flag)
    env.pop("CPP_KYLE_COORDINATION_ADMISSION", None)
    result = subprocess.run(["bash", str(SCRIPT)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len((bindir / "supervisor.log").read_text().splitlines()) == 1
    assert (bindir / "make.log").read_text().splitlines() == [
        "lint", "test", "lint", "test", "typecheck", "typecheck", "verify"]


@requires_bash
@pytest.mark.skipif(shutil.which("cmp") is None, reason="requires cmp for exact flag bytes")
@pytest.mark.parametrize("content", [None, b"", b"garbage\n", b"on", b"on\n\n", b"on\x00\n", b"on\n"])
def test_coordination_flag_exact_bytes_and_silent_off(tmp_path: Path, content: bytes | None):
    flag = tmp_path / "flag"
    if content is not None:
        flag.write_bytes(content)
    env = dict(os.environ, CPP_COORDINATION_ADMISSION_FILE=str(flag))
    result = subprocess.run(["bash", "-c", '. "$1"; coordination_admission_on', "probe",
                             str(ROOT / "scripts/coordination-admission.sh")],
                            env=env, capture_output=True, text=True, timeout=5)
    assert result.returncode == (0 if content == b"on\n" else 1)
    assert result.stdout == result.stderr == ""


@requires_bash
def test_coordination_unreadable_flag_is_silently_off():
    # If the test itself is root, read as an unprivileged process so chmod(0)
    # actually makes the input unreadable. A root-only access check is blind.
    lower_privileges = None
    if os.geteuid() == 0:
        import pwd
        account = pwd.getpwnam("nobody")

        def lower_privileges():
            os.setgroups([])
            os.setgid(account.pw_gid)
            os.setuid(account.pw_uid)

    with tempfile.TemporaryDirectory(prefix="cpp-unreadable-flag-") as directory:
        root = Path(directory)
        root.chmod(0o755)
        flag = root / "flag"
        flag.write_bytes(b"on\n")
        flag.chmod(0)
        command = (ROOT / "scripts/coordination-admission.sh").read_text()
        result = subprocess.run(["bash", "-c", command + '\n[[ ! -r "$CPP_COORDINATION_ADMISSION_FILE" ]] || exit 91; '
                                'coordination_admission_on'],
                                env=dict(os.environ, CPP_COORDINATION_ADMISSION_FILE=str(flag)),
                                preexec_fn=lower_privileges, capture_output=True, text=True, timeout=5)
        flag.chmod(0o600)
        assert result.returncode == 1
        assert result.stdout == result.stderr == ""


@requires_bash
def test_coordination_flag_symlink_is_off_and_changes_are_observed_per_call(tmp_path: Path):
    flag = tmp_path / "flag"
    target = tmp_path / "target"
    target.write_bytes(b"on\n")
    flag.symlink_to(target)
    helper = ROOT / "scripts/coordination-admission.sh"
    result = subprocess.run(["bash", "-c", '. "$1"; coordination_admission_on', "probe", str(helper)],
                            env=dict(os.environ, CPP_COORDINATION_ADMISSION_FILE=str(flag)),
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 1
    flag.unlink()
    # One process calls the same loaded function before and after the owner
    # changes its flag; a cached environment snapshot would miss this switch.
    result = subprocess.run(["bash", "-c", '. "$1"; coordination_admission_on && exit 90; '
                             'printf "on\\n" > "$CPP_COORDINATION_ADMISSION_FILE"; coordination_admission_on',
                             "probe", str(helper)], env=dict(os.environ, CPP_COORDINATION_ADMISSION_FILE=str(flag)),
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


@requires_git
@requires_bash
@pytest.mark.parametrize("content", [None, b"", b"garbage\n"])
@pytest.mark.parametrize("gate_exit", [0, 1])
def test_coordination_off_is_byte_exact_prechange_behavior(tmp_path: Path, content: bytes | None, gate_exit: int):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _make_stub(bindir, "make", gate_exit)
    (tmp_path / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    flag = tmp_path / "flag"
    if content is not None:
        flag.write_bytes(content)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FLOW_GATE_CPP_DIR="",
               CLAUDE_PLUGIN_ROOT=str(ROOT), CPP_COORDINATION_ADMISSION_FILE=str(flag))
    env.pop("CPP_KYLE_FULL_SUITE_ACTIVE", None)
    anchor = ROOT / "controls/flow-finish-coordination/anchors/6bc585a-flow-finish-gate.sh"
    old = subprocess.run(["bash", str(anchor)], cwd=tmp_path, env=env,
                         capture_output=True, timeout=10)
    old_calls = (bindir / "make.log").read_bytes()
    (bindir / "make.log").unlink()
    new = subprocess.run(["bash", str(SCRIPT)], cwd=tmp_path, env=env,
                         capture_output=True, timeout=10)
    assert (new.returncode, new.stdout, new.stderr) == (old.returncode, old.stdout, old.stderr)
    assert (bindir / "make.log").read_bytes() == old_calls


@requires_bash
@pytest.mark.parametrize("xdg", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_coordination_default_uses_only_dedicated_folder(tmp_path: Path, xdg: bool, enabled: bool):
    home = tmp_path / "operator-home"
    config = tmp_path / "xdg-config" if xdg else home / ".config"
    folder = config / "claude-power-pack" / "coordination"
    folder.mkdir(parents=True)
    # The old sibling flag is deliberately the opposite value. It must never
    # control admission after moving to the dedicated directory contract.
    (folder.parent / "coordination-admission").write_bytes(b"garbage\n" if enabled else b"on\n")
    (folder / "admission").write_bytes(b"on\n" if enabled else b"garbage\n")
    env = dict(os.environ, HOME=str(home))
    env.pop("CPP_COORDINATION_ADMISSION_FILE", None)
    env.pop("XDG_CONFIG_HOME", None)
    if xdg:
        env["XDG_CONFIG_HOME"] = str(config)
    result = subprocess.run(["bash", "-c", '. "$1"; coordination_admission_on', "probe",
                             str(ROOT / "scripts/coordination-admission.sh")],
                            env=env, capture_output=True, text=True, timeout=5)
    assert result.returncode == (0 if enabled else 1)
    assert result.stdout == result.stderr == ""


@requires_bash
def test_coordination_directory_replacement_and_removal_are_observed(tmp_path: Path):
    home = tmp_path / "operator-home"
    folder = home / ".config" / "claude-power-pack" / "coordination"
    folder.mkdir(parents=True)
    env = dict(os.environ, HOME=str(home))
    env.pop("CPP_COORDINATION_ADMISSION_FILE", None)
    env.pop("XDG_CONFIG_HOME", None)
    command = ('. "$1"; coordination_admission_on && exit 90; '
               'printf "on\\n" > "$2/replacement"; mv "$2/replacement" "$2/admission"; '
               'coordination_admission_on || exit 91; rm "$2/admission"; '
               'coordination_admission_on && exit 92; exit 0')
    result = subprocess.run(["bash", "-c", command, "probe",
                             str(ROOT / "scripts/coordination-admission.sh"), str(folder)],
                            env=env, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""


# ── --help prints the header, by marker, and nothing else (issue #1692) ─────
#
# `--help` used to print a NUMBERED line range of the script (`sed -n 2,90p`),
# so any edit to the header silently changed what it printed: a shorter header
# would print code, and the range already stopped before the environment table.
# It now prints from line 2 to an explicit `#: END-HELP` marker.

HELP_TABLES = {
    "usage": "flow-finish-gate.sh --plan check",
    "verdict": "FLOW_FINISH_GATE: ok | fail | warn | skipped",
    "exit-code": "verdict  exit  meaning",
    "environment": "FLOW_GATE_CPP_DIR",
}
HELP_CODE_SENTINELS = ("set -uo pipefail", "coordination_admission_on()", "END-HELP")


@requires_bash
@requires_git
def test_help_prints_all_four_tables_and_no_code() -> None:
    """A shorter help that silently drops a table is the failure to guard, and
    so is one that runs past the header into the script's code."""
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.strip(), "--help printed nothing"
    for table, needle in HELP_TABLES.items():
        assert needle in out, f"--help no longer prints the {table} table ({needle!r})"
    for sentinel in HELP_CODE_SENTINELS:
        assert sentinel not in out, f"--help printed past the header: {sentinel!r}"
    # The header is all comment lines, so every source line --help printed must
    # have been one: its output is exactly the lines between line 2 and the marker.
    source = SCRIPT.read_text().splitlines()
    end = source.index("#: END-HELP")
    assert all(line.startswith("#") for line in source[1:end]), (
        "a non-comment line sits inside the --help range"
    )
    assert len(out.splitlines()) == end - 1


# ── An exit nobody announced never reports a clean status (issue #1705) ─────
#
# The gate's EXIT trap also runs when the gate is killed, and `$?` is then the
# status of the last command that completed - usually 0 - so an interrupted
# gate printed `FLOW_FINISH_GATE_EXIT=0`. It now prints 128 for any exit that
# was not the `exit` builtin. No signal is trapped: the gate must still stop
# promptly when stopped alone, which the coordination and late-tee tests above
# pin and which a signal trap would break.

UNANNOUNCED_EXIT = 128


def _gate_killed_mid_run(
    tmp_path: Path, sig: int, *, group: bool, extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Start a gate whose runner blocks, signal it, and return what it left.

    `group=True` delivers to the gate's whole process group, as Ctrl-C and
    `timeout` do; `group=False` delivers to the gate's pid alone.
    """
    import signal as _signal
    import time

    cpp = _fake_cpp(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    started = tmp_path / "runner-started"
    # `exec`, so no shell is left in the group to print its own "Terminated"
    # onto the stderr the gate shares with it.
    (bindir / "uv").write_text(f'#!/usr/bin/env bash\n: > "{started}"\nexec sleep 30\n')
    (bindir / "uv").chmod(0o755)
    env = os.environ.copy()
    env.pop("FLOW_GATE_RERUN", None)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FLOW_GATE_CPP_DIR"] = str(cpp)
    for key in ("CPP_KYLE_FULL_SUITE_ACTIVE", "CPP_FLOW_FINISH_GATE_STATUS_FILE"):
        env.pop(key, None)
    # A host whose coordination admission is ON would route this gate through
    # the real kyle-lock instead of the stub runner: point it at a file that
    # does not exist, so the fixture owns the answer (counter-model review).
    env["CPP_COORDINATION_ADMISSION_FILE"] = str(tmp_path / "no-coordination-admission")
    env.update(extra_env or {})
    proc = subprocess.Popen(
        ["bash", str(SCRIPT)], cwd=tmp_path, env=env, start_new_session=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert started.exists(), "precondition: the runner never started"
        if group:
            os.killpg(proc.pid, sig)
        else:
            proc.send_signal(sig)
        # Promptness is part of the claim: well under the runner's 30s sleep.
        # wait(), not communicate(): a runner left running still holds the
        # pipes open, and EOF would not come until it ended.
        returncode = proc.wait(timeout=10)
    finally:
        try:
            os.killpg(proc.pid, _signal.SIGKILL)
        except ProcessLookupError:
            pass
    stdout, stderr = proc.communicate(timeout=10)
    return subprocess.CompletedProcess(proc.args, returncode, stdout, stderr)


@requires_bash
@requires_git
@pytest.mark.parametrize("signame", ["SIGTERM", "SIGINT", "SIGHUP"])
def test_a_gate_killed_mid_run_reports_128_once_and_still_dies_by_the_signal(
    tmp_path: Path, signame: str,
) -> None:
    """RED on the pre-#1705 script: the marker read 0, the status of whatever
    completed last, on a gate that never reached a verdict."""
    import signal

    sig = getattr(signal, signame)
    result = _gate_killed_mid_run(tmp_path, sig, group=True)
    assert "running deterministic gate" in result.stdout, "precondition: killed mid-run"
    assert "FLOW_FINISH_GATE: " not in result.stdout, "precondition: before any verdict"
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    markers = [line for line in lines if line.startswith("FLOW_FINISH_GATE_EXIT=")]
    assert markers == [f"FLOW_FINISH_GATE_EXIT={UNANNOUNCED_EXIT}"], result.stderr
    # NOT asserted: that the line is LAST on stderr. On a group kill bash itself
    # reports the dead pipeline AFTER the EXIT trap has run ("Terminated", or a
    # "Hangup ... | tee /dev/fd/9" job notice). Measured on the pre-#1705 script
    # too: 12 of 12 runs for SIGTERM, 6 of 12 for SIGHUP, 0 of 12 for SIGINT. So
    # the claim pinned here is narrower and true: nothing follows the line
    # except bash's own notice about the killed job.
    after = lines[lines.index(markers[0]) + 1:]
    assert all(
        "Terminated" in line or "Hangup" in line or line.rstrip().endswith("| tee /dev/fd/9")
        for line in after
    ), after
    # Dies BY the signal, exactly as before: no handler turned it into an exit.
    assert result.returncode == -sig


@requires_bash
@requires_git
def test_a_gate_stopped_alone_stops_promptly_and_reports_128(tmp_path: Path) -> None:
    """SIGTERM to the gate's pid ALONE, the runner left running: the gate must
    not wait for its child (a signal trap would make it), and its line reads 128."""
    import signal

    result = _gate_killed_mid_run(tmp_path, signal.SIGTERM, group=False)
    assert result.returncode == -signal.SIGTERM
    assert result.stderr.strip().splitlines()[-1] == f"FLOW_FINISH_GATE_EXIT={UNANNOUNCED_EXIT}"


@requires_bash
@requires_git
def test_a_continued_gate_killed_mid_run_records_128_in_its_status_file(tmp_path: Path) -> None:
    """The coordination lane (kyle#2130): a gate continued under the supervisor
    writes its status to a private file and prints no exit line. Killed mid-run
    it recorded the stale 0 there; it must record 128."""
    import signal

    status_file = tmp_path / "continued-status"
    result = _gate_killed_mid_run(
        tmp_path, signal.SIGTERM, group=False,
        extra_env={
            "CPP_KYLE_FULL_SUITE_ACTIVE": "1",
            "CPP_FLOW_FINISH_GATE_STATUS_FILE": str(status_file),
        },
    )
    assert result.returncode == -signal.SIGTERM
    assert status_file.read_text().strip() == str(UNANNOUNCED_EXIT)
    assert "FLOW_FINISH_GATE_EXIT=" not in result.stderr, "a continued gate prints no exit line"


@requires_bash
@requires_git
def test_an_announced_exit_never_reports_128(tmp_path: Path) -> None:
    """The must-not-flip side: a deliberate exit keeps its own status. A real
    pass printing 128 would be a worse lie than the one being fixed."""
    usage = subprocess.run(
        ["bash", str(SCRIPT), "--no-such-flag"], cwd=tmp_path, capture_output=True, text=True,
    )
    assert usage.returncode == 2
    assert usage.stderr.strip().splitlines()[-1] == "FLOW_FINISH_GATE_EXIT=2"
    helped = subprocess.run(
        ["bash", str(SCRIPT), "--help"], cwd=tmp_path, capture_output=True, text=True,
    )
    assert helped.returncode == 0
    assert helped.stderr.strip().splitlines()[-1] == "FLOW_FINISH_GATE_EXIT=0"


def _mutated_gate_killed_while_running(tmp_path: Path, injected: str, stub_name: str | None) -> str:
    """Run a copy of the gate with `injected` added after gate_map, kill it
    while that line is the executing command, and return its exit line."""
    import signal
    import time

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for lib in ("gate-lib.sh", "coordination-admission.sh"):
        shutil.copy(SCRIPT.parent / lib, scripts / lib)
    started = tmp_path / "mutant-started"
    body = SCRIPT.read_text()
    marker = "\ngate_map "
    assert body.count(marker) == 1, "precondition: one gate_map line to inject after"
    head, tail = body.split(marker)
    first_line, rest = tail.split("\n", 1)
    (scripts / "flow-finish-gate.sh").write_text(
        f'{head}{marker}{first_line}\n: > "{started}"\n{injected}\n{rest}'
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    if stub_name:
        (bindir / stub_name).write_text("#!/usr/bin/env bash\nexec sleep 30\n")
        (bindir / stub_name).chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["CPP_COORDINATION_ADMISSION_FILE"] = str(tmp_path / "no-coordination-admission")
    for key in ("CPP_KYLE_FULL_SUITE_ACTIVE", "CPP_FLOW_FINISH_GATE_STATUS_FILE"):
        env.pop(key, None)
    proc = subprocess.Popen(
        ["bash", str(scripts / "flow-finish-gate.sh")], cwd=tmp_path, env=env,
        start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert started.exists(), "precondition: the injected line was never reached"
        time.sleep(0.3)  # let the shell move from the marker line onto the injected command
        proc.send_signal(signal.SIGTERM)
        returncode = proc.wait(timeout=10)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    _, stderr = proc.communicate(timeout=10)
    assert returncode == -signal.SIGTERM, "precondition: died by the signal, mid-command"
    return [line for line in stderr.splitlines() if line.startswith("FLOW_FINISH_GATE_EXIT=")][-1]


@requires_bash
@requires_git
@pytest.mark.parametrize("injected,stub_name", [
    ("exit_handler --now", "exit_handler"),   # a COMMAND whose name starts with `exit`
    ("exit_code=$(sleep 30)", None),          # an ASSIGNMENT whose name starts with `exit`
    ("exitcode --flush", "exitcode"),         # no separator at all after the four letters
])
def test_only_the_exit_builtin_as_a_whole_word_counts_as_announced(
    tmp_path: Path, injected: str, stub_name: str | None,
) -> None:
    """`exit` alone or `exit <args>` announces; anything that merely STARTS with
    those letters does not. Killed while such a command is executing, the gate
    must still read 128 - a prefix match would report the stale status."""
    line = _mutated_gate_killed_while_running(tmp_path, injected, stub_name)
    assert line == f"FLOW_FINISH_GATE_EXIT={UNANNOUNCED_EXIT}"


def test_the_gate_never_replaces_its_shell_with_exec() -> None:
    """The other way out of a bash script that is not the exit builtin: `exec
    <program>` replaces the shell and the EXIT trap never runs at all. `exec`
    may appear here only as a descriptor redirection."""
    execs = [
        line.strip() for line in SCRIPT.read_text().splitlines()
        if re.match(r"\s*exec\b", line)
    ]
    assert execs, "precondition: the script still has its fd-9 redirections to look at"
    for line in execs:
        assert re.fullmatch(r"exec \d+>(&-|\S+)", line), f"exec that is not a redirection: {line}"


def test_the_gate_never_ends_by_running_off_its_last_line() -> None:
    """Announcement is "the shell was executing `exit`". A script that ended by
    falling off its last line would be an unannounced exit and print 128 for a
    real result, so its last statement must be an exit."""
    statements = [
        line.strip() for line in SCRIPT.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert statements[-1].startswith(("gate_exit ", "exit ")), statements[-1]
    assert UNANNOUNCED_EXIT not in {0, 1, 2, 3, 4, 5, 64}, "128 must not be a status the gate announces"


# ── Enrolment judges the receipt NEAREST to HEAD (issue #1707) ──────────────
#
# The enrolment loop returned on the first receipt that passed its filters, in
# filename order - the OLDEST. Every matching receipt is now a candidate and the
# one whose reviewed head has the fewest commits to HEAD is judged; a filename
# only breaks a tie at one head.

def _named_receipt(
    repo: Path, name: str, head: str, status: str = "ran", *,
    scope: str | None = None, skip_reason: str | None = None,
) -> None:
    import json

    r = {
        "schema": 1, "recorded_at": "2026-09-21T12:00:00Z", "issue": "1707",
        "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": head, "status": status,
        "reviewer": "codex/gpt-6-astra", "implementer": "claude/claude-opus-5",
    }
    if scope:
        r["scope"] = scope
    if skip_reason:
        r["skip_reason"] = skip_reason
    (repo / "docs/measurements/counter-model" / name).write_text(json.dumps(r, indent=2))


def _repo_with_two_reviewed_commits(tmp_path: Path) -> tuple[Path, str, str]:
    """An enrolled repo whose branch has an OLDER commit A and HEAD = B."""
    repo = _enrolled_repo(tmp_path)
    (repo / "f.txt").write_text("a\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "first reviewed")
    older = _git(repo, "rev-parse", "HEAD")
    (repo / "f.txt").write_text("b\n")
    _git(repo, "commit", "-qam", "second reviewed")
    return repo, older, _git(repo, "rev-parse", "HEAD")


def _verdict(result: subprocess.CompletedProcess) -> str:
    lines = [line for line in result.stdout.splitlines() if line.startswith("FLOW_FINISH_GATE: ")]
    assert len(lines) == 1, result.stdout + result.stderr
    return lines[0]


def _counter_model_line(result: subprocess.CompletedProcess) -> str:
    lines = [
        line for line in result.stdout.splitlines()
        if line.startswith("FLOW_FINISH_GATE_COUNTER_MODEL: ")
    ]
    assert len(lines) == 1, result.stdout + result.stderr
    return lines[0]


@requires_bash
@requires_git
def test_enrolment_names_the_receipt_for_this_head_not_the_oldest(tmp_path: Path) -> None:
    """The acceptance case. RED before #1707: the line named the older receipt."""
    repo, older, head = _repo_with_two_reviewed_commits(tmp_path)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", older)
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", head)
    line = _counter_model_line(_gate(repo))
    assert "receipt: 2026-01-02T000000Z-issue-1707.json" in line, line


@requires_bash
@requires_git
def test_an_older_valid_receipt_cannot_carry_an_unusable_one_at_head(tmp_path: Path) -> None:
    """The fail-open direction. RED before #1707: the gate passed on the older
    receipt and never judged the one for the commit being merged."""
    repo, older, head = _repo_with_two_reviewed_commits(tmp_path)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", older)
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", head, status="garbage")
    result = _gate(repo)
    assert "unknown: receipt 2026-01-02T000000Z-issue-1707.json has status 'garbage'" in _counter_model_line(result)
    assert _verdict(result) == "FLOW_FINISH_GATE: fail (counter-model line unknown)"


@requires_bash
@requires_git
def test_an_older_unusable_receipt_no_longer_reds_a_valid_one_at_head(tmp_path: Path) -> None:
    """The false-red direction. RED before #1707: the older receipt decided."""
    repo, older, head = _repo_with_two_reviewed_commits(tmp_path)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", older, status="garbage")
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", head)
    result = _gate(repo)
    assert "receipt: 2026-01-02T000000Z-issue-1707.json" in _counter_model_line(result)
    assert "fail" not in _verdict(result)


@requires_bash
@requires_git
def test_commit_distance_beats_the_latest_filename(tmp_path: Path) -> None:
    """A receipt written LATE for an OLDER head must not win. This is the case a
    simpler "take the last file" rule gets wrong, so it is what pins the rule.
    Three receipts: the nearest by count is neither first nor last by filename."""
    repo, older, head = _repo_with_two_reviewed_commits(tmp_path)
    base = _git(repo, "rev-parse", "HEAD~2")
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", base, status="garbage")
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", head)
    _named_receipt(repo, "2026-01-03T000000Z-issue-1707.json", older, status="garbage")
    result = _gate(repo)
    assert "receipt: 2026-01-02T000000Z-issue-1707.json" in _counter_model_line(result)
    assert "fail" not in _verdict(result)


@requires_bash
@requires_git
def test_at_one_head_the_later_file_is_the_later_review(tmp_path: Path) -> None:
    """The tie-break, and only a tie-break: two receipts for the SAME head."""
    repo, _older, head = _repo_with_two_reviewed_commits(tmp_path)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", head, status="garbage")
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", head)
    assert "receipt: 2026-01-02T000000Z-issue-1707.json" in _counter_model_line(_gate(repo))
    _named_receipt(repo, "2026-01-03T000000Z-issue-1707.json", head, status="garbage")
    assert "unknown: receipt 2026-01-03T000000Z-issue-1707.json" in _counter_model_line(_gate(repo))


def _gate_with_uncountable(repo: Path, tmp_path: Path, uncountable: str) -> subprocess.CompletedProcess:
    """Run the gate with a `git` that cannot count the distance from heads whose
    sha starts with one of the space-separated prefixes in `uncountable`."""
    real_git = shutil.which("git")
    assert real_git, "precondition: a real git to wrap"
    bindir = tmp_path / "git-bin"
    bindir.mkdir(exist_ok=True)
    wrapper = bindir / "git"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == rev-list && "$2" == --count ]]; then\n'
        f"  for p in {uncountable}; do\n"
        '    [[ "$3" == "$p"* ]] && exit 128\n'
        "  done\n"
        "fi\n"
        f'exec {real_git} "$@"\n'
    )
    wrapper.chmod(0o755)
    env = dict(os.environ)
    env["FLOW_GATE_CPP_DIR"] = ""
    env["CM_RECEIPT_HELPER"] = str(ROOT / "scripts" / "counter-model-receipt.py")
    env["PATH"] = f"{bindir}:{env['PATH']}"
    return subprocess.run(["bash", str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True)


@requires_bash
@requires_git
def test_a_receipt_whose_distance_cannot_be_computed_never_wins(tmp_path: Path) -> None:
    repo, older, head = _repo_with_two_reviewed_commits(tmp_path)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", older)
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", head, status="garbage")
    # The nearest receipt (at HEAD, unusable) cannot be measured, so it is set
    # aside and the measurable one is judged.
    result = _gate_with_uncountable(repo, tmp_path, head[:12])
    assert "receipt: 2026-01-01T000000Z-issue-1707.json" in _counter_model_line(result)


@requires_bash
@requires_git
def test_when_no_distance_can_be_computed_the_answer_is_undecidable(tmp_path: Path) -> None:
    """Not a fall back to the first match, which would restore the defect on
    exactly the checkout that cannot measure."""
    repo, older, head = _repo_with_two_reviewed_commits(tmp_path)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", older)
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", head)
    result = _gate_with_uncountable(repo, tmp_path, f"{older[:12]} {head[:12]}")
    line = _counter_model_line(result)
    assert line.startswith("FLOW_FINISH_GATE_COUNTER_MODEL: undecidable: 2 receipt(s) match"), line
    assert "receipt: " not in line.split("undecidable:")[0]


def _diamond_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """base -> B on one side, C on the other, merged at HEAD: B and C are two
    DIFFERENT heads at the same distance from HEAD."""
    repo = _enrolled_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("c\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "side commit")
    side = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "master")
    (repo / "main.txt").write_text("b\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "main commit")
    main = _git(repo, "rev-parse", "HEAD")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    assert _git(repo, "rev-list", "--count", f"{main}..HEAD") == _git(
        repo, "rev-list", "--count", f"{side}..HEAD"
    ), "precondition: the two reviewed heads are equally far from HEAD"
    return repo, main, side


@requires_bash
@requires_git
@pytest.mark.parametrize("valid_first", [True, False])
def test_two_heads_at_one_distance_are_both_judged_whatever_the_filenames(
    tmp_path: Path, valid_first: bool,
) -> None:
    """Counter-model review: at equal distance the filename chose between two
    DIFFERENT heads, so renaming a receipt switched the gate between pass and
    fail. Both are judged now; one unusable receipt reds the gate either way."""
    repo, main, side = _diamond_repo(tmp_path)
    first, second = ("ran", "garbage") if valid_first else ("garbage", "ran")
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", main, status=first)
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", side, status=second)
    result = _gate(repo)
    assert "unknown: receipt " in _counter_model_line(result), result.stdout
    assert _verdict(result) == "FLOW_FINISH_GATE: fail (counter-model line unknown)"


@requires_bash
@requires_git
def test_two_reviewed_sides_of_a_merge_both_usable_pass(tmp_path: Path) -> None:
    repo, main, side = _diamond_repo(tmp_path)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", main)
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", side)
    result = _gate(repo)
    assert "receipt: " in _counter_model_line(result)
    assert "fail" not in _verdict(result)


def _enrolment_only(repo: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["FLOW_GATE_CPP_DIR"] = ""
    env["CM_RECEIPT_HELPER"] = str(ROOT / "scripts" / "counter-model-receipt.py")
    return subprocess.run(
        ["bash", str(SCRIPT), "--enrolment-only"], cwd=repo, env=env, capture_output=True, text=True,
    )


@requires_bash
@requires_git
@pytest.mark.parametrize("scopeless_first", [True, False])
def test_enrolment_only_checks_the_scope_of_every_accepted_review(
    tmp_path: Path, scopeless_first: bool,
) -> None:
    """Counter-model review, pass 2: with two reviewed heads at one distance the
    scope check looked only at the LAST receipt, so a review recorded without a
    scope passed when the other carried one - and failed with the filenames
    swapped. Every accepted `ran` receipt is checked, in either order."""
    repo, main, side = _diamond_repo(tmp_path)
    first_scope, second_scope = (None, "full") if scopeless_first else ("full", None)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", main, scope=first_scope)
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", side, scope=second_scope)
    result = _enrolment_only(repo)
    assert _verdict(result) == "FLOW_FINISH_GATE: fail (counter-model line receipt-without-scope)"
    assert result.returncode == 1


@requires_bash
@requires_git
def test_a_scopeless_review_is_not_excused_by_an_allowed_skip_beside_it(tmp_path: Path) -> None:
    repo, main, side = _diamond_repo(tmp_path)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", main)
    _named_receipt(
        repo, "2026-01-02T000000Z-issue-1707.json", side, status="skipped", skip_reason="codex-absent",
    )
    result = _enrolment_only(repo)
    assert _verdict(result) == "FLOW_FINISH_GATE: fail (counter-model line receipt-without-scope)"


@requires_bash
@requires_git
def test_two_scoped_reviews_at_one_distance_pass_enrolment_only(tmp_path: Path) -> None:
    repo, main, side = _diamond_repo(tmp_path)
    _named_receipt(repo, "2026-01-01T000000Z-issue-1707.json", main, scope="full")
    _named_receipt(repo, "2026-01-02T000000Z-issue-1707.json", side, scope="diff-only")
    result = _enrolment_only(repo)
    assert _verdict(result) == "FLOW_FINISH_GATE: ok"
    assert result.returncode == 0


# ── An escalated review is its own passing state; an unruled count is not (#1700) ──
#
# The gate did not read `passes` at all, so a hand-made receipt claiming five
# passed as an ordinary one, and a review that honestly ran five could not be
# written. A receipt above the ceiling now passes ONLY with a recorded ruling,
# and the line says `escalated:`. "ruled by" is RECORDED, NOT AUTHENTICATED.

RULING = {
    "ruled_by": "orchestrator (wave cpp-improvement)",
    "reference": "issue #1700 comment 6812970075",
    "raised_cap": 5,
}


def _receipt_fields(repo: Path, name: str, head: str, **fields: object) -> None:
    import json

    r: dict[str, object] = {
        "schema": 2, "recorded_at": "2026-09-21T12:00:00Z", "issue": "1700",
        "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": head, "status": "ran",
        "reviewer": "codex/gpt-6-astra", "implementer": "claude/claude-opus-5",
    }
    r.update(fields)
    (repo / "docs/measurements/counter-model" / name).write_text(json.dumps(r, indent=2))


def _one_reviewed_commit(tmp_path: Path) -> tuple[Path, str]:
    repo = _enrolled_repo(tmp_path)
    (repo / "f.txt").write_text("a\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "reviewed")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_the_gate_and_the_writer_agree_on_the_pass_ceiling() -> None:
    """The gate keeps a COPY of the ceiling only to decide when to ask the
    receipt script. A drift would make it stop asking, or ask for everything."""
    shell = re.search(r"^readonly CM_PASSES_HARD_CEILING=(\d+)$", SCRIPT.read_text(), re.M)
    python = re.search(
        r"^PASSES_HARD_CEILING = (\d+)$",
        (ROOT / "scripts" / "counter-model-receipt.py").read_text(), re.M,
    )
    assert shell and python, "precondition: both constants are declared in the expected form"
    assert shell.group(1) == python.group(1)


@requires_bash
@requires_git
def test_an_escalated_receipt_is_its_own_passing_state(tmp_path: Path) -> None:
    repo, head = _one_reviewed_commit(tmp_path)
    _receipt_fields(
        repo, "2026-01-01T000000Z-issue-1700.json", head, passes=5, escalation=RULING,
        extra_passes_reason="passes 1-4 each found a real defect", scope="full",
    )
    finish = _gate(repo)
    line = _counter_model_line(finish)
    assert line.startswith(
        "FLOW_FINISH_GATE_COUNTER_MODEL: escalated: 5 passes, ruled by "
        "orchestrator (wave cpp-improvement) (2026-01-01T000000Z-issue-1700.json)"
    ), line
    assert "fail" not in _verdict(finish)
    only = _enrolment_only(repo)
    assert _verdict(only) == "FLOW_FINISH_GATE: ok" and only.returncode == 0


@requires_bash
@requires_git
@pytest.mark.parametrize("fields", [
    {"passes": 5, "extra_passes_reason": "kept finding things"},                      # no ruling
    {"passes": 7, "extra_passes_reason": "x",
     "escalation": {"ruled_by": "a", "reference": "b", "raised_cap": 7}},              # beyond the bound
    {"passes": 5, "extra_passes_reason": "x",
     "escalation": {"ruled_by": "a", "reference": "b", "raised_cap": 4}},              # beyond the raised cap
    {"passes": 5, "extra_passes_reason": "x",
     "escalation": {"ruled_by": " ", "reference": "b", "raised_cap": 5}},              # nobody named
    {"passes": 5, "escalation": dict(RULING)},                                         # no reason
])
def test_a_count_above_the_ceiling_without_a_usable_ruling_reds_the_gate(
    tmp_path: Path, fields: dict,
) -> None:
    """RED before #1700 for every row: the gate never read `passes`, printed
    `receipt:` and passed."""
    repo, head = _one_reviewed_commit(tmp_path)
    _receipt_fields(repo, "2026-01-01T000000Z-issue-1700.json", head, scope="full", **fields)
    result = _gate(repo)
    assert "unknown: receipt 2026-01-01T000000Z-issue-1700.json claims" in _counter_model_line(result)
    assert "with no usable recorded ruling" in _counter_model_line(result)
    assert _verdict(result) == "FLOW_FINISH_GATE: fail (counter-model line unknown)"
    assert _verdict(_enrolment_only(repo)).startswith("FLOW_FINISH_GATE: fail")


@requires_bash
@requires_git
def test_three_passes_with_a_reason_is_still_an_ordinary_receipt(tmp_path: Path) -> None:
    """The must-not-flip side: exactly three keeps today's form and today's line."""
    repo, head = _one_reviewed_commit(tmp_path)
    _receipt_fields(
        repo, "2026-01-01T000000Z-issue-1700.json", head, passes=3,
        extra_passes_reason="orchestrator requested a third pass", scope="full",
    )
    result = _gate(repo)
    assert "receipt: 2026-01-01T000000Z-issue-1700.json" in _counter_model_line(result)
    assert "escalated" not in _counter_model_line(result)
    assert _verdict(_enrolment_only(repo)) == "FLOW_FINISH_GATE: ok"


@requires_bash
@requires_git
def test_an_escalated_review_still_owes_a_scope_in_enrolment_only(tmp_path: Path) -> None:
    repo, head = _one_reviewed_commit(tmp_path)
    _receipt_fields(
        repo, "2026-01-01T000000Z-issue-1700.json", head, passes=5, escalation=RULING,
        extra_passes_reason="passes 1-4 each found a real defect",
    )
    assert _verdict(_enrolment_only(repo)) == (
        "FLOW_FINISH_GATE: fail (counter-model line receipt-without-scope)"
    )

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
from pathlib import Path

import pytest

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


def _run(
    tmp_path: Path,
    *args: str,
    cpp_dir: str | None = None,
    uv_exit: int | None = 0,
    make_exit: int | None = None,
    cwd: Path | None = None,
    uv_stdout: str = "",
    inject_gates: bool = True,
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
    assert f"run --project {cpp} python -m lib.cicd run --plan finish" in argv


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
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


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

    assert proc.returncode == 0
    assert "SUBSUMPTION REFUSED" in proc.stdout
    assert "an include" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" in proc.stdout


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

        assert proc.returncode == 0, refusals
        assert "SUBSUMPTION REFUSED" not in proc.stdout, refusals


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

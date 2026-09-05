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
  (exit 0) with a loud warning.
- ``--check-summary`` runs ``lib.cicd check --summary`` as an ADVISORY: verdict
  ``ok``/``warn``/``skipped``, always exit 0.
- The flow command docs invoke the helper BARE at the stable path and no longer
  carry the inline ``PYTHONPATH=... uv run ...`` gate shape that could never
  match a permission prefix rule.

The behaviour tests stub ``uv`` and ``make`` with PATH shims that record their
argv, so no real runner is needed; ``FLOW_GATE_CPP_DIR`` pins (or empties) the
checkout resolution.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-finish-gate.sh"

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="requires bash on PATH",
)


def _make_stub(bindir: Path, name: str, exit_code: int = 0) -> Path:
    """An executable PATH shim that logs its argv and exits ``exit_code``."""
    log = bindir / f"{name}.log"
    stub = bindir / name
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{log}"\n'
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
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the helper with stubbed uv/make; returns (proc, stub bin dir)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    if uv_exit is not None:
        _make_stub(bindir, "uv", uv_exit)
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


def _fake_cpp(tmp_path: Path) -> Path:
    cpp = tmp_path / "cpp"
    cpp.mkdir()
    (cpp / "CLAUDE.md").write_text("# fake\n")
    return cpp


# --- Runner path -------------------------------------------------------------


@requires_bash
def test_runner_ok(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    proc, bindir = _run(tmp_path, cpp_dir=str(cpp), uv_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    argv = (bindir / "uv.log").read_text()
    assert f"run --project {cpp} python -m lib.cicd run --plan finish" in argv


@requires_bash
def test_runner_fail(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    proc, _ = _run(tmp_path, cpp_dir=str(cpp), uv_exit=1)
    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout


@requires_bash
def test_plan_passthrough(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    proc, bindir = _run(tmp_path, "--plan", "check", cpp_dir=str(cpp), uv_exit=0)
    assert proc.returncode == 0
    assert "--plan check" in (bindir / "uv.log").read_text()


# --- Makefile fallback -------------------------------------------------------


@requires_bash
def test_fallback_all_three_targets_is_ok(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text(
        "lint:\n\ttrue\ntest:\n\ttrue\ntypecheck:\n\ttrue\n"
    )
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "Makefile fallback" in proc.stdout
    argv = (bindir / "make.log").read_text().splitlines()
    assert argv == ["lint", "test", "typecheck"]


@requires_bash
def test_fallback_missing_gate_reports_warn_named(tmp_path: Path) -> None:
    """A repo with lint+test targets but no typecheck target and no configured
    mypy: the gate did not run, so the marker is `warn (skipped gates: ...)` and
    names it - never a bare `ok` (#628)."""
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\ntest:\n\ttrue\n")
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    assert "typecheck" in proc.stdout
    # lint + test still actually ran.
    argv = (bindir / "make.log").read_text().splitlines()
    assert argv == ["lint", "test"]


@requires_bash
def test_fallback_uses_uv_when_no_makefile_but_pyproject(tmp_path: Path) -> None:
    """No Makefile at all, but pyproject configures ruff/pytest/mypy and uv is
    available: the fallback runs each gate via `uv run --extra dev <tool>`
    instead of skipping (#628)."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\n[tool.pytest.ini_options]\n[tool.mypy]\n"
    )
    proc, bindir = _run(tmp_path, cpp_dir="", uv_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    argv = (bindir / "uv.log").read_text()
    assert "run --extra dev ruff check ." in argv
    assert "run --extra dev pytest" in argv
    assert "run --extra dev mypy ." in argv


@requires_bash
def test_fallback_fail(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\ntest:\n\ttrue\n")
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, make_exit=1)
    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout


@requires_bash
def test_skipped_when_no_runner_and_no_makefile(tmp_path: Path) -> None:
    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: skipped" in proc.stdout
    assert "SKIPPED" in proc.stdout


# --- --check-summary (advisory) ---------------------------------------------


@requires_bash
def test_check_summary_ok(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\n")
    proc, bindir = _run(tmp_path, "--check-summary", cpp_dir=str(cpp), uv_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "lib.cicd check --summary" in (bindir / "uv.log").read_text()


@requires_bash
def test_check_summary_warn_is_exit_zero(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\n")
    proc, _ = _run(tmp_path, "--check-summary", cpp_dir=str(cpp), uv_exit=3)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: warn" in proc.stdout


@requires_bash
def test_check_summary_skipped_without_runner(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("lint:\n\ttrue\n")
    proc, _ = _run(tmp_path, "--check-summary", cpp_dir="", uv_exit=None)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: skipped" in proc.stdout


@requires_bash
def test_check_summary_skipped_without_makefile(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    proc, _ = _run(tmp_path, "--check-summary", cpp_dir=str(cpp), uv_exit=0)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: skipped" in proc.stdout


@requires_bash
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
) -> subprocess.CompletedProcess[str]:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    _uv_stub_printing(bindir, payload, exit_code)
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
def test_qualified_run_reports_warn_not_ok(tmp_path: Path) -> None:
    """The runner qualifies an all-skipped test step; this helper is the layer
    the flow commands read, so flattening that back to a bare `ok` would re-hide
    the #621 false green one level up. Exit status stays 0 - it is a signal."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 3,\n'
        '  "tests": {"test": {"passed": 0, "skipped": 66, "executed": 0}},\n'
        '  "warnings": ["test: exited 0 but executed NO tests (0 passed, 66 skipped)"]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    assert "issue #621" in proc.stdout
    # The runner's own JSON still reaches the caller (tee, not swallow).
    assert '"warnings"' in proc.stdout


@requires_bash
def test_unqualified_run_still_reports_ok(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = '{\n  "success": true,\n  "steps_completed": 3,\n  "steps_total": 3\n}'
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "warn" not in proc.stdout


@requires_bash
def test_failed_run_is_fail_even_with_warnings(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = '{\n  "success": false,\n  "warnings": ["test: exited 0 but executed NO tests"]\n}'
    proc = _run_with_uv_stub(tmp_path, cpp, payload, exit_code=1)
    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout


# --- #769: one targeted re-run of pytest's failed ids -----------------------


@requires_bash
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
      "outcome": "passed",
      "first_attempt": null,
      "rerun": null
    }
  ]
}"""
    proc = _run_with_uv_stub(tmp_path, cpp, payload)

    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    assert "RERUN_PASSED: tests/a.py::t1" in proc.stdout
    assert "issue #769" in proc.stdout


@requires_bash
@pytest.mark.parametrize("rerun_outcome", ["failed", "inconclusive"])
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
def test_gate_enables_runner_rerun_by_default(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = '{\n  "success": true\n}'
    proc = _run_with_uv_stub(tmp_path, cpp, payload)

    assert proc.returncode == 0
    assert (tmp_path / "bin" / "uv.env.log").read_text().strip() == (
        "CPP_GATE_RERUN_FAILED=1"
    )


@requires_bash
def test_gate_can_disable_runner_rerun(tmp_path: Path) -> None:
    cpp = _fake_cpp(tmp_path)
    payload = '{\n  "success": true\n}'
    proc = _run_with_uv_stub(tmp_path, cpp, payload, flow_gate_rerun="0")

    assert proc.returncode == 0
    assert (tmp_path / "bin" / "uv.env.log").read_text().strip() == (
        "CPP_GATE_RERUN_FAILED=0"
    )


@requires_bash
def test_disabled_rerun_overrides_an_inherited_opt_in(tmp_path: Path) -> None:
    """FLOW_GATE_RERUN=0 must OVERRIDE an inherited CPP_GATE_RERUN_FAILED=1, not
    merely decline to set it. A nested gate is the normal case - CPP's own suite
    runs under an outer gate that already exported the opt-in - so an opt-out
    that only omits the assignment disables nothing where it matters most."""
    cpp = _fake_cpp(tmp_path)
    payload = '{\n  "success": true\n}'
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    _uv_stub_printing(bindir, payload, 0)
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
      "outcome": "passed",
      "first_attempt": null,
      "rerun": null
    }
  ]
}"""
    proc = _run_with_uv_stub(tmp_path, cpp, payload)

    assert proc.returncode == 0
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
def test_fallback_rerun_passes_and_warns(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("lint:\n\ntest:\n\ntypecheck:\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fallback_make_stub(bindir, rerun_passes=True)

    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, cwd=tmp_path)

    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "RERUN_PASSED: tests/a.py::t1" in proc.stdout
    assert "issue #769" in proc.stdout
    assert (bindir / "test-attempts").read_text() == "xx"
    assert "--last-failed --last-failed-no-failures none" in proc.stdout


@requires_bash
def test_fallback_rerun_failure_stays_failed(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("lint:\n\ntest:\n\ntypecheck:\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fallback_make_stub(bindir, rerun_passes=False)

    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, cwd=tmp_path)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout
    assert "RERUN_PASSED:" not in proc.stdout
    assert (bindir / "test-attempts").read_text() == "xx"


@requires_bash
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
      "outcome": "passed",
      "first_attempt": null,
      "rerun": null
    }
  ],
  "skipped": [
    "typecheck"
  ]
}"""
    proc = _run_with_uv_stub(tmp_path, cpp, payload)

    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: warn (skipped gates: typecheck)" in proc.stdout
    assert "RERUN_PASSED: tests/a.py::t1" in proc.stdout


@requires_bash
def test_fallback_prints_rerun_ids_even_when_a_later_gate_fails(
    tmp_path: Path,
) -> None:
    """The runner path prints RERUN_PASSED before verdict precedence is applied;
    the fallback must too. Emitting it only after the `fail` branch dropped the
    ids on exactly the red-and-flaky run that is hardest to read - a test cleared
    by its re-run, then a genuinely failing typecheck - which is the fallback
    silently diverging from the runner, the #617/#621/#628 trap."""
    (tmp_path / "Makefile").write_text("lint:\n\ntest:\n\ntypecheck:\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fallback_make_stub(bindir, rerun_passes=True, fail_target="typecheck")

    proc, _ = _run(tmp_path, cpp_dir="", uv_exit=None, cwd=tmp_path)

    assert proc.returncode == 1
    assert "FLOW_FINISH_GATE: fail" in proc.stdout
    # The genuine failure still wins the verdict, but the flake is not erased.
    assert "RERUN_PASSED: tests/a.py::t1" in proc.stdout


@requires_bash
def test_fallback_rerun_appends_to_host_pytest_addopts(tmp_path: Path) -> None:
    """The runner's rerun_env APPENDS to any host PYTEST_ADDOPTS; the fallback
    must not replace it, or the two attempts are not the same invocation and the
    caller's own pytest options silently vanish on the re-run only."""
    (tmp_path / "Makefile").write_text("lint:\n\ntest:\n\ntypecheck:\n")
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

    assert proc.returncode == 0
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
def test_runner_skipped_gates_report_warn_named(tmp_path: Path) -> None:
    """The runner emits a "skipped": [...] array for skip_if-skipped gates. This
    helper is the layer the flow commands read, so it must report `warn` and NAME
    the skipped gates rather than flatten the run to a bare `ok` - the exact
    false green of #628. Exit stays 0 - it is a signal."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 4,\n  "steps_total": 4,\n'
        '  "skipped": [\n    "lint",\n    "test",\n    "typecheck"\n  ]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: warn" in proc.stdout
    assert "FLOW_FINISH_GATE: ok" not in proc.stdout
    for gate in ("lint", "test", "typecheck"):
        assert gate in proc.stdout
    assert "issue #628" in proc.stdout


@requires_bash
def test_runner_skipped_non_gate_still_ok(tmp_path: Path) -> None:
    """A skipped NON-gate step (e.g. security_scan) is a legitimate skip - the
    runner would not list it as a gate, so the marker stays `ok`."""
    cpp = _fake_cpp(tmp_path)
    payload = (
        '{\n  "success": true,\n  "steps_completed": 4,\n  "steps_total": 4,\n'
        '  "skipped": [\n    "security_scan"\n  ]\n}'
    )
    proc = _run_with_uv_stub(tmp_path, cpp, payload)
    assert proc.returncode == 0
    assert "FLOW_FINISH_GATE: ok" in proc.stdout
    assert "warn" not in proc.stdout

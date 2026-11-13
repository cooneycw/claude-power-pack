"""PATH handoff policy and independent refusal controls (#1801)."""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lib.cicd import __main__ as entry
from lib.cicd.runner import _build_step_env
from lib.cicd.steps import ShellStep, StepDef, _query_env

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/cicd-target-path"
BIN = os.path.dirname(sys.executable)
VALUE = "CPP_RUNNER_TARGET_PATH"
PRESENT = VALUE + "_PRESENT"


@pytest.mark.parametrize("original", ["", "/caller/bin:/usr/bin", "/path with spaces/bin::/usr/bin",
                                      f"{BIN}:/caller/bin", f"/caller/bin:{BIN}",
                                      "/literal/$(not-evaluated)/bin"])
def test_exact_caller_path_survives_with_presence_and_metadata_consumed(  # negative-fixture: allow pure decoder mapping
    original: str
) -> None:
    env = {"PATH": BIN + os.pathsep + original, VALUE: original, PRESENT: "x", "KEEP": "yes"}
    entry.restore_target_path(env)
    assert env == {"PATH": original, "KEEP": "yes"}


def test_captured_absence_and_unmarked_absence_are_preserved(  # negative-fixture: allow pure decoder mapping

) -> None:
    env = {"PATH": BIN + os.pathsep, VALUE: "", PRESENT: ""}
    entry.restore_target_path(env)
    assert env == {}
    entry.restore_target_path(env)
    assert env == {}, "no record must not manufacture a default PATH"


def test_unmarked_direct_caller_keeps_its_intentional_cpp_path(  # negative-fixture: allow pure decoder mapping

) -> None:
    env = {"PATH": f"{BIN}:/owned/bin"}
    before = dict(env)
    entry.restore_target_path(env)
    assert env == before


@pytest.mark.parametrize("env", [
    {VALUE: "private-path-record", "PATH": BIN + ":private-path-record"},
    {PRESENT: "x", "PATH": BIN + ":"},
    {VALUE: "private-path-record", PRESENT: "invalid", "PATH": BIN + ":private-path-record"},
    {VALUE: "private-path-record", PRESENT: "", "PATH": BIN + ":private-path-record"},
    {VALUE: "", PRESENT: "x"},
    {VALUE: "private-path-record:/owned", PRESENT: "x", "PATH": BIN + ":/owned"},
])
def test_refusal_precedes_mutation_and_does_not_echo_search_policy(  # negative-fixture: allow pure decoder mapping
    env: dict[str, str]
) -> None:
    before = dict(env)
    with pytest.raises(ValueError, match="PATH policy is unverified") as error:
        entry.restore_target_path(env)
    assert "private-path-record" not in str(error.value)
    assert env == before, "a failed handoff cannot partially restore policy"


def test_reserved_runtime_cannot_be_selected_by_host_or_step_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CPP_RUNNER_PYTHON", "/foreign/python")
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "cache"))
    env = _build_step_env(tmp_path)
    assert env["CPP_RUNNER_PYTHON"] == sys.executable
    step = ShellStep(StepDef(id="owned", command="true", env={"CPP_RUNNER_PYTHON": "/other/python"}))
    resolved = step._resolve_env({"env": env})
    assert resolved is not None and resolved["CPP_RUNNER_PYTHON"] == sys.executable
    assert _query_env({"CPP_RUNNER_PYTHON": "/foreign/query-python"})["CPP_RUNNER_PYTHON"] == sys.executable


GUARDS = {
    "complete": "incomplete launch handoff",
    "presence": "invalid presence marker",
    "absence": "inconsistent absent value",
    "current": "current search policy is unavailable",
    "topology": "search policy differs from launch handoff",
}
CASES = sorted(path.name for path in (CONTROL / "cases").glob("bad-*")
               if "guard" in json.loads((path / "case.json").read_text()))


@pytest.mark.skipif(shutil.which("python3") is None, reason="executes actual control adapter with Python")
@pytest.mark.parametrize("case_name", CASES)
def test_each_refusal_flips_when_only_its_named_guard_is_removed(tmp_path: Path, case_name: str) -> None:
    case = CONTROL / "cases" / case_name
    guard = json.loads((case / "case.json").read_text())["guard"]
    source = ROOT / "lib/cicd/__main__.py"
    command = [sys.executable, str(CONTROL / "run-case.py"), str(case)]
    baseline = subprocess.run([*command, str(source)], text=True, capture_output=True, check=False)
    assert baseline.returncode == 1 and baseline.stdout.strip() == "CICD_TARGET_PATH_CONTROL: blocked"
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "restore_target_path")
    removed = 0
    body = []
    for node in function.body:
        if isinstance(node, ast.If) and any(
            isinstance(value, ast.Constant) and isinstance(value.value, str) and GUARDS[guard] in value.value
            for statement in node.body for value in ast.walk(statement)
        ):
            body.append(ast.Pass())
            removed += 1
        else:
            body.append(node)
    assert removed == 1, "the mutant must remove exactly one guard, not a validation family"
    function.body = body
    mutant = tmp_path / "single-guard-mutant.py"
    mutant.write_text(ast.unparse(ast.fix_missing_locations(tree)) + "\n")
    changed = subprocess.run([*command, str(mutant)], text=True, capture_output=True, check=False)
    assert changed.returncode == 0, changed.stdout + changed.stderr
    assert changed.stdout.strip() == "CICD_TARGET_PATH_CONTROL: ready"


@pytest.mark.skipif(shutil.which("python3") is None, reason="executes historical Python control adapter")
@pytest.mark.parametrize("case_name", CASES)
def test_actual_pre_fix_entrypoint_misses_each_refusal(case_name: str) -> None:
    done = subprocess.run([sys.executable, str(CONTROL / "run-case.py"), str(CONTROL / "cases" / case_name),
                           str(CONTROL / "anchors/pre-path-handoff.py")],
                          text=True, capture_output=True, check=False)
    assert done.returncode == 0 and done.stdout.strip() == "CICD_TARGET_PATH_CONTROL: ready"


def test_forged_record_refuses_before_cli_import_without_echoing_path(  # negative-fixture: allow no subprocess
    monkeypatch, capsys,
) -> None:
    import builtins
    import runpy

    imported = []
    original_import = builtins.__import__

    def observe(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "cli" and level == 1:
            imported.append(True)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", observe)
    monkeypatch.setenv("PATH", BIN + ":/owned/caller")
    monkeypatch.setenv(VALUE, "/private-forged-record:/owned/caller")
    monkeypatch.setenv(PRESENT, "x")
    monkeypatch.setattr(sys, "argv", ["lib.cicd", "run", "--plan", "owned"])
    monkeypatch.delitem(sys.modules, "lib.cicd.__main__", raising=False)
    with pytest.raises(SystemExit) as error:
        runpy.run_module("lib.cicd", run_name="__main__")
    assert error.value.code == 1 and imported == []
    output = capsys.readouterr()
    assert not output.out and "PATH policy is unverified" in output.err
    assert "private-forged-record" not in output.err


@pytest.mark.skipif(shutil.which("python3") is None or shutil.which("sh") is None,
                    reason="runs owned shell interpreter sentinel through actual Python control")
def test_restoration_control_fails_when_only_the_path_assignment_is_removed(tmp_path: Path) -> None:
    source = ROOT / "lib/cicd/__main__.py"
    command = [sys.executable, str(CONTROL / "run-case.py"), str(CONTROL / "cases/bad-polluted-path")]
    good = subprocess.run([*command, str(source)], text=True, capture_output=True, check=False)
    assert good.returncode == 1 and good.stdout.strip() == "CICD_TARGET_PATH_CONTROL: restored"
    text = source.read_text()
    assert text.count('environment["PATH"] = value') == 1
    mutant = tmp_path / "restoration-mutant.py"
    mutant.write_text(text.replace('environment["PATH"] = value', 'pass'))
    failed = subprocess.run([*command, str(mutant)], text=True, capture_output=True, check=False)
    assert failed.returncode == 0 and failed.stdout.strip() == "CICD_TARGET_PATH_CONTROL: ready"
    old = subprocess.run([*command, str(CONTROL / "anchors/pre-path-handoff.py")],
                         text=True, capture_output=True, check=False)
    assert old.returncode == 0 and old.stdout.strip() == "CICD_TARGET_PATH_CONTROL: ready"

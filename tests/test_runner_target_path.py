"""Design-stage #1801 regressions, using the real CPP_RUN array and runner.

This executes only one owned custom plan. It does not run a finish gate.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/runner_target_path"
pytestmark = pytest.mark.skipif(
    shutil.which("uv") is None or shutil.which("bash") is None
    or shutil.which("sh") is None or shutil.which("python3") is None,
    reason="needs uv, bash, sh and Python for the owned real-runner fixture",
)


def run_probe(work: Path, target_uv_environment: bool, inherited_path_record: bool = False,
              make_query: bool = False) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    target = work / "target"
    target.mkdir()
    target_venv = target / ".target-venv"
    target_python = shutil.which("python3", path="/usr/bin:/bin")
    assert target_python, "precondition: fixture needs an interpreter outside CPP's venv"
    subprocess.run(["uv", "venv", "--python", target_python, "--no-python-downloads", str(target_venv)],
                   check=True, capture_output=True, text=True, timeout=30)
    target_path = f"{target_venv / 'bin'}:/usr/local/bin:/usr/bin:/bin"
    assert shutil.which("python3", path=target_path) == str(target_venv / "bin/python3")
    assert str(target_venv / "bin") != str(ROOT / ".venv/bin")
    shutil.copy2(FIXTURE / "probe.sh", target / "probe.sh")
    (target / ".claude").mkdir()
    (target / ".claude/cicd_tasks.yml").write_text(
        'version: "1"\nsteps:\n  path_probe:\n    command: sh probe.sh\n'
        '    timeout: 30\n    skip_if: "command -v python3 > skip-command-v.txt; false"\n'
        'plans:\n  path_probe:\n    steps: [path_probe]\n')
    if make_query:
        import shlex

        real_make = shutil.which("make")
        assert real_make
        (target_venv / "bin/make").write_text(
            '#!/bin/sh\nprintf \'%s\\n\' "$PATH" >> "$CPP_PATH_PROBE_MAKE_RECORD"\n'
            f'exec {shlex.quote(real_make)} "$@"\n')
        (target_venv / "bin/make").chmod(0o755)
        (target / "Makefile").write_text(".PHONY: verify lint\nverify: lint\nlint:\n\tsh probe.sh\n")
        (target / ".claude/cicd_tasks.yml").write_text(
            'version: "1"\nsteps:\n  lint:\n    command: make lint\n'
            '  verify:\n    command: make verify\nplans:\n  path_probe:\n    steps: [lint, verify]\n')
    # Extract the shipped assignment verbatim, rather than duplicate its argv.
    source = (ROOT / "scripts/flow-finish-gate.sh").read_text()
    wrapper = "CPP_RUN=(" + source.split("CPP_RUN=(", 1)[1].split("\n\n", 1)[0]
    assert wrapper.endswith("python -m lib.cicd)"), "the wrapper extraction must be complete"
    (work / "wrapper.txt").write_text(wrapper + "\n")
    env = os.environ.copy()
    for key in ("UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV", "PYTHONHOME", "UV_PYTHON",
                "CPP_RUNNER_TARGET_PATH", "CPP_RUNNER_TARGET_PATH_PRESENT"):
        env.pop(key, None)
    env.update(PATH=target_path, CPP_DIR=str(ROOT), PYTHONPATH=f"{FIXTURE}:{ROOT}",
               CPP_OFFLINE="1", UV_OFFLINE="1",
               CPP_PATH_PROBE_RUNNER_RECORD=str(work / "runner-environment.json"),
               CPP_PATH_PROBE_MAKE_RECORD=str(work / "make-paths.txt"))
    if inherited_path_record:
        env["CPP_RUNNER_TARGET_PATH"] = "/foreign/inherited-record"
        env["CPP_RUNNER_TARGET_PATH_PRESENT"] = "invalid"
    if target_uv_environment:
        env["UV_PROJECT_ENVIRONMENT"] = str(target_venv)
    caller = {key: env.get(key) for key in ("PATH", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")}
    done = subprocess.run(["bash", "-c", wrapper + '\n"${CPP_RUN[@]}" run --plan path_probe'],
                          cwd=target, env=env, capture_output=True, text=True, timeout=60, check=False)
    (work / "stdout.log").write_text(done.stdout)
    (work / "stderr.log").write_text(done.stderr)
    assert done.returncode == 0, done.stdout + done.stderr
    observed = {"caller": caller,
                "runner": json.loads((work / "runner-environment.json").read_text()),
                "step": json.loads((target / "step-environment.json").read_text()),
                "command_v": (target / "step-command-v.txt").read_text().strip(),
                "version_output": (target / "step-version.txt").read_text().strip(),
                "target_python": str(target_venv / "bin/python3"),
                "source": str(ROOT / "scripts/flow-finish-gate.sh"),
                "runner_source": str(ROOT / "lib/cicd/runner.py")}
    if make_query:
        observed["make_paths"] = (work / "make-paths.txt").read_text().splitlines()
        observed["result"] = json.loads(done.stdout)
    else:
        observed["skip_command_v"] = (target / "skip-command-v.txt").read_text().strip()
    (work / "observation.json").write_text(json.dumps(observed, indent=2) + "\n")
    return observed


@pytest.mark.parametrize("target_uv_environment", [False, True])
def test_bare_python_uses_the_target_callers_interpreter(tmp_path: Path, target_uv_environment: bool) -> None:
    observed = run_probe(tmp_path, target_uv_environment)
    assert observed["step"]["VIRTUAL_ENV"] is None
    expected_uv = observed["caller"]["UV_PROJECT_ENVIRONMENT"]
    assert observed["step"]["UV_PROJECT_ENVIRONMENT"] == expected_uv
    assert observed["command_v"] == observed["target_python"], observed
    assert observed["step"]["PATH"] == observed["caller"]["PATH"], observed


@pytest.mark.parametrize("target_uv_environment", [False, True])
def test_the_runners_own_interpreter_stays_in_cpp(tmp_path: Path, target_uv_environment: bool) -> None:
    observed = run_probe(tmp_path, target_uv_environment)
    assert Path(observed["runner"]["executable"]).parent == ROOT / ".venv/bin"
    assert observed["runner"]["prefix"] == str(ROOT / ".venv")
    assert observed["runner"]["version"].startswith("3.11.")
    assert observed["runner"]["VIRTUAL_ENV"] == str(ROOT / ".venv")


# Security migration observations use the proposed restored target PATH
# directly in an owned ShellStep context. The production wrapper is unchanged.
def security_probe(work: Path, with_yaml: bool, builtin: str | None = None,
                   refuse_target_import: bool = False, source: str = "builtin") -> dict:
    import shlex

    import yaml

    from lib.cicd.state import StepStatus
    from lib.cicd.steps import BUILTIN_PLANS, ShellStep, StepDef

    work.mkdir(parents=True, exist_ok=True)
    target = work / "target"
    target.mkdir()
    target_venv = target / ".target-venv"
    target_python = shutil.which("python3", path="/usr/bin:/bin")
    assert target_python
    subprocess.run(["uv", "venv", "--python", target_python, "--no-python-downloads", str(target_venv)],
                   check=True, capture_output=True, text=True, timeout=30)
    site = subprocess.check_output([str(target_venv / "bin/python3"), "-c",
                                    "import sysconfig;print(sysconfig.get_path('purelib'))"], text=True).strip()
    if with_yaml:
        # The actual installed PyYAML's Python implementation, not a fake module.
        # Binary extensions for CPP's different Python are deliberately excluded.
        shutil.copytree(Path(yaml.__file__).parent, Path(site) / "yaml",
                        ignore=shutil.ignore_patterns("*.so", "__pycache__"))
    yaml_probe = subprocess.run([str(target_venv / "bin/python3"), "-c", "import yaml;print(yaml.__version__)"],
                                text=True, capture_output=True, check=False)
    assert (yaml_probe.returncode == 0) is with_yaml, "precondition: actual target PyYAML population"
    (target / ".claude").mkdir()
    (target / ".claude/security.yml").write_text("{}\n")
    (target / ".gitignore").write_text(".env\n.env.*\n*.pem\n*.key\nsecrets.*\n*.p12\n.claude/security.yml\n")
    (target / "owned.py").write_text("answer = 42\n")
    env = os.environ.copy()
    env.update(PATH=f"{target_venv / 'bin'}:/usr/local/bin:/usr/bin:/bin",
               CPP_RUNNER_PYTHON=str(ROOT / ".venv/bin/python3"))
    for key in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"):
        env.pop(key, None)
    assert shutil.which("python3", path=env["PATH"]) == str(target_venv / "bin/python3")
    if refuse_target_import:
        # Force the separate skip-guard population explicitly. Missing PyYAML
        # alone is NOT enough: lib.security loads that dependency lazily.
        target_command = target_venv / "bin/python3"
        target_command.unlink()
        target_command.write_text(
            '#!/bin/sh\nif [ "${1-}" = -c ] && [ "${2-}" = "import lib.security" ]; then exit 1; fi\n'
            f'exec {shlex.quote(str(target_venv / "bin/python"))} "$@"\n')
        target_command.chmod(0o755)
        refused = subprocess.run([str(target_command), "-c", "import lib.security"],
                                 env={**env, "PYTHONPATH": str(ROOT)}, check=False)
        assert refused.returncode == 1, "precondition: target import probe really refuses"
    if builtin:
        if source == "builtin":
            plan = "finish" if builtin == "security_scan" else "deploy"
            definition = next(step for step in BUILTIN_PLANS[plan] if step.id == builtin)
        else:
            from lib.cicd.manifest import generate_manifest, load_manifest, step_model_to_step_def

            manifest = generate_manifest(target) if source == "generated" else load_manifest(ROOT)
            assert manifest is not None
            definition = step_model_to_step_def(builtin, manifest.steps[builtin])
            # CPP's own manifest normally imports via its checkout cwd; keep
            # the scan population owned and tiny while resolving that real module.
            env["PYTHONPATH"] = str(ROOT)
    else:
        definition = StepDef(id="handwritten_security", command=(
            f"PYTHONPATH={shlex.quote(str(ROOT))} python3 -m lib.security gate flow_finish"))
    step = ShellStep(definition)
    context = {"project_root": str(target), "env": env}
    skipped = step.should_skip(context)
    result = None if skipped else step.execute(context)
    observed = {"with_yaml": with_yaml, "yaml_version": yaml_probe.stdout.strip(),
                "builtin": builtin, "refuse_target_import": refuse_target_import, "skipped": skipped,
                "success": result is not None and result.status == StepStatus.SUCCESS,
                "exit_code": None if result is None else result.exit_code,
                "output": "" if result is None else result.output,
                "error": "" if result is None else result.error,
                "command": definition.command, "skip_if": definition.skip_if}
    (work / "observation.json").write_text(json.dumps(observed, indent=2) + "\n")
    return observed


@pytest.mark.parametrize("builtin", ["security_scan", "deploy_security_scan"])
@pytest.mark.parametrize("refuse_target_import", [False, True])
def test_cpp_security_runs_without_borrowing_target_pyyaml(
    tmp_path: Path, builtin: str, refuse_target_import: bool,
) -> None:
    observed = security_probe(tmp_path, with_yaml=False, builtin=builtin,
                              refuse_target_import=refuse_target_import)
    assert not observed["skipped"], observed
    assert observed["success"], observed
    assert "SECURITY_GATE:" in observed["output"] and " PASS " in observed["output"]


@pytest.mark.parametrize("with_yaml", [False, True])
def test_handwritten_security_on_target_path_names_missing_yaml_honestly(tmp_path: Path, with_yaml: bool) -> None:
    observed = security_probe(tmp_path, with_yaml=with_yaml)
    assert not observed["skipped"]
    assert observed["exit_code"] == (0 if with_yaml else 2), observed
    if with_yaml:
        assert "SECURITY_GATE: flow_finish PASS " in observed["output"]
    else:
        assert "SECURITY_GATE: flow_finish UNKNOWN" in observed["output"]
        assert "PyYAML is not importable" in observed["output"]


@pytest.mark.parametrize("builtin", ["security_scan", "deploy_security_scan"])
def test_owned_security_population_passes_when_target_yaml_is_installed(tmp_path: Path, builtin: str) -> None:
    observed = security_probe(tmp_path, with_yaml=True, builtin=builtin)
    assert not observed["skipped"] and observed["success"], observed
    assert " PASS " in observed["output"]


def test_wrapper_overwrites_inherited_path_metadata(tmp_path: Path) -> None:
    observed = run_probe(tmp_path, False, inherited_path_record=True)
    assert observed["command_v"] == observed["target_python"]
    assert observed["step"]["PATH"] == observed["caller"]["PATH"]


@pytest.mark.parametrize("builtin", ["security_scan", "deploy_security_scan"])
def test_command_only_security_mutant_is_still_rejected_by_acceptance(
    tmp_path: Path, monkeypatch, builtin: str,
) -> None:
    from dataclasses import replace

    from lib.cicd.steps import BUILTIN_PLANS

    plan = "finish" if builtin == "security_scan" else "deploy"
    original = next(step for step in BUILTIN_PLANS[plan] if step.id == builtin)
    assert original.skip_if
    mutant = replace(original, skip_if=original.skip_if.replace('"$CPP_RUNNER_PYTHON"', "python3"))
    modified = [mutant if step.id == builtin else step for step in BUILTIN_PLANS[plan]]
    monkeypatch.setitem(BUILTIN_PLANS, plan, modified)
    observed = security_probe(tmp_path, False, builtin, refuse_target_import=True)
    assert observed["skipped"] and not observed["success"], observed


@pytest.mark.skipif(shutil.which("make") is None, reason="queries and executes owned real Makefile")
def test_make_queries_and_the_target_step_share_restored_path(tmp_path: Path) -> None:
    observed = run_probe(tmp_path, False, make_query=True)
    assert len(observed["make_paths"]) >= 2, "the real query and actual recipe must both run"
    assert set(observed["make_paths"]) == {observed["caller"]["PATH"]}
    assert observed["command_v"] == observed["target_python"]
    assert observed["result"]["subsumed_gates"] == {"lint": "verify"}, observed["result"]


def test_skip_probe_uses_the_same_target_interpreter_as_the_command(tmp_path: Path) -> None:
    observed = run_probe(tmp_path, False)
    assert observed["skip_command_v"] == observed["command_v"] == observed["target_python"]


@pytest.mark.parametrize("source", ["generated", "cpp-manifest"])
@pytest.mark.parametrize("builtin", ["security_scan", "deploy_security_scan"])
def test_emitted_cpp_security_commands_and_guards_use_cpp_runtime(
    tmp_path: Path, source: str, builtin: str,
) -> None:
    observed = security_probe(tmp_path, False, builtin, refuse_target_import=True, source=source)
    assert not observed["skipped"] and observed["success"], observed
    assert " PASS " in observed["output"]


# Missing/empty PATH can prevent finding env/uv before Python starts. The
# resolved-executable variant freezes only those two known launch binaries;
# the exact extracted array and PATH record still run through actual uv.
def run_empty_path_probe(work: Path, state: str, resolve_launchers: bool) -> dict:
    work.mkdir(parents=True)
    target = work / "target"
    (target / ".claude").mkdir(parents=True)
    (target / ".claude/cicd_tasks.yml").write_text(
        'version: "1"\nsteps:\n  owned:\n    command: >-\n'
        '      printf \'%s\' "${PATH+x}:${PATH-}" > step-path;\n'
        '      command -v python3 > step-python || :;\n'
        '      echo dispatched > dispatched\n'
        'plans:\n  owned:\n    steps: [owned]\n')
    env_exe = shutil.which("env")
    uv_exe = shutil.which("uv")
    bash_exe = shutil.which("bash")
    assert env_exe and uv_exe and bash_exe
    source = (ROOT / "scripts/flow-finish-gate.sh").read_text()
    wrapper = "CPP_RUN=(" + source.split("CPP_RUN=(", 1)[1].split("\n\n", 1)[0]
    env = os.environ.copy()
    for key in ("PATH", "VIRTUAL_ENV", "PYTHONHOME", "UV_PROJECT_ENVIRONMENT", "UV_PYTHON"):
        env.pop(key, None)
    if state == "empty":
        env["PATH"] = ""
    assert env.get("PATH") in (None, ""), "precondition: no caller search directories"
    assert shutil.which("env", path=str(target)) is None, "empty PATH searches owned cwd, which has no env"
    env.update(CPP_DIR=str(ROOT), PYTHONPATH=f"{FIXTURE}:{ROOT}", UV_OFFLINE="1", CPP_OFFLINE="1",
               ENV_EXE=env_exe, UV_EXE=uv_exe,
               CPP_PATH_PROBE_RUNNER_RECORD=str(work / "runtime.json"))
    prefix = "unset PATH\n" if state == "unset" else ""
    fix_lookup = '' if not resolve_launchers else (
        '\nCPP_RUN[0]="$ENV_EXE"\n'
        'for _i in "${!CPP_RUN[@]}"; do\n'
        '  if [[ "${CPP_RUN[_i]}" == uv ]]; then CPP_RUN[_i]="$UV_EXE"; fi\n'
        'done\n')
    done = subprocess.run([bash_exe, "-c", prefix + wrapper + fix_lookup + '\n"${CPP_RUN[@]}" run --plan owned'],
                          cwd=target, env=env, text=True, capture_output=True, timeout=60, check=False)
    observation = {"state": state, "resolved_launchers": resolve_launchers, "exit_code": done.returncode,
                   "dispatched": (target / "dispatched").exists(), "stderr": done.stderr,
                   "step_path": (target / "step-path").read_text() if (target / "step-path").exists() else None,
                   "step_python": (target / "step-python").read_text() if (target / "step-python").exists() else None,
                   "runtime": json.loads((work / "runtime.json").read_text())
                   if (work / "runtime.json").exists() else None}
    (work / "observation.json").write_text(json.dumps(observation, indent=2) + "\n")
    return observation


@pytest.mark.parametrize("state", ["unset", "empty"])
def test_actual_uv_missing_or_empty_path_never_borrows_cpp_for_target(tmp_path: Path, state: str) -> None:
    observed = run_empty_path_probe(tmp_path / "resolved", state, True)
    assert observed["runtime"] is not None, "the real uv child must have started"
    if state == "unset":
        assert observed["runtime"]["PATH"] == str(ROOT / ".venv/bin")
        assert observed["exit_code"] == 1 and not observed["dispatched"]
        assert "PATH policy is unverified" in observed["stderr"]
    else:
        assert observed["runtime"]["PATH"] == str(ROOT / ".venv/bin") + os.pathsep
        assert observed["exit_code"] == 0 and observed["dispatched"]
        assert observed["step_path"] == "x:" and observed["step_python"] == ""


@pytest.mark.parametrize("state", ["unset", "empty"])
def test_unresolved_empty_path_launcher_never_silently_dispatches(tmp_path: Path, state: str) -> None:
    observed = run_empty_path_probe(tmp_path / "unresolved", state, False)
    assert observed["exit_code"] != 0 and not observed["dispatched"]
    if observed["runtime"] is not None:
        assert "PATH policy is unverified" in observed["stderr"]

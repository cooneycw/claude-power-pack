"""The real shell wrapper loads CPP's configuration from an external cwd."""
import ast
import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "bootstrap-check.sh"
pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("python3") is None
    or shutil.which(sys.executable) is None,
    reason="requires bash and a Python interpreter",
)


def _test_python_env(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    # Pin only this TEST's ambient python3; the real wrapper's policy is unchanged.
    python = tools / "python3"
    python.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' "$@"\n')
    python.chmod(0o755)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"])
    env.pop("PYTHONPATH", None)
    return env


@pytest.mark.parametrize("shadow", ["none", "regular-lib", "yaml-module", "pythonpath-lib"])
def test_real_wrapper_lists_cpp_from_outside_and_ignores_caller_lure(tmp_path, shadow):
    assert importlib.util.find_spec("yaml") is not None, "the selected test interpreter must have real PyYAML"
    external = tmp_path / "caller"
    external.mkdir()
    assert external != ROOT and ROOT not in external.parents, "caller must be outside CPP"
    (external / ".claude").mkdir()
    (external / ".claude/bootstrap.yaml").write_text(
        'dependencies:\n  caller_owned_lure:\n    check_command: "exit 73"\n    description: "caller only"\n'
    )
    env = _test_python_env(tmp_path)
    ready = subprocess.run(["python3", "-c", "import yaml"], cwd=external,
                           env=env, capture_output=True, text=True, timeout=20)
    assert ready.returncode == 0, ready.stderr
    if shadow in {"regular-lib", "pythonpath-lib"}:
        (external / "lib").mkdir()
        (external / "lib/__init__.py").write_text("# Caller-owned regular package.\n")
        assert (external / "lib/__init__.py").is_file(), "construct a regular package that shadows CPP"
    if shadow == "pythonpath-lib":
        (external / "lib/cicd").mkdir()
        (external / "lib/cicd/__init__.py").write_text("")
        (external / "lib/cicd/bootstrap.py").write_text('print("caller checker")\n')
        env["PYTHONPATH"] = str(external)
        assert (external / "lib/cicd/bootstrap.py").is_file(), "construct a substitute checker"
    elif shadow == "yaml-module":
        (external / "yaml.py").write_text('raise ImportError("caller yaml")\n')
        assert (external / "yaml.py").is_file(), "construct a caller-owned dependency shadow"
    inside = subprocess.run(["bash", str(WRAPPER), "--list"], cwd=ROOT,
                            env=env, capture_output=True, text=True, timeout=20)
    assert inside.returncode == 0 and "jq:" in inside.stdout, inside.stdout + inside.stderr
    outside = subprocess.run(["bash", str(WRAPPER), "--list"], cwd=external,
                             env=env, capture_output=True, text=True, timeout=20)
    assert outside.returncode == 0, outside.stdout + outside.stderr
    assert outside.stdout == inside.stdout
    assert "caller_owned_lure" not in outside.stdout


@pytest.mark.parametrize("case,code,signal,anchor", [
    ("bad-blocking-unmet", 1, "finding -", False),
    ("good-blocking-satisfied", 0, "clean -", False),
    ("bad-caller-regular-lib", 1, "finding -", False),
    ("good-caller-regular-lib", 0, "clean -", False),
    ("bad-caller-yaml-module", 1, "finding -", False),
    ("good-caller-yaml-module", 0, "clean -", False),
    ("bad-caller-pythonpath-lib", 1, "finding -", False),
    ("good-caller-pythonpath-lib", 0, "clean -", False),
    ("bad-installed-lib", 1, "finding -", False),
    ("good-installed-lib", 0, "clean -", False),
    ("unknown-module-unimportable", 3, "unknown - unavailable", False),
    ("unknown-pyyaml-missing", 3, "unknown - unavailable", False),
    ("bad-blocking-unmet", 0, "clean -", True),
])
def test_committed_control_distinguishes_blockers_and_unavailable(tmp_path, case, code, signal, anchor):
    assert importlib.util.find_spec("yaml") is not None, "supported control lane needs real PyYAML"
    control = ROOT / "controls/bootstrap-wrapper"
    gate = control / "anchors/blind-list-instead-check.sh" if anchor else WRAPPER
    done = subprocess.run([sys.executable, str(control / "run-case.py"),
                           str(control / "cases" / case), str(gate)],
                          cwd=tmp_path, env=_test_python_env(tmp_path),
                          capture_output=True, text=True, timeout=30)
    assert done.returncode == code, done.stdout + done.stderr
    assert "BOOTSTRAP_WRAPPER_CONTROL: " + signal in done.stdout


def _assert_checker_has_no_lib_imports(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] != "lib" for alias in node.names), "checker must not import lib.*"
        elif isinstance(node, ast.ImportFrom):
            assert not node.level and (node.module or "").split(".")[0] != "lib", "checker must remain standalone"


def _assert_no_stdlib_shadow(directory):
    names = {p.stem if p.is_file() and p.suffix == ".py" else p.name
             for p in directory.iterdir() if p.is_dir() or p.suffix == ".py"}
    assert not names.intersection(sys.stdlib_module_names), "checker directory must not shadow stdlib modules"


def test_checker_file_has_no_lib_imports():
    _assert_checker_has_no_lib_imports((ROOT / "lib/cicd/bootstrap.py").read_text())


def test_checker_directory_has_no_stdlib_shadow():
    _assert_no_stdlib_shadow(ROOT / "lib/cicd")


def test_standalone_import_pin_rejects_internal_import(tmp_path):
    source = tmp_path / "bootstrap.py"
    source.write_text((ROOT / "lib/cicd/bootstrap.py").read_text() + "\nimport lib.cicd\n")
    assert "import lib.cicd" in source.read_text(), "construct forbidden package import"
    with pytest.raises(AssertionError, match="must not import lib"):
        _assert_checker_has_no_lib_imports(source.read_text())


def test_stdlib_shadow_pin_rejects_new_module(tmp_path):
    directory = tmp_path / "cicd"
    shutil.copytree(ROOT / "lib/cicd", directory, ignore=shutil.ignore_patterns("__pycache__"))
    (directory / "subprocess.py").write_text("# Unintended local stdlib shadow.\n")
    assert (directory / "subprocess.py").is_file() and "subprocess" in sys.stdlib_module_names
    with pytest.raises(AssertionError, match="must not shadow stdlib"):
        _assert_no_stdlib_shadow(directory)

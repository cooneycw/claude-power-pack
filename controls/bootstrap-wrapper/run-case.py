"""Own the CPP layout and run the real wrapper/checker; unavailable is not clean."""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
case = json.loads((Path(sys.argv[1]) / "input.json").read_text())
gate = Path(sys.argv[2]).resolve()
python = shutil.which("python3")
if shutil.which("bash") is None or python is None:
    print("BOOTSTRAP_WRAPPER_CONTROL: unavailable - bash or python3 absent")
    raise SystemExit(3)
with tempfile.TemporaryDirectory(prefix="bootstrap-control-") as raw:
    top = Path(raw)
    cpp, caller, tools = top / "cpp", top / "caller", top / "bin"
    for path in (cpp / "scripts", cpp / ".claude", caller, tools):
        path.mkdir(parents=True, exist_ok=True)
    assert cpp not in caller.parents and caller != cpp
    wrapper = cpp / "scripts/bootstrap-check.sh"
    shutil.copy2(gate, wrapper)
    if not case.get("missing_module"):
        package = cpp / "lib/cicd"
        package.mkdir(parents=True)
        for name in ("__init__.py", "bootstrap.py"):
            shutil.copy2(ROOT / "lib/cicd" / name, package / name)
    else:
        assert not (cpp / "lib").exists(), "construct missing engine before running it"
    (cpp / ".claude/bootstrap.yaml").write_text(json.dumps({
        "version": "1", "dependencies": {"owned": {
            "description": "owned blocking fixture", "check_command": case["check_command"],
            "remediation": "satisfy the owned fixture",
        }},
    }))
    launcher = tools / "python3"
    launcher.write_text("#!/bin/sh\nexec " + shlex.quote(python)
                        + (" -S" if case.get("without_site") else "") + ' "$@"\n')
    launcher.chmod(0o755)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"])
    env.pop("PYTHONPATH", None)
    ready = subprocess.run([str(launcher), "-c", "import yaml"], cwd=caller, env=env,
                           capture_output=True, text=True, timeout=20)
    if ready.returncode != 0:
        if case.get("without_site"):
            assert "No module named 'yaml'" in ready.stderr, "construct actual PyYAML absence"
        prefix = "unknown - unavailable" if case.get("without_site") else "unavailable -"
        print("BOOTSTRAP_WRAPPER_CONTROL: " + prefix + " selected python3 cannot import PyYAML")
        raise SystemExit(3)
    if case.get("without_site"):
        raise AssertionError("without-site fixture unexpectedly imports PyYAML")
    if case.get("caller_shadow") == "regular-lib":
        (caller / "lib").mkdir()
        (caller / "lib/__init__.py").write_text("# Caller-owned regular package.\n")
        assert (caller / "lib/__init__.py").is_file(), "construct regular lib shadow"
    elif case.get("caller_shadow") == "yaml-module":
        (caller / "yaml.py").write_text('raise ImportError("caller yaml")\n')
        assert (caller / "yaml.py").is_file(), "construct dependency shadow"
    done = subprocess.run(["bash", str(wrapper)], cwd=caller, env=env,
                          capture_output=True, text=True, timeout=20)
    if "ModuleNotFoundError" in done.stderr or "ImportError" in done.stderr:
        print("BOOTSTRAP_WRAPPER_CONTROL: unknown - unavailable wrapper cannot import its checker or dependency")
        raise SystemExit(3)
    if done.returncode == 1 and "bootstrap prerequisite(s) not satisfied" in done.stdout:
        print("BOOTSTRAP_WRAPPER_CONTROL: finding - real checker blocked an unmet prerequisite")
        raise SystemExit(1)
    if done.returncode == 0:
        print("BOOTSTRAP_WRAPPER_CONTROL: clean - wrapper accepted")
        raise SystemExit(0)
    print("BOOTSTRAP_WRAPPER_CONTROL: unavailable - wrapper did not produce a prerequisite verdict")
    raise SystemExit(3)

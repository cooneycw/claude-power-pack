"""Run supplied decoder over one owned policy; never print PATH contents."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

case = json.loads((Path(sys.argv[1]) / "case.json").read_text())
spec = importlib.util.spec_from_file_location("_path_handoff_under_test", sys.argv[2])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory() as temporary:
    replacements = {"@CPP_BIN@": os.path.dirname(sys.executable),
                    "@CALLER@": temporary + "/caller/bin", "@OTHER@": temporary + "/other/bin",
                    "@FOREIGN@": temporary + "/foreign/bin"}
    def substitute(value):
        for marker, actual in replacements.items():
            value = value.replace(marker, actual)
        return value
    environment = {key: substitute(value) for key, value in case["environment"].items()}
    if case.get("restore"):
        caller = Path(replacements["@CALLER@"])
        caller.mkdir(parents=True)
        command = caller / "python3"
        command.write_text("#!/bin/sh\n# Owned interpreter-resolution sentinel.\nprintf 'TARGET\\n'\n")
        command.chmod(0o755)
        assert environment["PATH"].startswith(replacements["@CPP_BIN@"] + os.pathsep)
        assert environment["CPP_RUNNER_TARGET_PATH"] == str(caller)
    guard = case.get("guard")
    if guard == "complete":
        assert ("CPP_RUNNER_TARGET_PATH" in environment) != ("CPP_RUNNER_TARGET_PATH_PRESENT" in environment)
    elif guard == "presence":
        assert environment["CPP_RUNNER_TARGET_PATH_PRESENT"] not in ("", "x")
    elif guard == "absence":
        assert environment["CPP_RUNNER_TARGET_PATH_PRESENT"] == "" and environment["CPP_RUNNER_TARGET_PATH"]
    elif guard == "current":
        assert "PATH" not in environment
    elif guard == "topology":
        value = environment["CPP_RUNNER_TARGET_PATH"]
        assert environment["PATH"] not in (value, replacements["@CPP_BIN@"] + os.pathsep + value)
    sentinel = Path(temporary) / "later-effect"
    try:
        # The actual historical artifact predates this decoder and ignores records.
        getattr(module, "restore_target_path", lambda environment: None)(environment)
    except ValueError as exc:
        assert "PATH policy is unverified" in str(exc)
        assert not sentinel.exists()
        print("CICD_TARGET_PATH_CONTROL: blocked")
        raise SystemExit(1) from None
    if case.get("restore"):
        observed = subprocess.run(["python3", "-c", "print('RUNNER')"], env=environment,
                                  capture_output=True, text=True, timeout=10, check=False)
        if observed.returncode == 0 and observed.stdout.strip() == "TARGET":
            print("CICD_TARGET_PATH_CONTROL: restored")
            raise SystemExit(1)
    if "expected_path" in case:
        assert environment.get("PATH") == substitute(case["expected_path"])
    sentinel.write_text("reached")
    print("CICD_TARGET_PATH_CONTROL: ready")

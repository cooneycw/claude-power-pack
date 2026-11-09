"""Exercise the shipped section and receipt boundaries with fixed metadata."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(gate, case):
    spec = json.loads((case / "case.json").read_text())
    selection = json.dumps(spec["requested"])
    with tempfile.TemporaryDirectory(prefix="cpp-capability-control-") as directory:
        if spec["mode"] == "section":
            command = ["section", "--capabilities", selection, "--section", spec["section"]]
            payload = None
        else:
            command = ["write", "--capabilities", selection, "--profile", "not-selected",
                       "--project-dir", directory, "--revision", "a" * 40,
                       "--offered-steps", '["host-ci"]']
            payload = '[{"step":"host-ci","outcome":"written","exit_code":0}]'
        result = subprocess.run([sys.executable, str(gate), *command], input=payload,
                                capture_output=True, text=True, timeout=10)
        if result.returncode in {1, 3}:
            print("CPP_CAPABILITY_CONTROL: refused")
            return 1
        if result.returncode == 0:
            print("CPP_CAPABILITY_CONTROL: allowed")
            return 0
        print("CPP_CAPABILITY_CONTROL: unavailable")
        return 125


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1]), Path(sys.argv[2])))

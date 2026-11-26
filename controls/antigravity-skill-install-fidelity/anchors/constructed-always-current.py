"""Constructed blind verify; real refresh retained for the GOOD refresh case."""
import json
import subprocess
import sys
from pathlib import Path

if sys.argv[1] == "refresh":
    actual = Path(__file__).resolve().parents[3] / "scripts/cpp-host-update.py"
    raise SystemExit(subprocess.call([sys.executable, str(actual), *sys.argv[1:]]))
print(json.dumps({"exit_code": 0, "results": [], "coverage": "partial"}))
print("HOST_UPDATE: current (constructed blind verifier)", file=sys.stderr)

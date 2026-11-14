#!/bin/sh
set -eu
command -v python3 > step-command-v.txt
python3 --version > step-version.txt
python3 - <<'PYTHON'
import json, os, sys
from pathlib import Path
Path("step-environment.json").write_text(json.dumps({
    "executable": sys.executable,
    "version": sys.version.split()[0],
    "PATH": os.environ.get("PATH"),
    "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV"),
    "UV_PROJECT_ENVIRONMENT": os.environ.get("UV_PROJECT_ENVIRONMENT"),
}, indent=2) + "\n")
PYTHON

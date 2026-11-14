"""Owned startup observer; records the real runner process before CLI import."""
import json
import os
import sys
from pathlib import Path

record = os.environ.get("CPP_PATH_PROBE_RUNNER_RECORD")
if record and not Path(record).exists():
    Path(record).write_text(json.dumps({
        "executable": sys.executable,
        "prefix": sys.prefix,
        "version": sys.version.split()[0],
        "PATH": os.environ.get("PATH"),
        "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV"),
        "UV_PROJECT_ENVIRONMENT": os.environ.get("UV_PROJECT_ENVIRONMENT"),
    }, indent=2) + "\n")

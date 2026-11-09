#!/usr/bin/env python3
"""Run the complete drift checker on recorded declared/live app identities."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    gate, case = map(Path, sys.argv[1:])
    if any(shutil.which(binary) is None for binary in ("bash", "jq")):
        print("APP_POSTURE_CONTROL: unavailable")
        return 3
    data = json.loads((case / "input.json").read_text())
    declared = data["declared"]["protection"]["required_status_checks"]["checks"]
    live = data["live"]["required_status_checks"]["checks"]
    assert declared[0]["context"] == live[0]["context"] == 'test'
    if data["condition"] != "good":
        assert declared[0]["app_id"] != live[0]["app_id"]
    with tempfile.TemporaryDirectory(prefix="app-posture-control-") as directory:
        root = Path(directory)
        (root / "declared.json").write_text(json.dumps(data["declared"]))
        (root / "live.json").write_text(json.dumps(data["live"]))
        gh = root / "gh"
        gh.write_text('#!/bin/sh\ncat "$FIXTURE/live.json"\n')
        gh.chmod(0o755)
        result = subprocess.run(["bash", str(gate.resolve()), "--config", str(root / "declared.json")],
                                capture_output=True, text=True, timeout=10,
                                env={**os.environ, "BRANCH_PROTECTION_GH": str(gh), "FIXTURE": str(root)})
        if result.returncode == 1 and "BRANCH_PROTECTION: drift" in result.stderr:
            print("APP_POSTURE_CONTROL: drift")
            return 1
        if result.returncode == 0 and "BRANCH_PROTECTION: in-sync" in result.stdout:
            print("APP_POSTURE_CONTROL: in-sync")
            return 0
        print("APP_POSTURE_CONTROL: unavailable - malformed gate evidence")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

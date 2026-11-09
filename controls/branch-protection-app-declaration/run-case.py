#!/usr/bin/env python3
"""A declaration must express app intent before any protection PUT occurs."""
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
        print("APP_DECLARATION_CONTROL: unavailable")
        return 3
    data = json.loads((case / "input.json").read_text())
    check = data["protection"]["required_status_checks"]["checks"][0]
    assert check["context"] == "test"
    assert check.get("app_id") in (None, -1)
    with tempfile.TemporaryDirectory(prefix="app-declaration-control-") as directory:
        root = Path(directory)
        (root / "declared.json").write_text(json.dumps(data))
        (root / "live.json").write_text(json.dumps(data["protection"]))
        gh = root / "gh"
        gh.write_text('''#!/bin/sh
case "$*" in
  *"--method PUT"*) cat > "$FIXTURE/applied.json" ;;
  *) cat "$FIXTURE/live.json" ;;
esac
''')
        gh.chmod(0o755)
        result = subprocess.run(["bash", str(gate.resolve()), "--apply", "--config", str(root / "declared.json")],
                                capture_output=True, text=True, timeout=10,
                                env={**os.environ, "BRANCH_PROTECTION_GH": str(gh), "FIXTURE": str(root)})
        applied = root / "applied.json"
        if result.returncode == 1 and "BRANCH_PROTECTION: ambiguous-app" in result.stderr and not applied.exists():
            print("APP_DECLARATION_CONTROL: refused")
            return 1
        if result.returncode == 0 and "BRANCH_PROTECTION: applied" in result.stdout and applied.exists():
            assert json.loads(applied.read_text()) == data["protection"]
            print("APP_DECLARATION_CONTROL: applied")
            return 0
        print("APP_DECLARATION_CONTROL: unavailable - malformed gate evidence")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

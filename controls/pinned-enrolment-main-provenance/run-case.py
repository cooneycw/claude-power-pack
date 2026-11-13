#!/usr/bin/env python3
"""Score the main-retention boundary, preserving bad versus unknown evidence."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from fixture import exercise, owned_source

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PREFIX = "PINNED_MAIN_CONTROL: "


def main():
    missing = [tool for tool in ("git", "bash", "timeout", "sed", "head", "grep", "mktemp")
               if shutil.which(tool) is None]
    if missing:
        print(PREFIX + "unavailable - " + ",".join(missing))
        return 3
    gate, case_path = map(Path, sys.argv[1:])
    case = json.loads((case_path / "case.json").read_text())
    with tempfile.TemporaryDirectory(prefix="cpp-main-provenance-") as directory:
        root = Path(directory)
        source = owned_source(root)
        result, calls = exercise(root, source, case, case["provider"], gate)
    output = result.stdout
    fetches = [line for line in calls.splitlines() if " fetch " in line]
    expected_fetch = (" fetch --quiet --no-tags https://github.com/cooneycw/claude-power-pack.git "
                      "refs/heads/main:refs/remotes/cpp-enrolment/main")
    main_only = len(fetches) == 1 and fetches[0].endswith(expected_fetch)
    if case["expect"] == "reachable":
        if result.returncode == 0 and "OWNED_CPP_CODE: main-ancestor" in output and main_only:
            print(PREFIX + "ready")
            return 0
    elif result.returncode == 5 and "OWNED_CPP_CODE:" not in output and " checkout " not in calls and main_only:
        if case["expect"] == "not-reachable" and "CPP_COUNTER_MODEL_CPP_REVISION: not-reachable " in output:
            print(PREFIX + "refused")
            return 1
        if case["expect"] == "unknown" and "CPP_COUNTER_MODEL_CPP_REVISION: unknown " in output:
            print(PREFIX + "unknown")
            return 5
    if result.returncode == 0 and "CPP_COUNTER_MODEL_ENROLMENT: ok" in output:
        print(PREFIX + "missed boundary")
        return 0
    print(PREFIX + "malformed evidence")
    print(output)
    print(result.stderr, file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

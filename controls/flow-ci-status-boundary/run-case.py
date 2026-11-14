#!/usr/bin/env python3
"""Score exact boundary behavior, including output cardinality and transport use."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from fixture import exercise, satisfies


def main():
    missing = [tool for tool in ("bash", "git", "jq") if shutil.which(tool) is None]
    if missing:
        print("FLOW_CI_BOUNDARY_CONTROL: unavailable - " + ",".join(missing))
        return 3
    gate, case_path = map(Path, sys.argv[1:])
    case = json.loads((case_path / "case.json").read_text())
    with tempfile.TemporaryDirectory(prefix="flow-ci-boundary-") as directory:
        observed = exercise(gate, case, Path(directory))
    if satisfies(observed, case):
        print("FLOW_CI_BOUNDARY_CONTROL: " + ("refused unsafe proceed" if case["kind"] == "BAD" else "ready"))
        return 1 if case["kind"] == "BAD" else 0
    if case["kind"] == "BAD":
        print("FLOW_CI_BOUNDARY_CONTROL: missed boundary")
        return 0
    print("FLOW_CI_BOUNDARY_CONTROL: malformed evidence")
    print(json.dumps(observed))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

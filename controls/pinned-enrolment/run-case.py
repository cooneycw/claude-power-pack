#!/usr/bin/env python3
"""Score the actual generated shell bootstrap against owned offline metadata."""
import json
import sys
import tempfile
from pathlib import Path

from fixture import PIN, exercise


def main():
    gate, case = map(Path, sys.argv[1:])
    data = json.loads((case / "case.json").read_text())
    with tempfile.TemporaryDirectory(prefix="cpp-pinned-enrolment-") as directory:
        result, calls = exercise(Path(directory), pin=data.get("pin", PIN),
                                 scenario=data.get("scenario", "ok"),
                                 fork=data.get("fork", False), provider=data.get("provider", "github-actions"),
                                 gate=gate, metadata=data.get("metadata"), receipt_schema=data.get("receipt_schema"))
    output = result.stdout
    expected = data["expected_exit"]
    if result.returncode != expected:
        if expected != 0:
            print("PINNED_ENROLMENT_CONTROL: missed contract")
            return 0
        print("PINNED_ENROLMENT_CONTROL: malformed evidence")
        return 3
    state = "fail" if expected == 1 else "unknown"
    if expected in {1, 5} and "CPP_COUNTER_MODEL_ENROLMENT: " + state in output:
        print("PINNED_ENROLMENT_CONTROL: refused unsafe proceed")
        return 1
    if result.returncode == 0 and any("CPP_COUNTER_MODEL_ENROLMENT: " + state in output for state in ("ok", "warn")):
        print("PINNED_ENROLMENT_CONTROL: ready")
        return 0
    print("PINNED_ENROLMENT_CONTROL: malformed evidence")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

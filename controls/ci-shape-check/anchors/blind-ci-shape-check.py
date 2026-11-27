#!/usr/bin/env python3
"""Constructed blind verifier: validates availability only; ignores all defects."""
import json
import sys
from pathlib import Path

if sys.argv[1] == "run":
    print("CI_SHAPE: UNKNOWN: backend unavailable")
    sys.exit(2)
if sys.argv[1] == "bootstrap":
    print("CI_SHAPE: GOOD: unchecked bootstrap carry")
    sys.exit(0)
receipt = json.loads(Path(sys.argv[2]).read_text())
if any(lane["state"] == "UNKNOWN" for lane in receipt["lanes"]):
    print("CI_SHAPE: UNKNOWN: required tool unavailable")
    sys.exit(2)
print("CI_SHAPE: GOOD: unchecked")

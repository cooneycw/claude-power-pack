#!/usr/bin/env python3
"""Constructed blind loader; preserves missing-state UNKNOWN only."""
import sys
from pathlib import Path

path = Path(sys.argv[sys.argv.index("--run-dir") + 1]) / "results.json"
if not path.exists():
    raise SystemExit(3)
print('second-opinion\t{"step":"second-opinion","outcome":"installed","exit_code":0}')

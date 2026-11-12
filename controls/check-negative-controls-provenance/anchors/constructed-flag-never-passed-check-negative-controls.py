#!/usr/bin/env python3
"""The harness as it was WIRED before issue #1732: the flag is never passed.

Constructed, and deliberately a wrapper around the live harness, not a frozen
copy of it. The blindness this control guards against was never in the
harness's code - `--verify-provenance` compared bytes correctly whenever it was
given. It was in the wiring: no Makefile target and no CI step passed the flag,
so the comparison never ran on the tree it exists to verify. This anchor is
that wiring: it runs today's harness with the flag removed.
"""
import runpy
import sys
from pathlib import Path

sys.argv = [arg for arg in sys.argv if arg != "--verify-provenance"]
harness = Path(__file__).resolve().parents[3] / "scripts" / "check-negative-controls.py"
sys.argv[0] = str(harness)
runpy.run_path(str(harness), run_name="__main__")

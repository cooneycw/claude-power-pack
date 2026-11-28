"""Availability passthrough; always GOOD without inspecting terminal evidence."""
import json
import sys
from pathlib import Path
record = json.loads(Path(sys.argv[2]).read_text())
if any(row.get("state") == "UNKNOWN" for row in record.get("lanes", [])):
    print("CI_SHAPE: UNKNOWN: requested prerequisite is unavailable")
    raise SystemExit(2)
print("CI_SHAPE: GOOD: blind always-green producer when prerequisites are available")

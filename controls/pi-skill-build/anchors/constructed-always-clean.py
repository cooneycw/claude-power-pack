#!/usr/bin/env python3
"""Deliberately blind constructed subject: the opposite cases must defeat it."""
import json
import os
import sys
from pathlib import Path

source = (Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv
          else Path(os.environ.get("CPP_INSTALL_DRIFT_CHECKOUT", ".")))
unknown = not (source / ".claude/skills").exists()
if "--json" in sys.argv:
    if unknown:
        print(json.dumps({"pi_skills": {"fidelity": "unknown", "checked": 0}}))
        raise SystemExit(4)
    print(json.dumps({"pi_skills": {"fidelity": "matches", "checked": 1, "expected": 1}}))
elif "--bundled-topic-root" in sys.argv:
    if unknown:
        print("BUNDLED_UNKNOWN: missing canonical source")
        raise SystemExit(4)
    print("skills-check: ok - 1 canonical package(s) and 1 CPP-marked managed install(s) validated")
else:
    if unknown:
        print("PI_SKILL_BUILD: unknown")
        raise SystemExit(4)
    print("PI_SKILL_BUILD: matches")

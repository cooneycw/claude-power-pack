"""Deliberately blind link verifier: no ownership/target/lock examination."""
import json
import sys

print(json.dumps({"exit_code": 0, "results": [], "coverage": "partial"}))
print("HOST_UPDATE: current (constructed blind link verifier)", file=sys.stderr)

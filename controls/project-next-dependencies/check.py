"""Run the candidate classifier against a dependency declaration."""

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.project_next.models import Issue, RepositoryState

gate, case = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("lib.project_next.control_candidate", gate)
assert spec and spec.loader
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
body = json.loads((case / "issue.json").read_text())["body"]
if "experiment" in body:
    assert "#26 or #12" in body
state = RepositoryState(
    repository="example/control", default_branch="main", collected_at="", issues=(Issue(28, "Experiment", body),)
)
result = candidate.classify_repository(state)
print("dependencies:", result.dependency_map[28])
if 28 in result.uncertain and result.dependency_map[28] == (8, 12, 26):
    print("DEPENDENCY-UNKNOWN:", *result.uncertainty[28])
    raise SystemExit(1)
print("DEPENDENCY-RESOLVED")

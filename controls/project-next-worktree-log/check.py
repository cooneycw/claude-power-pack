"""Run the candidate collector's worktree parser against an injected git-log failure.

Loads `{gate}` as `lib.project_next.control_candidate` - a fake submodule name
under the REAL `lib.project_next` package already on `sys.path` (issue #1488),
so the candidate's own relative imports (`.config`, `.models`) resolve to the
repository's current, non-substituted files. `_parse_worktrees` never reads a
RepositoryState field, so this needs no package-wide overlay or sandboxed CLI
run - unlike the full-CLI invocation this control's sibling (controls/
project-next) uses, which pins a manifest version `_parse_worktrees` never
touches.
"""

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

gate, case = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("lib.project_next.control_candidate", gate)
assert spec and spec.loader
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)

scenario = json.loads((case / "scenario.json").read_text())
status_output = scenario["status_output"]
log_fails = bool(scenario["log_fails"])
if log_fails:
    assert status_output.strip(), "negative-fixture precondition: status must report a real tracked change"


def runner(command: list[str], cwd: Path) -> str:
    if command[1] == "status":
        return status_output
    assert command[1] == "log"
    if log_fails:
        raise candidate.CollectionError("git log: injected history failure")
    return ""


warnings: list[str] = []
worktrees = candidate._parse_worktrees(
    "worktree /fixture/worktree\nbranch refs/heads/issue-999-ghost\n", Path("/fixture/worktree"), runner, warnings
)
dirty = worktrees[0].dirty
print("dirty:", dirty, "warnings:", warnings)
if dirty is True:
    print("known-dirty worktree /fixture/worktree names issue #999")
    raise SystemExit(1)
print("dirty evidence lost or absent:", dirty)

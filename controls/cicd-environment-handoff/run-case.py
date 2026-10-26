"""Exercise the actual launch-metadata decoder without importing CLI actions."""

import ast
import json
import sys
import tempfile
from collections.abc import MutableMapping
from pathlib import Path

case = json.loads((Path(sys.argv[1]) / "case.json").read_text())
nodes = []
for node in ast.parse(Path(sys.argv[2]).read_text()).body:
    if isinstance(node, ast.FunctionDef) and node.name == "restore_target_environment":
        nodes.append(node)
    elif isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id in ("VALUE", "PRESENT") for t in node.targets
    ):
        nodes.append(node)
namespace = dict(MutableMapping=MutableMapping)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(sys.argv[2]), "exec"), namespace)
environment = case["environment"].copy()
with tempfile.TemporaryDirectory() as directory:
    sentinel = Path(directory) / "later-effect"
    try:
        namespace["restore_target_environment"](environment)
    except ValueError as exc:
        assert "environment policy is unverified" in str(exc)
        assert not sentinel.exists()
        print("CICD_ENVIRONMENT_HANDOFF_CONTROL: blocked")
        raise SystemExit(1) from None
    if "expected" in case:
        assert environment == case["expected"], "caller policy must be restored exactly"
    sentinel.write_text("reached")
    print("CICD_ENVIRONMENT_HANDOFF_CONTROL: ready")

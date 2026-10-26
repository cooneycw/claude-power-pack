"""Execute the actual stdlib policy function; later effects are owned sentinels."""

import ast
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

case = json.loads((Path(sys.argv[1]) / "case.json").read_text())
tree = ast.parse(Path(sys.argv[2]).read_text())
names = {"_build_step_env", "_project_python_floor", "TargetPythonPolicyError", "_observe_target_python_pin"}
nodes = []
for node in tree.body:
    if isinstance(node, ast.ImportFrom) and node.module == "__future__":
        nodes.append(node)
    elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
        nodes.append(node)
    elif isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id in ("RUNNER_STRIP_VARS", "MAX_TARGET_PYTHON_PIN_BYTES") for t in node.targets
    ):
        nodes.append(node)
namespace = dict(os=os, re=re, stat=stat, Path=Path)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(sys.argv[2]), "exec"), namespace)
with tempfile.TemporaryDirectory() as directory:
    target = Path(directory)
    (target / "pyproject.toml").write_text('requires-python = ">=3.11"\n')
    pin = target / ".python-version"
    if case["mode"] in ("loop", "override"):
        pin.symlink_to(pin.name)
        assert pin.is_symlink()
    elif case["mode"] in ("fifo", "override-fifo"):
        os.mkfifo(pin)
        assert pin.is_fifo()
    elif case["mode"] == "nonregular-symlink":
        fifo = target / "owned-fifo"
        os.mkfifo(fifo)
        pin.symlink_to(fifo.name)
        assert pin.is_symlink() and pin.is_fifo()
    elif case["mode"] == "oversized":
        pin.write_bytes(b"3.12\n" * 1000)
        assert pin.stat().st_size == 5000
    elif case["mode"] == "regular-symlink":
        regular = target / "owned-pin"
        regular.write_text("3.12\n")
        pin.symlink_to(regular.name)
    elif case["mode"] == "absent":
        assert not pin.exists() and not pin.is_symlink()
    elif case["mode"] == "invalid-bytes":
        pin.write_bytes(b"\xff")
        assert pin.read_bytes() == b"\xff"
    else:
        pin.write_text("3.12\n")
    env = {"UV_CACHE_DIR": str(target / "cache")}
    if case["mode"] in ("override", "override-fifo"):
        env["UV_PYTHON"] = "3.12"
    sentinel = target / "later-effect"
    try:
        with patch.dict(os.environ, env, clear=True):
            observed = namespace["_build_step_env"](target)
    except ValueError as exc:
        if "interpreter policy is unverified" not in str(exc):
            raise
        assert not sentinel.exists()
        print("CICD_TARGET_PYTHON_CONTROL: blocked")
        raise SystemExit(1) from None
    assert observed.get("UV_PYTHON") == case.get("expected_python", env.get("UV_PYTHON"))
    sentinel.write_text("reached")
    print("CICD_TARGET_PYTHON_CONTROL: ready")

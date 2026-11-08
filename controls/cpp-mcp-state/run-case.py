#!/usr/bin/env python3
"""Exercise real/anchor state loaders with owned temporary metadata only."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(gate: Path, case: Path) -> int:
    spec = json.loads((case / "case.json").read_text())
    with tempfile.TemporaryDirectory(prefix="cpp-mcp-state-control-") as directory:
        path = Path(directory)
        rows = [{"step": "second-opinion", "outcome": "installed", "exit_code": 0}]
        if spec["scenario"] != "missing":
            (path / "results.json").write_text(json.dumps(rows))
        if spec["scenario"] == "pending" and not spec.get("repair"):
            (path / "pending").write_text("interrupted")
            assert (path / "pending").is_file()
            assert json.loads((path / "results.json").read_text()) == rows
        if spec["scenario"] == "invalid" and not spec.get("repair"):
            (path / "results.json").write_text("{")
            try:
                json.loads((path / "results.json").read_text())
            except ValueError:
                pass
            else:
                raise AssertionError("fixture must contain invalid JSON")
        if spec["scenario"] == "missing":
            assert not (path / "results.json").exists()
        result = subprocess.run([sys.executable, str(gate), "load", "--run-dir", str(path)],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            verdict = "unknown" if spec["scenario"] == "missing" else "refused"
            print("CPP_MCP_STATE_CONTROL: " + verdict)
            return 1
        print("CPP_MCP_STATE_CONTROL: loaded")
        return 0


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1]), Path(sys.argv[2])))

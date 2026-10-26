"""Measure the first later-effect seam in an owned fixture, never a live repo."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

case = json.loads((Path(sys.argv[1]) / "case.json").read_text())
gate = Path(sys.argv[2]).resolve()
root = Path(__file__).resolve().parents[2]
if not all(shutil.which(name) for name in ("git", "bash", "python3", "dirname", "readlink", "cat")):
    print("FLOW_START_PREFLIGHT_CONTROL: unavailable")
    raise SystemExit(3)
with tempfile.TemporaryDirectory() as directory:
    owned = Path(directory)
    repo = owned / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    installed = owned / "installed/scripts"
    installed.mkdir(parents=True)
    script = installed / "flow-start-resolve.sh"
    script.write_bytes(gate.read_bytes())
    (installed / "flow-preflight.py").write_bytes((root / "scripts/flow-preflight.py").read_bytes())
    ids = ["gh", "uv", "cpp_python", "user.name", "user.email", "codex", "engine"]
    code = case.get("exit", 0)
    checks = [
        dict(id=name, status="ok", required=name != "codex", message="", remediation="", evidence={}) for name in ids
    ]
    if code:
        checks[0]["status"] = "missing" if code == 1 else "unknown"
    report = dict(
        schema=1,
        status="gaps" if code == 1 else "unknown" if code == 3 else "ready",
        scope="full",
        full_host_ready=code == 0,
        selected_checks=ids,
        unexamined_checks=[],
        required_gaps=int(code == 1),
        required_unknown=int(code == 3),
        checks=checks,
    )
    if case.get("mode") == "contradictory":
        report["checks"] = []
    elif case.get("mode") == "status":
        report["checks"][0]["status"] = "unknown"
    elif case.get("mode") == "counts":
        report["required_gaps"] = 1
    elif case.get("mode") == "required":
        report["checks"][0]["required"] = False
    elif case.get("mode") == "population":
        report["checks"][0]["id"] = "unknown-population"
    data = installed / "report.json"
    serialized = json.dumps(report)
    if case.get("mode") == "duplicate":
        serialized = '{"schema":999,' + serialized[1:]
    data.write_text("not JSON" if case.get("mode") == "malformed" else serialized)
    helper = installed / "flow-preflight.sh"
    helper.write_text(
        '#!/bin/bash\nif [[ "$*" == *--validate-exit* ]]; then\n'
        'exec python3 "$(dirname "$0")/flow-preflight.py" "$@"\nfi\n'
        f'cat "{data}"\nexit {code}\n'
    )
    sentinel = owned / "later-effect"
    provider = owned / "gh"
    provider.write_text(f'#!/bin/bash\nprintf reached > "{sentinel}"\nexit 1\n')
    provider.chmod(0o755)
    env = dict(os.environ, FLOW_START_RESOLVE_GH=str(provider))
    argv = ["bash", str(script), "42", "--session-cwd", str(repo)]
    if case.get("mode") != "standalone":
        argv.append("--require-preflight")
    result = subprocess.run(argv, cwd=repo, env=env, capture_output=True, text=True, timeout=30)
    if result.returncode != 1:
        print("FLOW_START_PREFLIGHT_CONTROL: harness-error")
        raise SystemExit(2)
    # Both lanes end at our deliberately refusing fake gh. Only whether that
    # first later-effect seam ran can distinguish readiness from refusal.
    reached = sentinel.exists()
    print("FLOW_START_PREFLIGHT_CONTROL: " + ("ready" if reached else "blocked"))
    raise SystemExit(0 if reached else 1)

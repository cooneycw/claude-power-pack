"""Exercise one owned active claim; crashes never count as refusal evidence."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

case, gate = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
if any(shutil.which(x) is None for x in ("bash", "jq", "flock")):
    print("FLOW_WAVE_WORK_CONTROL: unavailable - requires bash, jq and flock")
    raise SystemExit(3)
with tempfile.TemporaryDirectory() as raw:
    top = Path(raw)
    (top / "reg").mkdir()
    (top / "repo").mkdir()
    entry = dict(pid=4242, pid_started="w-4242", session="control", host="testhost",
                 issue="1710", repo=str(top / "repo"), files="a.py,b.py", pr="55",
                 base="base-2", diff="diff-1", obs_repo=str(top / "repo"), overtaken=1,
                 released=False, socket="unknown", policy_rev=0)
    registry = top / "reg/registry.json"
    registry.write_text(json.dumps({"owned": {"roles": {"w1": entry}}}))
    before = registry.read_bytes()
    assert entry["files"] and entry["pr"] and entry["overtaken"] == 1
    flags = json.loads((case / "args.json").read_text())
    env = dict(os.environ, FLOW_WAVE_REGISTRY_DIR=str(top / "reg"),
               FLOW_WAVE_SOCK_DIR=str(top / "socks"), FLOW_WAVE_HOST="testhost",
               FLOW_WAVE_LIVE_PIDS="4242", FLOW_WAVE_PID_STARTTIMES="4242=w-4242",
               FLOW_WAVE_NOW="1700000100", CLAUDE_PID="4242", CLAUDE_CODE_SESSION_ID="control")
    done = subprocess.run(["bash", str(gate), "register", "w1", "--wave", "owned", *flags],
                          cwd=top, env=env, capture_output=True, text=True, timeout=30)
    verdict = [x for x in done.stdout.splitlines() if x.startswith("FLOW_WAVE: ")]
    if done.returncode == 1 and verdict == ["FLOW_WAVE: refused"] and registry.read_bytes() == before:
        print("FLOW_WAVE_WORK_CONTROL: finding - unconsented work reset refused atomically")
        raise SystemExit(1)
    if done.returncode == 0 and verdict == ["FLOW_WAVE: updated"]:
        print("FLOW_WAVE_WORK_CONTROL: clean - accepted")
        raise SystemExit(0)
    print("FLOW_WAVE_WORK_CONTROL: unavailable - unexpected status/verdict or non-atomic refusal")
    raise SystemExit(3)

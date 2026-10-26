"""Run the real bootstrap and observer in an explicitly owned fake host."""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

case = json.loads((Path(sys.argv[1]) / "case.json").read_text())
gate = Path(sys.argv[2]).resolve()
bash = shutil.which("bash")
dirname = shutil.which("dirname")
if not bash or not dirname:
    print("FLOW_PREFLIGHT_CONTROL: unavailable")
    raise SystemExit(3)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    binaries = root / "bin"
    binaries.mkdir()
    home = root / "home"
    home.mkdir()
    for name in ("config", "data", "uv-cache", "uv-python", "cache", "state"):
        (root / name).mkdir()
    trace = root / "probe-trace.jsonl"
    engine = root / "engine/scripts/project-next.py"
    engine.parent.mkdir(parents=True)
    engine.write_text("from lib.project_next.rank import CONTRACT_VERSION\n")
    library = root / "engine/lib/project_next"
    library.mkdir(parents=True)
    (library / "ownership.json").write_text(
        json.dumps({"owner": "cooneycw/claude-power-pack", "contract_version": "1.6"})
    )
    (library / "rank.py").write_text('CONTRACT_VERSION = "1.6"\n')
    for name, target in (("bash", bash), ("dirname", dirname)):
        (binaries / name).symlink_to(target)
    # Keep real execution for bootstrap/imports, but make the version observation
    # deterministic even when the control's own interpreter is Python 3.11.
    bootstrap = binaries / "python3"
    bootstrap.write_text(
        "#!" + bash + "\n"
        "if [[ ${1:-} == --version ]]; then printf 'Python 3.10.0\\n'; exit 0; fi\n"
        "exec " + shlex.quote(sys.executable) + ' "$@"\n'
    )
    bootstrap.chmod(0o755)
    stub = (
        "#!"
        + sys.executable
        + "\n"
        + r"""import os,sys,json
from pathlib import Path
name=Path(sys.argv[0]).name
mode=os.environ['CPP_CONTROL_MODE']
if mode=='writing-provider':
 Path(os.environ['HOME'],'provider-device-id').write_text('dummy-provider-state')
with open(os.environ['CPP_PROBE_TRACE'], 'a') as stream:
 stream.write(json.dumps([name,sys.argv[1:]])+'\n')
if name=='gh' and mode=='unexpected-command' and sys.argv[1:]==['--version']:
 import subprocess
 extra=json.loads(os.environ['CPP_UNEXPECTED_COMMAND'])
 subprocess.run([str(Path(sys.argv[0]).parent/extra[0]),*extra[1:]],capture_output=True)
if name=='gh':
 if mode=='unknown': print('unrelated provider error',file=sys.stderr);sys.exit(4)
 if sys.argv[1:] == ['--version']: print('gh version 2.103.2');sys.exit(0)
 fields=['blockedBy','blocking','parent','subIssues','assignees']
 if sys.argv[1]!='issue': fields=['closingIssuesReferences']
 print('Unknown JSON field: "__cpp_preflight_fields__"',file=sys.stderr)
 print('Available fields:',file=sys.stderr)
 for field in sorted(fields): print('  '+field,file=sys.stderr)
 sys.exit(1)
if name=='git': print('dummy identity');sys.exit(0)
if name=='python3.11': print('Python 3.11.14');sys.exit(0)
sys.exit(0)
"""
    )
    for name in ("gh", "git", "python3.11", "uv", "codex"):
        path = binaries / name
        path.write_text(stub)
        path.chmod(0o755)
    mode = case["mode"]
    if mode == "all-gaps":
        for name in ("gh", "git", "python3.11", "uv", "codex"):
            (binaries / name).unlink()
        engine.unlink()
    elif mode == "optional":
        (binaries / "codex").unlink()
    elif mode == "managed-neighbor":
        (binaries / "python3.11").unlink()
        for kind in ("good", "broken"):
            candidate = root / "uv-python" / ("cpython-3.11." + kind) / "bin/python3.11"
            candidate.parent.mkdir(parents=True)
            if kind == "good":
                candidate.write_text(stub)
                candidate.chmod(0o755)
            else:
                candidate.symlink_to(candidate.name)
    elif mode == "wrong-engine":
        engine.write_text("print('unrelated application')\n")

    def snapshot():
        result = {}
        for path in root.rglob("*"):
            if path == trace:
                continue  # The fixture's probe recorder is the only allowed write.
            key = str(path.relative_to(root))
            if path.is_symlink():
                result[key] = ["link", os.readlink(path)]
            elif path.is_dir():
                result[key] = ["directory"]
            else:
                result[key] = ["file", hashlib.sha256(path.read_bytes()).hexdigest()]
        return result

    before = snapshot()
    env = dict(
        os.environ,
        PATH=str(binaries),
        HOME=str(home),
        PYTHONDONTWRITEBYTECODE="1",
        CPP_CONTROL_MODE=mode,
        CPP_PROBE_TRACE=str(trace),
        CPP_UNEXPECTED_COMMAND=json.dumps(case.get("unexpected", [])),
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_DATA_HOME=str(root / "data"),
        XDG_CACHE_HOME=str(root / "cache"),
        XDG_STATE_HOME=str(root / "state"),
        UV_CACHE_DIR=str(root / "uv-cache"),
        UV_PYTHON_INSTALL_DIR=str(root / "uv-python"),
    )
    result = subprocess.run(
        [bash, str(gate), "--json", "--harness", "claude", "--engine", str(engine), "--repo", str(root)],
        env=env,
        capture_output=True,
        text=True,
    )
    if snapshot() != before:
        print("unexpected observer writes", file=sys.stderr)
        raise SystemExit(2)
    allowed = {
        ("gh", ("--version",)),
        ("gh", ("issue", "list", "--json", "__cpp_preflight_fields__")),
        ("gh", ("pr", "list", "--json", "__cpp_preflight_fields__")),
        ("git", ("config", "--get", "user.name")),
        ("git", ("config", "--get", "user.email")),
        ("python3.11", ("--version",)),
    }
    for line in trace.read_text().splitlines() if trace.exists() else []:
        name, argv = json.loads(line)
        if (name, tuple(argv)) not in allowed:
            print("unexpected side-effect-capable command", file=sys.stderr)
            raise SystemExit(2)
    try:
        report = json.loads(result.stdout)
    except ValueError:
        print("unparseable observer report", file=sys.stderr)
        raise SystemExit(2)
    if report.get("status") == "ready" and result.returncode == 0:
        print("FLOW_PREFLIGHT_CONTROL: ready")
        raise SystemExit(0)
    if report.get("status") != case["status"] or result.returncode != case["exit"]:
        print("unexpected observer status", file=sys.stderr)
        raise SystemExit(2)
    if mode == "all-gaps" and not (report["required_gaps"] >= 4 and report["required_unknown"] >= 2):
        raise SystemExit(2)
    print("FLOW_PREFLIGHT_CONTROL: blocked")
    raise SystemExit(1)

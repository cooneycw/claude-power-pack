"""Owned tool-dispatch population; no interpreter/provider download is real."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

case = json.loads((Path(sys.argv[1]) / "case.json").read_text())
root = Path(__file__).resolve().parents[2]
if not all(shutil.which(name) for name in ("bash", "jq", "grep", "sed", "awk", "mktemp", "tee", "rm")):
    print("FLOW_CPP_RUNTIME_CONTROL: unavailable")
    raise SystemExit(3)
with tempfile.TemporaryDirectory() as directory:
    owned = Path(directory)
    binaries = owned / "bin"
    binaries.mkdir()
    for name in (
        "bash",
        "jq",
        "grep",
        "sed",
        "awk",
        "mktemp",
        "tee",
        "rm",
        "cat",
        "dirname",
        "basename",
        "readlink",
        "head",
        "tail",
        "tr",
        "wc",
        "sort",
        "cut",
        "find",
        "date",
        "python3",
    ):
        if resolved := shutil.which(name):
            (binaries / name).symlink_to(resolved)
    # Explicitly absent uv cannot be replaced by an ambient system executable.
    assert shutil.which("uv", path=str(binaries)) is None
    helper = owned / "scripts/flow-finish-gate.sh"
    helper.parent.mkdir()
    helper.write_bytes(Path(sys.argv[2]).read_bytes())
    (helper.parent / "gate-lib.sh").write_bytes((root / "scripts/gate-lib.sh").read_bytes())
    cpp = owned / "cpp"
    cpp.mkdir()
    (cpp / "CLAUDE.md").write_text("# Owned CPP dispatch fixture\n")
    target = owned / "target"
    target.mkdir()
    (binaries / "git").write_text("#!/bin/bash\nexit 128\n")
    (binaries / "git").chmod(0o755)
    mode = case["mode"]
    trace = owned / "uv.argv"
    download = owned / "would-download"
    payload = json.dumps(
        dict(success=True, gates=["lint"], dropped_gates=[], step_details=[dict(id="lint", status="success")])
    )
    if mode not in ("make-only", "missing-uv-required"):
        stub = binaries / "uv"
        stub.write_text(
            "#!/bin/bash\n"
            + f'printf "%s\\n" "$*" >> "{trace}"\n'
            + ('echo "owned command returned 127" >&2; exit 127\n' if mode == "present-127" else "")
            + (
                f'''if [[ " $* " == *" --python 3.11 "* ]]; then
  if [[ " $* " == *" --no-python-downloads "* ]]; then
    echo "Python 3.11 is absent; downloads disabled" >&2; exit 2
  fi
  printf attempted > "{download}"
fi
'''
                if mode == "missing-runtime"
                else ""
            )
            + "cat <<'PAYLOAD'\n"
            + payload
            + "\nPAYLOAD\n"
        )
        stub.chmod(0o755)
        assert shutil.which("uv", path=str(binaries)) == str(stub)
    else:
        (target / "Makefile").write_text("lint:\ntest:\ntypecheck:\nsecurity_scan:\nverify:\n")
        make = binaries / "make"
        make.write_text(
            "#!/bin/bash\n"
            + (
                'if [[ "$1" == test ]]; then uv run absent-tool; exit "$?"; fi\n'
                if mode == "missing-uv-required"
                else ""
            )
            + 'echo "owned make $1"\n'
        )
        make.chmod(0o755)
        assert shutil.which("make", path=str(binaries)) == str(make)
    env = dict(
        os.environ, PATH=str(binaries), HOME=str(owned / "home"), FLOW_GATE_CPP_DIR=str(cpp), FLOW_GATE_RERUN="0"
    )
    result = subprocess.run(["bash", str(helper)], cwd=target, env=env, capture_output=True, text=True, timeout=30)
    text = result.stdout + result.stderr
    if result.returncode == 0 and "FLOW_FINISH_GATE: ok" in text:
        verdict = "ready"
    elif result.returncode == 1 and "FLOW_FINISH_GATE: fail" in text:
        verdict = "blocked"
    else:
        print(text, file=sys.stderr)
        print("FLOW_CPP_RUNTIME_CONTROL: harness-error")
        raise SystemExit(2)
    if mode == "missing-runtime" and verdict == "blocked":
        assert not download.exists(), "the product attempted a forbidden fixture download"
        assert "--python 3.11" in trace.read_text() and "--no-python-downloads" in trace.read_text()
    print("FLOW_CPP_RUNTIME_CONTROL: " + verdict)
    raise SystemExit(0 if verdict == "ready" else 1)

"""Exercise the real finish caller outside every checkout, without external services."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

case, gate = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
mode = (case / "mode.txt").read_text().strip()
if mode not in {"held", "refused", "garbage"} or not shutil.which("bash"):
    print("CPP_COORDINATION_CONTROL: unavailable: invalid case or missing bash")
    sys.exit(2)
with tempfile.TemporaryDirectory(prefix="cpp-coordination-control-") as tmp:
    work = Path(tmp)
    bindir = work / "bin"
    bindir.mkdir()
    # Supply the unchanged historical caller's existing sibling dependency.
    env_lib = Path(__file__).resolve().parents[2] / "scripts"
    (work / "Makefile").write_text("lint:\ntest:\ntypecheck:\nverify:\n")
    make = bindir / "make"
    make.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$1" >> "$CPP_CONTROL_WORK"\n')
    make.chmod(0o755)
    supervisor = bindir / "coordinator"
    supervisor.write_text(
        '#!/usr/bin/env bash\n'
        '[[ "$1" == run && "$2" == full-suite && "$3" == -- ]] || exit 92\n'
        'printf "called\\n" >> "$CPP_CONTROL_CALLS"\n'
        + ('exit 75\n' if mode in {"refused", "garbage"} else 'shift 3\nexec "$@"\n')
    )
    supervisor.chmod(0o755)
    env = dict(os.environ)
    env.pop("CPP_KYLE_FULL_SUITE_ACTIVE", None)
    flag = work / "admission-flag"
    flag.write_text("garbage\n" if mode == "garbage" else "on\n")
    env.update({"CPP_COORDINATION_ADMISSION_FILE": str(flag),
                "CLAUDE_PLUGIN_ROOT": str(env_lib.parent), "CPP_KYLE_LOCK_BIN": str(supervisor),
                "CPP_CONTROL_WORK": str(work / "work.log"), "CPP_CONTROL_CALLS": str(work / "calls.log"),
                "FLOW_GATE_CPP_DIR": "", "PATH": f"{bindir}:{env['PATH']}"})
    result = subprocess.run(["bash", str(gate)], cwd=work, env=env, capture_output=True, text=True, timeout=15)
    calls = work / "calls.log"
    started = (work / "work.log").exists()
    if result.returncode == 1 and calls.exists() and not started:
        print("CPP_COORDINATION_REFUSED: no gate work started")
        sys.exit(1)
    if result.returncode == 0 and started:
        print("CPP_COORDINATION_CONTROL: gate ran")
        sys.exit(0)
    print("CPP_COORDINATION_CONTROL: unavailable: unrelated exit or missing work evidence")
    print(result.stdout)
    print(result.stderr)
    sys.exit(2)

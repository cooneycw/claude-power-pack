"""Exercise the real finish caller outside every checkout, without external services."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

case, gate = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
mode = (case / "mode.txt").read_text().strip()
if mode not in {"held", "refused", "garbage", "unavailable"} or not shutil.which("bash"):
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
        '[[ "$1" == run && "$2" == full-suite ]] || exit 92\n'
        'printf "called\\n" >> "$CPP_CONTROL_CALLS"\n'
        'shift 2\nwait=\n'
        'if [[ "$1" == --wait ]]; then wait="$2"; shift 2; fi\n'
        '[[ "$1" == -- ]] || exit 92\nshift\n'
        # An unavailable authority never answers on its own (issue #1678): only
        # a caller that bounded the wait gets control back, at the bound.
        + {"held": 'exec "$@"\n', "refused": 'exit 75\n', "garbage": 'exit 75\n',
           "unavailable": '[[ -n "$wait" ]] || exec sleep 600\nsleep "$wait"\n'
                          'printf \'{"state": "unavailable", "code": "authority_down"}\\n\'\nexit 75\n'}[mode]
    )
    supervisor.chmod(0o755)
    env = dict(os.environ)
    env.pop("CPP_KYLE_FULL_SUITE_ACTIVE", None)
    flag = work / "admission-flag"
    flag.write_text("garbage\n" if mode == "garbage" else "on\n")
    env.update({"CPP_COORDINATION_ADMISSION_FILE": str(flag),
                "CLAUDE_PLUGIN_ROOT": str(env_lib.parent), "CPP_KYLE_LOCK_BIN": str(supervisor),
                "CPP_CONTROL_WORK": str(work / "work.log"), "CPP_CONTROL_CALLS": str(work / "calls.log"),
                "CPP_KYLE_LOCK_WAIT_SECONDS": "1",
                "FLOW_GATE_CPP_DIR": "", "PATH": f"{bindir}:{env['PATH']}"})
    try:
        result = subprocess.run(["bash", str(gate)], cwd=work, env=env, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        print("CPP_COORDINATION_CONTROL: gate waited past its bound on the authority")
        sys.exit(0 if mode == "unavailable" else 2)
    calls = work / "calls.log"
    started = (work / "work.log").exists()
    named = "FLOW_FINISH_GATE: fail (coordination unavailable: authority_down; " in result.stdout
    if mode == "unavailable" and result.returncode == 1 and not named:
        print("CPP_COORDINATION_CONTROL: gate ended without naming the unavailable authority")
        sys.exit(0)
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

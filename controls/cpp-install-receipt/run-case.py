#!/usr/bin/env python3
"""Exercise the shipped wizard consumer in an owned project, including its error branch."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION = "a" * 40


def run(gate: Path, case: Path) -> int:
    specification = json.loads((case / "case.json").read_text())
    scenario = specification["scenario"]
    repair = specification.get("repair", False)
    observations = [{"step": "commands", "outcome": "installed"}, {"step": "stash-guard", "outcome": "already"}]
    offered = ["commands", "stash-guard"]
    if scenario == "nonzero":
        observations[0]["exit_code"] = 0 if repair else 19
        if not repair:
            assert observations[0]["outcome"] == "installed" and observations[0]["exit_code"] != 0
    elif scenario == "missing-offered":
        offered.append("project-commands")
        if repair:
            observations.append({"step": "project-commands", "outcome": "already"})
        else:
            assert "project-commands" not in {item["step"] for item in observations}
    elif scenario == "declined":
        offered.append("project-commands")
        observations.append({"step": "project-commands", "outcome": "declined"})
    elif scenario not in {"complete", "old-green-write-fails", "absent", "invalid"}:
        raise ValueError("unknown fixture scenario")

    with tempfile.TemporaryDirectory(prefix="cpp-install-control-") as directory:
        project = Path(directory)
        path = project / ".claude/cpp-install.json"
        if scenario == "old-green-write-fails":
            path.parent.mkdir()
            previous = path.with_name("previous.json")
            seed = json.loads((Path(__file__).parent / "good-receipt.json").read_text())
            assert all(item["outcome"] in {"installed", "already"} for item in seed["steps"])
            previous.write_text(json.dumps(seed))
            if repair:
                path.write_text(previous.read_text())
            else:
                path.symlink_to(previous.name)
                assert path.is_symlink() and path.read_bytes() == previous.read_bytes(), \
                    "negative-fixture precondition: blocked destination exposes a real old green receipt"
        if scenario in {"absent", "invalid"}:
            if scenario == "invalid":
                path.parent.mkdir()
                path.write_text("{")
                assert path.read_text() == "{"
            else:
                assert not path.exists(), "negative-fixture precondition: receipt absent"
            return subprocess.run([
                sys.executable, str(gate), "status", "--project-dir", str(project), "--revision", REVISION,
            ], check=False).returncode

        if shutil.which("bash") is None:
            print("CPP_INSTALL_CONTROL: unavailable - bash missing")
            return 125
        text = (ROOT / ".claude/commands/cpp/init.md").read_text()
        match = re.search(r"# CPP_INSTALL_RECEIPT_WRITE_BEGIN\n(.*?)# CPP_INSTALL_RECEIPT_WRITE_END", text, re.S)
        assert match and match[1].strip(), "must exercise the actual shipped consumer"
        # Adapt transport only: select the supplied real/anchor helper and a
        # fixed revision, so controls require neither git nor host configuration.
        script = match[1].replace('"$CPP_DIR/scripts/cpp-install-receipt.py"', '"$CPP_RECEIPT_CONTROL_GATE"')
        script = script.replace('--cpp-dir "$CPP_DIR"', '--revision "$CPP_RECEIPT_CONTROL_REVISION"')
        result = subprocess.run(
            ["bash", "-c", script], cwd=project, capture_output=True, text=True, timeout=15,
            env=dict(os.environ, CPP_RECEIPT_CONTROL_GATE=str(gate), CPP_RECEIPT_CONTROL_REVISION=REVISION,
                     SELECTED_TIER="1", PROFILE_NAME="not-selected", PERMISSION_REPORT="{}",
                     STEP_RESULTS_JSON=json.dumps(observations), OFFERED_STEPS_JSON=json.dumps(offered)),
        )
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        lines = result.stdout.splitlines()
        # A displayed success is the exact bad claim, even if an error was also
        # displayed. Reading the final echo's exit code would hide that defect.
        if "CPP Installation Complete" in lines:
            return 0
        if "CPP Installation Incomplete" in lines:
            return 1
        print("CPP_INSTALL_CONTROL: unknown - no final summary")
        return 2


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()))

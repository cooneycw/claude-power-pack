"""Remove each planted app/duplicate defect and require the control to turn green."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None,
                    reason="controls shell out to bash and jq")
@pytest.mark.parametrize("control,case,gate,prefix", [
    ("gh-pr-merge-app-identity", "bad-wrong-app", "gh-pr-merge.sh", "APP_CHECK_CONTROL"),
    ("gh-pr-merge-app-identity", "bad-plain-status", "gh-pr-merge.sh", "APP_CHECK_CONTROL"),
    ("gh-pr-merge-app-identity", "bad-red-first", "gh-pr-merge.sh", "APP_CHECK_CONTROL"),
    ("gh-pr-merge-app-identity", "bad-pending-first", "gh-pr-merge.sh", "APP_CHECK_CONTROL"),
    ("branch-protection-app-identity", "bad-wrong-app", "branch-protection.sh", "APP_POSTURE_CONTROL"),
    ("branch-protection-app-identity", "bad-unbound-app", "branch-protection.sh", "APP_POSTURE_CONTROL"),
])
def test_removing_the_planted_defect_removes_detection(tmp_path, control, case, gate, prefix):
    directory = ROOT / "controls" / control
    data = json.loads((directory / "cases" / case / "input.json").read_text())
    if "runs" in data:
        rows = data["runs"]["check_runs"]
        assert not rows or any(row["app"]["id"] != 15368 or row["conclusion"] != "success" for row in rows)
    else:
        assert data["live"]["required_status_checks"]["checks"][0]["app_id"] != 15368
    command = [sys.executable, str(directory / "run-case.py"), str(ROOT / "scripts" / gate)]
    bad = subprocess.run([*command, str(directory / "cases" / case)], capture_output=True, text=True, timeout=15)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert prefix + (": blocked" if "runs" in data else ": drift") in bad.stdout
    if "runs" in data:
        # Restore only the app identity or remove the adverse duplicate. A plain
        # status needs the genuinely missing authenticated check, not a label.
        rows = data["runs"]["check_runs"]
        if not rows:
            rows.append({"name": "test", "app": {"id": 15368}, "head_sha": "a" * 40,
                         "status": "completed", "conclusion": "success"})
        elif case == "bad-wrong-app":
            rows[0]["app"]["id"] = 15368
        else:
            rows.pop(0)
        data["rollup"] = "test|SUCCESS\n"
    else:
        data["live"]["required_status_checks"]["checks"][0]["app_id"] = 15368
    data["condition"] = "good"
    (tmp_path / "input.json").write_text(json.dumps(data))
    fixed = subprocess.run([*command, str(tmp_path)], capture_output=True, text=True, timeout=15)
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    assert prefix + (": green" if "runs" in data else ": in-sync") in fixed.stdout

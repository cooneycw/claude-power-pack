"""Execute the Tier 4 readiness boundary without installation side effects."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.parametrize("population", ["ready", "missing", "unknown", "malformed-zero"])
def test_tier4_prerequisites_gate_only_tier4(tmp_path, population):
    match = re.search(r"<!-- CPP_TIER4_PREFLIGHT_BEGIN -->\s*```bash\n(.*?)```", INIT.read_text(), re.S)
    assert match, "Tier 4 must have an executable readiness boundary"
    installed = tmp_path / "cpp/scripts"
    installed.mkdir(parents=True)
    (installed / "flow-preflight.py").write_text((ROOT / "scripts/flow-preflight.py").read_text())
    checks = [
        dict(id=name, required=True, status="ok", message="", remediation="", evidence={})
        for name in ("uv", "cpp_python")
    ]
    code = 1 if population == "missing" else 3 if population == "unknown" else 0
    if code:
        checks[0]["status"] = population
    report = dict(
        schema=1,
        scope="selected",
        full_host_ready=None,
        selected_checks=["uv", "cpp_python"],
        unexamined_checks=["gh", "user.name", "user.email", "codex", "engine"],
        checks=checks,
        required_gaps=int(code == 1),
        required_unknown=int(code == 3),
        status="selected_gaps" if code == 1 else "selected_unknown" if code == 3 else "selected_ready",
    )
    raw = installed / "report.json"
    raw.write_text("not JSON" if population == "malformed-zero" else json.dumps(report))
    helper = installed / "flow-preflight.sh"
    helper.write_text(
        '#!/bin/bash\nif [[ "$*" == *--validate-exit* ]]; then\n'
        'exec python3 "$(dirname "$0")/flow-preflight.py" "$@"\nfi\n'
        f'cat "{raw}"\nexit {code}\n'
    )
    sentinel = tmp_path / "tier4-generator"
    script = match[1] + f'\nprintf reached > "{sentinel}"\n'
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=dict(os.environ, CPP_DIR=str(installed.parent)),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == (0 if population == "ready" else 1)
    assert sentinel.exists() is (population == "ready")


def test_init_repair_is_allowed_and_cpp_calls_are_process_selected():
    text = INIT.read_text()
    assert "Do not stop authorized setup or repair" in text
    for path in (INIT, ROOT / ".claude/commands/flow/auto.md"):
        for line in path.read_text().splitlines():
            if "uv run" in line and '--project "$CPP_DIR"' in line:
                assert "--python 3.11 --no-python-downloads" in line
                assert (
                    'env -u UV_PROJECT_ENVIRONMENT '
                    '"CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT-}"'
                    in line
                )
                assert '"CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT_PRESENT=${UV_PROJECT_ENVIRONMENT+x}"' in line

"""Focused CLI regressions for issue #1498's host tooling fixes."""
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def require(*names):
    for name in names:
        if shutil.which(name) is None:
            pytest.skip(f"requires {name} on PATH")


@pytest.mark.parametrize("flags", [("pool", "--json"), ("--json", "pool")])
def test_playwright_desk_json_positions(tmp_path, flags):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/playwright-desk.py"), "--root", str(tmp_path), *flags],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True


def test_checkout_freshness_ssh_without_timeout(tmp_path):
    require("bash", "readlink", "dirname", "grep", "sed", "head")
    bins = tmp_path / "bin"
    bins.mkdir()
    for name in ("bash", "readlink", "dirname", "grep", "sed", "head"):
        (bins / name).symlink_to(shutil.which(name))
    git = bins / "git"
    git.write_text(f'''#!{sys.executable}
import os, sys, time
args = sys.argv[1:]
if "fetch" in args:
    os.execv("{sys.executable}", ["{sys.executable}", "{bins / 'ssh'}"])
elif "--show-toplevel" in args: print(args[1])
elif "--git-dir" in args: print(".git")
elif "--show-current" in args: print("main")
elif "--short" in args: print("1234567")
elif "get-url" in args: print("git@example.invalid:repo")
elif "config" in args: sys.exit(1)
''')
    git.chmod(0o755)
    (bins / "ssh").write_text('''import os, sys, time
command = os.environ.get("GIT_SSH_COMMAND", "")
if "BatchMode=yes" in command and "ConnectTimeout=1" in command and "ServerAliveInterval=1" in command:
    time.sleep(0.1)
    print("ssh: connect to host example.invalid port 22: Connection timed out", file=sys.stderr)
    sys.exit(255)
time.sleep(60)
''')
    env = {k: v for k, v in os.environ.items() if k != "GIT_SSH_COMMAND"}
    env.update(PATH=str(bins), CPP_FRESHNESS_FETCH_TIMEOUT="1")
    assert not (bins / "timeout").exists()
    assert not env.get("GIT_SSH_COMMAND")
    proc = subprocess.Popen(
        [shutil.which("bash"), str(ROOT / "scripts/cpp-checkout-freshness.sh"), "--path", str(tmp_path)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        pytest.fail("SSH fetch hung beyond the 3-second deadline without timeout binary")
    assert proc.returncode == 4, (out, err)
    assert "CPP_CHECKOUT_FRESHNESS: unknown: fetch failed (ssh: connect" in out
    assert "current" not in out and "behind 0" not in out


def test_install_drift_json_family_round_trip(tmp_path):
    require("bash")
    family = 'family"with\\characters'
    cache = tmp_path / ".claude/plugins/cache/cpp" / family
    cache.mkdir(parents=True)
    assert cache.name == family and '"' in family and "\\" in family
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/install-drift.sh"), "--json"],
        env={**os.environ, "CPP_INSTALL_DRIFT_HOME": str(tmp_path), "CPP_INSTALL_DRIFT_CHECKOUT": str(ROOT)},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["cache_families"] == [family]


def test_mcp_drift_project_remedy_directory_scope(tmp_path):
    spec = importlib.util.spec_from_file_location("mcp_drift_regression", ROOT / "scripts/mcp-drift.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = tmp_path / "claude.json"
    config.write_text(json.dumps({"mcpServers": {"example": {"url": "http://user.invalid"}}}))
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"example": {"url": "http://project.invalid"}}}))
    code, out = module.scope_check(config, tmp_path, {})
    assert code == 1 and "SCOPE CONFLICT" in out
    assert "this directory only" in out
    assert "other worktrees of the same repository" in out
    assert "this host only" not in out


def test_tools_check_only_jq_missing(tmp_path):
    require("make")
    for name in ("shellcheck", "gitleaks"):
        stub = tmp_path / name
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    assert not (tmp_path / "jq").exists() and not (tmp_path / "docker").exists()
    scrubbed_path = str(tmp_path)
    assert shutil.which("shellcheck", path=scrubbed_path) is not None, "fixture must have shellcheck"
    assert shutil.which("gitleaks", path=scrubbed_path) is not None, "fixture must have gitleaks"
    assert shutil.which("jq", path=scrubbed_path) is None, "fixture must lack jq"
    assert shutil.which("docker", path=scrubbed_path) is None, "fixture must lack docker"
    result = subprocess.run(
        [shutil.which("make"), "tools-check", "TOOLS_HARD="], cwd=ROOT,
        env={**os.environ, "PATH": scrubbed_path}, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "NOT on PATH: jq" in result.stdout
    assert "shellcheck and secret-scan targets cannot run either" not in result.stdout
    assert "jq has no docker fallback target" in result.stdout

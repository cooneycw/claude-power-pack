"""The real copy-adapter control must join Git maintenance before cleanup."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/antigravity-skill-install-fidelity"
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="real Git maintenance required")


def test_copy_adapter_control_joins_automatic_gc(tmp_path):
    real_git = shutil.which("git")
    assert real_git is not None
    trace = tmp_path / "git-trace.jsonl"
    tools, temporary = tmp_path / "tools", tmp_path / "temporary"
    tools.mkdir()
    temporary.mkdir()
    wrapper = tools / "git"
    # The actual control deliberately removes inherited GIT_* variables.
    # Reapply tracing and a low real GC threshold at the executable boundary;
    # never emulate its commit, maintenance, adapter or cleanup operations.
    wrapper.write_text(
        f"#!{sys.executable}\nimport os, sys\n"
        f"os.environ.update(GIT_TRACE2_EVENT={str(trace)!r}, "
        "GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)\n"
        f"os.execv({real_git!r}, [{real_git!r}, '-c', 'gc.auto=1', *sys.argv[1:]])\n")
    wrapper.chmod(0o755)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"], TMPDIR=str(temporary))
    assert shutil.which("git", path=env["PATH"]) == str(wrapper)
    assert not trace.exists() and list(temporary.iterdir()) == []
    result = subprocess.run([
        sys.executable, str(CONTROL / "run-case.py"),
        str(CONTROL / "anchors/constructed-always-current.py"),
        str(CONTROL / "cases/bad-stale"),
    ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    # Cleanup waits for owned repacks even on the pre-fix red. The assertion
    # uses event ordering, never a race probability or a wall-time threshold.
    deadline = time.monotonic() + 30
    while True:
        events = [json.loads(line) for line in trace.read_text().splitlines(keepends=True)
                  if line.endswith("\n")]
        repacks = [row for row in events if row.get("event") == "start"
                   and row.get("argv", [None])[1:2] == ["repack"]]
        completed = all(any(row.get("event") == "exit" and row.get("sid") == repack["sid"]
                            for row in events) for repack in repacks)
        if repacks and completed and not list(temporary.rglob("gc.pid")):
            break
        assert time.monotonic() < deadline, "owned automatic repack did not complete"
        time.sleep(0.02)
    assert repacks, "negative input did not trigger actual automatic repacking"
    for repack in repacks:
        gc_sid = repack["sid"].rsplit("/", 1)[0]
        assert any(row.get("event") == "start" and row.get("sid") == gc_sid
                   and row.get("argv", [None])[1:2] == ["gc"] for row in events)
        gc_exits = [i for i, row in enumerate(events)
                    if row.get("event") == "exit" and row.get("sid") == gc_sid]
        repack_exits = [i for i, row in enumerate(events)
                        if row.get("event") == "exit" and row.get("sid") == repack["sid"]]
        assert gc_exits and repack_exits, "maintenance completion was not observed"
        assert min(gc_exits) > max(repack_exits), (
            "control fixture detached automatic GC before its repack finished")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HOST_UPDATE: current (constructed blind verifier)" in result.stderr

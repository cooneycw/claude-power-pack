"""Archive-before-delete controls for wave retirement (issue #1562)."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from tests.test_flow_wave_registry import REGISTRY, SELF_PID, _run
from tests.wave_namespace import unique_wave

MAILBOX = REGISTRY.with_name("flow-wave-mailbox.sh")
WAVE = unique_wave("close")
pytestmark = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("bash", "jq", "cp", "diff", "flock")),
    reason="requires bash, jq, cp, diff and flock",
)


def _seed(tmp: Path) -> tuple[Path, dict[str, str]]:
    env = {"FLOW_WAVE_MAILBOX_DIR": str(tmp / "boxes")}
    result = _run(tmp, "register", "worker", "--wave", WAVE, extra_env=env)
    assert result.returncode == 0, result.stderr
    wave = tmp / "boxes" / WAVE
    wave.mkdir(parents=True)
    for name in ("inbox-worker.md", "outbox-worker.md", ".ack-worker", "verdicts.json"):
        (wave / name).write_text(f"audit {name}\n")
    (wave / "policy-history").mkdir()
    (wave / "policy-history" / "1.json").write_text('{"rev":1}\n')
    return wave, env


def _close(tmp: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return _run(tmp, "close", "--wave", WAVE, "--archive", str(tmp / "archive"),
                *args, extra_env=env)


def _preserved(tmp: Path, wave: Path) -> None:
    assert (wave / "verdicts.json").read_text() == "audit verdicts.json\n"
    assert WAVE in json.loads((tmp / "reg" / "registry.json").read_text())


def test_close_live_role_refuses_and_names_role(tmp_path: Path) -> None:
    wave, env = _seed(tmp_path)
    before = _run(tmp_path, "list", "--wave", WAVE, "--any-live", live=SELF_PID)
    assert "FLOW_WAVE_ANY_LIVE=yes" in before.stdout
    result = _run(tmp_path, "close", "--wave", WAVE, "--archive",
                  str(tmp_path / "archive"), live=SELF_PID, extra_env=env)
    assert result.returncode != 0
    assert "FLOW_WAVE: refused" in result.stdout
    assert "worker" in result.stdout + result.stderr
    _preserved(tmp_path, wave)


def test_close_consuming_watcher_refuses(tmp_path: Path) -> None:
    wave, env = _seed(tmp_path)
    watcher = subprocess.Popen(
        ["bash", str(MAILBOX), "watch", "--role", "worker", "--wave", WAVE,
         "--timeout", "60", "--interval", "1", "--consume"],
        env={**os.environ, **env}, start_new_session=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 15
        status = ""
        while time.monotonic() < deadline:
            status = subprocess.run(
                ["bash", str(MAILBOX), "watch", "--status", "--role", "worker",
                 "--wave", WAVE], env={**os.environ, **env},
                capture_output=True, text=True, check=False,
            ).stdout
            if "FLOW_MAILBOX_WATCHER_COUNT=1\n" in status:
                break
            time.sleep(0.1)
        assert watcher.poll() is None, watcher.communicate()
        assert "FLOW_MAILBOX_WATCHER_COUNT=1\n" in status, status
        result = _close(tmp_path, env)
        assert result.returncode != 0
        assert "FLOW_WAVE: refused" in result.stdout
        assert "worker" in result.stdout + result.stderr
        assert str(watcher.pid) in result.stdout + result.stderr
        _preserved(tmp_path, wave)
    finally:
        os.killpg(watcher.pid, signal.SIGKILL)
        watcher.communicate(timeout=10)


def test_close_archive_verification_failure_preserves_source(tmp_path: Path) -> None:
    wave, env = _seed(tmp_path)
    stub = tmp_path / "bin"
    stub.mkdir()
    diff = stub / "diff"
    diff.write_text("#!/bin/sh\necho injected-archive-verification-failure >&2\nexit 1\n")
    diff.chmod(0o755)
    env["PATH"] = f"{stub}:{os.environ['PATH']}"
    assert subprocess.run([str(diff)], capture_output=True, check=False).returncode == 1
    result = _close(tmp_path, env)
    assert result.returncode != 0
    assert "FLOW_WAVE: refused" in result.stdout
    assert "injected-archive-verification-failure" in result.stderr
    _preserved(tmp_path, wave)


def test_close_archives_all_state_and_preserves_other_wave(tmp_path: Path) -> None:
    wave, env = _seed(tmp_path)
    assert _run(tmp_path, "register", "other", "--wave", "remaining").returncode == 0
    before = json.loads((tmp_path / "reg" / "registry.json").read_text())
    expected = {p.relative_to(wave): p.read_bytes() for p in wave.rglob("*") if p.is_file()}
    result = _close(tmp_path, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FLOW_WAVE: closed" in result.stdout
    assert f"FLOW_WAVE_ARCHIVE={tmp_path / 'archive'}" in result.stdout
    assert "FLOW_WAVE_BYTES_FREED=" in result.stdout
    assert not wave.exists()
    archive = tmp_path / "archive"
    assert json.loads((archive / "registry-entry.json").read_text()) == before[WAVE]
    for relative, data in expected.items():
        assert (archive / relative).read_bytes() == data
    after = json.loads((tmp_path / "reg" / "registry.json").read_text())
    assert WAVE not in after
    assert after["remaining"] == before["remaining"]
    assert (tmp_path / "reg" / "registry.json").stat().st_mode & 0o777 == 0o600
    remaining = _run(tmp_path, "list", "--wave", "remaining", "--any-live", live=SELF_PID)
    assert "FLOW_WAVE_ANY_LIVE=yes" in remaining.stdout

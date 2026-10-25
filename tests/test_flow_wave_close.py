"""Archive-before-delete controls for wave retirement (issue #1562)."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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


@pytest.mark.parametrize("force", [False, True])
def test_close_consuming_watcher_refuses(tmp_path: Path, force: bool) -> None:
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
        # Freeze the heartbeat: the watcher guard must refuse even when no
        # changing audit file lets archive verification catch a blind guard.
        os.killpg(watcher.pid, signal.SIGSTOP)
        result = _close(tmp_path, env, *(["--force"] if force else []))
        _preserved(tmp_path, wave)
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
    _preserved(tmp_path, wave)
    assert result.returncode != 0
    assert "FLOW_WAVE: refused" in result.stdout
    assert "injected-archive-verification-failure" in result.stderr


@pytest.mark.parametrize("colocated", [False, True])
def test_close_archives_all_state_and_preserves_other_wave(tmp_path: Path, colocated: bool) -> None:
    wave, env = _seed(tmp_path)
    if colocated:
        wave = Path(shutil.move(str(wave), tmp_path / "reg" / WAVE))
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "reg")
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


def test_close_unknown_role_refuses(tmp_path: Path) -> None:
    wave, env = _seed(tmp_path)
    result = _run(tmp_path, "close", "--wave", WAVE, unknown=SELF_PID, extra_env=env)
    assert result.returncode != 0
    assert "FLOW_WAVE: refused" in result.stdout
    assert "worker': unknown" in result.stderr
    _preserved(tmp_path, wave)


def test_close_unknown_watcher_refuses(tmp_path: Path) -> None:
    wave, env = _seed(tmp_path)
    env["FLOW_WAVE_WATCHER_SCAN"] = "none"
    status = subprocess.run(
        ["bash", str(MAILBOX), "watch", "--status", "--role", "worker", "--wave", WAVE],
        env={**os.environ, **env}, capture_output=True, text=True, check=False,
    )
    assert "FLOW_MAILBOX_WATCHER_COUNT=unknown" in status.stdout
    result = _close(tmp_path, env)
    assert result.returncode != 0
    assert "FLOW_WAVE: refused" in result.stdout
    assert "watcher holder role 'worker': unknown" in result.stderr
    _preserved(tmp_path, wave)


def test_close_force_names_overridden_live_role(tmp_path: Path) -> None:
    wave, env = _seed(tmp_path)
    result = _run(tmp_path, "close", "--wave", WAVE, "--archive", str(tmp_path / "archive"),
                  "--force", live=SELF_PID, extra_env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "worker': live" in result.stderr
    assert "--force overrides" in result.stderr
    assert not wave.exists()


def test_close_dry_run_touches_nothing(tmp_path: Path) -> None:
    wave, env = _seed(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = _close(tmp_path, env, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FLOW_WAVE: dry-run" in result.stdout
    assert "would archive" in result.stdout
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert not (tmp_path / "archive").exists()
    _preserved(tmp_path, wave)


def test_close_archive_collision_never_overwrites(tmp_path: Path) -> None:
    _, env = _seed(tmp_path)
    archive = tmp_path / "archive"
    archive.mkdir()
    marker = archive / "old-audit"
    marker.write_text("keep me")
    result = _close(tmp_path, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.read_text() == "keep me"
    assert f"FLOW_WAVE_ARCHIVE={archive}-1" in result.stdout
    assert (tmp_path / "archive-1" / "registry-entry.json").exists()


def test_close_policy_only_wave_without_directory(tmp_path: Path) -> None:
    env = {"FLOW_WAVE_MAILBOX_DIR": str(tmp_path / "boxes")}
    assert _run(tmp_path, "policy", "set", "--wave", WAVE, "--gate", "review", extra_env=env).returncode == 0
    assert not (tmp_path / "boxes" / WAVE).exists()
    result = _close(tmp_path, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FLOW_WAVE_BYTES_FREED=0" in result.stdout
    entry = json.loads((tmp_path / "archive" / "registry-entry.json").read_text())
    assert entry["policy"]["gate"] == "review"
    assert WAVE not in json.loads((tmp_path / "reg" / "registry.json").read_text())


@pytest.mark.parametrize("nested", [False, True])
def test_close_refuses_wave_directory_containing_registry(tmp_path: Path, nested: bool) -> None:
    reg_dir = tmp_path / "reg" / "nested" if nested else tmp_path / "reg"
    env = {"FLOW_WAVE_MAILBOX_DIR": str(tmp_path), "FLOW_WAVE_REGISTRY_DIR": str(reg_dir)}
    assert _run(tmp_path, "policy", "set", "--wave", "reg", "--gate", "review", extra_env=env).returncode == 0
    assert _run(tmp_path, "policy", "set", "--wave", "remaining", "--gate", "review", extra_env=env).returncode == 0
    registry = reg_dir / "registry.json"
    before = registry.read_bytes()
    assert (tmp_path / "reg").resolve() in (registry.parent.resolve(), *registry.parent.resolve().parents)
    result = _run(tmp_path, "close", "--wave", "reg", "--archive", str(tmp_path / "archive"), extra_env=env)
    assert registry.exists(), "close must not delete the shared registry directory"
    assert registry.read_bytes() == before
    assert result.returncode != 0
    assert "FLOW_WAVE: refused" in result.stdout
    assert not (tmp_path / "archive").exists()


def test_close_lock_open_failure_reports_refusal(tmp_path: Path) -> None:
    wave, env = _seed(tmp_path)
    lock = tmp_path / "reg" / "registry.lock"
    lock.unlink()
    lock.mkdir()
    assert lock.is_dir(), "registry lock must be impossible to open as a file"
    result = _close(tmp_path, env)
    assert result.returncode != 0
    assert "FLOW_WAVE: refused" in result.stdout
    _preserved(tmp_path, wave)


def test_send_during_close_waits_then_fails_cleanly(tmp_path: Path) -> None:
    """A send queued behind the archive lock cannot report a lost delivery."""
    wave, env = _seed(tmp_path)
    stub = tmp_path / "bin"
    stub.mkdir()
    ready, release, sending = (tmp_path / name for name in ("copy-ready", "copy-release", "send-lock"))
    real_cp, real_flock = shutil.which("cp"), shutil.which("flock")
    assert real_cp and real_flock
    cp = stub / "cp"
    cp.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, os, sys, time\n"
        f"pathlib.Path({str(ready)!r}).touch()\n"
        "deadline = time.monotonic() + 30\n"
        f"while not pathlib.Path({str(release)!r}).exists():\n"
        "    if time.monotonic() > deadline: sys.exit(97)\n"
        "    time.sleep(0.05)\n"
        f"os.execv({real_cp!r}, [{real_cp!r}, *sys.argv[1:]])\n"
    )
    flock = stub / "flock"
    flock.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys\n"
        "if 'CPP_SEND_LOCK' in os.environ: pathlib.Path(os.environ['CPP_SEND_LOCK']).touch()\n"
        f"os.execv({real_flock!r}, [{real_flock!r}, *sys.argv[1:]])\n"
    )
    cp.chmod(0o755)
    flock.chmod(0o755)
    env["PATH"] = f"{stub}:{os.environ['PATH']}"
    sender = None
    with ThreadPoolExecutor(max_workers=1) as pool:
        closing = pool.submit(_close, tmp_path, env)
        try:
            deadline = time.monotonic() + 15
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert ready.exists(), "close never reached its archive copy"
            with (wave / ".mailbox.lock").open() as lock:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            sender = subprocess.Popen(
                ["bash", str(MAILBOX), "send", "--wave", WAVE, "--to", "worker",
                 "--body", "racing-message", "--no-lexicon"],
                env={**os.environ, **env, "CPP_SEND_LOCK": str(sending)},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            deadline = time.monotonic() + 10
            while not sending.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert sending.exists(), "send never attempted the mailbox lock"
            assert sender.poll() is None, "send should be blocked by close"
        finally:
            release.touch()
            if sender is not None:
                try:
                    stdout, stderr = sender.communicate(timeout=20)
                except subprocess.TimeoutExpired:
                    sender.kill()
                    sender.communicate(timeout=5)
                    raise
        result = closing.result(timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sender is not None
    assert sender.returncode == 3, stdout + stderr
    assert "FLOW_MAILBOX: error" in stdout
    assert "FLOW_MAILBOX: sent" not in stdout
    assert not wave.exists()
    assert (tmp_path / "archive" / "outbox-worker.md").read_text() == "audit outbox-worker.md\n"

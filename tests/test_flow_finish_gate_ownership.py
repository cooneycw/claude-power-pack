"""Only the gate invocation that installed the trap may emit or clean up."""

import errno
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/flow-finish-gate.sh"
requires_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")


def _trap_preamble():
    # Keep initialization and the real function together. Stop before CLI and
    # runner dispatch so these checks need neither a runner nor ptrace.
    preamble, separator, _ = GATE.read_text().partition("# --- The shared gate conventions")
    assert separator, "refuse to execute the full gate if the initialization boundary moved"
    return preamble


def _shell_env():
    return {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}


@requires_bash
@pytest.mark.parametrize("status_file", [False, True])
def test_forked_trap_cannot_emit_write_status_or_remove_owner_files(tmp_path, status_file):
    capability = subprocess.run(["bash", "-c", '[[ -n "${BASHPID:-}" ]]'], env=_shell_env(), timeout=10)
    if capability.returncode == 1:
        pytest.skip("BASHPID unavailable: ownership guard intentionally unarmed")
    assert capability.returncode == 0
    runner_json = tmp_path / "runner.json"
    runner_json.write_text("owned runner evidence\n")
    coordination = tmp_path / "coordination"
    coordination.mkdir()
    (coordination / "evidence").write_text("owned lease evidence\n")
    status = tmp_path / "status"
    assert runner_json.is_file() and (coordination / "evidence").is_file() and not status.exists()
    probe = tmp_path / "probe.sh"
    probe.write_text(_trap_preamble() + r'''
trap - EXIT
RUNNER_JSON=$1
_coordination_tmp=$2
_gate_status_file=$3
owner_pid=$BASHPID
(
    [[ "$BASHPID" != "$owner_pid" ]] || exit 90
    _gate_on_exit 9 'interrupted fixture'
)
[[ -f "$RUNNER_JSON" && -f "$_coordination_tmp/evidence" ]] || exit 91
[[ -z "$_gate_status_file" || ! -e "$_gate_status_file" ]] || exit 92
printf 'CHILD_LEFT_OWNER_UNTOUCHED\n'
_gate_on_exit 7 'exit 7'
''')
    result = subprocess.run(
        ["bash", str(probe), str(runner_json), str(coordination), str(status) if status_file else ""],
        env=_shell_env(), capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "CHILD_LEFT_OWNER_UNTOUCHED\n"
    assert not runner_json.exists() and not coordination.exists()
    if status_file:
        assert result.stderr == "" and status.read_text() == "7\n"
    else:
        assert result.stderr == "FLOW_FINISH_GATE_EXIT=7\n" and not status.exists()


@requires_bash
def test_without_bashpid_the_existing_unarmed_behavior_is_retained(tmp_path):
    probe = tmp_path / "legacy-probe.sh"
    probe.write_text("unset BASHPID\n" + _trap_preamble() + r'''
trap - EXIT
[[ -z "${BASHPID+x}" ]] || exit 90
(
    _gate_on_exit 9 'interrupted fixture'
)
_gate_on_exit 2 'exit 2'
''')
    result = subprocess.run(["bash", str(probe)], env=_shell_env(), capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stderr.splitlines() == ["FLOW_FINISH_GATE_EXIT=128", "FLOW_FINISH_GATE_EXIT=2"]


@requires_bash
@pytest.mark.skipif(sys.platform != "linux", reason="ptrace driver is Linux-specific")
def test_denied_ptrace_is_explicitly_unavailable_never_success(monkeypatch, capsys):
    capability = subprocess.run(["bash", "-c", '[[ -n "${BASHPID:-}" ]]'], env=_shell_env(), timeout=10)
    if capability.returncode == 1:
        pytest.skip("BASHPID unavailable: ownership guard intentionally unarmed")
    assert capability.returncode == 0
    control = ROOT / "controls/flow-finish-gate-owner"
    spec = importlib.util.spec_from_file_location("owner_control", control / "run-case.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class DeniedPtrace:
        restype = None

        def __call__(self, *args):
            return -1

    class Library:
        ptrace = DeniedPtrace()

        def prctl(self, *args):
            return 0

    monkeypatch.setattr(module.ctypes, "CDLL", lambda *args, **kwargs: Library())
    monkeypatch.setattr(module.ctypes, "get_errno", lambda: errno.EPERM)
    result = module.main([str(control / "cases/bad-fork-sigterm"), str(GATE)])
    assert result == 3
    assert capsys.readouterr().out == "FLOW_FINISH_GATE_OWNER_CONTROL: unavailable - ptrace unavailable (EPERM)\n"

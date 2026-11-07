"""coordination-admission.sh run directly and sourced (cooneycw/kyle#2130).

The callers' decisions under each flag state are driven by
test_flow_finish_gate.py and test_gh_pr_merge.py. This module drives the signal
itself: its direct-execution report and exit line, and that sourcing it changes
nothing in the caller's shell except defining the function.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "coordination-admission.sh"

requires_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")


def _env(flag: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["CPP_COORDINATION_ADMISSION_FILE"] = str(flag)
    return env


def _direct(flag: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], env=_env(flag), capture_output=True, text=True, timeout=30, check=False
    )


def test_the_shipped_helper_is_executable() -> None:
    # The installer's --check reports a non-executable helper as stale, which
    # turned every capability-readiness flow row stale-or-unknown.
    assert os.access(SCRIPT, os.X_OK)


@requires_bash
@pytest.mark.parametrize(
    ("content", "verdict"),
    [
        (b"on\n", "on"),
        (None, "off"),
        (b"", "off"),
        (b"on", "off"),
        (b"on\n\n", "off"),
        (b"ON\n", "off"),
        (b"1\n", "off"),
    ],
)
def test_direct_run_reports_the_callers_decision(tmp_path: Path, content: bytes | None, verdict: str) -> None:
    flag = tmp_path / "admission"
    if content is not None:
        flag.write_bytes(content)
        assert flag.read_bytes() == content
    else:
        assert not flag.exists()
    result = _direct(flag)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"COORDINATION_ADMISSION: {verdict}\n"
    assert result.stderr.splitlines()[-1] == "COORDINATION_ADMISSION_EXIT=0"


@requires_bash
def test_a_symlinked_flag_is_off_even_when_its_target_says_on(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(b"on\n")
    flag = tmp_path / "admission"
    flag.symlink_to(target)
    assert flag.is_symlink() and flag.read_bytes() == b"on\n"
    assert _direct(flag).stdout == "COORDINATION_ADMISSION: off\n"


@requires_bash
@pytest.mark.parametrize("args", [("--enable",), ("",), ("--help", "--enable"), ("", "--enable")])
def test_an_unknown_argument_is_a_usage_refusal(tmp_path: Path, args: tuple[str, ...]) -> None:
    flag = tmp_path / "admission"
    flag.write_bytes(b"on\n")
    result = _direct(flag, *args)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.splitlines()[-1] == "COORDINATION_ADMISSION_EXIT=2"


@requires_bash
@pytest.mark.parametrize(("content", "rc"), [(b"on\n", 0), (b"off\n", 1)])
def test_sourcing_defines_the_function_and_keeps_the_callers_trap(tmp_path: Path, content: bytes, rc: int) -> None:
    flag = tmp_path / "admission"
    flag.write_bytes(content)
    caller = (
        'trap \'printf "CALLER_EXIT=%d\\n" "$?" >&2\' EXIT\n'
        f'. "{SCRIPT}"\n'
        "coordination_admission_on; status=$?\n"
        'echo "status=$status"\n'
        "exit 7\n"
    )
    result = subprocess.run(
        ["bash", "-c", caller], env=_env(flag), capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 7
    assert result.stdout == f"status={rc}\n"
    assert "COORDINATION_ADMISSION" not in result.stdout + result.stderr
    assert result.stderr.splitlines()[-1] == "CALLER_EXIT=7"

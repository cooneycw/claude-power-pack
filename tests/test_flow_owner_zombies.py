"""Real unreaped-owner controls for the claim and registry liveness gates (#1605)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from tests.test_flow_wave_registry import _detail
from tests.test_flow_wave_registry import _run as wave_run
from tests.test_flow_worktree_claim import _field, _git, _verdict
from tests.test_flow_worktree_claim import _run as claim_run

requires_linux_tools = pytest.mark.skipif(
    not hasattr(os, "fork") or not hasattr(os, "WNOWAIT") or not Path("/proc/self/stat").exists()
    or any(shutil.which(tool) is None for tool in ("bash", "git", "jq", "flock")),
    reason="requires Linux procfs, fork/waitid and bash/git/jq/flock",
)


def process_state(pid: int) -> str:
    return Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[0]


@pytest.fixture
def owner(monkeypatch):
    """Own the child through its live and unreaped states, then always reap it."""
    for key in ("FLOW_CLAIM_PROC_ROOT", "FLOW_CLAIM_LIVE_PIDS", "FLOW_WAVE_PROC_ROOT",
                "FLOW_WAVE_LIVE_PIDS", "FLOW_WAVE_UNKNOWN_PIDS", "FLOW_WAVE_PID_STARTTIMES"):
        monkeypatch.delenv(key, raising=False)
    reader, writer = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(writer)
        try:
            os.read(reader, 1)
        finally:
            os._exit(0)
    os.close(reader)

    def exit_without_reaping():
        os.write(writer, b"x")
        observed = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT)
        assert observed.si_pid == pid
        assert process_state(pid) == "Z", "negative-fixture precondition: child exited and is unreaped"
        os.kill(pid, 0)  # The exact blind input: kill -0 still succeeds.

    try:
        assert process_state(pid) not in ("Z", "X")
        yield pid, exit_without_reaping
    finally:
        os.close(writer)
        os.waitpid(pid, 0)


def claim_owner(tmp_path, pid, proc_root=None):
    main, wt = tmp_path / "main", tmp_path / "wt"
    main.mkdir()
    for args in (("init", "-q"), ("commit", "-q", "--allow-empty", "-m", "init"),
                 ("worktree", "add", "-q", str(wt), "-b", "issue-42-zombie")):
        result = _git(main, *args)
        assert result.returncode == 0, result.stderr
    claimed = claim_run(Path(__file__).resolve().parents[1] / "scripts/flow-worktree-claim.sh",
                        "claim", str(wt), "--issue", "42", pid=str(pid), session="owner", proc_root=proc_root)
    assert claimed.returncode == 0, claimed.stderr
    return wt


@requires_linux_tools
@pytest.mark.parametrize("zombie", [False, True], ids=["live", "unreaped"])
def test_claim_real_owner_lifetime(tmp_path, owner, zombie):
    pid, exit_without_reaping = owner
    wt = claim_owner(tmp_path, pid)
    if zombie:
        exit_without_reaping()
    checked = claim_run(Path(__file__).resolve().parents[1] / "scripts/flow-worktree-claim.sh",
                        "check", str(wt), pid=str(os.getpid()), session="observer")
    assert checked.returncode == 0, checked.stderr
    assert _verdict(checked) == ("stale" if zombie else "held"), checked.stdout
    assert _field(checked, "STALE_REASON") == ("owner-zombie" if zombie else "-"), checked.stdout


@requires_linux_tools
@pytest.mark.parametrize("zombie", [False, True], ids=["live", "unreaped"])
def test_wave_real_owner_lifetime(tmp_path, owner, zombie):
    pid, exit_without_reaping = owner
    registered = wave_run(tmp_path, "register", "worker", "--wave", "owned", pid=str(pid),
                          session="owner", live="", starttimes="")
    assert registered.returncode == 0, registered.stderr
    if zombie:
        exit_without_reaping()
    checked = wave_run(tmp_path, "get", "worker", "--wave", "owned", session="observer", live="", starttimes="")
    assert checked.returncode == 0, checked.stderr
    assert _detail(checked, "FLOW_WAVE_LIVENESS") == ("stale" if zombie else "live"), checked.stdout
    assert _detail(checked, "FLOW_WAVE_LIVENESS_BASIS") == ("owner-zombie" if zombie else "pid-present")
    any_live = wave_run(tmp_path, "list", "--wave", "owned", "--any-live", live="", starttimes="")
    assert any_live.returncode == (1 if zombie else 0), any_live.stderr
    assert f"FLOW_WAVE_ANY_LIVE={'no-roles-ended' if zombie else 'yes'}" in any_live.stdout


@requires_linux_tools
@pytest.mark.parametrize("state", ["S", "Z", "X"])
@pytest.mark.parametrize("helper", ["claim", "wave"])
def test_terminal_stat_with_spaces_and_parentheses_in_comm(tmp_path, owner, helper, state):
    pid, _ = owner
    proc = tmp_path / "proc"
    entry = proc / str(pid) / "stat"
    entry.parent.mkdir(parents=True)
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
    fields[0] = "S"

    def save_stat():
        entry.write_text(f"{pid} (odd ) Z X owner) " + " ".join(fields) + "\n")

    save_stat()
    env = {"FLOW_WAVE_PROC_ROOT": str(proc)}
    if helper == "claim":
        wt = claim_owner(tmp_path, pid, proc)
    else:
        registered = wave_run(tmp_path, "register", "worker", "--wave", "owned", pid=str(pid),
                              session="owner", live="", starttimes="", extra_env=env)
        assert registered.returncode == 0, registered.stderr
    fields[0] = state
    save_stat()
    if state in ("Z", "X"):
        assert entry.read_text().rsplit(") ", 1)[1].split()[0] in ("Z", "X"), \
            "negative-fixture precondition: terminal state, independent of comm text"
    if helper == "claim":
        checked = claim_run(Path(__file__).resolve().parents[1] / "scripts/flow-worktree-claim.sh",
                            "check", str(wt), session="observer", proc_root=proc)
        assert _verdict(checked) == ("held" if state == "S" else "stale"), checked.stdout
        assert _field(checked, "STALE_REASON") == ("-" if state == "S" else "owner-zombie")
    else:
        checked = wave_run(tmp_path, "get", "worker", "--wave", "owned", session="observer",
                           live="", starttimes="", extra_env=env)
        assert _detail(checked, "FLOW_WAVE_LIVENESS") == ("live" if state == "S" else "stale"), checked.stdout
        assert _detail(checked, "FLOW_WAVE_LIVENESS_BASIS") == ("pid-present" if state == "S" else "owner-zombie")

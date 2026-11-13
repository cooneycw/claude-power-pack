"""Drive the real external-command fork window, without running real gates.

A BAD input is a non-owner shell carrying the copied trap. One marker means
that child was refused; two mean it was permitted. These control verdicts
describe the injected child, while the property test is one marker after the
fix versus two before it. Unsupported tracing is UNAVAILABLE, never ready.
"""

import ctypes
import errno
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "FLOW_FINISH_GATE_OWNER_CONTROL: "


class Unavailable(Exception):
    pass


class HarnessError(Exception):
    pass


class Tracer:
    """Linux ptrace of this driver's own descendants only."""

    def __init__(self):
        if sys.platform != "linux":
            raise Unavailable("the fork-boundary driver requires Linux ptrace")
        self.lib = ctypes.CDLL(None, use_errno=True)
        self.lib.ptrace.restype = ctypes.c_long

    def request(self, request, pid, address=0, data=0):
        result = self.lib.ptrace(request, pid, ctypes.c_void_p(address), ctypes.c_void_p(data))
        if result == -1:
            code = ctypes.get_errno()
            if code in (errno.EPERM, errno.EACCES, errno.ENOSYS):
                raise Unavailable(f"ptrace unavailable ({errno.errorcode[code]})")
            raise HarnessError(f"ptrace request {request} failed ({errno.errorcode.get(code, code)})")
        return result

    def run(self, owned, gate, env, started, sig):
        # Reap orphaned gate descendants here rather than leaving zombies at
        # container pid 1. This changes no parentage before the signal arrives.
        if self.lib.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise Unavailable("cannot establish owned-descendant cleanup")
        output = os.open(owned / "stdout", os.O_WRONLY | os.O_CREAT, 0o600)
        error = os.open(owned / "stderr", os.O_WRONLY | os.O_CREAT, 0o600)
        gate_pid = os.fork()
        if gate_pid == 0:
            os.setsid()
            os.chdir(owned)
            os.dup2(output, 1)
            os.dup2(error, 2)
            os.close(output)
            os.close(error)
            try:
                self.request(0, 0)  # PTRACE_TRACEME
            except Unavailable as exc:
                (owned / "unavailable").write_text(str(exc))
                os._exit(101)
            except HarnessError:
                os._exit(102)
            os.execve(shutil.which("bash", path=env["PATH"]), ["bash", str(gate)], env)
        os.close(output)
        os.close(error)
        traced = {gate_pid}
        try:
            _, status = os.waitpid(gate_pid, 0)
            if not os.WIFSTOPPED(status):
                traced.clear()
                if (owned / "unavailable").exists():
                    raise Unavailable((owned / "unavailable").read_text())
                raise HarnessError("traced shell did not reach the initial exec stop")
            # TRACEFORK | TRACEVFORK | TRACEEXEC | EXITKILL
            self.request(0x4200, gate_pid, data=2 | 4 | 16 | (1 << 20))
            self.request(7, gate_pid)  # PTRACE_CONT
            held = {}
            runner = None
            next_fork = False
            target = None
            injected = False
            returncode = None
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if runner is not None and started.exists() and not next_fork:
                    if runner not in held:
                        raise HarnessError("runner readiness lost its held-parent precondition")
                    self.request(7, gate_pid)
                    held.pop(runner)
                    next_fork = True
                try:
                    pid, status = os.waitpid(-1, os.WNOHANG | 0x40000000)  # __WALL
                except ChildProcessError:
                    break
                if pid == 0:
                    time.sleep(0.001)
                    continue
                if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                    traced.discard(pid)
                    if pid == gate_pid:
                        returncode = os.waitstatus_to_exitcode(status)
                    if pid in held:
                        self.request(7, held.pop(pid))
                    if returncode is not None and not traced:
                        break
                    continue
                event, stopsig = status >> 16, os.WSTOPSIG(status)
                if event in (1, 2):
                    child = ctypes.c_ulong()
                    self.request(0x4201, pid, data=ctypes.addressof(child))  # GETEVENTMSG
                    child = child.value
                    traced.add(child)
                    if pid == gate_pid and not injected:
                        held[child] = gate_pid
                        if next_fork:
                            target = child
                    else:
                        self.request(7, pid)
                elif event == 4:
                    argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                    if pid in held:
                        if pid == runner or b"uv" in argv:
                            runner = pid
                        else:
                            self.request(7, held.pop(pid))
                    self.request(7, pid)
                elif pid == target and not injected:
                    # The runner is ready; parent and tee-side child are both
                    # stopped at fork, BEFORE Bash resets the copied trap.
                    assert started.exists() and pid != gate_pid and held[pid] == gate_pid
                    os.killpg(gate_pid, sig)
                    self.request(17, pid)  # DETACH, deliver the queued group signal normally
                    traced.discard(pid)
                    held.pop(pid)
                    self.request(17, gate_pid)
                    traced.discard(gate_pid)
                    injected = True
                elif injected and pid in traced:
                    deliver = stopsig if stopsig not in (signal.SIGSTOP, signal.SIGTRAP) else 0
                    self.request(17, pid, data=deliver)
                    traced.discard(pid)
                else:
                    deliver = stopsig if stopsig not in (signal.SIGSTOP, signal.SIGTRAP) else 0
                    self.request(7, pid, data=deliver)
            if not injected or returncode != -sig:
                raise HarnessError("fork injection did not finish with the requested signal death")
            # Reap detached descendants before reading, so a late child marker
            # cannot arrive after the verdict was computed.
            reap_deadline = time.monotonic() + 2
            while time.monotonic() < reap_deadline:
                try:
                    pid, _ = os.waitpid(-1, os.WNOHANG | 0x40000000)
                except ChildProcessError:
                    return (owned / "stderr").read_text()
                if pid == 0:
                    time.sleep(0.001)
            raise HarnessError("signalled descendants did not finish before the evidence deadline")
        finally:
            try:
                os.killpg(gate_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            for pid in traced:
                try:
                    self.request(17, pid, data=signal.SIGKILL)
                except (Unavailable, HarnessError):
                    pass
            cleanup_deadline = time.monotonic() + 2
            while time.monotonic() < cleanup_deadline:
                try:
                    pid, _ = os.waitpid(-1, os.WNOHANG | 0x40000000)
                except ChildProcessError:
                    break
                if pid == 0:
                    time.sleep(0.001)


def run(case_dir, source, provided_bin=None):
    if shutil.which("bash") is None:
        raise Unavailable("bash is not installed")
    case = json.loads((case_dir / "case.json").read_text())
    with tempfile.TemporaryDirectory(prefix="cpp-gate-owner-") as directory:
        owned = Path(directory)
        scripts = owned / "scripts"
        scripts.mkdir()
        gate = scripts / "flow-finish-gate.sh"
        shutil.copy2(source, gate)
        for name in ("gate-lib.sh", "coordination-admission.sh"):
            shutil.copy2(ROOT / "scripts" / name, scripts / name)
        cpp = owned / "cpp"
        cpp.mkdir()
        (cpp / "CLAUDE.md").write_text("Owned synthetic runner; no project environment.\n")
        started = owned / "started"
        binaries = provided_bin or owned / "bin"
        uv = binaries / "uv"
        if provided_bin is None:
            # Direct unit/probe calls own their fixture too. The registered
            # invocation uses the shell-staged stub, verified by CI deps.
            binaries.mkdir()
            uv.write_text('#!/bin/sh\n: > "$CPP_OWNER_STARTED"\nexec sleep 30\n')
            uv.chmod(0o755)
        env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
        env.update(PATH=f"{binaries}:{env.get('PATH', '')}", FLOW_GATE_CPP_DIR=str(cpp),
                   CPP_COORDINATION_ADMISSION_FILE=str(owned / "no-admission"), CPP_OWNER_STARTED=str(started))
        assert shutil.which("uv", path=env["PATH"]) == str(uv)
        if case["mode"] == "announced":
            result = subprocess.run(["bash", str(gate), "--no-such-flag"], cwd=owned, env=env,
                                    capture_output=True, text=True, timeout=10)
            markers = [line for line in result.stderr.splitlines() if line.startswith("FLOW_FINISH_GATE_EXIT=")]
            if (result.returncode != 2 or markers != ["FLOW_FINISH_GATE_EXIT=2"]
                    or result.stderr.splitlines()[-1:] != ["FLOW_FINISH_GATE_EXIT=2"]):
                raise HarnessError("announced owner exit changed")
            print(PREFIX + "owner-only")
            return 0
        capability = subprocess.run(["bash", "-c", '[[ -n "${BASHPID:-}" ]]'],
                                    env=env, capture_output=True, timeout=5)
        if capability.returncode == 1:
            raise Unavailable("BASHPID absent; ownership guard is intentionally unarmed")
        if capability.returncode != 0:
            raise HarnessError("cannot query Bash ownership capability")
        sig = getattr(signal, case["signal"])
        stderr = Tracer().run(owned, gate, env, started, sig)
        markers = [line for line in stderr.splitlines() if line.startswith("FLOW_FINISH_GATE_EXIT=")]
        if markers == ["FLOW_FINISH_GATE_EXIT=128"]:
            print(PREFIX + "child-refused")
            return 1
        if markers == ["FLOW_FINISH_GATE_EXIT=128"] * 2:
            print(PREFIX + "child-permitted")
            return 0
        raise HarnessError(f"unexpected marker population: {markers!r}")


def main(argv):
    try:
        provided = Path(argv[2]).resolve() if len(argv) > 2 else None
        return run(Path(argv[0]).resolve(), Path(argv[1]).resolve(), provided)
    except Unavailable as exc:
        print(PREFIX + "unavailable - " + str(exc))
        return 3
    except (HarnessError, OSError, ValueError, KeyError) as exc:
        print(PREFIX + "harness-error - " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

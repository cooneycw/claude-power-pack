"""Constructed blind owner: the pre-#1961 launch/wait path without signal ownership.

Origin: lib/ci_shape_check.py at 5ca522147a0a6ccaef97c13820935b35318fbd12.
The function wrapper adapts its existing block to the extracted owner interface.
"""
import os
import signal
import subprocess


def owned_pytest(argv, *, cwd, env, output, timeout=1200):
    proc = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env,
                            stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        proc.wait(timeout=timeout)
    except BaseException:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        raise
    return proc.returncode

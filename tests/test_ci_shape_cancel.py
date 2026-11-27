"""Real cancellation of the production pytest owner; no shape/root qualification."""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def live(pid):
    try:
        # A zombie is already stopped; orphaned grandchildren are reaped by init.
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def until(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return bool(predicate())


def cancellation_probe(owned, *, ignore_term=False, driver_signal=signal.SIGTERM):
    """Cancel actual run_lane after its real pytest and grandchild are ready.

    Checkout/probe preparation is controlled to keep this a tiny process-owner
    test. The launch, signal delivery, wait and group cleanup are production.
    Outer exit is the release boundary here; live-authority release is measured
    separately, never contacted by the normal test suite.
    """
    checkout = owned / "checkout"
    checkout.mkdir()
    (checkout / "lib").mkdir()
    (checkout / "lib/__init__.py").write_text("")
    shutil.copyfile(ROOT / "lib/ci_shape_pytest.py", checkout / "lib/ci_shape_pytest.py")
    (checkout / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    ready = owned / "ready.json"
    grandchild = (
        "import json,os,signal,time; from pathlib import Path; "
        + ("signal.signal(signal.SIGTERM,signal.SIG_IGN); " if ignore_term else "")
        + f"Path({str(ready)!r}).write_text(json.dumps(dict(pytest=os.getppid(),grandchild=os.getpid()))); "
        + "time.sleep(120)"
    )
    (checkout / "test_hold.py").write_text(
        "import subprocess,sys,time\n"
        "def test_hold():\n"
        f"    subprocess.Popen([sys.executable, '-c', {grandchild!r}])\n"
        "    time.sleep(120)\n"
    )
    stage = owned / "stage"
    stage.mkdir()
    for name in ("git", "make"):
        binary = shutil.which(name)
        assert binary is not None
        (stage / name).symlink_to(binary)
    logs = owned / "logs"
    logs.mkdir()
    driver = owned / "driver.py"
    driver.write_text(
        "import sys; from pathlib import Path\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from lib import ci_shape_check as shape\n"
        f"owned = Path({str(owned)!r})\n"
        "shape.SELECTORS = ('test_hold.py',)\n"
        "shape.checkout = lambda *args: owned / 'checkout'\n"
        "shape.observe = lambda *args: ({'controlled_input': True}, {})\n"
        "row = shape.run_lane(owned, owned, 'controlled', owned / 'lane', "
        "owned / 'stage', Path(sys.executable), 'local', False, owned / 'logs', 0o022)\n"
        "raise SystemExit('unexpected qualification completion: ' + repr(row))\n"
    )
    pids = {}
    with (owned / "driver.log").open("w") as log:
        producer = subprocess.Popen([sys.executable, str(driver)], stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
        try:
            assert until(lambda: ready.exists() or producer.poll() is not None), "child readiness deadline"
            assert ready.exists(), (owned / "driver.log").read_text()
            pids = json.loads(ready.read_text())
            assert producer.poll() is None and all(live(pid) for pid in pids.values())
            assert os.getpgid(pids["pytest"]) == pids["pytest"] != producer.pid
            assert os.getpgid(pids["grandchild"]) == pids["pytest"]
            os.killpg(producer.pid, driver_signal)
            outer_exit = producer.wait(timeout=15)
            # Record before fixture cleanup; a lingering process must be visible.
            survivors = [name for name, pid in pids.items() if live(pid)]
            return dict(outer_exit=outer_exit, survivors=survivors, pids=pids)
        finally:
            if producer.poll() is None:
                os.killpg(producer.pid, signal.SIGKILL)
                producer.wait(timeout=5)
            if pids:
                try:
                    os.killpg(pids["pytest"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
                assert until(lambda: not any(live(pid) for pid in pids.values()), 5), pids


@pytest.mark.skipif(not Path('/proc').is_dir() or not shutil.which('git') or not shutil.which('make'),
                    reason='Linux process state, Git and Make required')
@pytest.mark.parametrize('ignore_term', [False, True], ids=['term', 'term-ignoring-grandchild'])
def test_cancel_reaps_pytest_group_before_outer_completion(tmp_path, ignore_term):
    observed = cancellation_probe(tmp_path, ignore_term=ignore_term)
    assert not observed['survivors'], f"owned work survived outer completion: {observed}"
    assert observed['outer_exit'] == 128 + signal.SIGTERM, observed

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
BLIND_OWNER = ROOT / "controls/ci-shape-check/history/1961-unhandled-pytest.py"


def live(pid, *, started=None):
    try:
        # A zombie is already stopped; orphaned grandchildren are reaped by init.
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[0] != "Z" and (started is None or int(fields[19]) == started)
    except FileNotFoundError:
        return False


def until(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return bool(predicate())


def cancellation_probe(owned, *, ignore_term=False, driver_signal=signal.SIGTERM,
                       blind_owner=False, supervisor=(), readiness_seconds=15, observe_group=None,
                       force_unconfirmed=False):
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
    assert not ready.exists()
    grandchild = (
        "import json,os,signal,time; from pathlib import Path; "
        + ("signal.signal(signal.SIGTERM,signal.SIG_IGN); " if ignore_term else "")
        + f"target=Path({str(ready)!r}); temporary=target.with_suffix('.tmp'); "
        + "temporary.write_text(json.dumps(dict(pytest=os.getppid(),grandchild=os.getpid()))); "
        + "temporary.replace(target); "
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
    blind = ""
    if blind_owner:
        blind = ("import runpy\n"
                 f"shape._owned_pytest = runpy.run_path({str(BLIND_OWNER)!r})['owned_pytest']\n")
    forced = "shape._pytest_group_live = lambda pgid: True\n" if force_unconfirmed else ""
    next_lane = ("(owned / 'next-lane-started').write_text('attempted after cancellation')\n"
                 "shape.run_lane(owned, owned, 'controlled', owned / 'next-lane', owned / 'stage', "
                 "Path(sys.executable), 'local', False, owned / 'logs', 0o022)\n") if force_unconfirmed else ""
    driver.write_text(
        "import sys; from pathlib import Path\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from lib import ci_shape_check as shape\n"
        f"owned = Path({str(owned)!r})\n"
        "shape.SELECTORS = ('test_hold.py',)\n"
        "shape.checkout = lambda *args: owned / 'checkout'\n"
        "shape.observe = lambda *args: ({'controlled_input': True}, {})\n"
        + blind + forced + "row = shape.run_lane(owned, owned, 'controlled', owned / 'lane', "
        "owned / 'stage', Path(sys.executable), 'local', False, owned / 'logs', 0o022)\n"
        + next_lane + "raise SystemExit('unexpected qualification completion: ' + repr(row))\n"
    )
    pids = {}
    starts = {}
    with (owned / "driver.log").open("w") as log:
        command = [*supervisor, "--", sys.executable, str(driver)] if supervisor else [sys.executable, str(driver)]
        producer = subprocess.Popen(command, stdout=log,
                                    stderr=subprocess.STDOUT)
        try:
            assert until(lambda: ready.exists() or producer.poll() is not None,
                         readiness_seconds), "child readiness deadline"
            assert ready.exists(), (owned / "driver.log").read_text()
            pids = json.loads(ready.read_text())
            starts = {name: int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
                      for name, pid in pids.items()}
            assert producer.poll() is None and all(live(pid, started=starts[name]) for name, pid in pids.items())
            assert os.getpgid(pids["pytest"]) == pids["pytest"] != producer.pid
            assert os.getpgid(pids["grandchild"]) == pids["pytest"]
            if observe_group is not None:
                assert observe_group(pids["pytest"]), "production probe missed a live owned group"
            timing = dict(ready_published=ready.stat().st_mtime, cancel_sent=time.time())
            producer.send_signal(driver_signal)
            outer_exit = producer.wait(timeout=15)
            timing["outer_completed"] = time.time()
            # Record before fixture cleanup; a lingering process must be visible.
            survivors = [name for name, pid in pids.items() if live(pid, started=starts[name])]
            if observe_group is not None:
                assert not observe_group(pids["pytest"]), "production probe retained a stopped group"
            return dict(outer_exit=outer_exit, survivors=survivors, pids=pids, timing=timing,
                        next_lane_started=(owned / "next-lane-started").exists(),
                        diagnostic=(owned / "driver.log").read_text())
        finally:
            if producer.poll() is None:
                producer.terminate()
                try:
                    producer.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    producer.kill()
                    producer.wait(timeout=5)
            if pids and any(live(pid, started=starts.get(name)) for name, pid in pids.items()):
                try:
                    os.killpg(pids["pytest"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
                assert until(lambda: not any(live(pid, started=starts.get(name))
                                             for name, pid in pids.items()), 5), pids


@pytest.mark.skipif(not Path('/proc').is_dir() or not shutil.which('git') or not shutil.which('make'),
                    reason='Linux process state, Git and Make required')
@pytest.mark.parametrize('ignore_term', [False, True], ids=['term', 'term-ignoring-grandchild'])
@pytest.mark.parametrize('driver_signal', [signal.SIGTERM, signal.SIGHUP, signal.SIGINT])
def test_cancel_reaps_pytest_group_before_outer_completion(tmp_path, ignore_term, driver_signal):
    observed = cancellation_probe(tmp_path, ignore_term=ignore_term, driver_signal=driver_signal)
    assert not observed['survivors'], f"owned work survived outer completion: {observed}"
    assert observed['outer_exit'] == 128 + driver_signal, observed


@pytest.mark.skipif(not Path('/proc').is_dir() or not shutil.which('git') or not shutil.which('make'),
                    reason='Linux process state, Git and Make required')
@pytest.mark.parametrize('ignore_term', [False, True])
def test_cancel_probe_detects_committed_blind_owner(tmp_path, ignore_term):
    observed = cancellation_probe(tmp_path, ignore_term=ignore_term, blind_owner=True)
    assert observed['survivors'] == ['pytest', 'grandchild'], observed
    assert observed['outer_exit'] == -signal.SIGTERM, observed


def test_owned_pytest_preserves_exit_and_prior_signal_handlers(tmp_path):
    from lib import ci_shape_check as shape
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
    with (tmp_path / 'normal.log').open('w') as output:
        code = shape._owned_pytest([sys.executable, '-c', 'raise SystemExit(7)'], cwd=tmp_path,
                                  env={'PATH': os.environ.get('PATH', '')}, output=output)
    assert code == 7
    assert {sig: signal.getsignal(sig) for sig in before} == before


@pytest.mark.skipif(not Path('/proc').is_dir() or not shutil.which('git') or not shutil.which('make'),
                    reason='Linux process state, Git and Make required')
def test_group_probe_distinguishes_actual_live_and_stopped_pytest(tmp_path):
    from lib import ci_shape_check as shape
    observed = cancellation_probe(tmp_path, ignore_term=True, observe_group=shape._pytest_group_live)
    assert observed['survivors'] == []
    assert observed['outer_exit'] == 128 + signal.SIGTERM


@pytest.mark.skipif(not Path('/proc').is_dir() or not shutil.which('git') or not shutil.which('make'),
                    reason='Linux process state, Git and Make required')
def test_cancel_wins_when_group_stop_is_unconfirmed(tmp_path):
    observed = cancellation_probe(tmp_path, force_unconfirmed=True)
    assert not observed['next_lane_started'], (
        f"cancel swallowed: outer_exit={observed['outer_exit']}; next_lane_started={observed['next_lane_started']}"
    )
    assert observed['outer_exit'] == 143, observed
    assert observed['survivors'] == [], observed
    assert 'CI_SHAPE_CANCEL: UNKNOWN:' in observed['diagnostic']
    assert 'owned pytest group did not stop after SIGKILL' in observed['diagnostic']
    assert 'CI_SHAPE: GOOD' not in observed['diagnostic']

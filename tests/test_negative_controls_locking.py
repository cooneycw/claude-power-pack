"""The generalized tracking scanner joins the live-tree lock (#1641)."""

import os
import select
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests import test_negative_controls as controls

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")


def _clean_fixture(tmp_path):
    root = controls._two_control_repo(tmp_path)
    # That helper deliberately leaves beta's ignored JSON untracked (#1406).
    # Track it before planting THIS test's sole untracked-file condition.
    subprocess.run(
        ["git", "-C", str(root), "add", "-f", "controls/beta/anchors/nested/control.json"], check=True,
    )
    harness = controls._load_harness_module()
    directories = sorted({control for _, control in harness.discover(root)})
    assert directories and not controls._check_all_tracked(harness, root, directories)
    return root


def _dirty_fixture(tmp_path):
    root = _clean_fixture(tmp_path)
    probe = root / "controls/alpha/cases/untracked-probe.sh"
    probe.parent.mkdir()
    assert not probe.exists(), "fixture must not overwrite a case"
    probe.write_text("#!/bin/sh\nexit 0\n")
    failures = controls._check_all_tracked(controls._load_harness_module(), root, ["controls/alpha"])
    assert failures["controls/alpha"][0] == "UNTRACKED", failures
    assert "untracked-probe.sh" in str(failures)
    return root, probe


_SCANNER_CHILD = '''
import importlib.util, pathlib, sys, traceback
spec = importlib.util.spec_from_file_location("scanner_under_test", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.ROOT = pathlib.Path(sys.argv[2])
module._LIVE_TREE_LOCK = pathlib.Path(sys.argv[3])
original = module.fcntl.flock
reported = False
def observed(fd, operation):
    global reported
    try:
        return original(fd, operation)
    except OSError as exc:
        if exc.errno in module._CONTENDED and not reported:
            print("CONTENDED", flush=True)
            reported = True
        raise
module.fcntl.flock = observed
try:
    module.test_every_discovered_controls_files_are_tracked()
except AssertionError:
    print("FAILED", flush=True)
    traceback.print_exc()
    sys.exit(1)
print("PASSED", flush=True)
'''


@requires_git
def test_tracking_scanner_waits_for_the_probe_to_be_removed(tmp_path):
    # A private tree and lock reproduce the production interleaving without
    # dirtying the real checkout or racing another real lock holder (#1420).
    root = _clean_fixture(tmp_path)
    probe = root / "controls/alpha/cases/untracked-probe.sh"
    probe.parent.mkdir()
    lock = tmp_path / "tree.lock"
    process = None
    first = ""
    try:
        with controls.live_controls_tree_exclusive(lock_path=lock):
            held_since = time.monotonic()
            assert not probe.exists(), "fixture must not overwrite a case"
            probe.write_text("#!/bin/sh\nexit 0\n")
            try:
                failures = controls._check_all_tracked(controls._load_harness_module(), root, ["controls/alpha"])
                assert failures["controls/alpha"][0] == "UNTRACKED", failures
                process = subprocess.Popen(
                    [sys.executable, "-c", _SCANNER_CHILD, str(Path(controls.__file__)), str(root), str(lock)],
                    cwd=controls.ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, start_new_session=True,
                )
                assert process.stdout is not None
                ready, _, _ = select.select([process.stdout], [], [], controls._HOLD_BUDGET / 2)
                assert ready, "child scanner produced neither contention nor a verdict"
                first = process.stdout.readline().strip()
                if first == "CONTENDED":
                    assert probe.exists() and process.poll() is None
            finally:
                # Remove while still holding the lock, just like the planter.
                probe.unlink(missing_ok=True)
        assert time.monotonic() - held_since <= controls._HOLD_BUDGET
        stdout, stderr = process.communicate(timeout=15)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
    assert first == "CONTENDED", f"scanner ran inside the dirty window: {first}\n{stdout}\n{stderr}"
    assert process.returncode == 0 and "PASSED" in stdout, stderr


@requires_git
def test_tracking_scanner_still_refuses_an_untracked_file_after_taking_lock(tmp_path, monkeypatch):
    root, _ = _dirty_fixture(tmp_path)
    monkeypatch.setattr(controls, "ROOT", root)
    monkeypatch.setattr(controls, "_LIVE_TREE_LOCK", tmp_path / "tree.lock")
    with pytest.raises(AssertionError, match="UNTRACKED.*untracked-probe"):
        controls.test_every_discovered_controls_files_are_tracked()

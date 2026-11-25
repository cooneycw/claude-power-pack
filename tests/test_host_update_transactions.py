"""Bounded pipe handshakes pin real lock ordering, not scheduler timing."""

from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from lib.host_update import store
from lib.host_update.driver import inspect, refresh
from lib.host_update.fixture import FixtureAdapter
from lib.host_update.models import Revision, State
from lib.host_update.scope import Scope
from tests.test_host_update_core import Case, tree_snapshot

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git for real source binding")
ROOT = Path(__file__).absolute().parents[1]

# Events: A = attempted lock, B = actual flock EAGAIN, H = lock granted.
# The worker waits for a release byte before entering any publication code.
WORKER = r'''
import errno, fcntl, json, os, sys
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from lib.host_update import store
from lib.host_update.driver import refresh
from lib.host_update.fixture import FixtureAdapter
from lib.host_update.models import Request, Revision
root, raw, revision, event, release, bypass = sys.argv[1:]
event, release = int(event), int(release)
spec = json.loads(raw)
original_flock = fcntl.flock
reported = False
def observed_flock(*args):
    global reported
    try:
        return original_flock(*args)
    except OSError as exc:
        if exc.errno in (errno.EAGAIN, errno.EACCES) and not reported:
            os.write(event, b'B')
            reported = True
        raise
fcntl.flock = observed_flock
original = store.locked
@contextmanager
def synchronized(scope, request, *, write):
    os.write(event, b'A')
    if bypass == 'yes':
        os.write(event, b'H')
        os.read(release, 1)
        yield True
    else:
        with original(scope, request, write=write) as held:
            os.write(event, b'H')
            os.read(release, 1)
            yield held
store.locked = synchronized
import lib.host_update.driver as driver
driver.locked = synchronized
request = Request(Revision(revision, Path(root)/spec['source']), lock_timeout_seconds=10)
result = refresh(FixtureAdapter(Path(root), spec), request)
print(json.dumps(asdict(result)))
'''


class Worker:
    def __init__(self, case, spec, revision, *, bypass=False):
        event_r, event_w = os.pipe()
        release_r, release_w = os.pipe()
        self.event_fd, self.release_fd = event_r, release_w
        self.proc = subprocess.Popen(
            [sys.executable, "-c", WORKER, str(case.root), json.dumps(spec), revision,
             str(event_w), str(release_r), "yes" if bypass else "no"],
            cwd=ROOT, pass_fds=(event_w, release_r), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        os.close(event_w)
        os.close(release_r)

    def event(self):
        ready, _, _ = select.select([self.event_fd], [], [], 10)
        assert ready, "worker did not reach synchronization point within deadline"
        event = os.read(self.event_fd, 1)
        assert event, "worker exited before synchronization point"
        return event

    def release(self):
        os.write(self.release_fd, b"R")

    def finish(self):
        output, error = self.proc.communicate(timeout=10)
        assert self.proc.returncode == 0, error
        value = json.loads(output)
        assert value["exit_code"] == 0, value
        return value

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.communicate(timeout=5)
        os.close(self.event_fd)
        os.close(self.release_fd)


def ordered_pair(case, first_spec, first_revision, second_spec, second_revision, *, bypass=False):
    first = Worker(case, first_spec, first_revision, bypass=bypass)
    second = None
    try:
        assert first.event() == b"A"
        assert first.event() == b"H"
        second = Worker(case, second_spec, second_revision, bypass=bypass)
        assert second.event() == b"A"
        # First really owns the lock; B comes from the second process's actual
        # EAGAIN, not an elapsed-time assumption or a sleep in the parent.
        assert second.event() == b"B", "second copier entered without waiting for held flock"
        first.release()
        assert second.event() == b"H"
        first_result = first.finish()
        second.release()
        return first_result, second.finish()
    finally:
        first.close()
        if second:
            second.close()


def test_verify_no_lock_is_byte_identical_even_when_tree_is_unwritable(tmp_path):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    lock = case.root / "a/.install.lock"
    lock.unlink()
    assert not lock.exists()
    parent = case.root / "a"
    parent.chmod(0o500)
    try:
        if os.geteuid() != 0:
            with pytest.raises(PermissionError):
                (parent / "write-precondition").write_bytes(b"must fail")
        before = tree_snapshot(parent)
        result = inspect(case.adapter(), case.request())
        assert result.exit_code == 0
        assert not lock.exists()
        assert tree_snapshot(parent) == before
    finally:
        parent.chmod(0o700)


def test_no_lock_control_fails_on_always_create_lock_mutation(tmp_path, monkeypatch):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    lock = case.root / "a/.install.lock"
    lock.unlink()
    assert not lock.exists()
    before = tree_snapshot(case.root / "a")
    original = store.locked

    @contextmanager
    def bad(scope, request, *, write):
        with original(scope, request, write=True) as held:
            yield held

    monkeypatch.setattr(store, "locked", bad)
    assert inspect(case.adapter(), case.request()).exit_code == 0
    with pytest.raises(AssertionError):
        assert tree_snapshot(case.root / "a") == before
    assert lock.exists(), "the planted mutation must really have created a file"


def test_real_exclusive_holder_makes_verify_unknown_without_writes(tmp_path):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    worker = Worker(case, case.spec(), case.revision)
    try:
        assert worker.event() == b"A" and worker.event() == b"H"
        before = tree_snapshot(case.root / "a")
        result = inspect(case.adapter(), case.request(lock_timeout_seconds=0.05))
        assert result.exit_code == 4 and "deadline" in result.reason
        assert tree_snapshot(case.root / "a") == before
        worker.release()
        worker.finish()
    finally:
        worker.close()


@pytest.mark.parametrize("reverse", [False, True])
def test_same_package_two_revisions_end_in_one_complete_revision(tmp_path, reverse):
    case = Case(tmp_path / "fixture")
    revision_one = case.revision
    snapshot_one = case.root / "source-v1"
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(case.source), str(snapshot_one)],
                   check=True, timeout=10)
    (case.source / "topic/SKILL.md").write_bytes(b"skill v2\n")
    (case.source / "topic/guide.md").write_bytes(b"guide v2\n")
    revision_two = case.commit()
    assert (snapshot_one / "topic/SKILL.md").read_bytes() != (case.source / "topic/SKILL.md").read_bytes()
    assert (snapshot_one / "topic/guide.md").read_bytes() != (case.source / "topic/guide.md").read_bytes()
    one = dict(case.spec(), source="source-v1")
    two = case.spec()
    order = [(one, revision_one), (two, revision_two)]
    if reverse:
        order.reverse()
    first, second = ordered_pair(case, *order[0], *order[1])
    assert first["revision"] == order[0][1] and second["revision"] == order[1][1]
    spec, revision = order[1]
    request = replace(case.request(), revision=Revision(revision, case.root / spec["source"]))
    assert inspect(FixtureAdapter(case.root, spec), request).exit_code == 0
    installed = case.root / "a/skills/topic"
    expected_root = case.root / spec["source"] / "topic"
    assert (installed / "SKILL.md").read_bytes() == (expected_root / "SKILL.md").read_bytes()
    assert (installed / "references/guide.md").read_bytes() == (expected_root / "guide.md").read_bytes()
    ledger = json.loads((case.root / "a/skills/.managed/ownership.json").read_bytes())
    assert ledger["adapters"]["fixture-a"]["topic"]["revision"] == revision


def test_concurrency_handshake_rejects_unlocked_copier_mutation(tmp_path):
    case = Case(tmp_path / "fixture")
    # The bad worker emits H without ever seeing EAGAIN. This deterministic
    # failure occurs before either worker is released into publication.
    with pytest.raises(AssertionError, match="without waiting"):
        ordered_pair(case, case.spec(), case.revision, case.spec(), case.revision, bypass=True)


def test_different_packages_shared_lock_and_ledger_preserve_both_updates(tmp_path):
    case = Case(tmp_path / "fixture", second_package=True)
    first = dict(case.spec(), packages=case.rows[:1])
    second = dict(case.spec(), harness="fixture-b", packages=case.rows[1:])
    assert first["packages"][0]["name"] != second["packages"][0]["name"]
    assert first["lock"] == second["lock"] and first["ledger"] == second["ledger"]
    ordered_pair(case, first, case.revision, second, case.revision)
    for spec in (first, second):
        assert inspect(FixtureAdapter(case.root, spec), case.request()).exit_code == 0
    ledger = json.loads((case.root / "a/skills/.managed/ownership.json").read_bytes())
    assert set(ledger["adapters"]) == {"fixture-a", "fixture-b"}
    assert (case.root / "a/skills/topic/SKILL.md").is_file()
    assert (case.root / "a/skills/old/SKILL.md").is_file()


def test_shared_ledger_different_policy_locks_cannot_lose_record(tmp_path, monkeypatch):
    case = Case(tmp_path / "fixture", second_package=True)
    first = dict(case.spec(), packages=case.rows[:1])
    second = dict(case.spec(), harness="fixture-b", packages=case.rows[1:],
                  lock="a/second.lock", work="a/skills/.managed/work-b")
    assert first["ledger"] == second["ledger"] and first["lock"] != second["lock"]
    original = store._ledger_bytes
    interleaved = []

    def capture_then_interleave(scope, build):
        captured = original(scope, build)
        if scope.owner == "fixture-b" and not interleaved:
            result = refresh(FixtureAdapter(case.root, first), case.request(lock_timeout_seconds=0.05))
            interleaved.append(result)
        return captured

    monkeypatch.setattr(store, "_ledger_bytes", capture_then_interleave)
    result = refresh(FixtureAdapter(case.root, second), case.request())
    assert result.exit_code == 0 and len(interleaved) == 1
    if interleaved[0].exit_code:
        assert "deadline" in interleaved[0].reason, interleaved[0]
        assert refresh(FixtureAdapter(case.root, first), case.request()).exit_code == 0
    ledger = json.loads((case.root / "a/skills/.managed/ownership.json").read_bytes())
    assert set(ledger["adapters"]) == {"fixture-a", "fixture-b"}, "successful update lost its ownership record"
    for spec in (first, second):
        assert inspect(FixtureAdapter(case.root, spec), case.request()).exit_code == 0


@pytest.mark.parametrize("shared", ["ledger", "work"])
def test_shared_resource_serializes_different_policy_locks(tmp_path, shared):
    case = Case(tmp_path / "fixture", second_package=True)
    first = dict(case.spec(), packages=case.rows[:1])
    second = dict(case.spec(), harness="fixture-b", packages=case.rows[1:], lock="a/second.lock")
    if shared == "ledger":
        second["work"] = "a/skills/.managed/work-b"
    else:
        second["ledger"] = "a/skills/.managed/second-ledger.json"
    assert first["lock"] != second["lock"]
    assert first[shared] == second[shared]
    ordered_pair(case, first, case.revision, second, case.revision)
    for spec in (first, second):
        assert inspect(FixtureAdapter(case.root, spec), case.request()).exit_code == 0


def test_interrupted_publication_retains_backup_and_reports_unknown(tmp_path, monkeypatch):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    original_bytes = (case.root / "a/skills/topic/SKILL.md").read_bytes()
    (case.source / "topic/SKILL.md").write_bytes(b"replacement\n")
    case.commit()
    original = Scope.rename

    def interrupted(self, source, target):
        original(self, source, target)
        if target == case.root / "a/skills/topic":
            raise OSError("fixture interruption after replacement")

    monkeypatch.setattr(Scope, "rename", interrupted)
    result = refresh(case.adapter(), case.request())
    assert result.exit_code == 1 and result.after.state == State.UNKNOWN
    pending = case.root / "a/skills/.managed/work/pending.json"
    assert pending.is_file()
    backups = list(pending.parent.glob("transaction-*/backup/topic/SKILL.md"))
    assert len(backups) == 1 and backups[0].read_bytes() == original_bytes
    observed = inspect(case.adapter(), case.request())
    assert observed.exit_code == 4 and observed.after.state == State.UNKNOWN


def test_mixed_revision_bytes_cannot_verify_current(tmp_path):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    old_skill = (case.source / "topic/SKILL.md").read_bytes()
    (case.source / "topic/SKILL.md").write_bytes(b"new skill\n")
    (case.source / "topic/guide.md").write_bytes(b"new guide\n")
    case.commit()
    assert refresh(case.adapter(), case.request()).exit_code == 0
    installed = case.root / "a/skills/topic/SKILL.md"
    installed.write_bytes(old_skill)
    assert installed.read_bytes() != (case.source / "topic/SKILL.md").read_bytes()
    assert inspect(case.adapter(), case.request()).after.state == State.HAND_EDITED

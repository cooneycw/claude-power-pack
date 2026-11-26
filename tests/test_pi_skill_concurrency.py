"""Real locks and real CLI subprocesses, with explicit pipe handshakes."""
from __future__ import annotations

import fcntl
import json
import os
import select
import shutil
import subprocess
import sys

import pytest

from tests.test_pi_skill_install import ROOT, installed_case, snapshot

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git for real pi/core requests")


def handshake(child):
    assert select.select([child.stdout], [], [], 10)[0], "bounded child handshake expired"
    return child.stdout.readline()


@pytest.mark.parametrize("relative", [".cpp-skills.lock", "skills/.cpp-managed/.ownership.json.cpp-lock",
                                      "skills/.cpp-managed/.work.cpp-lock"])
def test_each_actual_core_lock_blocks_verify_without_creating_or_changing_files(tmp_path, relative):
    case = installed_case(tmp_path)
    lock = case.agent / relative
    assert lock.is_file()
    child = subprocess.Popen([sys.executable, "-c", """
import fcntl, sys
with open(sys.argv[1], 'rb') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    print('LOCKED', flush=True)
    sys.stdin.readline()
""", str(lock)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert handshake(child) == "LOCKED\n"
        fd = os.open(lock, os.O_RDONLY)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        finally:
            os.close(fd)
        before = snapshot(case.agent)
        answer, report = case.call("--verify-installed", "--lock-timeout", "0.01")
        assert answer.returncode == 4 and "bounded deadline" in report["reason"], report
        assert snapshot(case.agent) == before
    finally:
        child.communicate("release\n", timeout=5)
        assert child.returncode == 0
    answer, report = case.call("--verify-installed")
    assert answer.returncode == 0, report


def test_existing_install_verify_with_all_three_locks_removed_creates_none(tmp_path):
    case = installed_case(tmp_path)
    for path in (case.agent / ".cpp-skills.lock", case.skills / ".cpp-managed/.ownership.json.cpp-lock",
                 case.skills / ".cpp-managed/.work.cpp-lock"):
        assert path.is_file()
        path.unlink()
    before = snapshot(case.agent)
    answer, report = case.call("--verify-installed")
    assert answer.returncode == 0, report
    assert snapshot(case.agent) == before


@pytest.mark.parametrize("add_package", [False, True])
def test_two_real_adapter_revisions_contend_then_publish_one_complete_population(tmp_path, add_package):
    case = installed_case(tmp_path)
    first_revision = case.revision
    old = tmp_path / "old-source"
    case.git("worktree", "add", "--detach", str(old), first_revision)
    case.guide.write_text("Fixture guide v2\n")
    if add_package:
        second = case.topic.parent.parent / "second/SKILL.md"
        second.parent.mkdir()
        second.write_text("---\nname: second\ndescription: Second fixture topic\n---\nSecond body.\n")
    case.commit()
    # The observer forwards the actual syscall and reports only real EAGAIN.
    # Both writers must reach that condition before the parent releases its lock.
    code = r'''
import fcntl, json, pathlib, sys
from dataclasses import asdict
sys.path.insert(0, sys.argv[1])
from lib.host_update.pi_adapter import PiAdapter, make_request
from lib.host_update.driver import refresh
original, notified = fcntl.flock, False
def observed(fd, operation):
    global notified
    try:
        return original(fd, operation)
    except BlockingIOError:
        if not notified:
            print('CONTENDED', flush=True)
            notified = True
        raise
fcntl.flock = observed
adapter = PiAdapter(cwd=pathlib.Path(sys.argv[5]), home=pathlib.Path(sys.argv[4]), agent=pathlib.Path(sys.argv[3]))
request = make_request(adapter, pathlib.Path(sys.argv[2]), lock_timeout=10)
print(json.dumps(asdict(refresh(adapter, request))), flush=True)
'''
    holder = os.open(case.agent / ".cpp-skills.lock", os.O_RDONLY)
    fcntl.flock(holder, fcntl.LOCK_EX)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PI_", "GIT_"))}
    children = [subprocess.Popen([sys.executable, "-c", code, str(ROOT), str(source), str(case.agent),
                                  str(case.home), str(case.cwd)], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, env=env) for source in (old, case.source)]
    try:
        for child in children:
            assert handshake(child) == "CONTENDED\n"
        fcntl.flock(holder, fcntl.LOCK_UN)
        for child in children:
            stdout, stderr = child.communicate(timeout=20)
            assert child.returncode == 0, stderr
            result = json.loads(stdout)
            assert result["exit_code"] == 0 and result["after"]["state"] == "current", result
    finally:
        os.close(holder)
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
    rows = json.loads(case.ledger.read_bytes())["adapters"]["pi"]
    revisions = {row["revision"] for row in rows.values()}
    assert len(revisions) == 1 and revisions <= {first_revision, case.revision}
    selected = next(iter(revisions))
    expected_guide = "Fixture guide v1\n" if selected == first_revision else "Fixture guide v2\n"
    assert (case.skills / "topic/references/guide.md").read_text() == expected_guide
    assert set(rows) == ({"topic", "second"} if add_package and selected == case.revision else {"topic"})

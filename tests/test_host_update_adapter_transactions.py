"""Real AGY lock schedules and full-build fidelity, not JSON-only checks."""
import fcntl
import json
import multiprocessing
import os
import shutil
from dataclasses import asdict

import pytest

from lib.host_update.driver import inspect, refresh
from lib.host_update.host import registry, run_host
from lib.host_update.scope import Scope
from lib.host_update.store import lock_paths
from tests.test_host_update_adapters import cli, files, git, request
from tests.test_host_update_adapters import source as source_fixture
from tests.test_host_update_adapters import source_template as template_fixture

source, source_template = source_fixture, template_fixture
pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for real AGY transactions")


def worker(source, home, pipe, inherited):
    for fd in inherited:
        os.close(fd)
    original = fcntl.flock
    announced = False

    def observed(fd, operation):
        nonlocal announced
        try:
            return original(fd, operation)
        except BlockingIOError:
            if not announced:
                announced = True
                pipe.send("blocked")
                assert pipe.poll(45) and pipe.recv() == "proceed"
            raise

    fcntl.flock = observed
    adapter = registry(home)[2]
    pipe.send(asdict(refresh(adapter, request(source, lock_timeout_seconds=45))))


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
@pytest.mark.parametrize("two_packages", [False, True], ids=["two-revisions", "same-revision-two-packages"])
def test_actual_agy_whole_manifest_lock_orders(source, tmp_path, order, two_packages):
    home = tmp_path / "home"
    home.mkdir()
    assert run_host(registry(home, ("antigravity",)), request(source)).exit_code == 0
    versions = []
    for index in range(2):
        if two_packages and index == 1:
            versions.append(versions[0])
            continue
        root = tmp_path / f"revision-{index}"
        git(tmp_path, "clone", "-q", str(source), str(root))
        guide = root / "docs/skills/python-packaging.md"
        guide.write_bytes(guide.read_bytes() + f"\nRevision {index} content\n".encode())
        if two_packages:
            second = root / "docs/skills/code-quality.md"
            second.write_bytes(second.read_bytes() + b"\nSecond package update\n")
        git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "-am", f"revision {index}")
        versions.append(root)
    if two_packages:
        assert request(versions[0]).revision.commit == request(versions[1]).revision.commit
    else:
        assert request(versions[0]).revision.commit != request(versions[1]).revision.commit
    adapter = registry(home)[2]
    policy = adapter.preflight(request(source))
    fds = [os.open(path, os.O_RDWR) for path in lock_paths(Scope(policy, owner=adapter.harness))]
    for fd in fds:
        fcntl.flock(fd, fcntl.LOCK_EX)
    children = []
    try:
        for version in versions:
            parent, child = multiprocessing.Pipe()
            process = multiprocessing.get_context("fork").Process(target=worker,
                                                                   args=(version, home, child, fds))
            process.start()
            child.close()
            children.append((process, parent))
        # Both real refreshes actually attempted an exclusive lock and failed
        # against our holder. Neither owns a coordination fd yet.
        for _process, pipe in children:
            assert pipe.poll(45) and pipe.recv() == "blocked"
        for fd in fds:
            fcntl.flock(fd, fcntl.LOCK_UN)
        for index in order:
            process, pipe = children[index]
            pipe.send("proceed")
            assert pipe.poll(45)
            row = pipe.recv()
            assert row["exit_code"] == 0, row
            process.join(5)
            assert process.exitcode == 0
        last = versions[order[-1]]
        final = registry(home)[2]
        expected = final.build(request(last).revision, final.preflight(request(last)))
        for package in expected.packages:
            root = policy.install_root / package.name
            assert files(root) == {p: (m.content, m.mode) for p, m in package.members.items()}
        ledger = json.loads(policy.ledger_path.read_text())["adapters"]["antigravity"]
        assert all(row["revision"] == expected.revision for row in ledger.values())
        if two_packages:
            for topic, marker in (("python-packaging", b"Revision 0 content"),
                                  ("code-quality", b"Second package update")):
                guide = policy.install_root / topic / f"references/docs/skills/{topic}.md"
                assert marker in guide.read_bytes()
    finally:
        for fd in fds:
            os.close(fd)
        for process, pipe in children:
            if process.is_alive():
                process.terminate()
            process.join(5)
            pipe.close()


def test_verify_no_lock_and_held_lock(source, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert run_host(registry(home, ("antigravity",)), request(source)).exit_code == 0
    adapter = registry(home)[2]
    policy = adapter.preflight(request(source))
    paths = lock_paths(Scope(policy, owner=adapter.harness))
    for path in paths:
        path.unlink()
    assert all(not p.exists() for p in paths)
    before = files(home)
    assert inspect(adapter, request(source)).exit_code == 0
    assert files(home) == before and all(not p.exists() for p in paths)
    with policy.lock_path.open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        answer = inspect(adapter, request(source, lock_timeout_seconds=0))
        assert answer.exit_code == 4 and answer.after.state == "unknown"


@pytest.mark.parametrize("damage", ["bytes", "mode"])
def test_mixed_unlocked_copy_is_rejected(source, tmp_path, damage):
    home = tmp_path / "home"
    home.mkdir()
    adapter = registry(home, ("antigravity",))[2]
    assert run_host(registry(home, ("antigravity",)), request(source)).exit_code == 0
    # A naive unlocked copier interleaves a new guide with an old SKILL/record.
    package = home / ".gemini/config/skills/python-packaging"
    old = files(package)
    guide = package / "references/docs/skills/python-packaging.md"
    if damage == "bytes":
        guide.write_bytes(guide.read_bytes() + b"\nunlocked competing writer\n")
    else:
        guide.chmod(0o600)
    assert files(package) != old
    answer = inspect(adapter, request(source))
    assert answer.exit_code == 1 and answer.after.state == "hand-edited"


@pytest.mark.parametrize("edited", [False, True])
def test_actual_prior_revision_orphan_pruning(source, tmp_path, edited):
    home = tmp_path / "home"
    home.mkdir()
    builder = source / "lib/antigravity_skills.py"
    original = builder.read_text()
    builder.write_text(original.replace("TOPICS = frozenset({", 'TOPICS = frozenset({"retired-topic",'))
    skill = source / ".claude/skills/retired-topic/SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: retired-topic\ndescription: Former owned topic\n---\nOld content\n")
    git(source, "add", ".")
    git(source, "commit", "-qm", "former 19-topic producer")
    first, report = cli(source, home, "refresh", "--select", "antigravity")
    assert first.returncode == 0, report
    retired = home / ".gemini/config/skills/retired-topic"
    assert retired.is_dir()
    ledger = home / ".gemini/config/skills/.cpp-managed/ownership.json"
    assert "retired-topic" in json.loads(ledger.read_text())["adapters"]["antigravity"]
    builder.write_text(original)
    git(source, "rm", "-r", ".claude/skills/retired-topic")
    git(source, "add", ".")
    git(source, "commit", "-qm", "current 18-topic producer")
    if edited:
        (retired / "SKILL.md").write_bytes(b"personal edited former topic")
        assert b"personal edited" in (retired / "SKILL.md").read_bytes()
    second, current = cli(source, home)
    assert second.returncode == (1 if edited else 0), current
    assert retired.exists() is edited
    if edited:
        assert (retired / "SKILL.md").read_bytes() == b"personal edited former topic"


def test_interrupted_actual_publication_remains_unknown(source, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    assert run_host(registry(home, ("antigravity",)), request(source)).exit_code == 0
    guide = source / "docs/skills/python-packaging.md"
    guide.write_bytes(guide.read_bytes() + b"\nnew source before interruption\n")
    git(source, "commit", "-am", "interrupted target revision")
    adapter = registry(home)[2]
    policy = adapter.preflight(request(source))
    original = Scope.write

    def interrupted(scope, path, content, mode=0o644):
        if path == policy.ledger_path:
            raise OSError("controlled record-publication interruption")
        return original(scope, path, content, mode)

    with monkeypatch.context() as patch:
        patch.setattr(Scope, "write", interrupted)
        result = refresh(adapter, request(source))
    assert result.exit_code == 1 and result.action == "failed"
    assert (policy.work_root / "pending.json").exists()
    before = files(home)
    assert inspect(adapter, request(source)).exit_code == 4
    assert files(home) == before

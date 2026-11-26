"""Actual links and owned source histories; no target reads via installed links."""
import fcntl
import os
import shutil
from pathlib import Path

import pytest

from lib.host_update.links import ClaudeLinks
from tests.test_host_update_adapters import cli, git, request
from tests.test_host_update_adapters import source as source_fixture
from tests.test_host_update_adapters import source_template as template_fixture

source_template = template_fixture
source = source_fixture
pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for real pinned link sources")


def seed(home, source, kinds=("commands", "scripts")):
    for kind in kinds:
        root = home / ".claude" / kind
        root.mkdir(parents=True, exist_ok=True)
        names = ["cpp", "flow"] if kind == "commands" else ["cpp-commands-link.sh", "cpp-host-write.sh"]
        for name in names:
            target = source / (".claude/commands" if kind == "commands" else "scripts") / name
            assert target.exists()
            (root / name).symlink_to(target)
    return ClaudeLinks(home, source=source)


def tree(root):
    """Whole fixture-home oracle records links without traversing their targets."""
    result = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            key = str(path.relative_to(root))
            result[key] = ("link", os.readlink(path)) if path.is_symlink() else (
                ("dir",) if path.is_dir() else ("file", path.read_bytes()))
    return result


def test_confined_links_refresh_verify_and_never_temporary_target(source, tmp_path):
    home = tmp_path / "home"
    seed(home, source)
    result, report = cli(source, home)
    assert result.returncode == 0, result.stderr + str(report)
    row = next(r for r in report["results"] if r["harness"] == "claude-links")
    assert report["schema"] == 2 and report["backend"] == "mixed"
    assert row["backend"] == "links" and row["after"]["state"] == "current"
    assert row["after"]["examined_members"] == row["after"]["expected_members"] > 20
    assert all(r["backend"] == "copies" for r in report["results"] if r["harness"] != "claude-links")
    for kind in ("commands", "scripts"):
        for link in (home / ".claude" / kind).iterdir():
            assert link.is_symlink() and str(link.readlink()).startswith(str(source) + "/")
    lock = home / ".claude/.cpp-skill-install.lock"
    lock.unlink()
    before = tree(home)
    checked, payload = cli(source, home, "verify")
    assert checked.returncode == 0, payload
    assert tree(home) == before and not lock.exists()
    assert git(source, "status", "--porcelain") == ""


@pytest.mark.parametrize("fault", ["outside", "dangling", "regular", "directory", "relative"])
def test_foreign_expected_entry_preserved_other_entries_progress(source, tmp_path, fault):
    home = tmp_path / "home"
    adapter = seed(home, source)
    path = home / ".claude/commands/cpp"
    path.unlink()
    outside = tmp_path / "outside"
    outside.write_bytes(b"private neighbour")
    if fault == "regular":
        path.write_bytes(b"personal replacement")
    elif fault == "directory":
        path.mkdir()
        (path / "personal").write_bytes(b"personal directory")
    else:
        target = outside if fault == "outside" else (tmp_path / "missing" if fault == "dangling" else "relative")
        path.symlink_to(target)
    assert path.exists() or path.is_symlink()
    if fault in ("dangling", "relative"):
        assert not path.exists()
    protected = tree(home)[".claude/commands/cpp"]
    before = tree(home)
    checked = adapter.operate(request(source), verify_only=True)
    assert checked.exit_code == 1 and checked.after.state == "unmanaged"
    assert tree(home) == before
    refreshed = adapter.operate(request(source), verify_only=False)
    assert refreshed.exit_code == 1 and refreshed.after.state == "unmanaged"
    assert refreshed.action == "refreshed" and refreshed.after.examined_members > checked.after.examined_members
    assert tree(home)[".claude/commands/cpp"] == protected
    assert outside.read_bytes() == b"private neighbour"


@pytest.mark.parametrize("kind", ["commands", "scripts"])
def test_each_kind_enrolls_independently_without_tier_upgrade(source, tmp_path, kind):
    home = tmp_path / "home"
    adapter = seed(home, source, (kind,))
    other = "scripts" if kind == "commands" else "commands"
    root = home / ".claude" / other
    root.mkdir()
    (root / "personal").write_bytes(b"foreign-only does not enroll")
    before = tree(root)
    row = adapter.operate(request(source), verify_only=False)
    assert row.exit_code == 0, row
    assert tree(root) == before
    shutil.rmtree(root)
    assert adapter.operate(request(source), verify_only=False).exit_code == 0
    assert not root.exists()


def test_helper_population_uses_git_executable_kind_not_suffix(source, tmp_path):
    helper = source / "scripts/fixture-helper"
    helper.write_text("#!/bin/sh\nexit 0\n")
    helper.chmod(0o755)
    hidden = source / "scripts/.fixture-hidden"
    hidden.write_text("#!/bin/sh\nexit 0\n")
    hidden.chmod(0o755)
    nonexec = source / "scripts/fixture-plain.py"
    nonexec.write_text("# not an installed helper\n")
    git(source, "add", ".")
    git(source, "commit", "-qm", "tracked helper without suffix")
    home = tmp_path / "home"
    row = seed(home, source, ("scripts",)).operate(request(source), verify_only=False)
    assert row.exit_code == 0, row
    assert (home / ".claude/scripts/fixture-helper").is_symlink()
    assert not (home / ".claude/scripts/fixture-plain.py").exists()
    assert not (home / ".claude/scripts/.fixture-hidden").exists()


@pytest.mark.parametrize("prefix", [".claude", ".claude/commands", ".claude/scripts"])
def test_install_alias_refused_before_source_read(source, tmp_path, monkeypatch, prefix):
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    path = home / prefix
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(outside, target_is_directory=True)
    assert path.is_symlink()
    before = tree(home)

    def forbidden(*args, **kwargs):
        pytest.fail("source read reached before install alias refusal")

    monkeypatch.setattr("lib.host_update.links._source_git", forbidden)
    row = ClaudeLinks(home, source=source).operate(request(source), verify_only=True)
    assert row.exit_code == 1 and row.after.state == "unmanaged"
    assert tree(home) == before and list(outside.iterdir()) == []


@pytest.mark.parametrize("fault", ["dirty", "moved", "mode", "alias"])
def test_persistent_target_invalidity_never_mutates_install(source, tmp_path, fault):
    home = tmp_path / "home"
    adapter = seed(home, source)
    req = request(source)
    member = source / "scripts/cpp-host-write.sh"
    if fault == "dirty":
        member.write_bytes(member.read_bytes() + b"\n# changed\n")
        assert git(source, "status", "--porcelain")
    elif fault == "mode":
        member.chmod(0o644)
        assert not member.stat().st_mode & 0o111
    elif fault == "alias":
        alias = tmp_path / "source-alias"
        alias.symlink_to(source, target_is_directory=True)
        for kind in ("commands", "scripts"):
            for link in (home / ".claude" / kind).iterdir():
                target = link.readlink().relative_to(source)
                link.unlink()
                link.symlink_to(alias / target)
        adapter = ClaudeLinks(home, source=alias)
    else:
        source.rename(tmp_path / "moved")
        assert not source.exists()
    before = tree(home)
    row = adapter.operate(req, verify_only=False)
    assert row.exit_code == (1 if fault == "alias" else 4), row
    # Refresh may open the exact install lock, but never touch link entries.
    after = tree(home)
    after.pop(".claude/.cpp-skill-install.lock", None)
    assert after == before


def test_source_moves_after_mutation_cannot_report_current(source, tmp_path, monkeypatch):
    home = tmp_path / "home"
    adapter = seed(home, source)
    original = adapter.manifest
    calls = []

    def moving(req):
        calls.append(1)
        if len(calls) == 2:
            (source / "CLAUDE.md").write_bytes(b"moved source contents")
        return original(req)

    monkeypatch.setattr(adapter, "manifest", moving)
    row = adapter.operate(request(source), verify_only=False)
    assert len(calls) == 2 and row.action == "failed" and row.exit_code == 1
    assert row.after.state != "current"


def test_shared_lock_held_refuses_without_link_changes(source, tmp_path):
    home = tmp_path / "home"
    adapter = seed(home, source)
    lock = home / ".claude/.cpp-skill-install.lock"
    with lock.open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        before = tree(home)
        for verify in (True, False):
            row = adapter.operate(request(source, lock_timeout_seconds=0), verify_only=verify)
            assert row.exit_code == 4 and row.after.state == "unknown"
            assert tree(home) == before


def test_proven_retired_link_pruned_unproven_orphan_preserved(source, tmp_path):
    helper = source / "scripts/fixture-retired"
    helper.write_text("#!/bin/sh\nexit 0\n")
    helper.chmod(0o755)
    git(source, "add", ".")
    git(source, "commit", "-qm", "prior tracked helper")
    home = tmp_path / "home"
    adapter = seed(home, source, ("scripts",))
    retired = home / ".claude/scripts/fixture-retired"
    retired.symlink_to(helper)
    helper.unlink()
    git(source, "commit", "-am", "retire helper")
    unproven = home / ".claude/scripts/never-tracked"
    unproven.symlink_to(source / "scripts/never-tracked")
    assert retired.is_symlink() and not retired.exists()
    assert unproven.is_symlink() and not unproven.exists()
    before = tree(home)
    checked = adapter.operate(request(source), verify_only=True)
    assert checked.exit_code == 1 and tree(home) == before
    row = adapter.operate(request(source), verify_only=False)
    assert row.exit_code == 1 and row.action == "refreshed"
    assert not retired.is_symlink() and unproven.is_symlink()
    assert any(c.reason.startswith("orphan ownership unproven") for c in row.after.conflicts)


def test_shallow_missing_orphan_history_preserves_unknown_link(source, tmp_path):
    helper = source / "scripts/fixture-retired"
    helper.write_text("#!/bin/sh\nexit 0\n")
    helper.chmod(0o755)
    git(source, "add", ".")
    git(source, "commit", "-qm", "prior owned helper")
    helper.unlink()
    git(source, "commit", "-am", "retire helper before shallow boundary")
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "-q", "--depth=1", source.as_uri(), str(shallow))
    assert git(shallow, "rev-parse", "--is-shallow-repository") == "true"
    home = tmp_path / "home"
    adapter = seed(home, shallow, ("scripts",))
    orphan = home / ".claude/scripts/fixture-retired"
    orphan.symlink_to(shallow / "scripts/fixture-retired")
    assert orphan.is_symlink() and not orphan.exists()
    row = adapter.operate(request(shallow), verify_only=False)
    assert row.exit_code == 1 and orphan.is_symlink()
    assert any("unproven" in c.reason for c in row.after.conflicts)


def test_lock_appearing_during_verify_is_unknown_without_our_writes(source, tmp_path, monkeypatch):
    home = tmp_path / "home"
    adapter = seed(home, source)
    lock = home / ".claude/.cpp-skill-install.lock"
    assert not lock.exists()
    original = adapter.manifest
    calls = []

    def appearing(req):
        calls.append(1)
        if len(calls) == 2:
            lock.write_bytes(b"concurrent writer's new lock")
        return original(req)

    monkeypatch.setattr(adapter, "manifest", appearing)
    before = tree(home)
    row = adapter.operate(request(source), verify_only=True)
    assert len(calls) == 2 and row.exit_code == 4 and row.after.state == "unknown"
    after = tree(home)
    assert after.pop(".claude/.cpp-skill-install.lock") == ("file", b"concurrent writer's new lock")
    assert after == before


def test_foreign_target_never_opened_for_contents(source, tmp_path, monkeypatch):
    home = tmp_path / "home"
    adapter = seed(home, source, ("commands",))
    link = home / ".claude/commands/cpp"
    link.unlink()
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"unreadable personal content")
    link.symlink_to(foreign)
    assert link.is_symlink() and link.readlink() == foreign
    original_open, original_path_open = os.open, Path.open

    def guarded_open(path, *args, **kwargs):
        if isinstance(path, (str, Path)):
            assert Path(path) not in (link, foreign), "foreign installed target opened"
        return original_open(path, *args, **kwargs)

    def guarded_path_open(path, *args, **kwargs):
        assert path not in (link, foreign), "foreign installed target opened"
        return original_path_open(path, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(os, "open", guarded_open)
        guard.setattr(Path, "open", guarded_path_open)
        row = adapter.operate(request(source), verify_only=True)
    assert row.exit_code == 1 and foreign.read_bytes() == b"unreadable personal content"


@pytest.mark.parametrize("deferred", ["~/.claude/commands", "~/.claude/scripts", "~/.claude/.cpp-skill-install.lock"])
def test_explicit_link_or_lock_deferral_prevents_io(source, tmp_path, deferred):
    home = tmp_path / "home"
    seed(home, source)
    before = tree(home)
    row = ClaudeLinks(home, source=source, deferred=(deferred,)).operate(request(source), verify_only=False)
    assert row.exit_code == 1 and "deferred" in row.reason
    assert tree(home) == before


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -1, 3601])
def test_direct_api_rejects_unbounded_wait_before_io(source, tmp_path, timeout):
    home = tmp_path / "home"
    adapter = seed(home, source)
    before = tree(home)
    row = adapter.operate(request(source, lock_timeout_seconds=timeout), verify_only=False)
    assert row.exit_code == 4 and "lock timeout" in row.reason and tree(home) == before


def test_interrupted_link_refresh_reports_failure_then_reinspects(source, tmp_path, monkeypatch):
    home = tmp_path / "home"
    adapter = seed(home, source, ("commands",))
    original = os.symlink
    created = []

    def interrupted(target, name, **kwargs):
        if created:
            raise PermissionError("controlled link-publication interruption")
        original(target, name, **kwargs)
        created.append(name)

    with monkeypatch.context() as guard:
        guard.setattr(os, "symlink", interrupted)
        row = adapter.operate(request(source), verify_only=False)
    assert len(created) == 1 and row.exit_code == 1 and row.action == "failed"
    assert row.after.state != "current"
    checked = adapter.operate(request(source), verify_only=True)
    assert checked.exit_code == 1 and checked.after.state == "stale"
    assert adapter.operate(request(source), verify_only=False).exit_code == 0


def test_first_link_write_denied_is_failure_without_false_current(source, tmp_path, monkeypatch):
    home = tmp_path / "home"
    adapter = seed(home, source, ("commands",))
    called = []

    def denied(*args, **kwargs):
        called.append(1)
        raise PermissionError("controlled first write denial")

    before = tree(home)
    with monkeypatch.context() as guard:
        guard.setattr(os, "symlink", denied)
        row = adapter.operate(request(source), verify_only=False)
    assert called == [1] and row.exit_code == 1 and row.action == "failed" and row.after.state != "current"
    after = tree(home)
    after.pop(".claude/.cpp-skill-install.lock")
    assert after == before


@pytest.mark.parametrize("fault", ["bytes", "mode"])
def test_git_clean_cache_does_not_replace_source_fidelity(source, tmp_path, fault):
    member = source / (".claude/commands/cpp/update.md" if fault == "bytes" else "scripts/cpp-host-write.sh")
    git(source, "update-index", "--assume-unchanged", str(member.relative_to(source)))
    if fault == "bytes":
        member.write_bytes(member.read_bytes() + b"\nconcealed modified source\n")
    else:
        member.chmod(0o644)
        assert not member.stat().st_mode & 0o111
    assert git(source, "status", "--porcelain") == "", "fixture must exercise the second fidelity oracle"
    home = tmp_path / "home"
    adapter = seed(home, source)
    before = tree(home)
    row = adapter.operate(request(source), verify_only=True)
    assert row.exit_code == 4 and "bytes or executable mode differ" in row.reason
    assert tree(home) == before


def test_requested_copy_revision_does_not_move_persistent_link_target(source, tmp_path):
    home = tmp_path / "home"
    seed(home, source)
    first, installed = cli(source, home, "refresh", "--select", "claude-topics")
    assert first.returncode == 0, installed
    prior = installed["revision"]
    guide = source / "docs/skills/python-packaging.md"
    guide.write_bytes(guide.read_bytes() + b"\nnew persistent target head\n")
    git(source, "commit", "-am", "target advanced independently")
    head = git(source, "rev-parse", "HEAD")
    assert head != prior
    before = tree(home / ".claude/commands")
    result, report = cli(source, home, "refresh", "--revision", prior)
    assert result.returncode == 4, report
    rows = {r["harness"]: r for r in report["results"]}
    assert rows["claude-links"]["after"]["state"] == "unknown"
    assert rows["claude-topics"]["after"]["state"] == "current"
    assert report["revision"] == prior and git(source, "rev-parse", "HEAD") == head
    assert tree(home / ".claude/commands") == before


@pytest.mark.parametrize("relative", [".claude/commands/cpp", "scripts/cpp-host-write.sh"])
def test_tracked_source_alias_is_unknown_before_target_reads(source, tmp_path, relative):
    target = source / relative
    outside = tmp_path / "outside"
    if target.is_dir():
        outside.mkdir()
        (outside / "personal").write_bytes(b"private directory")
    else:
        outside.write_bytes(b"private file")
    git(source, "rm", "-r", relative)
    target.symlink_to(outside)
    git(source, "add", relative)
    git(source, "commit", "-qm", "tracked source alias")
    assert git(source, "ls-tree", "HEAD", relative).startswith("120000")
    assert git(source, "status", "--porcelain") == ""
    home = tmp_path / "home"
    adapter = seed(home, source)
    before = tree(home)
    row = adapter.operate(request(source), verify_only=True)
    assert row.exit_code == 4 and "alias" in row.reason
    assert tree(home) == before

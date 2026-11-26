"""Committed opposite cases for the one-use #1897 probe; no real pi execution."""

import fcntl
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.pi_owner_fixture_tools import fixture_source, fixture_subprocess

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("make") is None,
    reason="requires git and make for disposable owner fixtures",
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pi_owner_probe", ROOT / "docs/measurements/pi/issue-1897-owner-probe.py")
assert SPEC is not None and SPEC.loader is not None
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


@pytest.fixture(autouse=True)
def owner_tools(tmp_path, monkeypatch, source):
    # The real host helper deliberately excludes ambient PATH. Deliver CI's
    # staged tools only in this disposable fixture, without changing its bytes.
    monkeypatch.setattr(PROBE, "subprocess", fixture_subprocess(tmp_path))
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.setattr(PROBE, "REVISION", revision)


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    path = tmp_path_factory.mktemp("pi-owner-source") / "repo"
    return fixture_source(ROOT, path)


def arguments(tmp_path, source):
    home, agent = tmp_path / "owner", tmp_path / "owner/agent"
    agent.mkdir(parents=True)
    return type("Args", (), dict(source=str(source), home=str(home), agent=str(agent),
                                 journal=str(tmp_path / "journal"), exclusive_window_confirmed=True))()


@pytest.mark.parametrize("personal_neighbor", [True, False])
def test_positive_full_real_cli_and_scoped_undo(tmp_path, source, monkeypatch, personal_neighbor):
    args = arguments(tmp_path, source)
    personal = Path(args.agent) / "skills/personal/SKILL.md"
    if personal_neighbor:
        personal.parent.mkdir(parents=True)
        personal.write_text("synthetic personal fixture\n")
    baseline = PROBE.manifest(personal.parent)
    answers = iter(["RELOAD-PRESENCE-CAPTURED", "RELOAD-BASELINE-CAPTURED"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    PROBE.run(args)
    assert PROBE.manifest(personal.parent) == baseline
    if personal_neighbor:
        assert sorted(path.name for path in personal.parent.parent.iterdir()) == ["personal"]
    else:
        assert not personal.parent.parent.exists()
    assert not (Path(args.agent) / ".cpp-skills.lock").exists()
    assert (Path(args.journal) / "scoped-restored.json").exists()
    # Simulated confirmations test sequencing only, never actual pi discovery.


def test_staged_only_tools_reproduce_missing_git_then_run_real_cli(tmp_path, source, monkeypatch):
    args = arguments(tmp_path, source)
    git = PROBE.subprocess.tool_dir / "git"
    binary = git.readlink()
    git.unlink()
    assert shutil.which("git", path=str(git.parent)) is None
    with pytest.raises(FileNotFoundError, match="git"):
        PROBE.run(args)
    assert not Path(args.journal).exists()
    git.symlink_to(binary)
    answers = iter(["RELOAD-PRESENCE-CAPTURED", "RELOAD-BASELINE-CAPTURED"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    PROBE.run(args)
    assert (Path(args.journal) / "scoped-restored.json").exists()


@pytest.mark.parametrize("collision", ["skills/code-quality", "skills/.cpp-managed", ".cpp-skills.lock"])
def test_existing_target_or_state_refuses_before_install(tmp_path, source, collision):
    args = arguments(tmp_path, source)
    target = Path(args.agent) / collision
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("retain existing state\n")
    before = PROBE.manifest(Path(args.agent))
    with pytest.raises(ValueError, match="preflight refused"):
        PROBE.run(args)
    assert PROBE.manifest(Path(args.agent)) == before


def test_intervening_edit_refuses_undo_without_any_deletion(tmp_path, source, monkeypatch):
    args = arguments(tmp_path, source)
    changed = {}

    def edit_before_undo(prompt):
        target = Path(args.agent) / "skills/code-quality/SKILL.md"
        target.write_bytes(target.read_bytes() + b"\nintervening fixture edit\n")
        changed.update(PROBE.manifest(Path(args.agent)))
        return "RELOAD-PRESENCE-CAPTURED"

    monkeypatch.setattr("builtins.input", edit_before_undo)
    with pytest.raises(ValueError, match="undo refused"):
        PROBE.run(args)
    assert PROBE.manifest(Path(args.agent)) == changed
    assert not (Path(args.journal) / "scoped-restored.json").exists()


def test_unexpected_management_member_refuses_all_deletion(tmp_path, source, monkeypatch):
    args = arguments(tmp_path, source)
    changed = {}

    def add_before_undo(prompt):
        target = Path(args.agent) / "skills/.cpp-managed/foreign-note"
        target.write_text("do not remove\n")
        changed.update(PROBE.manifest(Path(args.agent)))
        return "RELOAD-PRESENCE-CAPTURED"

    monkeypatch.setattr("builtins.input", add_before_undo)
    with pytest.raises(ValueError, match="undo refused"):
        PROBE.run(args)
    assert PROBE.manifest(Path(args.agent)) == changed


def test_no_confirmation_preserves_install(tmp_path, source, monkeypatch):
    args = arguments(tmp_path, source)
    monkeypatch.setattr("builtins.input", lambda prompt: "stop")
    with pytest.raises(ValueError, match="undo not authorized"):
        PROBE.run(args)
    assert (Path(args.agent) / "skills/code-quality/SKILL.md").exists()
    assert not (Path(args.journal) / "scoped-restored.json").exists()


def test_busy_lock_refuses_without_any_deletion(tmp_path, source, monkeypatch):
    args = arguments(tmp_path, source)
    held = []
    unchanged = {}

    def lock_before_undo(prompt):
        handle = (Path(args.agent) / ".cpp-skills.lock").open("r+")
        held.append(handle)
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        unchanged.update(PROBE.manifest(Path(args.agent)))
        return "RELOAD-PRESENCE-CAPTURED"

    monkeypatch.setattr("builtins.input", lock_before_undo)
    try:
        with pytest.raises(BlockingIOError):
            PROBE.run(args)
        assert PROBE.manifest(Path(args.agent)) == unchanged
    finally:
        for handle in held:
            handle.close()


def test_alias_refused_without_following_it(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="alias refused"):
        PROBE.physical(alias / "child")
    assert list(outside.iterdir()) == []


def test_make_metacharacters_in_path_refused(tmp_path):
    with pytest.raises(ValueError, match="unsupported path characters"):
        PROBE.physical(tmp_path / "$(shell touch unwanted)")


def test_umask_0002_build_uses_installer_directory_policy(tmp_path, source, monkeypatch):
    """Regression: original a3dc5d6e stops after actual positive installation."""
    # Existing output from a prior test must not mask directory creation under
    # 0002. A worktree excludes ignored output without copying a detached
    # shallow/partial clone's object store a second time (CI pipeline 4046).
    isolated = tmp_path / "umask-source"
    subprocess.run(["git", "-C", str(source), "worktree", "add", "--quiet",
                    "--detach", str(isolated), PROBE.REVISION], check=True)
    args = arguments(tmp_path, isolated)
    answers = iter(["RELOAD-PRESENCE-CAPTURED", "RELOAD-BASELINE-CAPTURED"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    old_umask = os.umask(0o002)
    try:
        PROBE.run(args)
    finally:
        os.umask(old_umask)
    assert (Path(args.journal) / "scoped-restored.json").exists()
    assert not (Path(args.agent) / "skills").exists()
    record = json.loads((Path(args.journal) / "before-and-undo.json").read_text())
    directories = [row for tree in record["expected"].values() for row in tree.values() if row["kind"] == "dir"]
    assert len(directories) == 28 and all(row["mode"] == 0o775 for row in directories)

"""Recovery controls use only disposable homes and the exact original probe."""

import fcntl
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pi_owner_recovery", ROOT / "docs/measurements/pi/issue-1897-owner-recovery.py")
assert SPEC is not None and SPEC.loader is not None
RECOVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECOVERY)
PROBE = RECOVERY.PROBE


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    path = tmp_path_factory.mktemp("pi-recovery-source") / "repo"
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "checkout", "--quiet", "--detach", PROBE.REVISION], check=True)
    return path


@pytest.fixture
def stopped(tmp_path, source, monkeypatch):
    old_path = tmp_path / "original_probe.py"
    original = (ROOT / "tests/fixtures/pi-owner-probe-a3dc5d6e.py.txt").read_bytes()
    assert hashlib.sha256(original).hexdigest() == "8bfd731d395d61b9f25a970aa247867a5e1cbd811bf171b912ff4b0745afa938"
    old_path.write_bytes(original)
    spec = importlib.util.spec_from_file_location("original_probe", old_path)
    assert spec is not None and spec.loader is not None
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    home, agent = tmp_path / "owner", tmp_path / "owner/agent"
    agent.mkdir(parents=True)
    personal = agent / "skills/personal-fixture/SKILL.md"
    personal.parent.mkdir(parents=True)
    personal.write_text("personal fixture retained\n")
    journal = tmp_path / "journal"
    args = type("Args", (), dict(source=str(source), home=str(home), agent=str(agent),
                                 journal=str(journal), exclusive_window_confirmed=True))()
    old_umask = os.umask(0o002)
    try:
        with pytest.raises(ValueError, match="installed bytes/modes differ"):
            old.run(args)
    finally:
        os.umask(old_umask)
    assert not (journal / "sealed-post.json").exists()
    report = json.loads(json.loads((journal / "command-verify.json").read_text())["stdout"])
    assert report["exit_code"] == 0 and report["after"]["examined_members"] == 36
    # Test-only substitution for synthetic journal bytes. The production CLI
    # has no override: it requires master's four original unsanitized digests.
    monkeypatch.setattr(RECOVERY, "ORIGINAL_HASHES", {
        name: hashlib.sha256((journal / name).read_bytes()).hexdigest() for name in RECOVERY.ORIGINAL_HASHES})
    return type("RecoveryArgs", (), dict(source=str(source), journal=str(journal),
                                          home=str(home),
                                          evidence=str(tmp_path / "recovery"), dry_run=True, execute=False,
                                          exclusive_window_confirmed=True))()


def agent(args):
    return Path(json.loads((Path(args.journal) / "before-and-undo.json").read_text())["agent"])


def execute(args):
    args.dry_run, args.execute = False, True
    RECOVERY.run(args)


def test_matching_install_dry_run_then_cleanup_preserves_unrecorded_neighbor(stopped, capsys):
    root = agent(stopped)
    before = PROBE.manifest(root)
    RECOVERY.run(stopped)
    assert PROBE.manifest(root) == before  # Dry-run cannot delete anything.
    output = capsys.readouterr().out
    operations, _ = json.JSONDecoder().raw_decode(output)
    plan = json.loads((Path(stopped.evidence) / "removal-plan.json").read_text())
    assert operations == plan["operations"] and operations
    assert {row["operation"] for row in operations} == {"unlink", "rmdir"}
    for row in operations:
        assert any(Path(row["path"]).is_relative_to(Path(target)) for target in plan["targets"])
    personal = PROBE.manifest(root / "skills/personal-fixture")
    # An unrecorded neighbor arriving after review is outside the removal plan.
    neighbor = root / "skills/another-personal"
    neighbor.mkdir()
    (neighbor / "SKILL.md").write_text("another personal fixture\n")
    neighbor_before = PROBE.manifest(neighbor)
    execute(stopped)
    assert PROBE.manifest(root / "skills/personal-fixture") == personal
    assert PROBE.manifest(neighbor) == neighbor_before
    assert sorted(path.name for path in (root / "skills").iterdir()) == ["another-personal", "personal-fixture"]
    assert not (root / ".cpp-skills.lock").exists()
    assert (Path(stopped.evidence) / "recovered.json").exists()
    report = json.loads(json.loads((Path(stopped.evidence) / "after-recovery-verify.json").read_text())["stdout"])
    assert report["exit_code"] == 1 and report["after"]["state"] == "absent"
    assert report["after"]["expected_packages"] == 18 and report["after"]["examined_members"] == 0


@pytest.mark.parametrize("change", ["file", "directory-mode", "management-extra"])
def test_changed_install_refuses_before_any_deletion(stopped, change):
    root = agent(stopped)
    if change == "file":
        target = root / "skills/boot/SKILL.md"
        target.write_bytes(target.read_bytes() + b"\npreserve edit\n")
    elif change == "directory-mode":
        (root / "skills/boot").chmod(0o775)
    else:
        (root / "skills/.cpp-managed/foreign-note").write_text("preserve\n")
    before = PROBE.manifest(root)
    with pytest.raises(ValueError):
        RECOVERY.run(stopped)
    assert PROBE.manifest(root) == before
    assert not (Path(stopped.evidence) / "removal-plan.json").exists()


def test_cpp_marked_canonical_path_missing_from_record_refuses(stopped):
    root = agent(stopped)
    boot = root / "skills/boot"
    assert "  source: claude-power-pack/.claude/skills/boot" in (boot / "SKILL.md").read_text()
    record_path = Path(stopped.journal) / "before-and-undo.json"
    record = json.loads(record_path.read_text())
    record["targets"].remove(str(boot))
    del record["before"][str(boot)]
    record_path.write_text(json.dumps(record))
    RECOVERY.ORIGINAL_HASHES["before-and-undo.json"] = hashlib.sha256(record_path.read_bytes()).hexdigest()
    before = PROBE.manifest(root)
    with pytest.raises(ValueError, match="recorded target list differs"):
        RECOVERY.run(stopped)
    assert PROBE.manifest(root) == before


def test_execute_refuses_tampered_plan_without_deletion(stopped):
    root = agent(stopped)
    RECOVERY.run(stopped)
    plan_path = Path(stopped.evidence) / "removal-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["operations"].append({"operation": "unlink", "path": str(root / "skills/personal-fixture/SKILL.md")})
    plan_path.write_text(json.dumps(plan))
    before = PROBE.manifest(root)
    with pytest.raises(ValueError, match="reviewed dry-run plan changed"):
        execute(stopped)
    assert PROBE.manifest(root) == before


def test_execute_refuses_edit_after_dry_run(stopped):
    root = agent(stopped)
    RECOVERY.run(stopped)
    path = root / "skills/boot/SKILL.md"
    path.write_bytes(path.read_bytes() + b"\nedit after dry-run\n")
    before = PROBE.manifest(root)
    with pytest.raises(ValueError):
        execute(stopped)
    assert PROBE.manifest(root) == before


def test_busy_lock_refuses_after_verification_without_deletion(stopped, monkeypatch):
    root = agent(stopped)
    before = PROBE.manifest(root)
    original = PROBE.state
    held = []

    def lock_after_verification(targets):
        if not held:
            handle = (root / ".cpp-skills.lock").open("r+")
            held.append(handle)
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return original(targets)

    monkeypatch.setattr(PROBE, "state", lock_after_verification)
    try:
        with pytest.raises(BlockingIOError):
            RECOVERY.run(stopped)
        assert PROBE.manifest(root) == before
        assert not (Path(stopped.evidence) / "removal-plan.json").exists()
    finally:
        for handle in held:
            handle.close()


def test_missing_lock_is_not_recreated(stopped):
    root = agent(stopped)
    lock = root / ".cpp-skills.lock"
    lock.unlink()
    before = PROBE.manifest(root)
    with pytest.raises(ValueError, match="primary lock content/mode differs"):
        RECOVERY.run(stopped)
    assert not lock.exists()
    assert PROBE.manifest(root) == before


def test_original_journal_hash_mismatch_refuses_before_owner_io(stopped):
    root = agent(stopped)
    before = PROBE.manifest(root)
    RECOVERY.ORIGINAL_HASHES["command-build.json"] = "0" * 64
    with pytest.raises(ValueError, match="original journal hash differs"):
        RECOVERY.run(stopped)
    assert PROBE.manifest(root) == before
    assert not Path(stopped.evidence).exists()


def test_explicit_home_mismatch_refuses(stopped, tmp_path):
    root = agent(stopped)
    before = PROBE.manifest(root)
    stopped.home = str(tmp_path / "different-home")
    with pytest.raises(ValueError, match="explicit home differs"):
        RECOVERY.run(stopped)
    assert PROBE.manifest(root) == before

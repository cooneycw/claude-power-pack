"""Production pi CLI consumes the real core and a revision-bound topic build."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/pi-skill-sync.py"
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git for source binding")


@pytest.mark.skipif(os.geteuid() != 0, reason="requires real root for unreadable-fixture privilege regression")
def test_root_unreadable_control_executes_real_cli_as_unprivileged_child():
    assert os.geteuid() == 0
    answer = subprocess.run(
        [sys.executable, str(ROOT / "controls/pi-skill-install/run-case.py"), str(CLI),
         str(ROOT / "controls/pi-skill-install/cases/unreadable-install")],
        capture_output=True, text=True, timeout=45)
    assert answer.returncode == 4, (answer.stdout, answer.stderr)
    assert "PI_INSTALL_CONTROL_PRECONDITION: unreadable uid=65534 gid=65534 groups=[]" in answer.stderr
    report = json.loads(answer.stdout.split("PI_SKILL_INSTALL: unknown ", 1)[1])
    assert report["exit_code"] == 4
    assert report["reason"] == "filesystem unavailable (PermissionError)"


def test_unreadable_control_unknown_is_the_actual_ledger_permission_failure():
    answer = subprocess.run(
        [sys.executable, str(ROOT / "controls/pi-skill-install/run-case.py"), str(CLI),
         str(ROOT / "controls/pi-skill-install/cases/unreadable-install")],
        capture_output=True, text=True, timeout=45)
    assert answer.returncode == 4, (answer.stdout, answer.stderr)
    report = json.loads(answer.stdout.split("PI_SKILL_INSTALL: unknown ", 1)[1])
    assert report["exit_code"] == 4
    assert report["reason"] == "filesystem unavailable (PermissionError)"


class Case:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.source = root / "source"
        self.home = root / "home"
        self.agent = root / "agent"
        self.cwd = root / "work"
        for path in (self.source, self.home, self.agent, self.cwd):
            path.mkdir(parents=True)
        self.topic = self.source / ".claude/skills/topic/SKILL.md"
        self.topic.parent.mkdir(parents=True)
        self.topic.write_text("---\nname: topic\ndescription: Fixture topic\n---\n"
                              "[guide](../../../docs/skills/guide.md)\n")
        self.guide = self.source / "docs/skills/guide.md"
        self.guide.parent.mkdir(parents=True)
        self.guide.write_text("Fixture guide v1\n")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "fixture")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", "/dev/null")
        self.commit()

    @property
    def skills(self):
        return self.agent / "skills"

    @property
    def ledger(self):
        return self.skills / ".cpp-managed/ownership.json"

    def git(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.run(["git", "-C", str(self.source), *args], env=env,
                              capture_output=True, text=True, check=True, timeout=10).stdout.strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture source")
        self.revision = self.git("rev-parse", "HEAD")

    def call(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PI_", "GIT_"))}
        env["HOME"] = str(self.home)
        answer = subprocess.run([sys.executable, str(CLI), *args, "--root", str(self.source),
                                 "--agent-dir", str(self.agent), "--home", str(self.home), "--json"],
                                cwd=self.cwd, env=env, capture_output=True, text=True, timeout=20)
        return answer, json.loads(answer.stdout) if answer.stdout else {}


def test_cli_installs_real_topics_and_verifies_under_core(tmp_path):
    case = Case(tmp_path)
    installed, report = case.call("--install")
    assert installed.returncode == 0, (installed.stderr, report)
    assert report["after"]["state"] == "current"
    assert report["after"]["expected_members"] == report["after"]["examined_members"] == 2
    assert (case.skills / "topic/references/guide.md").read_text() == "Fixture guide v1\n"
    before = case.ledger.read_bytes()
    verified, report = case.call("--verify-installed")
    assert verified.returncode == 0, report
    assert report["effectiveness"]["state"] == "unknown"
    assert case.ledger.read_bytes() == before


def test_verify_absent_does_not_create_any_lock_or_skills(tmp_path):
    case = Case(tmp_path)
    assert not case.skills.exists()
    verified, report = case.call("--verify-installed")
    assert verified.returncode == 1, (verified.stderr, report)
    assert report["after"]["state"] == "absent"
    assert list(case.agent.iterdir()) == []


def test_canonical_install_from_home_allows_default_agent_inside_home_dot_pi(tmp_path):
    case = Case(tmp_path)
    canonical = case.home / ".pi/agent"
    canonical.parent.mkdir()
    case.agent.rename(canonical)
    case.agent, case.cwd = canonical, case.home
    assert case.agent.is_relative_to(case.cwd / ".pi")
    result, report = case.call("--install")
    assert result.returncode == 0, report


def snapshot(root):
    return {str(p.relative_to(root)): (p.lstat().st_mode, p.read_bytes() if p.is_file() else None)
            for p in root.rglob("*")}


def installed_case(tmp_path):
    case = Case(tmp_path)
    result, report = case.call("--install")
    assert result.returncode == 0, report
    return case


@pytest.mark.parametrize("member", ["SKILL.md", "references/guide.md"])
def test_edited_member_refused_without_adoption_and_preserved(tmp_path, member):
    case = installed_case(tmp_path)
    target = case.skills / "topic" / member
    target.write_bytes(target.read_bytes() + b"hand edit\n")
    assert target.read_bytes().endswith(b"hand edit\n")
    before = snapshot(case.agent)
    result, report = case.call("--install")
    assert result.returncode == 1 and report["before"]["state"] == "hand-edited", report
    assert snapshot(case.agent) == before


def test_foreign_collision_and_neighbor_preserved_then_explicit_backup_adoption(tmp_path):
    case = Case(tmp_path)
    foreign = case.skills / "topic/SKILL.md"
    neighbor = case.skills / "personal/SKILL.md"
    for file in (foreign, neighbor):
        file.parent.mkdir(parents=True)
        file.write_bytes(b"foreign fixture\n")
    refused, report = case.call("--install")
    assert refused.returncode == 1, report
    assert foreign.read_bytes() == neighbor.read_bytes() == b"foreign fixture\n"
    installed, report = case.call("--install", "--adopt", "topic")
    assert installed.returncode == 0 and "backup" in report["remedy"], report
    backups = list((case.skills / ".cpp-managed/work").glob("transaction-*/backup/topic/SKILL.md"))
    assert len(backups) == 1 and backups[0].read_bytes() == b"foreign fixture\n"
    assert neighbor.read_bytes() == b"foreign fixture\n"


def test_dual_identity_cannot_be_adopted_even_with_equal_bytes(tmp_path):
    case = installed_case(tmp_path)
    value = json.loads(case.ledger.read_bytes())
    value["adapters"]["other-identity"] = value["adapters"].pop("pi")
    case.ledger.write_text(json.dumps(value))
    assert "pi" not in value["adapters"] and "topic" in value["adapters"]["other-identity"]
    before = snapshot(case.agent)
    refused, report = case.call("--install", "--adopt", "topic")
    assert refused.returncode == 1 and "another CPP identity" in report["reason"], report
    assert snapshot(case.agent) == before


def test_record_only_reconciliation_keeps_package_inodes_and_verify_never_reconciles(tmp_path):
    case = installed_case(tmp_path)
    # Revision change with identical topic bytes still makes the record stale.
    (case.source / "unrelated.md").write_text("fixture revision only\n")
    case.commit()
    before = {str(p): (p.stat().st_ino, p.stat().st_mtime_ns, p.read_bytes())
              for p in (case.skills / "topic").rglob("*") if p.is_file()}
    old_record = case.ledger.read_bytes()
    verified, report = case.call("--verify-installed")
    assert verified.returncode == 1 and report["after"]["state"] == "stale", report
    assert case.ledger.read_bytes() == old_record
    refreshed, report = case.call("--install")
    assert refreshed.returncode == 0 and report["metadata_refreshed"], report
    assert {str(p): (p.stat().st_ino, p.stat().st_mtime_ns, p.read_bytes())
            for p in (case.skills / "topic").rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("seed", ["dirty", "wrong-revision", "ignored"])
def test_source_binding_refuses_dirty_wrong_and_ignored_inputs(tmp_path, seed):
    case = Case(tmp_path)
    extra = []
    if seed == "dirty":
        case.guide.write_text("uncommitted content\n")
        assert case.git("status", "--porcelain")
    elif seed == "wrong-revision":
        extra = ["--revision", "f" * 40]
        assert case.revision != "f" * 40
    else:
        (case.source / ".gitignore").write_text(".claude/skills/topic/references/\n")
        case.commit()
        ignored = case.topic.parent / "references/ignored.md"
        ignored.parent.mkdir()
        ignored.write_text("must not be read or attributed\n")
        assert case.git("status", "--porcelain") == ""
        assert case.git("check-ignore", str(ignored))
    result, report = case.call("--install", *extra)
    assert result.returncode == 4, report
    assert not case.skills.exists()


def test_user_controlled_agent_prefix_alias_refused_before_target_access(tmp_path):
    case = Case(tmp_path)
    actual = tmp_path / "protected"
    actual.mkdir()
    case.agent.rmdir()
    case.agent.symlink_to(actual, target_is_directory=True)
    assert case.agent.is_symlink()
    result, report = case.call("--install")
    assert result.returncode == 1 and "symlink" in report["reason"], report
    assert list(actual.iterdir()) == []


@pytest.mark.parametrize("layout", ["linked", "shallow"])
def test_revision_bound_adapter_in_linked_and_shallow_source_layouts(tmp_path, layout):
    case = Case(tmp_path)
    original = case.source
    selected = tmp_path / layout
    if layout == "linked":
        case.git("worktree", "add", "--detach", str(selected), case.revision)
        assert (selected / ".git").is_file()
    else:
        case.git("clone", "--depth=1", "--single-branch", original.as_uri(), str(selected))
        shallow = subprocess.run(["git", "-C", str(selected), "rev-parse", "--is-shallow-repository"],
                                 capture_output=True, text=True, check=True)
        assert shallow.stdout.strip() == "true"
    case.source = selected
    answer, report = case.call("--install")
    assert answer.returncode == 0 and report["revision"] == case.revision, report


@pytest.mark.parametrize("history_source", ["cli", "environment", "global", "project", "default"])
def test_installer_refuses_every_history_candidate_overlapping_skills(tmp_path, history_source):
    case = Case(tmp_path)
    extra = []
    if history_source == "cli":
        extra = ["--session-dir", str(case.skills)]
    elif history_source == "environment":
        # Case.call intentionally removes PI_*; use the adapter with explicit environment.
        from lib.host_update.models import AdapterError, Request, Revision
        from lib.host_update.pi_adapter import PiAdapter
        adapter = PiAdapter(cwd=case.cwd, home=case.home, agent=case.agent,
                            environ={"PI_CODING_AGENT_SESSION_DIR": str(case.skills)})
        with pytest.raises(AdapterError, match="output_root_under_sessions"):
            adapter.preflight(Request(Revision(case.revision, case.source)))
        return
    elif history_source == "default":
        # Default agent/sessions contains skills by an alias, never traverse its descendants.
        (case.agent / "sessions").symlink_to(case.agent, target_is_directory=True)
        assert (case.agent / "sessions").is_symlink()
    else:
        settings = case.agent / "settings.json" if history_source == "global" else case.cwd / ".pi/settings.json"
        settings.parent.mkdir(exist_ok=True)
        settings.write_text(json.dumps({"sessionDir": str(case.skills)}))
    result, report = case.call("--install", *extra)
    assert result.returncode == 1 and "output_root_under_sessions" in report["reason"], report
    assert not case.skills.exists()

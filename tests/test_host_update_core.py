"""The real core consumes real builds/ledgers; no copied report stand-ins."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from lib.host_update.driver import inspect, refresh, run
from lib.host_update.fixture import FIXTURE_MARKER, FixtureAdapter
from lib.host_update.models import AdapterError, Request, Revision, State
from lib.host_update.scope import Scope

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git for real source binding")


class Case:
    def __init__(self, root: Path, *, second_package: bool = False) -> None:
        self.root = root
        root.mkdir(parents=True)
        (root / ".cpp-host-update-fixture").write_bytes(FIXTURE_MARKER)
        self.source = root / "source"
        self.source.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "fixture")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", "/dev/null")
        (self.source / "topic").mkdir()
        (self.source / "topic" / "SKILL.md").write_bytes(b"fixture skill v1\n")
        (self.source / "topic" / "guide.md").write_bytes(b"fixture guide v1\n")
        self.rows = [{"name": "topic", "canonical_source": "fixture/topic", "members": {
            "SKILL.md": {"source": "topic/SKILL.md"},
            "references/guide.md": {"source": "topic/guide.md"},
        }}]
        if second_package:
            (self.source / "old").mkdir()
            (self.source / "old" / "SKILL.md").write_bytes(b"orphan candidate\n")
            self.rows.append({"name": "old", "canonical_source": "fixture/old", "members": {
                "SKILL.md": {"source": "old/SKILL.md"},
            }})
        self.revision = self.commit()
        for name in ("a", "b"):
            (root / name).mkdir()

    def git(self, *args: str) -> str:
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.run(["git", "-C", str(self.source), *args], capture_output=True,
                              text=True, check=True, timeout=10, env=env).stdout.strip()

    def commit(self) -> str:
        self.git("add", ".")
        self.git("commit", "-qm", "fixture revision")
        self.revision = self.git("rev-parse", "HEAD")
        return self.revision

    def spec(self, name: str = "a") -> dict:
        return {"harness": f"fixture-{name}", "selected": True, "source": "source",
                "install": f"{name}/skills", "ledger": f"{name}/skills/.managed/ownership.json",
                "lock": f"{name}/.install.lock", "work": f"{name}/skills/.managed/work", "packages": self.rows}

    def adapter(self, name: str = "a") -> FixtureAdapter:
        return FixtureAdapter(self.root, self.spec(name))

    def request(self, **kwargs) -> Request:
        return Request(Revision(self.revision, self.source), **kwargs)

    def descriptor(self, *, two: bool = False) -> None:
        (self.root / "fixture.json").write_text(json.dumps({
            "schema": 1, "source": "source", "revision": self.revision,
            "adapters": [self.spec("a"), *([self.spec("b")] if two else [])],
        }))


def tree_snapshot(root: Path) -> dict:
    result = {}
    if not root.exists():
        return result
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        result[str(path.relative_to(root))] = (
            stat.S_IFMT(mode), stat.S_IMODE(mode),
            hashlib.sha256(path.read_bytes()).hexdigest() if stat.S_ISREG(mode) else "",
        )
    return result


def test_real_build_install_and_verify(tmp_path):
    case = Case(tmp_path / "fixture")
    assert inspect(case.adapter(), case.request()).after.state == State.ABSENT
    answer = refresh(case.adapter(), case.request())
    assert answer.exit_code == 0, answer
    assert answer.after.state == State.CURRENT
    observed = inspect(case.adapter(), case.request())
    assert observed.exit_code == 0
    assert observed.after.examined_members == observed.after.expected_members == 2
    assert observed.effectiveness.state == "unknown"


def test_missing_and_edited_conflicts_preserve_both(tmp_path):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    skill = case.root / "a/skills/topic/SKILL.md"
    guide = case.root / "a/skills/topic/references/guide.md"
    skill.write_bytes(b"personal edit")
    guide.unlink()
    assert skill.read_bytes() != (case.source / "topic/SKILL.md").read_bytes()
    assert not guide.exists()
    before = tree_snapshot(case.root / "a")
    result = refresh(case.adapter(), case.request())
    assert result.exit_code == 1 and result.before.state == State.HAND_EDITED
    assert {c.state for c in result.before.conflicts} >= {State.HAND_EDITED, State.ABSENT}
    assert tree_snapshot(case.root / "a") == before


def test_missing_member_repaired_but_foreign_sibling_unchanged(tmp_path):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    skill = case.root / "a/skills/topic/SKILL.md"
    skill.unlink()
    foreign = case.root / "a/skills/personal"
    foreign.mkdir()
    (foreign / "SKILL.md").write_bytes(b"user-owned")
    original = tree_snapshot(foreign)
    assert not skill.exists()
    assert refresh(case.adapter(), case.request()).exit_code == 0
    assert tree_snapshot(foreign) == original


def test_unexpected_internal_content_refused_without_reading_it(tmp_path, monkeypatch):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    extra = case.root / "a/skills/topic/personal.data"
    extra.write_bytes(b"foreign fixture bytes")
    assert extra.exists()
    reader = Scope.read

    def bounded(self, path):
        assert path != extra, "foreign content must not be opened for hashing"
        return reader(self, path)

    monkeypatch.setattr(Scope, "read", bounded)
    original = tree_snapshot(case.root / "a")
    result = refresh(case.adapter(), case.request())
    assert result.exit_code == 1 and result.before.state == State.UNMANAGED
    assert tree_snapshot(case.root / "a") == original


def test_unmanaged_same_name_target_preserved(tmp_path):
    case = Case(tmp_path / "fixture")
    target = case.root / "a/skills/topic"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_bytes(b"foreign skill")
    assert not (case.root / "a/skills/.managed/ownership.json").exists()
    original = tree_snapshot(target)
    result = refresh(case.adapter(), case.request())
    assert result.exit_code == 1 and result.before.state == State.UNMANAGED
    assert tree_snapshot(target) == original


def test_owned_mode_drift_is_hand_edited_and_preserved(tmp_path):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    skill = case.root / "a/skills/topic/SKILL.md"
    skill.chmod(0o755)
    assert stat.S_IMODE(skill.stat().st_mode) == 0o755
    result = refresh(case.adapter(), case.request())
    assert result.exit_code == 1 and result.before.state == State.HAND_EDITED
    assert stat.S_IMODE(skill.stat().st_mode) == 0o755


def test_record_only_reconciliation_does_not_republish_package(tmp_path, monkeypatch):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    (case.source / "topic/SKILL.md").write_bytes(b"v2\n")
    case.commit()
    installed = case.root / "a/skills/topic/SKILL.md"
    installed.write_bytes(b"v2\n")
    assert inspect(case.adapter(), case.request()).after.state == State.HAND_EDITED
    original = tree_snapshot(case.root / "a/skills/topic")

    def forbidden(*args):
        raise AssertionError("record-only reconciliation must not rename package trees")

    monkeypatch.setattr(Scope, "rename", forbidden)
    result = refresh(case.adapter(), case.request())
    assert result.exit_code == 0 and result.metadata_refreshed
    assert tree_snapshot(case.root / "a/skills/topic") == original
    assert inspect(case.adapter(), case.request()).exit_code == 0


@pytest.mark.parametrize("change", ["unchanged", "edited", "foreign"])
def test_prune_requires_every_orphan_member_to_be_proven_unchanged(tmp_path, change):
    case = Case(tmp_path / "fixture", second_package=True)
    assert refresh(case.adapter(), case.request()).exit_code == 0
    orphan = case.root / "a/skills/old"
    if change == "edited":
        (orphan / "SKILL.md").write_bytes(b"user edit")
        assert (orphan / "SKILL.md").read_bytes() != (case.source / "old/SKILL.md").read_bytes()
    elif change == "foreign":
        (orphan / "personal.data").write_bytes(b"user file")
        assert (orphan / "personal.data").exists()
    before = tree_snapshot(orphan)
    shutil.rmtree(case.source / "old")
    case.rows = case.rows[:1]
    case.commit()
    result = refresh(case.adapter(), case.request())
    if change == "unchanged":
        assert result.exit_code == 0 and not orphan.exists()
    else:
        assert result.exit_code == 1
        assert tree_snapshot(orphan) == before


def test_explicit_reviewed_adoption_retains_recoverable_backup(tmp_path):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    skill = case.root / "a/skills/topic/SKILL.md"
    skill.write_bytes(b"reviewed user edit")
    assert inspect(case.adapter(), case.request()).after.state == State.HAND_EDITED
    result = refresh(case.adapter(), case.request(adopt_paths=("topic/SKILL.md",)))
    assert result.exit_code == 0 and "backup retained" in result.remedy
    backups = list((case.root / "a/skills/.managed/work").glob("transaction-*/backup/topic/SKILL.md"))
    assert len(backups) == 1 and backups[0].read_bytes() == b"reviewed user edit"


@pytest.mark.parametrize("content", [b"{", b'{"schema":1,"schema":1}',
                                     b'{"producer":"foreign","schema":1,"packages":{}}'])
def test_unreadable_or_ambiguous_record_is_unknown(tmp_path, content):
    case = Case(tmp_path / "fixture")
    assert refresh(case.adapter(), case.request()).exit_code == 0
    ledger = case.root / "a/skills/.managed/ownership.json"
    ledger.write_bytes(content)
    assert ledger.read_bytes() == content
    before = tree_snapshot(case.root / "a")
    answer = refresh(case.adapter(), case.request())
    assert answer.exit_code == 4 and answer.after.state == State.UNKNOWN
    assert tree_snapshot(case.root / "a") == before


def test_preflight_refusal_before_any_generic_filesystem_access(tmp_path, monkeypatch):
    case = Case(tmp_path / "fixture")

    class Refused(FixtureAdapter):
        def preflight(self, request):
            raise AdapterError("pi fixture path refused", state=State.UNMANAGED)

    def forbidden(*args, **kwargs):
        raise AssertionError("filesystem reached before preflight accepted")

    monkeypatch.setattr(Scope, "directory", forbidden)
    answer = refresh(Refused(case.root, case.spec()), case.request())
    assert answer.exit_code == 1 and answer.reason == "pi fixture path refused"


def test_adapter_markdown_mode_policy_rejects_executable_before_writes(tmp_path):
    case = Case(tmp_path / "fixture")
    (case.source / "helper.sh").write_bytes(b"fixture executable content\n")
    case.rows[0]["members"]["helper.sh"] = {"source": "helper.sh", "mode": 0o755}
    case.commit()

    class MarkdownOnly(FixtureAdapter):
        def preflight(self, request):
            return replace(super().preflight(request),
                           member_allowed=lambda path, mode: path.endswith(".md") and mode == 0o644)

    assert case.rows[0]["members"]["helper.sh"]["mode"] == 0o755
    result = refresh(MarkdownOnly(case.root, case.spec()), case.request())
    assert result.exit_code == 1 and "adapter policy" in result.reason
    assert not (case.root / "a/.install.lock").exists()


def test_symlink_root_is_refused_without_touching_target(tmp_path):
    case = Case(tmp_path / "fixture")
    protected = case.root / "protected-fixture"
    protected.mkdir()
    (protected / "sentinel").write_bytes(b"untouched")
    (case.root / "a/skills").symlink_to(protected, target_is_directory=True)
    assert (case.root / "a/skills").is_symlink()
    before = tree_snapshot(protected)
    result = refresh(case.adapter(), case.request())
    assert result.exit_code == 1
    assert tree_snapshot(protected) == before


def test_dirty_source_and_wrong_build_revision_fail_unknown(tmp_path):
    case = Case(tmp_path / "fixture")
    (case.source / "topic/SKILL.md").write_bytes(b"not committed")
    assert case.git("status", "--porcelain")
    assert refresh(case.adapter(), case.request()).exit_code == 4
    assert not (case.root / "a/.install.lock").exists()
    case.commit()

    class Wrong(FixtureAdapter):
        def build(self, revision, policy):
            return replace(super().build(revision, policy), revision="0" * 40)

    assert refresh(Wrong(case.root, case.spec()), case.request()).exit_code == 4


def test_zero_validated_expected_population_never_current(tmp_path):
    case = Case(tmp_path / "fixture")
    case.rows.clear()
    assert not case.rows
    result = inspect(case.adapter(), case.request())
    assert result.exit_code == 4 and "population is zero" in result.reason


def test_source_binding_ignores_foreign_git_environment(tmp_path, monkeypatch):
    case = Case(tmp_path / "fixture")
    foreign = Case(tmp_path / "foreign")
    (foreign.source / "topic/SKILL.md").write_bytes(b"different source repository\n")
    foreign.commit()
    assert foreign.revision != case.revision
    monkeypatch.setenv("GIT_DIR", str(foreign.source / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(foreign.source))
    result = refresh(case.adapter(), case.request())
    assert result.exit_code == 0, result.reason
    assert result.revision == case.revision


def test_ignored_worktree_file_cannot_be_attributed_to_source_commit(tmp_path):
    case = Case(tmp_path / "fixture")
    (case.source / ".gitignore").write_text("ignored.md\n")
    (case.source / "ignored.md").write_bytes(b"not part of the source commit\n")
    case.commit()
    assert case.git("status", "--porcelain") == ""
    assert case.git("ls-files", "ignored.md") == ""
    case.rows[0]["members"]["references/ignored.md"] = {"source": "ignored.md"}
    result = refresh(case.adapter(), case.request())
    assert result.exit_code == 4, "untracked source bytes cannot inherit a commit's provenance"
    assert not (case.root / "a/skills/topic").exists()


def test_selected_absent_vs_unselected_not_applicable_without_mutation(tmp_path):
    case = Case(tmp_path / "fixture")
    before = tree_snapshot(case.root / "a")
    assert inspect(case.adapter(), case.request()).after.state == State.ABSENT
    assert inspect(case.adapter(), case.request(selected=False)).exit_code == 5
    assert tree_snapshot(case.root / "a") == before


def test_partial_failures_keep_other_adapter_outcomes_and_exit_precedence(tmp_path):
    case = Case(tmp_path / "fixture")

    class Refused(FixtureAdapter):
        def preflight(self, request):
            raise AdapterError("fixture policy refusal", state=State.UNMANAGED)

    class Unknown(FixtureAdapter):
        def preflight(self, request):
            raise AdapterError("fixture unexaminable", exit_code=4)

    refused = Refused(case.root, dict(case.spec(), harness="refused"))
    unknown = Unknown(case.root, dict(case.spec(), harness="unknown"))
    result = run([unknown, case.adapter("b"), refused], case.request())
    assert result.exit_code == 1
    assert [row.exit_code for row in result.results] == [4, 0, 1]
    assert all(row.revision == case.revision for row in result.results)
    assert inspect(case.adapter("b"), case.request()).exit_code == 0


def test_genuinely_unwritable_destination_does_not_stop_other_adapter(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("requires unprivileged identity to prove failed write")
    case = Case(tmp_path / "fixture")
    parent = case.root / "a"
    parent.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            (parent / "write-precondition").write_bytes(b"must fail")
        result = run([case.adapter(), case.adapter("b")], case.request())
        assert result.exit_code == 1
        assert result.results[0].exit_code == 1 and result.results[1].exit_code == 0
    finally:
        parent.chmod(0o700)

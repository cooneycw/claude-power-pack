"""Tests for lib.cpp_memory: bucket-2 classification, fingerprint, and fail-open.

These run with NO database and NO psycopg driver on purpose: the store-down /
driver-absent path IS the fail-open contract the issue (#433) requires us to
verify. Every store method must degrade to a benign value and never raise, and
non-portable learnings must never reach the shared store.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from lib.cpp_memory import (
    Learning,
    MemoryStore,
    append_local_learning,
    is_actionable,
    is_portable,
    issue_body,
    issue_marker,
    resolve_dsn,
    should_file_issue,
)
from lib.cpp_memory import cli as cli_mod
from lib.cpp_memory import client as client_mod
from lib.cpp_memory import config as config_mod
from lib.cpp_memory import fingerprint as fp_mod


# --------------------------------------------------------------------------- #
# Fingerprint: deterministic cross-VM dedup key over (class, normalized title)
# --------------------------------------------------------------------------- #
class TestFingerprint:
    def test_body_does_not_affect_key(self):
        a = fp_mod.fingerprint("knowledge", "Some Title", "body one")
        b = fp_mod.fingerprint("knowledge", "Some Title", "a totally different body")
        assert a == b

    def test_case_and_whitespace_insensitive(self):
        a = fp_mod.fingerprint("knowledge", "Codex   Hang")
        b = fp_mod.fingerprint("KNOWLEDGE", "  codex hang  ")
        assert a == b

    def test_class_and_title_change_key(self):
        base = fp_mod.fingerprint("knowledge", "T")
        assert fp_mod.fingerprint("infra_trap", "T") != base
        assert fp_mod.fingerprint("knowledge", "T2") != base

    def test_is_hex_sha256(self):
        h = fp_mod.fingerprint("knowledge", "x")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_learning_property_matches_helper(self):
        learning = Learning("infra_trap", "knowledge", "Woodpecker gRPC :9001 Tailscale-only", "b")
        assert learning.fingerprint == fp_mod.fingerprint("infra_trap", "Woodpecker gRPC :9001 Tailscale-only")


# --------------------------------------------------------------------------- #
# Portability / bucket-2 gate
# --------------------------------------------------------------------------- #
class TestPortability:
    @pytest.mark.parametrize(
        "cls,scope,expected",
        [
            ("knowledge", "knowledge", True),
            ("infra_trap", "knowledge", True),
            ("infra_trap", "repo_file", True),  # portable class alone qualifies
            ("permission", "permission", False),
            ("gate_failure", "repo_file", False),
            ("red_output", "repo_file", False),
            ("manual_intervention", "repo_file", False),
        ],
    )
    def test_is_portable(self, cls, scope, expected):
        assert is_portable(cls, scope) is expected

    def test_learning_portable_property(self):
        assert Learning("knowledge", "knowledge", "t", "b").portable is True
        assert Learning("permission", "permission", "t", "b").portable is False

    def test_validate_rejects_unknown_class(self):
        with pytest.raises(ValueError):
            Learning("bogus", "knowledge", "t", "b").validate()

    def test_validate_rejects_unknown_scope(self):
        with pytest.raises(ValueError):
            Learning("knowledge", "bogus", "t", "b").validate()

    def test_validate_requires_title(self):
        with pytest.raises(ValueError):
            Learning("knowledge", "knowledge", "   ", "b").validate()


# --------------------------------------------------------------------------- #
# Fail-open client: store unavailable -> benign returns, never raises
# --------------------------------------------------------------------------- #
@pytest.fixture
def down_store():
    """A store guaranteed unavailable: an empty DSN forces available() -> False."""
    return MemoryStore(dsn="")


class TestFailOpen:
    def test_available_false_without_dsn(self, down_store):
        assert down_store.available() is False

    def test_reads_return_benign(self, down_store):
        assert down_store.ping() is False
        assert down_store.is_known("deadbeef") is None
        assert down_store.rejected_here("deadbeef", "vm-a") is False
        assert down_store.list_learnings() == []
        assert down_store.sightings("deadbeef") == []
        assert down_store.init_db() is False

    def test_decisions_return_benign(self, down_store):
        assert down_store.mark_applied("fp", "vm-a") is False
        assert down_store.mark_rejected("fp", "vm-a") is False

    def test_record_portable_returns_none_when_down(self, down_store):
        learning = Learning("knowledge", "knowledge", "codex tty hang", "append </dev/null")
        assert down_store.record_learning(learning, "vm-a") is None

    def test_record_non_portable_raises_even_when_down(self, down_store):
        # The bucket-2 guard fires before the availability check: a permission
        # fix must never enter the shared store, from any code path.
        learning = Learning("permission", "permission", "allow npm", "b")
        with pytest.raises(ValueError):
            down_store.record_learning(learning, "vm-a")

    def test_driver_missing_with_dsn_is_unavailable(self, monkeypatch):
        # DSN present but no psycopg driver: still fail-open, and no connection
        # attempt is made (available() short-circuits before _conn()).
        monkeypatch.setattr(client_mod, "_HAVE_PSYCOPG", False)
        store = MemoryStore(dsn="postgres://u:p@127.0.0.1:5432/db")
        assert store.available() is False
        assert store.ping() is False
        assert store.record_learning(Learning("knowledge", "knowledge", "t", "b"), "vm-a") is None


# --------------------------------------------------------------------------- #
# Local fallback: append_local_learning writes .claude/learnings.md
# --------------------------------------------------------------------------- #
class TestLocalFallback:
    def test_writes_learnings_md(self, tmp_path):
        learning = Learning(
            "knowledge", "knowledge", "My Title", "reusable body text", proposed_fix="do X"
        )
        path = append_local_learning(learning, tmp_path)
        assert path == tmp_path / ".claude" / "learnings.md"
        text = path.read_text(encoding="utf-8")
        assert "My Title" in text
        assert "reusable body text" in text
        assert "do X" in text
        assert learning.fingerprint in text
        assert "portable: True" in text

    def test_appends_not_overwrites(self, tmp_path):
        append_local_learning(Learning("knowledge", "knowledge", "First", "b1"), tmp_path)
        append_local_learning(Learning("knowledge", "knowledge", "Second", "b2"), tmp_path)
        text = (tmp_path / ".claude" / "learnings.md").read_text(encoding="utf-8")
        assert "First" in text
        assert "Second" in text


# --------------------------------------------------------------------------- #
# Tiered DSN resolution (config), all hermetic (no real AWS / files)
# --------------------------------------------------------------------------- #
class TestResolveDsn:
    def test_env_wins_and_is_stripped(self, monkeypatch):
        monkeypatch.setenv("CPP_MEMORIES_DSN", "  postgres://env/db  ")
        assert resolve_dsn() == "postgres://env/db"

    def test_none_when_nothing_available(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CPP_MEMORIES_DSN", raising=False)
        monkeypatch.setattr(config_mod, "LOCAL_DSN_FILE", tmp_path / "nope.dsn")
        assert resolve_dsn(allow_aws=False) is None

    def test_local_file_tier(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CPP_MEMORIES_DSN", raising=False)
        dsn_file = tmp_path / "cpp.dsn"
        dsn_file.write_text("postgres://file/db\n", encoding="utf-8")
        monkeypatch.setattr(config_mod, "LOCAL_DSN_FILE", dsn_file)
        assert resolve_dsn(allow_aws=False) == "postgres://file/db"

    def test_aws_json_tier(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CPP_MEMORIES_DSN", raising=False)
        monkeypatch.setattr(config_mod, "LOCAL_DSN_FILE", tmp_path / "nope.dsn")

        def fake_run(cmd, **kwargs):
            payload = json.dumps({config_mod.AWS_SECRET_KEY: "postgres://aws/db"})
            return subprocess.CompletedProcess(cmd, 0, stdout=payload, stderr="")

        monkeypatch.setattr(config_mod.subprocess, "run", fake_run)
        assert resolve_dsn() == "postgres://aws/db"

    def test_aws_failure_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CPP_MEMORIES_DSN", raising=False)
        monkeypatch.setattr(config_mod, "LOCAL_DSN_FILE", tmp_path / "nope.dsn")

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

        monkeypatch.setattr(config_mod.subprocess, "run", fake_run)
        assert resolve_dsn() is None


# --------------------------------------------------------------------------- #
# CLI: the harness-facing surface. Forced offline so results are deterministic.
# --------------------------------------------------------------------------- #
@pytest.fixture
def cli_offline(monkeypatch):
    """Make the CLI construct a guaranteed-unavailable store regardless of env."""
    monkeypatch.setattr(cli_mod, "MemoryStore", lambda *a, **k: MemoryStore(dsn=""))


class TestCli:
    def test_ping_reports_unreachable(self, cli_offline, capsys):
        rc = cli_mod.main(["ping"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert out["reachable"] is False

    def test_record_local_only_stays_local(self, cli_offline, capsys, tmp_path):
        rc = cli_mod.main([
            "record", "--local-only", "--class", "permission", "--scope", "permission",
            "--title", "allow npm in project", "--body", "x", "--repo", str(tmp_path),
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["stored"] == "local"
        assert (tmp_path / ".claude" / "learnings.md").exists()

    def test_record_non_portable_kept_local(self, cli_offline, capsys, tmp_path):
        # A permission fix without --local-only is STILL kept local by the guard.
        rc = cli_mod.main([
            "record", "--class", "permission", "--scope", "permission",
            "--title", "grant push", "--body", "x", "--repo", str(tmp_path),
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["stored"] == "local"
        assert out["portable"] is False

    def test_record_portable_falls_back_when_down(self, cli_offline, capsys, tmp_path):
        rc = cli_mod.main([
            "record", "--class", "knowledge", "--scope", "knowledge",
            "--title", "codex exec tty hang", "--body", "append </dev/null",
            "--repo", str(tmp_path),
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["stored"] == "local-fallback"
        assert (tmp_path / ".claude" / "learnings.md").exists()

    def test_record_invalid_class_errors(self, cli_offline, capsys, tmp_path):
        rc = cli_mod.main([
            "record", "--class", "bogus", "--scope", "knowledge",
            "--title", "t", "--repo", str(tmp_path),
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 2
        assert "error" in out

    def test_query_fingerprint_benign_when_down(self, cli_offline, capsys):
        rc = cli_mod.main(["query", "--fingerprint", "deadbeef"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["known"] is False
        assert out["rejected_here"] is False
        assert out["sightings"] == 0

    def test_query_list_benign_when_down(self, cli_offline, capsys):
        rc = cli_mod.main(["query", "--class", "knowledge"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["count"] == 0

    def test_reject_benign_when_down(self, cli_offline, capsys):
        rc = cli_mod.main(["reject", "--fingerprint", "deadbeef", "--actor", "me"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert out["reject"] is False


# --------------------------------------------------------------------------- #
# learnings -> GitHub issue bridge (#463)
# --------------------------------------------------------------------------- #
class TestActionable:
    def test_portable_with_fix_is_actionable(self):
        learning = Learning("knowledge", "knowledge", "t", "b", proposed_fix="do X")
        assert is_actionable(learning) is True
        assert learning.actionable is True

    def test_portable_without_fix_is_not_actionable(self):
        # A "watch out for X" note with no concrete fix is knowledge, not work.
        assert is_actionable(Learning("knowledge", "knowledge", "t", "b")) is False
        assert is_actionable(Learning("infra_trap", "knowledge", "t", "b", proposed_fix="   ")) is False

    def test_non_portable_is_never_actionable(self):
        # Even with a fix, a permission learning must never become a shared issue.
        assert is_actionable(Learning("permission", "permission", "t", "b", proposed_fix="do X")) is False


class TestShouldFileIssue:
    def test_actionable_and_unfiled_files(self):
        assert should_file_issue(True, None) is True
        assert should_file_issue(True, "") is True
        assert should_file_issue(True, "   ") is True

    def test_already_filed_does_not_refile(self):
        assert should_file_issue(True, "https://github.com/o/r/issues/1") is False

    def test_non_actionable_never_files(self):
        assert should_file_issue(False, None) is False
        assert should_file_issue(False, "https://github.com/o/r/issues/1") is False


class TestIssueBody:
    def test_marker_is_html_comment_with_fingerprint(self):
        marker = issue_marker("abc123")
        assert marker == "<!-- cpp-learning: abc123 -->"

    def test_body_carries_marker_fix_and_provenance(self):
        learning = Learning(
            "infra_trap", "knowledge", "gRPC :9001 is Tailscale-only",
            "the woodpecker gRPC port is not on the LAN", proposed_fix="use the tailnet addr",
        )
        body = issue_body(learning, source_repo="agentic-asst")
        assert issue_marker(learning.fingerprint) in body      # dedup marker
        assert "use the tailnet addr" in body                  # the fix
        assert "the woodpecker gRPC port is not on the LAN" in body
        assert learning.fingerprint in body                    # provenance
        assert "agentic-asst" in body                          # source repo


class TestLinkIssueFailOpen:
    def test_link_issue_benign_when_down(self, down_store):
        assert down_store.link_issue("deadbeef", "https://github.com/o/r/issues/1") is False


class TestCliBridge:
    def test_record_emits_issue_candidate_for_actionable(self, cli_offline, capsys, tmp_path):
        rc = cli_mod.main([
            "record", "--class", "infra_trap", "--scope", "knowledge",
            "--title", "gh merge from worktree fails", "--body", "main already checked out",
            "--fix", "run from the main repo", "--repo", str(tmp_path),
            "--emit-issue-candidate",
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        cand = out["issue_candidate"]
        assert cand["actionable"] is True
        assert cand["should_file"] is True          # store down -> no existing url -> file (fail-open)
        assert cand["marker"] in cand["body"]
        assert cand["repo"] == str(tmp_path)

    def test_record_no_candidate_flag_omits_block(self, cli_offline, capsys, tmp_path):
        rc = cli_mod.main([
            "record", "--class", "knowledge", "--scope", "knowledge",
            "--title", "t", "--body", "b", "--fix", "do X", "--repo", str(tmp_path),
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert "issue_candidate" not in out

    def test_record_candidate_not_fileable_without_fix(self, cli_offline, capsys, tmp_path):
        rc = cli_mod.main([
            "record", "--class", "knowledge", "--scope", "knowledge",
            "--title", "just a note", "--body", "b", "--repo", str(tmp_path),
            "--emit-issue-candidate",
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["issue_candidate"]["actionable"] is False
        assert out["issue_candidate"]["should_file"] is False

    def test_link_issue_benign_when_down(self, cli_offline, capsys):
        rc = cli_mod.main(["link-issue", "--fingerprint", "deadbeef", "--url", "https://github.com/o/r/issues/1"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert out["linked"] is False

    def test_query_reports_has_issue_false_when_down(self, cli_offline, capsys):
        rc = cli_mod.main(["query", "--fingerprint", "deadbeef"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["has_issue"] is False

"""Per-backend tests for the pluggable common-memory store (issue #472).

Covers the ``StoreBackend`` contract across the mini-tier:

- **factory** (``select_backend``) - explicit choice, env, and DSN inference;
- **md backend** (tier i) - consult / best-effort dedup / reject sidecar /
  local acceptance of non-portable notes / federation="none";
- **pg backend** (tiers ii/iii) - it satisfies ``StoreBackend``, surfaces the
  right federation label, and (as a federated store) still refuses non-portable;
- **CLI surfacing** - ``ping`` / ``record`` now report ``backend`` + ``federation``.

Like test_cpp_memory.py these run with NO database and NO psycopg driver: the md
backend needs neither, and the pg assertions here are all about identity /
guard behaviour, not connectivity.
"""
from __future__ import annotations

import json

import pytest

from lib.cpp_memory import (
    FEDERATION_FLEET,
    FEDERATION_NONE,
    Learning,
    MarkdownStore,
    MemoryStore,
    StoreBackend,
    select_backend,
)
from lib.cpp_memory import cli as cli_mod
from lib.cpp_memory import store as store_mod


# --------------------------------------------------------------------------- #
# Factory: select_backend resolves md | local-pg | remote-pg
# --------------------------------------------------------------------------- #
class TestFactory:
    def test_explicit_md(self, tmp_path):
        s = select_backend(backend="md", repo_root=str(tmp_path))
        assert isinstance(s, MarkdownStore)
        assert s.name == "md"
        assert s.federation == FEDERATION_NONE
        assert s.federated is False

    def test_explicit_local_pg_defaults_dsn(self, monkeypatch):
        monkeypatch.delenv("CPP_MEMORIES_DSN", raising=False)
        s = select_backend(backend="local-pg")
        assert isinstance(s, MemoryStore)
        assert s.name == "local-pg"
        assert s.federation == FEDERATION_NONE  # single box, no federation
        assert "5433" in (s.dsn or "")          # the docker default DSN

    def test_explicit_remote_pg_is_federated(self):
        s = select_backend(backend="remote-pg", dsn="postgres://h/db")
        assert s.name == "remote-pg"
        assert s.federation == FEDERATION_FLEET
        assert s.federated is True

    def test_infer_md_when_no_dsn(self, monkeypatch):
        monkeypatch.setattr(store_mod, "resolve_backend", lambda: None)
        s = select_backend(dsn="")  # falsy DSN -> local md ledger
        assert s.name == "md"

    def test_infer_remote_pg_when_dsn_present(self, monkeypatch):
        monkeypatch.setattr(store_mod, "resolve_backend", lambda: None)
        s = select_backend(dsn="postgres://h/db")  # a DSN implies today's fleet default
        assert s.name == "remote-pg"

    def test_env_backend_wins(self, monkeypatch):
        monkeypatch.setenv("CPP_MEMORIES_BACKEND", "local-pg")
        s = select_backend(dsn="postgres://local/db")
        assert s.name == "local-pg"


# --------------------------------------------------------------------------- #
# Markdown backend (tier i): first-class local store, best-effort dedup
# --------------------------------------------------------------------------- #
@pytest.fixture
def md(tmp_path):
    return MarkdownStore(repo_root=tmp_path)


class TestMarkdownBackend:
    def test_identity_and_reachability(self, md):
        assert isinstance(md, StoreBackend)
        assert md.name == "md"
        assert md.federation == FEDERATION_NONE
        assert md.federated is False
        assert md.available() is True
        assert md.ping() is True
        assert md.init_db() is True
        assert md.describe() == {"backend": "md", "federation": "none", "federated": False}

    def test_record_then_consult(self, md, tmp_path):
        learning = Learning("knowledge", "knowledge", "MD Title", "body", proposed_fix="do X")
        path = md.record_learning(learning, "vm-a")
        assert path is not None
        assert (tmp_path / ".claude" / "learnings.md").exists()
        row = md.is_known(learning.fingerprint)
        assert row is not None
        assert row["fingerprint"] == learning.fingerprint
        assert row["friction_class"] == "knowledge"
        assert row["fix_scope"] == "knowledge"
        assert row["title"] == "MD Title"

    def test_unknown_reads_are_benign(self, md):
        assert md.is_known("deadbeef") is None
        assert md.list_learnings() == []
        assert md.sightings("deadbeef") == []

    def test_best_effort_dedup_no_fork(self, md, tmp_path):
        # Same (class, title) -> same fingerprint -> the second record is a no-op,
        # not a second block. That IS the "best-effort" dedup (no SQL index).
        md.record_learning(Learning("knowledge", "knowledge", "Dup", "first body"), "vm-a")
        md.record_learning(Learning("knowledge", "knowledge", "Dup", "totally other body"), "vm-a")
        text = (tmp_path / ".claude" / "learnings.md").read_text(encoding="utf-8")
        assert text.count("## Dup") == 1
        assert len(md.list_learnings()) == 1

    def test_accepts_non_portable_locally(self, md):
        # Unlike the federated pg store, the md ledger STORES non-portable notes -
        # that is precisely what .claude/learnings.md is for. No refusal.
        learning = Learning("permission", "permission", "allow npm here", "b")
        path = md.record_learning(learning, "vm-a")
        assert path is not None
        assert md.is_known(learning.fingerprint) is not None

    def test_reject_is_local_and_per_vm(self, md, tmp_path):
        learning = Learning("knowledge", "knowledge", "Rejectable", "b")
        md.record_learning(learning, "vm-a")
        assert md.rejected_here(learning.fingerprint, "vm-a") is False
        assert md.mark_rejected(learning.fingerprint, "vm-a", actor="me", note="no") is True
        assert md.rejected_here(learning.fingerprint, "vm-a") is True
        # per-VM: a different VM has NOT rejected it
        assert md.rejected_here(learning.fingerprint, "vm-b") is False
        sidecar = tmp_path / ".claude" / "learnings.rejected.jsonl"
        assert sidecar.exists()
        rec = json.loads(sidecar.read_text(encoding="utf-8").splitlines()[0])
        assert rec["action"] == "rejected"
        assert rec["source_vm"] == "vm-a"

    def test_reject_unknown_is_noop(self, md):
        assert md.mark_rejected("deadbeef", "vm-a") is False

    def test_apply_is_not_reject(self, md):
        learning = Learning("knowledge", "knowledge", "Appliable", "b")
        md.record_learning(learning, "vm-a")
        assert md.mark_applied(learning.fingerprint, "vm-a") is True
        assert md.rejected_here(learning.fingerprint, "vm-a") is False

    def test_sightings_known_reports_one_local(self, md):
        learning = Learning("knowledge", "knowledge", "Seen", "b")
        md.record_learning(learning, "vm-a")
        assert len(md.sightings(learning.fingerprint)) == 1

    def test_link_issue_is_best_effort_false(self, md):
        # md does not maintain an issue_url column (#463 bridge relies on pg).
        learning = Learning("knowledge", "knowledge", "Bridgeable", "b", proposed_fix="x")
        md.record_learning(learning, "vm-a")
        assert md.link_issue(learning.fingerprint, "https://github.com/o/r/issues/1") is False

    def test_list_filters_by_class_newest_first(self, md):
        md.record_learning(Learning("knowledge", "knowledge", "K1", "b"), "vm")
        md.record_learning(Learning("infra_trap", "knowledge", "I1", "b"), "vm")
        assert len(md.list_learnings()) == 2
        knowledge_rows = md.list_learnings("knowledge")
        assert len(knowledge_rows) == 1
        assert knowledge_rows[0]["title"] == "K1"


# --------------------------------------------------------------------------- #
# Postgres backend (tiers ii/iii) satisfies StoreBackend + keeps the share guard
# --------------------------------------------------------------------------- #
class TestPostgresBackendContract:
    def test_is_store_backend(self):
        assert isinstance(MemoryStore(dsn=""), StoreBackend)

    def test_defaults_to_remote_pg_fleet(self):
        s = MemoryStore(dsn="")
        assert s.name == "remote-pg"
        assert s.federation == FEDERATION_FLEET
        assert s.federated is True
        assert s.describe() == {"backend": "remote-pg", "federation": "fleet", "federated": True}

    def test_local_pg_label_is_unfederated(self):
        s = MemoryStore(dsn="postgres://127.0.0.1:5433/db", name="local-pg", federation=FEDERATION_NONE)
        assert s.name == "local-pg"
        assert s.federated is False

    def test_federated_store_refuses_non_portable_even_down(self):
        # Contrast with md.test_accepts_non_portable_locally: the federated store
        # refuses, from every path, even while unreachable.
        s = MemoryStore(dsn="", name="remote-pg", federation=FEDERATION_FLEET)
        with pytest.raises(ValueError):
            s.record_learning(Learning("permission", "permission", "allow npm", "b"), "vm-a")


# --------------------------------------------------------------------------- #
# CLI surfaces backend + federation (ping / record)
# --------------------------------------------------------------------------- #
class TestCliBackendSurface:
    def test_ping_reports_md_backend(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(cli_mod, "select_backend", lambda *a, **k: MarkdownStore(repo_root=tmp_path))
        rc = cli_mod.main(["ping"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["backend"] == "md"
        assert out["federation"] == "none"
        assert out["reachable"] is True

    def test_record_md_is_first_class_not_fallback(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(cli_mod, "select_backend", lambda *a, **k: MarkdownStore(repo_root=tmp_path))
        rc = cli_mod.main([
            "record", "--class", "knowledge", "--scope", "knowledge",
            "--title", "Via CLI", "--body", "b", "--repo", str(tmp_path),
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["backend"] == "md"
        assert out["federation"] == "none"
        assert out["stored"] == "md"  # NOT "local-fallback" - md is the store
        assert (tmp_path / ".claude" / "learnings.md").exists()

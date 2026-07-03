"""Fail-open client onto the common-memory Postgres store.

Every method swallows connection/query errors and returns a benign value
(None / False / []) so a store outage never breaks a flow run. Callers fall
back to :func:`append_local_learning` when :meth:`record_learning` returns None.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import resolve_dsn
from .models import Learning

log = logging.getLogger("cpp_memory")

try:
    import psycopg
    _HAVE_PSYCOPG = True
except Exception:  # pragma: no cover - driver is an optional runtime dep
    psycopg = None
    _HAVE_PSYCOPG = False

_LEARNING_COLS = (
    "id", "fingerprint", "friction_class", "fix_scope",
    "title", "status", "confidence",
)


class MemoryStore:
    def __init__(self, dsn: str | None = None, connect_timeout: int = 3):
        self.dsn = dsn if dsn is not None else resolve_dsn()
        self.connect_timeout = connect_timeout

    def available(self) -> bool:
        return bool(self.dsn) and _HAVE_PSYCOPG

    @contextmanager
    def _conn(self):
        conn = psycopg.connect(self.dsn, connect_timeout=self.connect_timeout)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ping(self) -> bool:
        if not self.available():
            return False
        try:
            with self._conn() as c:
                c.execute("SELECT 1")
            return True
        except Exception as e:  # noqa: BLE001 - fail-open
            log.warning("cpp_memory ping failed: %s", e)
            return False

    def is_known(self, fingerprint: str) -> dict | None:
        if not self.available():
            return None
        try:
            with self._conn() as c:
                row = c.execute(
                    "SELECT id, fingerprint, friction_class, fix_scope, title,"
                    " status, confidence FROM learnings WHERE fingerprint = %s",
                    (fingerprint,),
                ).fetchone()
        except Exception as e:  # noqa: BLE001
            log.warning("cpp_memory is_known failed: %s", e)
            return None
        return dict(zip(_LEARNING_COLS, row)) if row else None

    def rejected_here(self, fingerprint: str, source_vm: str) -> bool:
        """True if this VM already rejected this learning (do not re-propose)."""
        if not self.available():
            return False
        try:
            with self._conn() as c:
                row = c.execute(
                    "SELECT 1 FROM applications a"
                    " JOIN learnings l ON l.id = a.learning_id"
                    " WHERE l.fingerprint = %s AND a.source_vm = %s"
                    " AND a.action = 'rejected'",
                    (fingerprint, source_vm),
                ).fetchone()
            return bool(row)
        except Exception as e:  # noqa: BLE001
            log.warning("cpp_memory rejected_here failed: %s", e)
            return False

    def record_learning(
        self, learning: Learning, source_vm: str, source_repo: str | None = None
    ) -> int | None:
        """Upsert a portable learning + add a sighting. Returns id or None.

        Refuses non-portable learnings: permission / repo_file fixes must never
        enter the shared store (they stay per-machine / in git).
        """
        learning.validate()
        if not learning.portable:
            raise ValueError(
                "non-portable learning refused from shared store: "
                f"class={learning.friction_class} scope={learning.fix_scope}"
            )
        if not self.available():
            return None
        try:
            with self._conn() as c:
                lid = c.execute(
                    "INSERT INTO learnings (fingerprint, friction_class, fix_scope,"
                    " title, body, proposed_fix, confidence, evidence)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
                    " ON CONFLICT (fingerprint) DO UPDATE SET"
                    "   updated_at = now(),"
                    "   confidence = GREATEST(learnings.confidence, EXCLUDED.confidence)"
                    " RETURNING id",
                    (
                        learning.fingerprint, learning.friction_class,
                        learning.fix_scope, learning.title, learning.body,
                        learning.proposed_fix, learning.confidence,
                        json.dumps(learning.evidence),
                    ),
                ).fetchone()[0]
                c.execute(
                    "INSERT INTO sightings (learning_id, source_vm, source_repo)"
                    " VALUES (%s,%s,%s)",
                    (lid, source_vm, source_repo),
                )
            return lid
        except Exception as e:  # noqa: BLE001
            log.warning("cpp_memory record_learning failed: %s", e)
            return None

    def _decide(self, fingerprint, source_vm, action, actor=None, note=None) -> bool:
        if not self.available():
            return False
        try:
            with self._conn() as c:
                row = c.execute(
                    "SELECT id FROM learnings WHERE fingerprint = %s", (fingerprint,)
                ).fetchone()
                if not row:
                    return False
                lid = row[0]
                c.execute(
                    "INSERT INTO applications (learning_id, source_vm, action, actor, note)"
                    " VALUES (%s,%s,%s,%s,%s)"
                    " ON CONFLICT (learning_id, source_vm) DO UPDATE SET"
                    "   action = EXCLUDED.action, actor = EXCLUDED.actor,"
                    "   note = EXCLUDED.note, decided_at = now()",
                    (lid, source_vm, action, actor, note),
                )
                if action == "applied":
                    c.execute(
                        "UPDATE learnings SET status='applied', updated_at=now()"
                        " WHERE id = %s", (lid,)
                    )
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("cpp_memory _decide failed: %s", e)
            return False

    def mark_applied(self, fingerprint, source_vm, actor=None, note=None) -> bool:
        return self._decide(fingerprint, source_vm, "applied", actor, note)

    def mark_rejected(self, fingerprint, source_vm, actor=None, note=None) -> bool:
        return self._decide(fingerprint, source_vm, "rejected", actor, note)

    def list_learnings(self, friction_class: str | None = None, limit: int = 50) -> list[dict]:
        if not self.available():
            return []
        cols = _LEARNING_COLS + ("created_at",)
        try:
            with self._conn() as c:
                if friction_class:
                    rows = c.execute(
                        "SELECT id,fingerprint,friction_class,fix_scope,title,status,"
                        "confidence,created_at FROM learnings WHERE friction_class = %s"
                        " ORDER BY created_at DESC LIMIT %s",
                        (friction_class, limit),
                    ).fetchall()
                else:
                    rows = c.execute(
                        "SELECT id,fingerprint,friction_class,fix_scope,title,status,"
                        "confidence,created_at FROM learnings"
                        " ORDER BY created_at DESC LIMIT %s",
                        (limit,),
                    ).fetchall()
            return [dict(zip(cols, r)) for r in rows]
        except Exception as e:  # noqa: BLE001
            log.warning("cpp_memory list_learnings failed: %s", e)
            return []

    def init_db(self, schema_path: str | None = None) -> bool:
        """Apply the schema (idempotent)."""
        if not self.available():
            return False
        if schema_path is None:
            schema_path = str(Path(__file__).parent / "sql" / "schema.sql")
        try:
            sql = Path(schema_path).read_text(encoding="utf-8")
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            with self._conn() as c:
                for st in statements:
                    c.execute(st)
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("cpp_memory init_db failed: %s", e)
            return False


def append_local_learning(learning: Learning, repo_root: str | Path = ".") -> Path:
    """Fail-open fallback: append a learning to ``.claude/learnings.md``.

    Used when the shared store is unreachable OR when the learning is
    non-portable (permission / repo_file) and must stay on this machine.
    """
    path = Path(repo_root) / ".claude" / "learnings.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = (
        f"\n## {learning.title}\n"
        f"- when: {ts}\n"
        f"- class: {learning.friction_class} / scope: {learning.fix_scope}"
        f" / portable: {learning.portable}\n"
        f"- fingerprint: {learning.fingerprint}\n\n"
        f"{learning.body}\n"
    )
    if learning.proposed_fix:
        block += f"\n**Proposed fix:** {learning.proposed_fix}\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)
    return path

"""Tier-i markdown backend: promotes ``.claude/learnings.md`` to a real store.

This is the first-class local backend (issue #472), NOT the old fail-open
fallback. It subsumes the single ``.claude/learnings.md`` markdown ledger:

- **consult / dedup** - best-effort, by parsing the fingerprint stamped into each
  learning block (``- fingerprint: <sha256>``). No SQL fingerprint index, so a
  re-record of an already-present learning is a no-op rather than a fork; it is
  "best-effort local", not full-fidelity.
- **reject / apply** - recorded in a small sibling ``.claude/learnings.rejected.jsonl``
  sidecar keyed by ``(fingerprint, source_vm)`` so ``rejected_here`` works without
  a database. Local semantics: a rejection here is NOT seen by other VMs.
- **federation** - none. Everything is this-box-only; ``is_known`` /
  ``rejected_here`` never speak for the fleet. Pick tier iii (remote-pg) for that.

The markdown block format is exactly what :func:`~lib.cpp_memory.client.append_local_learning`
writes, so md-tier records stay human-readable and interoperate with the existing
learnings.md file byte-for-byte.
"""
from __future__ import annotations

import json
import logging
import re
import socket
from datetime import datetime, timezone
from pathlib import Path

from .backend import FEDERATION_NONE, StoreBackend
from .client import append_local_learning
from .models import Learning

log = logging.getLogger("cpp_memory")

# Parsers over the append_local_learning block format (see client.py).
_HEADER_RE = re.compile(r"^## (?P<title>.+)$", re.M)
_META_RE = re.compile(
    r"- class:\s*(?P<cls>\S+)\s*/\s*scope:\s*(?P<scope>\S+)\s*/\s*portable:\s*(?P<portable>\S+)"
)
_FP_RE = re.compile(r"- fingerprint:\s*(?P<fp>[0-9a-fA-F]+)")
_WHEN_RE = re.compile(r"- when:\s*(?P<when>\S+)")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _vm_local() -> str:
    return socket.gethostname()


def _parse_blocks(text: str) -> list[dict]:
    """Best-effort parse of learnings.md into per-learning dicts (file order)."""
    headers = list(_HEADER_RE.finditer(text))
    blocks: list[dict] = []
    for i, m in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        chunk = text[m.start():end]
        fp_m = _FP_RE.search(chunk)
        meta_m = _META_RE.search(chunk)
        when_m = _WHEN_RE.search(chunk)
        blocks.append({
            "title": m.group("title").strip(),
            "fingerprint": fp_m.group("fp") if fp_m else None,
            "friction_class": meta_m.group("cls") if meta_m else None,
            "fix_scope": meta_m.group("scope") if meta_m else None,
            "created_at": when_m.group("when") if when_m else None,
        })
    return blocks


class MarkdownStore(StoreBackend):
    """Tier-i local markdown backend (``federation="none"``)."""

    def __init__(self, repo_root: str | Path = ".", md_path=None, sidecar_path=None):
        self.name = "md"
        self.federation = FEDERATION_NONE
        self.repo_root = Path(repo_root)
        self._md_path = Path(md_path) if md_path else self.repo_root / ".claude" / "learnings.md"
        self._sidecar = (
            Path(sidecar_path) if sidecar_path
            else self.repo_root / ".claude" / "learnings.rejected.jsonl"
        )
        self.dsn = None  # symmetry with MemoryStore for CLI getattr()

    # --- reachability ------------------------------------------------------- #
    def available(self) -> bool:
        return True  # a local file ledger is always usable

    def ping(self) -> bool:
        try:
            self._md_path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as e:  # noqa: BLE001 - fail-open
            log.warning("cpp_memory md ping failed: %s", e)
            return False

    # --- consult / dedup ---------------------------------------------------- #
    def _read(self) -> str:
        if not self._md_path.is_file():
            return ""
        return self._md_path.read_text(encoding="utf-8")

    def _row(self, rec: dict) -> dict:
        """Shape a parsed block like a pg row (best-effort; unknown cols -> None)."""
        return {
            "id": None,
            "fingerprint": rec.get("fingerprint"),
            "friction_class": rec.get("friction_class"),
            "fix_scope": rec.get("fix_scope"),
            "title": rec.get("title"),
            "status": "proposed",
            "confidence": None,
            "issue_url": None,
        }

    def is_known(self, fingerprint: str) -> dict | None:
        try:
            for rec in _parse_blocks(self._read()):
                if rec.get("fingerprint") == fingerprint:
                    return self._row(rec)
        except Exception as e:  # noqa: BLE001 - fail-open
            log.warning("cpp_memory md is_known failed: %s", e)
        return None

    def list_learnings(self, friction_class: str | None = None, limit: int = 50) -> list[dict]:
        try:
            blocks = _parse_blocks(self._read())
        except Exception as e:  # noqa: BLE001
            log.warning("cpp_memory md list_learnings failed: %s", e)
            return []
        rows = [
            {**self._row(rec), "created_at": rec.get("created_at")}
            for rec in blocks
            if not friction_class or rec.get("friction_class") == friction_class
        ]
        rows.reverse()  # newest (appended last) first, matching pg ORDER BY DESC
        return rows[:limit]

    def sightings(self, fingerprint: str, limit: int = 100) -> list[dict]:
        # No cross-VM sighting ledger on tier i. A known learning is reported as a
        # single local sighting ("this one box hit it"); unknown -> [].
        if self.is_known(fingerprint):
            # harness=None: tier i does not persist per-sighting harness (#557);
            # the key is present for row-shape parity with the pg backend.
            return [{
                "id": None, "source_vm": _vm_local(), "source_repo": None,
                "harness": None, "seen_at": None,
            }]
        return []

    # --- record / decide ---------------------------------------------------- #
    def record_learning(
        self,
        learning: Learning,
        source_vm: str,
        source_repo: str | None = None,
        harness: str | None = None,
    ) -> str | None:
        """Append a learning to learnings.md (best-effort dedup). Returns the path.

        No share guard: this is the LOCAL ledger, so it accepts non-portable notes
        (permission / repo_file) - that is exactly what learnings.md is for. A
        federated backend (tier iii) is the one that refuses them.

        ``harness`` (issue #557) is accepted for signature parity with the pg
        backends but not persisted: tier i has no per-occurrence sighting ledger,
        so there is nowhere box-local to hang the tag. Cross-harness attribution
        is a fleet-store (remote-pg) property.
        """
        learning.validate()
        try:
            if self.is_known(learning.fingerprint):
                return str(self._md_path)  # already recorded - don't fork the block
            return str(append_local_learning(learning, self.repo_root))
        except Exception as e:  # noqa: BLE001 - fail-open
            log.warning("cpp_memory md record_learning failed: %s", e)
            return None

    def _decisions(self) -> list[dict]:
        try:
            if not self._sidecar.is_file():
                return []
            out: list[dict] = []
            for line in self._sidecar.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return out
        except Exception as e:  # noqa: BLE001
            log.warning("cpp_memory md _decisions failed: %s", e)
            return []

    def rejected_here(self, fingerprint: str, source_vm: str) -> bool:
        return any(
            d.get("fingerprint") == fingerprint
            and d.get("source_vm") == source_vm
            and d.get("action") == "rejected"
            for d in self._decisions()
        )

    def _decide(self, fingerprint, source_vm, action, actor=None, note=None) -> bool:
        # Mirror pg: a decision on an unknown learning is a no-op (False).
        if not self.is_known(fingerprint):
            return False
        rec = {
            "fingerprint": fingerprint, "source_vm": source_vm, "action": action,
            "actor": actor, "note": note, "decided_at": _now_iso(),
        }
        try:
            self._sidecar.parent.mkdir(parents=True, exist_ok=True)
            with self._sidecar.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            return True
        except OSError as e:  # noqa: BLE001 - fail-open
            log.warning("cpp_memory md _decide failed: %s", e)
            return False

    def mark_applied(self, fingerprint, source_vm, actor=None, note=None) -> bool:
        return self._decide(fingerprint, source_vm, "applied", actor, note)

    def mark_rejected(self, fingerprint, source_vm, actor=None, note=None) -> bool:
        return self._decide(fingerprint, source_vm, "rejected", actor, note)

    def link_issue(self, fingerprint: str, issue_url: str) -> bool:
        # Best-effort local ledger: md has no issue_url column, so it does not
        # participate in the #463 learnings->issue dedup. is_known reports
        # issue_url=None, so the retro re-proposes (human-confirmed) rather than
        # silently deduping. Use a pg tier for full bridge fidelity.
        return False

    # --- provisioning ------------------------------------------------------- #
    def init_db(self, schema_path: str | None = None) -> bool:
        try:
            self._md_path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as e:  # noqa: BLE001
            log.warning("cpp_memory md init_db failed: %s", e)
            return False

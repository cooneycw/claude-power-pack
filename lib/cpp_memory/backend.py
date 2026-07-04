"""Storage-backend interface for the CPP common-memory ledger (issue #472).

The ledger is pluggable across three tiers, selected at ``/cpp:init`` time:

  =====  ==========  ==========================  =========================
  Tier   Backend     Dedup fidelity              Federation
  =====  ==========  ==========================  =========================
  i      md          best-effort (grep/parse)    none  (local box only)
  ii     local-pg    full (SQL fingerprint)      none  (single box)
  iii    remote-pg   full (SQL fingerprint)      fleet (shared across VMs)
  =====  ==========  ==========================  =========================

**Federation** - whether a learning / rejection recorded here is visible to
*other* VMs - is an explicit, surfaced per-backend property (:attr:`federation`).
Only tier iii shares across the fleet; on tiers i and ii the ``is_known`` /
``rejected_here`` "global" semantic collapses to the local box. The
``/cpp:init`` selector shows this column so no one picks md / local-pg
expecting cross-VM sharing.

Framing (issue #472): this is "md = best-effort local, pg = full-fidelity", not
"the same feature three ways". The md backend deliberately offers weaker dedup
and no fleet federation; that is the trade for a zero-dependency local ledger.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Learning

# Federation labels (surfaced by every backend and by the /cpp:init selector).
FEDERATION_NONE = "none"     # local box only          - tiers i, ii
FEDERATION_FLEET = "fleet"   # shared across the fleet  - tier iii

# The three selectable backends (the /cpp:init mini-tier).
BACKENDS = ("md", "local-pg", "remote-pg")


class StoreBackend(ABC):
    """The consult / record / dedup / reject surface every backend implements.

    Contract shared by all backends:

    - **Fail-open.** A backend outage returns a benign value (None / False / [])
      and never raises, so a store problem never breaks a flow run. The ONE
      exception is the bucket-2 share guard (see below), which is intentionally
      not fail-open.
    - **Federation-scoped reads.** ``is_known`` / ``rejected_here`` answer within
      the backend's :attr:`federation` scope: on tiers i/ii they speak for THIS
      box only; on tier iii they speak for the whole fleet.
    - **Share guard (federated backends only).** A federated backend
      (``federation == FEDERATION_FLEET``) MUST refuse to ``record_learning`` a
      non-portable learning (a permission / repo_file fix) - those never enter a
      shared store. A local backend (tier i/ii) is the correct home for
      non-portable local notes and stores them without refusal.
    """

    #: short backend id, one of :data:`BACKENDS`: "md" | "local-pg" | "remote-pg"
    name: str = "backend"
    #: :data:`FEDERATION_NONE` or :data:`FEDERATION_FLEET` - shared across VMs?
    federation: str = FEDERATION_NONE

    @property
    def federated(self) -> bool:
        """True when a learning recorded here is visible to other VMs (tier iii)."""
        return self.federation == FEDERATION_FLEET

    def describe(self) -> dict:
        """Surfaced identity: backend id + federation scope (for ping / selector)."""
        return {"backend": self.name, "federation": self.federation, "federated": self.federated}

    # --- reachability ------------------------------------------------------- #
    @abstractmethod
    def available(self) -> bool:
        """Can this backend be used at all (config present, driver installed)?"""

    @abstractmethod
    def ping(self) -> bool:
        """Round-trip reachability check (benign False on any failure)."""

    # --- consult / dedup ---------------------------------------------------- #
    @abstractmethod
    def is_known(self, fingerprint: str) -> dict | None:
        """Return the learning row (dict) for a fingerprint, or None. Fail-open None."""

    @abstractmethod
    def rejected_here(self, fingerprint: str, source_vm: str) -> bool:
        """True if this VM already rejected this learning (do not re-propose)."""

    @abstractmethod
    def sightings(self, fingerprint: str, limit: int = 100) -> list[dict]:
        """The 'N machines/repos hit this' signal. Fail-open []."""

    @abstractmethod
    def list_learnings(self, friction_class: str | None = None, limit: int = 50) -> list[dict]:
        """Browse recorded learnings, newest first. Fail-open []."""

    # --- record / decide ---------------------------------------------------- #
    @abstractmethod
    def record_learning(
        self, learning: Learning, source_vm: str, source_repo: str | None = None
    ) -> int | str | None:
        """Record a learning. Returns a backend id/path, or None when unavailable.

        Federated backends refuse non-portable learnings (raise ValueError).
        """

    @abstractmethod
    def mark_applied(self, fingerprint: str, source_vm: str, actor=None, note=None) -> bool:
        """Record that this VM applied the learning. Fail-open False."""

    @abstractmethod
    def mark_rejected(self, fingerprint: str, source_vm: str, actor=None, note=None) -> bool:
        """Record that this VM rejected the learning (stops re-proposal). Fail-open False."""

    @abstractmethod
    def link_issue(self, fingerprint: str, issue_url: str) -> bool:
        """Record the GitHub issue a learning was promoted to (#463). Fail-open False."""

    # --- provisioning ------------------------------------------------------- #
    @abstractmethod
    def init_db(self, schema_path: str | None = None) -> bool:
        """Initialize backend storage (idempotent). Fail-open False."""

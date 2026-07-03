"""CPP common-memory: shared friction-knowledge ledger (bucket-2-plus).

A fail-open client onto a Postgres store that consolidates *portable* CPP
learnings and infra traps across the VM fleet, plus a dedup/rejection ledger
so no machine re-proposes an already-rejected fix.

Design invariants (see issue #433):
  - consult-not-push: VMs read the store at propose-time; a human confirms
    application per-machine. The store never distributes config or permissions.
  - fail-open: if the store is unreachable, callers degrade to a local
    ``.claude/learnings.md`` and never block a flow run.
  - bucket-2-plus only: portable knowledge / infra traps + the dedup ledger.
    Repo-file fixes belong in git; permission fixes stay per-machine.
"""

from .client import MemoryStore, append_local_learning
from .config import resolve_dsn
from .models import FIX_SCOPES, FRICTION_CLASSES, Learning, is_portable

__all__ = [
    "Learning",
    "FRICTION_CLASSES",
    "FIX_SCOPES",
    "is_portable",
    "MemoryStore",
    "append_local_learning",
    "resolve_dsn",
]

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

from .backend import (
    BACKENDS,
    FEDERATION_FLEET,
    FEDERATION_NONE,
    StoreBackend,
)
from .client import MemoryStore, append_local_learning
from .config import DEFAULT_LOCAL_PG_DSN, resolve_backend, resolve_dsn
from .markdown import MarkdownStore
from .models import (
    FIX_SCOPES,
    FRICTION_CLASSES,
    Learning,
    is_actionable,
    is_portable,
    issue_body,
    issue_marker,
    should_file_issue,
)
from .store import select_backend

__all__ = [
    "Learning",
    "FRICTION_CLASSES",
    "FIX_SCOPES",
    "is_portable",
    "is_actionable",
    "should_file_issue",
    "issue_body",
    "issue_marker",
    # storage backends (issue #472)
    "StoreBackend",
    "MemoryStore",
    "MarkdownStore",
    "select_backend",
    "BACKENDS",
    "FEDERATION_NONE",
    "FEDERATION_FLEET",
    "append_local_learning",
    "resolve_dsn",
    "resolve_backend",
    "DEFAULT_LOCAL_PG_DSN",
]

"""Backend factory: resolve the configured common-memory backend (issue #472).

``select_backend()`` is the single entry point every consumer (the CLI, the
retro/memory routines) uses instead of constructing a store directly, so the
``md | local-pg | remote-pg`` choice lives in exactly one place.
"""
from __future__ import annotations

import os

from .backend import FEDERATION_FLEET, FEDERATION_NONE, StoreBackend
from .client import MemoryStore
from .config import DEFAULT_LOCAL_PG_DSN, resolve_backend, resolve_dsn
from .markdown import MarkdownStore


def select_backend(
    *, backend: str | None = None, dsn: str | None = None, repo_root: str = "."
) -> StoreBackend:
    """Return the configured store backend.

    Selection order:
      1. explicit ``backend`` argument (``md`` | ``local-pg`` | ``remote-pg``)
      2. :func:`~lib.cpp_memory.config.resolve_backend` (``CPP_MEMORIES_BACKEND``
         env / local backend file)
      3. inferred - a resolvable DSN implies **remote-pg** (today's default, so
         existing fleet VMs are unchanged); no DSN implies the local **md** ledger.

    Never raises: an unavailable pg store still returns a (fail-open) backend.
    """
    chosen = (backend or resolve_backend() or "").strip().lower()
    if not chosen:
        chosen = "remote-pg" if (dsn if dsn is not None else resolve_dsn()) else "md"

    if chosen == "md":
        return MarkdownStore(repo_root=repo_root)

    if chosen == "local-pg":
        # Stay local: honor an explicit DSN / CPP_MEMORIES_DSN, else the docker
        # default; never reach to AWS (that is the fleet remote-pg tier).
        local_dsn = (
            dsn if dsn is not None
            else (os.environ.get("CPP_MEMORIES_DSN", "").strip() or DEFAULT_LOCAL_PG_DSN)
        )
        return MemoryStore(dsn=local_dsn, name="local-pg", federation=FEDERATION_NONE)

    # remote-pg (default / fleet) - full tiered DSN resolution incl. AWS.
    remote_dsn = dsn if dsn is not None else resolve_dsn()
    return MemoryStore(dsn=remote_dsn, name="remote-pg", federation=FEDERATION_FLEET)

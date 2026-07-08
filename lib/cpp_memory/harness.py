"""Which agent harness produced a friction signal (issue #557).

The shared common-memory ledger is written by more than one harness: Claude Code
(via ``/self-improvement:retro`` / ``/self-improvement:memory``) and, from the
companion codex-power-pack epic (cooneycw/codex-power-pack#67), Codex. Every
*sighting* (friction occurrence) carries a ``harness`` tag alongside its
``source_vm`` / ``source_repo`` provenance so consumers can attribute and filter
the two apart ("how much friction did Codex hit vs Claude?").

Resolution is deliberately explicit-first so the codex-power-pack writer has a
stable, unambiguous target (pass ``--harness codex`` or set ``CPP_HARNESS=codex``)
and never depends on us guessing its environment. See
``docs/contracts/friction-ledger-shared-store.md`` for the write contract.
"""
from __future__ import annotations

import os

CLAUDE = "claude"
CODEX = "codex"
SHELL = "shell"

#: The canonical harness tags. Free convention, NOT a DB CHECK constraint - an
#: unknown value is still recorded (forward-compat), just not normalized here.
KNOWN_HARNESSES = frozenset({CLAUDE, CODEX, SHELL})

#: Env var a harness sets to declare itself (the codex-power-pack writer's hook).
HARNESS_ENV = "CPP_HARNESS"


def normalize(value: str | None) -> str | None:
    """Lower/strip a harness label, or None when empty. Unknown values pass through.

    We do not reject an unrecognized harness: the ledger already serves "plain
    shell" and must stay open to a future harness. Normalization only folds case
    and whitespace so ``"Codex "`` and ``"codex"`` attribute to the same bucket.
    """
    if not value:
        return None
    v = value.strip().lower()
    return v or None


def resolve_harness(explicit: str | None = None) -> str | None:
    """Resolve the calling harness, or None when it cannot be determined.

    Order (first hit wins):
      1. ``explicit`` - a ``--harness`` CLI flag / caller argument.
      2. ``CPP_HARNESS`` env var - how a non-Claude harness declares itself.
      3. Auto-detect Claude Code (``CLAUDECODE`` env, set by the CLI) -> ``claude``.
      4. None - unresolved; the sighting's harness column stays NULL (backward
         compatible, exactly like a pre-#557 row).

    Never raises; a missing/blank value simply falls through to the next tier.
    """
    picked = normalize(explicit)
    if picked:
        return picked

    picked = normalize(os.environ.get(HARNESS_ENV))
    if picked:
        return picked

    # Claude Code exports CLAUDECODE=1; that is the CPP-side default attribution.
    if normalize(os.environ.get("CLAUDECODE")):
        return CLAUDE

    return None

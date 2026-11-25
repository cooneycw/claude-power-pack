"""Public adapter/core callback boundary, frozen before store implementation.

This interface-only checkpoint is not a usable installer. The entry functions
refuse until the next implementation commit supplies their internals. This
lets independent adapters target one concrete typed API without forking IO.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .models import (
    AdapterResult,
    Discovery,
    ExpectedBuild,
    Policy,
    Request,
    Revision,
    RunReport,
)


class Adapter(Protocol):
    """Trusted adapter callbacks; preflight precedes all installed-root IO.

    preflight may reject a request with AdapterError before any root walk,
    path-resolution descent, lock creation or staging. discover may inspect
    only approved locations. build reads only its approved immutable source
    snapshot and returns the real expected package bytes. Production discovery
    and credential probes are not supplied by the neutral core.
    """

    harness: str

    def preflight(self, request: Request) -> Policy: ...

    def discover(self, policy: Policy, request: Request) -> Discovery: ...

    def build(self, revision: Revision, policy: Policy) -> ExpectedBuild: ...


def inspect(adapter: Adapter, request: Request) -> AdapterResult:
    """Inspect under existing-only LOCK_SH; no creation or reconciliation."""
    raise NotImplementedError("Interface checkpoint: core implementation pending")


def refresh(adapter: Adapter, request: Request) -> AdapterResult:
    """Re-inspect under bounded LOCK_EX, publish and verify permitted output."""
    raise NotImplementedError("Interface checkpoint: core implementation pending")


def run(
    adapters: Sequence[Adapter], request: Request, *, verify_only: bool = False,
) -> RunReport:
    """Run all adapters at one revision, retaining every outcome and failure."""
    raise NotImplementedError("Interface checkpoint: core implementation pending")

"""Adapter preflight, revision binding, fault isolation and report aggregation."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol

from .models import (
    Action,
    AdapterError,
    AdapterResult,
    Discovery,
    ExpectedBuild,
    Inspection,
    Policy,
    Request,
    Revision,
    RunReport,
    State,
)
from .scope import Scope, absolute
from .store import inspect_locked, locked, publish, snapshot, validate_build


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
    return _operate(adapter, request, verify_only=True)


def refresh(adapter: Adapter, request: Request) -> AdapterResult:
    """Re-inspect under bounded LOCK_EX, publish and verify permitted output."""
    return _operate(adapter, request, verify_only=False)


def run(
    adapters: Sequence[Adapter], request: Request, *, verify_only: bool = False,
) -> RunReport:
    """Run all adapters at one revision, retaining every outcome and failure."""
    names = [adapter.harness for adapter in adapters]
    if len(set(names)) != len(names):
        rows = tuple(_error_result(name, request, AdapterError("duplicate adapter identity")) for name in names)
    else:
        rows = tuple(_operate(adapter, request, verify_only=verify_only) for adapter in adapters)
    codes = {row.exit_code for row in rows}
    code = 1 if 1 in codes else 4 if 4 in codes else 0 if 0 in codes else 5
    return RunReport(request.revision.commit, rows, code)


def _validate_revision(scope: Scope, revision: Revision) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", revision.commit):
        raise AdapterError("full source revision unavailable", exit_code=4)
    absolute(revision.snapshot_root)
    # No symlink aliases before Git is allowed to read this approved source.
    with scope.directory(revision.snapshot_root):
        pass
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    prefix = ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
              "-C", str(revision.snapshot_root)]
    head = subprocess.run([*prefix, "rev-parse", "HEAD"], capture_output=True, text=True, env=env, timeout=10)
    clean = subprocess.run([*prefix, "status", "--porcelain", "--untracked-files=normal"],
                           capture_output=True, text=True, env=env, timeout=10)
    if head.returncode or clean.returncode or head.stdout.strip() != revision.commit or clean.stdout:
        raise AdapterError("source snapshot is dirty, unavailable or bound to another revision", exit_code=4)


def _error_result(name: str, request: Request, error: AdapterError) -> AdapterResult:
    code = error.exit_code if error.exit_code in (1, 4, 5) else 4
    state = error.state
    if code == 5:
        state = State.NOT_APPLICABLE
    reason = str(error)
    value = Inspection(state, reason=reason)
    return AdapterResult(name, request.revision.commit, request.selected is not False, (), value,
                         Action.REFUSED if code == 1 else Action.NOT_ATTEMPTED, value, code, reason, error.remedy)


def _operate(adapter: Adapter, request: Request, *, verify_only: bool) -> AdapterResult:
    discovery: Discovery | None = None
    before: Inspection | None = None
    writing = False
    phase = "preflight"
    try:
        # No generic filesystem IO, including source Git, occurs before this.
        policy = adapter.preflight(request)
        scope = Scope(policy, owner=adapter.harness)
        discovery = adapter.discover(policy, request)
        selected = discovery.selected if request.selected is None else request.selected
        discovery = replace(discovery, selected=selected)
        if discovery.unknown:
            raise AdapterError(discovery.reason or "discovery is unexaminable", exit_code=4)
        if not selected:
            value = Inspection(State.NOT_APPLICABLE, reason="no managed installation selected")
            return AdapterResult(adapter.harness, request.revision.commit, False, discovery.evidence,
                                 value, Action.NOT_ATTEMPTED, value, 5, value.reason)
        _validate_revision(scope, request.revision)
        build = adapter.build(request.revision, policy)
        validate_build(scope, build, request)
        _validate_revision(scope, request.revision)
        if verify_only:
            before = inspect_locked(scope, build, request).inspection
            code = 0 if before.state == State.CURRENT else 1
            return AdapterResult(adapter.harness, build.revision, True, discovery.evidence,
                                 before, Action.UNCHANGED, before, code, before.reason)
        phase = "lock"
        with locked(scope, request, write=True):
            phase = "inspection"
            previous = snapshot(scope, build)
            before = previous.inspection
            if before.state == State.CURRENT:
                return AdapterResult(adapter.harness, build.revision, True, discovery.evidence,
                                     before, Action.UNCHANGED, before, 0)
            # publish rejects all adoption/collision issues before transaction IO.
            writing = True
            after, metadata_only, recovery = publish(scope, build, previous, request)
            return AdapterResult(adapter.harness, build.revision, True, discovery.evidence,
                                 before, Action.REFRESHED, after, 0, remedy=recovery,
                                 metadata_refreshed=metadata_only)
    except Exception as exc:
        if isinstance(exc, AdapterError):
            error = exc
        elif isinstance(exc, OSError):
            error = AdapterError(f"filesystem unavailable ({type(exc).__name__})",
                                 exit_code=1 if phase == "lock" and not verify_only else 4)
        else:
            error = AdapterError(f"adapter/core failed ({type(exc).__name__})", exit_code=4)
        result = _error_result(adapter.harness, request, error)
        if discovery is not None:
            result = replace(result, selected=discovery.selected, selection_evidence=discovery.evidence)
        if before is not None:
            result = replace(result, before=before)
            # Refusals occur before mutation; failed publication is incomplete.
            if error.exit_code == 1:
                result = replace(result, after=before, action=Action.REFUSED)
        if writing and error.exit_code != 1:
            result = replace(result, action=Action.FAILED, exit_code=1,
                             after=Inspection(State.UNKNOWN, reason="refresh incomplete; inspect retained transaction"))
        return result

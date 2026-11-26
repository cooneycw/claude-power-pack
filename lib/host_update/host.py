"""Production component registry; the neutral core and pi API are unchanged."""
from __future__ import annotations

import json
import os
import stat
from contextlib import ExitStack
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .driver import _error_result, _validate_revision, inspect, refresh
from .links import ClaudeLinks
from .models import (
    Action,
    AdapterError,
    AdapterResult,
    Discovery,
    ExpectedBuild,
    Inspection,
    OwnedMember,
    Policy,
    Request,
    Revision,
    State,
)
from .scope import Scope, absolute, slug
from .store import _directories, _document, locked, read_ledger, validate_build

INCLUDED = ("claude-topics", "codex", "antigravity", "claude-links")
BACKENDS = {n: "links" if n == "claude-links" else "copies" for n in INCLUDED}
DEFERRED = ("pi shared-updater enrollment", "qwen", "gemma/opencode",
            "command-derived AGY cpp-update invocation")


class BootstrapFailure(AdapterError):
    """Legacy metadata publication was attempted; inspect remaining state."""


@dataclass(frozen=True)
class HostReport:
    revision: str
    results: tuple[AdapterResult, ...]
    exit_code: int
    coverage: str = "partial"
    included: tuple[str, ...] = INCLUDED
    unimplemented: tuple[str, ...] = DEFERRED
    backend: str = "mixed"
    schema: int = 2


def document(report: HostReport) -> dict:
    """One production serializer; fixture/Pi AdapterResult stays unchanged."""
    payload = asdict(report)
    payload["results"] = [dict(row, backend=BACKENDS[row["harness"]]) for row in payload["results"]]
    return payload


class CopyAdapter:
    """Explicit home-relative root, bounded discovery and legacy migration."""
    harness = ""
    prefix: tuple[str, ...] = ()

    def __init__(self, home: Path, *, selected: bool | None = None, deferred: tuple[str, ...] = ()):
        self.home = absolute(home)
        self.selected = selected
        self.deferred = deferred
        self._build: ExpectedBuild | None = None

    def preflight(self, request: Request) -> Policy:
        root = self.home.joinpath(*self.prefix, "skills")
        if (root.is_relative_to(request.revision.snapshot_root)
                or request.revision.snapshot_root.is_relative_to(root)):
            raise AdapterError("install and canonical source scopes overlap", state=State.UNMANAGED)
        anchor = self.anchor()
        # No .claude/.codex/.gemini contents are listed: only approved prefixes
        # are opened, and every component beneath the home anchor is no-follow.
        for location in (root, root.parent / ".cpp-skill-install.lock"):
            try:
                with anchor.directory(location if location == root else location.parent):
                    pass
            except FileNotFoundError:
                pass
        for item in self.deferred:
            path = Path(item.replace("~/", str(self.home) + "/", 1))
            if any(path == loc or loc.is_relative_to(path) or path.is_relative_to(loc)
                   for loc in (root, root.parent / ".cpp-skill-install.lock")):
                raise AdapterError("surface deferred to its declared manager", state=State.UNMANAGED,
                                   remedy="refresh through the declared surface owner")
        return Policy(root, root / ".cpp-managed/ownership.json", root.parent / ".cpp-skill-install.lock",
                      root / ".cpp-managed/work", partial_refresh=True)

    def anchor(self) -> Scope:
        return Scope(Policy(self.home, self.home / ".unused-ledger", self.home / ".unused-lock",
                            self.home / ".unused-work"))

    def legacy_source(self, name: str, content: bytes) -> bool:
        raise NotImplementedError

    def legacy(self, scope: Scope, exclude: set[str] | None = None) -> set[str]:
        try:
            with scope.directory(scope.root) as fd:
                names = os.listdir(fd)
        except FileNotFoundError:
            return set()
        result = set()
        for name in names:
            if name.startswith(".") or name in (exclude or set()):
                continue
            try:
                slug(name)
            except AdapterError:
                continue  # foreign names cannot be CPP package identifiers
            info = scope.stat(scope.package(name))
            if info is None or not stat.S_ISDIR(info.st_mode):
                continue
            skill = scope.package(name) / "SKILL.md"
            if scope.stat(skill) is not None and self.legacy_source(name, scope.read(skill)):
                result.add(name)
        return result

    def discover(self, policy: Policy, request: Request) -> Discovery:
        scope = Scope(policy, owner=self.harness)
        records = read_ledger(scope)
        legacy = self.legacy(scope, set(records))
        managed = bool(records or legacy)
        legacy -= set(request.adopt_paths)
        chosen = managed if self.selected is None else self.selected
        return Discovery(chosen, managed, ("explicit selection" if self.selected else
                                          "validated ownership/CPP source marker",),
                         unknown=bool(chosen and legacy),
                         reason=("legacy installation lacks verified prior manifest; "
                                 "refresh exact current bytes or adopt reviewed paths"))

    def build(self, revision: Revision, policy: Policy) -> ExpectedBuild:
        raise NotImplementedError

    def bootstrap(self, request: Request) -> bool:
        """Initialize ONLY exact fresh legacy records, under the existing lock.

        Never write package bytes, invent a prior hash for stale output, or
        replace another ownership namespace. Core re-inspects after release.
        """
        policy = self.preflight(request)
        scope = Scope(policy, owner=self.harness)
        if scope.stat(policy.work_root / "pending.json") is not None:
            raise AdapterError("incomplete transaction retained; inspect recovery work", exit_code=4)
        records = read_ledger(scope)
        names = self.legacy(scope, set(records)) - set(request.adopt_paths)
        if not names:
            return False
        _validate_revision(scope, request.revision)
        built = self.build(request.revision, policy)
        validate_build(scope, built, request)
        expected = {p.name: p for p in built.packages}
        with ExitStack() as stack:
            try:
                stack.enter_context(locked(scope, request, write=True))
            except OSError as error:
                raise AdapterError("legacy write lock unavailable", exit_code=1) from error
            _validate_revision(scope, request.revision)
            if scope.stat(policy.work_root / "pending.json") is not None:
                raise AdapterError("incomplete transaction retained; inspect recovery work", exit_code=4)
            records = read_ledger(scope)
            names = self.legacy(scope, set(records)) - set(request.adopt_paths)
            document = _document(scope)
            additions = {}
            for name in names:
                if name not in expected or any(name in rows for owner, rows in document["adapters"].items()
                                                if owner != self.harness):
                    raise AdapterError("legacy ownership requires explicit migration", exit_code=4)
                package = expected[name]
                actual, directories = scope.inventory(scope.package(name), set(package.members))
                wanted = {p: OwnedMember(m.sha256, m.mode) for p, m in package.members.items()}
                if actual != wanted or directories != _directories(wanted):
                    raise AdapterError("stale legacy bytes have no verified prior manifest", exit_code=4,
                                       remedy="review explicit adoption with a recoverable backup")
                additions[name] = {"source": package.canonical_source, "revision": built.revision,
                                   "members": {p: {"sha256": m.sha256, "mode": m.mode}
                                               for p, m in package.members.items()}}
            own = document["adapters"].setdefault(self.harness, {})
            own.update(additions)
            if additions:
                try:
                    scope.mkdir(policy.ledger_path.parent)
                    scope.write(policy.ledger_path, (json.dumps(document, sort_keys=True, indent=2) + "\n").encode())
                    read_ledger(scope)
                except Exception as error:
                    raise BootstrapFailure("legacy record publication incomplete; inspect installed state",
                                           exit_code=1) from error
            return bool(additions)


def registry(home: Path, selected: tuple[str, ...] = (), deferred: tuple[str, ...] = (),
             *, source: Path | None = None) -> list[CopyAdapter | ClaudeLinks]:
    from .antigravity import AntigravityAdapter
    from .claude import ClaudeAdapter
    from .codex import CodexAdapter

    adapters: list[CopyAdapter | ClaudeLinks] = [
        cls(home, selected=True if cls.harness in selected else None, deferred=deferred)
        for cls in (ClaudeAdapter, CodexAdapter, AntigravityAdapter)]
    adapters.append(ClaudeLinks(home, source=source, selected=True if "claude-links" in selected else None,
                                deferred=deferred))
    return adapters


def run_host(adapters: list[CopyAdapter | ClaudeLinks], request: Request, *, verify_only: bool = False) -> HostReport:
    rows = []
    for adapter in adapters:
        if isinstance(adapter, ClaudeLinks):
            rows.append(adapter.operate(request, verify_only=verify_only))
            continue
        local = replace(request, adopt_paths=tuple(p.split(":", 1)[1] for p in request.adopt_paths
                                                  if p.startswith(adapter.harness + ":")))
        try:
            policy = adapter.preflight(local)
            discovery = adapter.discover(policy, local)
            bootstrapped = False
            if discovery.selected and not verify_only:
                try:
                    adapter.anchor().mkdir(policy.install_root.parent)
                except OSError as error:
                    raise AdapterError("selected install parent is unwritable", exit_code=1) from error
                bootstrapped = adapter.bootstrap(local)
            row = (inspect if verify_only else refresh)(adapter, local)
            if bootstrapped:
                row = replace(row, metadata_refreshed=True)
            if bootstrapped and row.exit_code == 0:
                note = ("legacy record initialized after exact fidelity check; package bytes unchanged"
                        if row.action == Action.UNCHANGED else "legacy record initialized before managed refresh")
                row = replace(row, metadata_refreshed=True, action=Action.REFRESHED,
                              before=Inspection(State.UNKNOWN, reason="legacy ownership record was absent"),
                              reason=note)
            rows.append(row)
        except Exception as error:
            failure = error if isinstance(error, AdapterError) else AdapterError(
                f"adapter unavailable ({type(error).__name__})", exit_code=4)
            row = _error_result(adapter.harness, request, failure)
            if isinstance(error, BootstrapFailure):
                observed = inspect(adapter, local)
                row = replace(row, action=Action.FAILED, after=observed.after,
                              selected=observed.selected, selection_evidence=observed.selection_evidence,
                              metadata_refreshed=observed.after.state == State.CURRENT)
            rows.append(row)
    codes = {r.exit_code for r in rows}
    return HostReport(request.revision.commit, tuple(rows),
                      1 if 1 in codes else 4 if 4 in codes else 0 if 0 in codes else 5)


def source_failure(reason: str, adapters: list[CopyAdapter | ClaudeLinks] | None = None,
                   request: Request | None = None, *, attempted: bool = False) -> HostReport:
    request = request or Request(Revision("", Path("/source-unavailable")))
    if adapters is None:
        return HostReport(request.revision.commit,
                          tuple(_error_result(n, request, AdapterError(reason, exit_code=4)) for n in INCLUDED), 4)
    rows = []
    for adapter in adapters:
        try:
            discovery = adapter.discover(adapter.preflight(request), request)
            if discovery.selected:
                row = _error_result(adapter.harness, request, AdapterError(reason, exit_code=1 if attempted else 4))
                if attempted:
                    row = replace(row, action=Action.FAILED)
            else:
                row = _error_result(adapter.harness, request, AdapterError("no managed installation selected",
                                                                                        exit_code=5))
            rows.append(replace(row, selected=discovery.selected, selection_evidence=discovery.evidence))
        except Exception as error:
            failure = error if isinstance(error, AdapterError) else AdapterError("discovery unavailable", exit_code=4)
            rows.append(_error_result(adapter.harness, request, failure))
    codes = {r.exit_code for r in rows}
    return HostReport(request.revision.commit, tuple(rows), 1 if 1 in codes else 4 if 4 in codes else 5)

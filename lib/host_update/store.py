"""Ownership inspection and cooperating-writer transactions for selected roots."""

from __future__ import annotations

import errno
import fcntl
import json
import math
import os
import re
import stat
import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from .models import (
    AdapterError,
    Conflict,
    ExpectedBuild,
    Inspection,
    OwnedMember,
    OwnershipRecord,
    Request,
    State,
    build_manifest_sha256,
)
from .scope import Scope, parts, slug

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_ORDER = {State.UNKNOWN: 0, State.UNMANAGED: 1, State.HAND_EDITED: 2,
          State.ABSENT: 3, State.STALE: 4, State.CURRENT: 5}


def _unknown(reason: str) -> AdapterError:
    return AdapterError(reason, exit_code=4, state=State.UNKNOWN)


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in items:
        if name in result:
            raise ValueError("duplicate ownership key")
        result[name] = value
    return result


def _document(scope: Scope) -> dict[str, Any]:
    location = scope.policy.ledger_path
    if scope.stat(location) is None:
        return {"schema": 1, "producer": "claude-power-pack", "adapters": {}}
    try:
        value = json.loads(scope.read(location), object_pairs_hook=_unique)
        if type(value.get("schema")) is not int or value["schema"] != 1 or value.get("producer") != "claude-power-pack":
            raise ValueError("unsupported ownership producer/schema")
        if not isinstance(value["adapters"], dict):
            raise ValueError("adapters is not an object")
        return value
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _unknown(f"ownership unreadable/incomplete: {exc}") from exc


def read_ledger(scope: Scope) -> dict[str, OwnershipRecord]:
    try:
        rows = _document(scope)["adapters"].get(scope.owner, {})
        if not isinstance(rows, dict):
            raise ValueError("packages is not an object")
        records: dict[str, OwnershipRecord] = {}
        for name, row in rows.items():
            scope.package(slug(name))
            if not isinstance(row["source"], str) or not row["source"] or not _COMMIT.fullmatch(row["revision"]):
                raise ValueError("incomplete source/revision")
            members = row["members"]
            if not isinstance(members, dict) or not members:
                raise ValueError("empty ownership member population")
            parsed: dict[str, OwnedMember] = {}
            for path, member in members.items():
                parts(path)
                digest, mode = member["sha256"], member["mode"]
                if not isinstance(digest, str) or not _SHA.fullmatch(digest):
                    raise ValueError("invalid member hash")
                if type(mode) is not int or not scope.policy.member_allowed(path, mode):
                    raise ValueError("unsupported recorded member mode/type")
                parsed[path] = OwnedMember(digest, mode)
            records[name] = OwnershipRecord(name, row["source"], row["revision"], parsed)
        return records
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _unknown(f"ownership unreadable/incomplete: {exc}") from exc


def validate_build(scope: Scope, build: ExpectedBuild, request: Request) -> None:
    if build.revision != request.revision.commit or not _COMMIT.fullmatch(build.revision):
        raise _unknown("build is not bound to the requested full revision")
    if not build.packages:
        raise _unknown("expected package population is zero")
    if build.manifest_sha256 != build_manifest_sha256(build.revision, build.packages):
        raise _unknown("expected manifest digest does not match its actual members")
    names: set[str] = set()
    for package in build.packages:
        scope.package(package.name)
        if package.name in names or not package.canonical_source or not package.members:
            raise _unknown("duplicate package or missing source/member population")
        names.add(package.name)
        for name, member in package.members.items():
            components = parts(name)
            if not scope.policy.member_allowed(name, member.mode):
                raise AdapterError(f"member refused by adapter policy: {name}", state=State.UNMANAGED)
            if any("/".join(components[:n]) in package.members for n in range(1, len(components))):
                raise AdapterError("file/directory membership collision", state=State.UNMANAGED)


def _directories(members: Mapping[str, object]) -> set[str]:
    result: set[str] = set()
    for name in members:
        items = parts(name)
        result.update("/".join(items[:n]) for n in range(1, len(items)))
    return result


@dataclass
class Snapshot:
    inspection: Inspection
    records: dict[str, OwnershipRecord]
    actual: dict[str, dict[str, OwnedMember]]
    record_only: bool
    foreign_owned: frozenset[str] = frozenset()


def snapshot(scope: Scope, build: ExpectedBuild, *, ignore_pending: bool = False) -> Snapshot:
    if not ignore_pending and scope.stat(scope.policy.work_root / "pending.json") is not None:
        raise _unknown("incomplete transaction retained; inspect recovery work before another refresh")
    records = read_ledger(scope)
    packages = {package.name: package for package in build.packages}
    foreign_owned: set[str] = set()
    for owner, rows in _document(scope)["adapters"].items():
        if not isinstance(rows, dict):
            raise _unknown("shared ownership namespace is incomplete")
        if owner != scope.owner:
            foreign_owned.update(packages.keys() & rows.keys())
    conflicts: list[Conflict] = []
    actual: dict[str, dict[str, OwnedMember]] = {}
    examined = 0
    matches_build = True

    def conflict(package: str, path: str, state: State, reason: str) -> None:
        conflicts.append(Conflict(package, path, state, reason))

    for name in sorted(packages.keys() | records.keys()):
        target = scope.package(name)
        package, record = packages.get(name), records.get(name)
        wanted = {p: OwnedMember(m.sha256, m.mode) for p, m in package.members.items()} if package else {}
        previous = dict(record.members) if record else {}
        if name in foreign_owned:
            conflict(name, "", State.UNMANAGED, "package claimed by another CPP adapter identity")
            matches_build = False
        exists = scope.stat(target)
        if exists is None:
            matches_build &= package is None
            if package:
                conflict(name, "", State.ABSENT, "expected package missing")
            elif record:
                conflict(name, "", State.STALE, "orphan record has no installed package")
            continue
        if not stat.S_ISDIR(exists.st_mode):
            conflict(name, "", State.UNMANAGED, "package target is not a directory")
            matches_build = False
            continue
        files, dirs = scope.inventory(target, set(wanted) | set(previous))
        actual[name] = files
        examined += sum(member.sha256 != "unowned-unread" for member in files.values())
        exact = files == wanted and dirs == _directories(wanted)
        matches_build &= exact
        if record is None:
            conflict(name, "", State.UNMANAGED, "present package has no CPP ownership")
            continue
        if package and record.canonical_source != package.canonical_source:
            conflict(name, "", State.UNMANAGED, "canonical source ownership collision")
        for path, member in files.items():
            if path not in previous:
                conflict(name, path, State.UNMANAGED, "unexpected unowned member preserved")
            elif member != previous[path]:
                conflict(name, path, State.HAND_EDITED, "member differs from recorded installation")
            elif path not in wanted or member != wanted[path]:
                conflict(name, path, State.STALE, "unchanged owned member differs from fresh build")
        for path in wanted.keys() - files.keys():
            conflict(name, path, State.ABSENT, "expected member missing")
        for path in previous.keys() - files.keys() - wanted.keys():
            conflict(name, path, State.STALE, "record retains a missing retired member")
        for path in dirs - (_directories(wanted) | _directories(previous)):
            conflict(name, path, State.UNMANAGED, "unexpected directory preserved")
        if package and record.revision != build.revision:
            conflict(name, "", State.STALE, "ownership revision differs from fresh build")
        if not package:
            conflict(name, "", State.STALE, "proven owned orphan eligible only if unchanged")
    state = min((c.state for c in conflicts), key=lambda s: _ORDER[s], default=State.CURRENT)
    inspection = Inspection(state, len(build.packages), sum(len(p.members) for p in build.packages),
                            examined, tuple(conflicts))
    # The exception requires prior valid ownership for every expected package,
    # matching sources, no orphan, and an exact fresh-build tree. It never adopts.
    record_only = bool(conflicts) and matches_build and records.keys() == packages.keys() and all(
        records[name].canonical_source == package.canonical_source for name, package in packages.items()
    )
    return Snapshot(inspection, records, actual, record_only, frozenset(foreign_owned))


@contextmanager
def locked(scope: Scope, request: Request, *, write: bool) -> Iterator[bool]:
    timeout = request.lock_timeout_seconds
    if not math.isfinite(timeout) or timeout < 0 or timeout > 3600:
        raise AdapterError("lock timeout must be finite and between 0 and 3600")
    location = scope.policy.lock_path
    if write and location.is_relative_to(scope.root):
        scope.mkdir(location.parent)
    try:
        with scope.directory(location.parent) as parent:
            flags = os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_RDWR | os.O_CREAT if write else os.O_RDONLY)
            fd = os.open(location.name, flags, 0o600, dir_fd=parent)
    except FileNotFoundError:
        if write:
            raise
        yield False
        return
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise AdapterError("lock is not a regular file", state=State.UNMANAGED)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AdapterError("lock wait exceeded bounded deadline", exit_code=1 if write else 4)
                time.sleep(min(remaining, 0.01))
        yield True
    finally:
        os.close(fd)


def inspect_locked(scope: Scope, build: ExpectedBuild, request: Request) -> Snapshot:
    with locked(scope, request, write=False) as held:
        answer = snapshot(scope, build)
        appeared = not held and scope.stat(scope.policy.lock_path) is not None
    if appeared:
        with locked(scope, request, write=False) as held:
            if not held:
                raise _unknown("lock changed during verification")
            return snapshot(scope, build)
    return answer


def _ledger_bytes(scope: Scope, build: ExpectedBuild) -> bytes:
    value = _document(scope)
    value["adapters"][scope.owner] = {
        p.name: {"source": p.canonical_source, "revision": build.revision, "members": {
            name: {"sha256": m.sha256, "mode": m.mode} for name, m in sorted(p.members.items())
        }} for p in sorted(build.packages, key=lambda p: p.name)
    }
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def publish(scope: Scope, build: ExpectedBuild, before: Snapshot, request: Request) -> tuple[Inspection, bool, str]:
    """Caller holds LOCK_EX. Leave pending evidence and recoverable bytes on failure."""
    if before.foreign_owned:
        raise AdapterError("another CPP identity owns this package; explicit migration required",
                           state=State.UNMANAGED)
    adopted = set(request.adopt_paths)
    for path in adopted:
        parts(path)
    blocking = [c for c in before.inspection.conflicts if c.state in (State.UNMANAGED, State.HAND_EDITED)]
    if not before.record_only and any(
        c.package not in adopted and f"{c.package}/{c.relative_path}".rstrip("/") not in adopted for c in blocking
    ):
        raise AdapterError("hand-edited or foreign content requires explicit reviewed adoption",
                           state=before.inspection.state)
    if adopted - {c.package for c in blocking} - {
        f"{c.package}/{c.relative_path}".rstrip("/") for c in blocking
    }:
        raise AdapterError("adoption names paths outside this reviewed conflict set", state=State.UNMANAGED)
    transaction = scope.policy.work_root / f"transaction-{uuid.uuid4().hex}"
    pending = scope.policy.work_root / "pending.json"
    scope.mkdir(transaction)
    journal = {"schema": 1, "transaction": transaction.name, "revision": build.revision}
    scope.write(pending, (json.dumps(journal) + "\n").encode())
    expected = {p.name: p for p in build.packages}
    if not before.record_only:
        for package in build.packages:
            dest = transaction / "staged" / package.name
            scope.mkdir(dest)
            for path, member in package.members.items():
                scope.write(dest / path, member.content, member.mode)
        for name in sorted(before.records.keys() | expected.keys()):
            dest = scope.package(name)
            if scope.stat(dest) is not None:
                scope.rename(dest, transaction / "backup" / name)
            if name in expected:
                scope.rename(transaction / "staged" / name, dest)
    # Verify actual bytes independently BEFORE publishing their ownership record.
    for package in build.packages:
        wanted = {p: OwnedMember(m.sha256, m.mode) for p, m in package.members.items()}
        files, dirs = scope.inventory(scope.package(package.name), set(wanted))
        if files != wanted or dirs != _directories(wanted):
            raise _unknown("installed output failed post-copy fidelity verification")
    scope.write(scope.policy.ledger_path, _ledger_bytes(scope, build))
    after = snapshot(scope, build, ignore_pending=True).inspection
    if after.state != State.CURRENT:
        raise _unknown("published record does not describe verified current output")
    scope.unlink(pending)
    recovery = ""
    if adopted and not before.record_only:
        recovery = f"reviewed adoption backup retained at {transaction.relative_to(scope.root)}"
    else:
        scope.remove_work_tree(transaction)
    return after, before.record_only, recovery

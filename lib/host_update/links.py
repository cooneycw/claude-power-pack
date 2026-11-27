"""Existing Claude command/helper links; a separate, bounded backend.

No link target is followed to discover ownership. The installed name and literal
absolute target must match the approved persistent checkout. Target content is
then read independently through a no-follow source authority, never via a link.
"""
from __future__ import annotations

import fcntl
import hashlib
import math
import os
import stat
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from .driver import _error_result, _source_git, _validate_revision
from .models import (
    Action,
    AdapterError,
    AdapterResult,
    Conflict,
    Discovery,
    Inspection,
    OwnedMember,
    Policy,
    Request,
    Revision,
    State,
)
from .scope import Scope, absolute, parts


@dataclass(frozen=True)
class LinkKind:
    name: str
    source: str
    directory: bool


KINDS = (LinkKind("commands", ".claude/commands", True), LinkKind("scripts", "scripts", False))


def authority(root: Path) -> Scope:
    return Scope(Policy(root, root / ".unused-ledger", root / ".unused-lock", root / ".unused-work"))


class ClaudeLinks:
    harness = "claude-links"

    def __init__(self, home: Path, *, source: Path | None = None,
                 selected: bool | None = None, deferred: tuple[str, ...] = ()):
        self.home = absolute(home)
        self.source = absolute(source) if source is not None else None
        self.selected = selected
        self.deferred = deferred

    def preflight(self, request: Request) -> Policy:
        # Grant only named surfaces after checking every user-controlled prefix.
        if not math.isfinite(request.lock_timeout_seconds) or not 0 <= request.lock_timeout_seconds <= 3600:
            raise AdapterError("lock timeout must be finite and between 0 and 3600", exit_code=4)
        scope = authority(self.home)
        for name in ("commands", "scripts"):
            root = self.home / ".claude" / name
            source = self.source or request.revision.snapshot_root
            if root.is_relative_to(source) or source.is_relative_to(root):
                raise AdapterError("link target and install scopes overlap", state=State.UNMANAGED)
            try:
                with scope.directory(root):
                    pass
            except FileNotFoundError:
                pass
            for item in self.deferred:
                path = Path(item.replace("~/", str(self.home) + "/", 1))
                lock = root.parent / ".cpp-skill-install.lock"
                if any(path == loc or path.is_relative_to(loc) or loc.is_relative_to(path)
                       for loc in (root, lock)):
                    raise AdapterError("Claude links deferred to declared owner", state=State.UNMANAGED)
        root = self.home / ".claude"
        return Policy(root, root / ".unused-ledger", root / ".cpp-skill-install.lock", root / ".unused-work")

    def target(self, kind: LinkKind, name: str, request: Request) -> Path:
        # listdir supplies a single leaf; foreign non-portable names are never
        # source members and do not become a path traversal authority.
        if name in ("", ".", "..") or "/" in name or "\0" in name:
            raise AdapterError("invalid link leaf", state=State.UNMANAGED)
        return (self.source or request.revision.snapshot_root) / kind.source / name

    def _entries(self, kind: LinkKind) -> dict[str, tuple | None]:
        try:
            with authority(self.home).directory(self.home / ".claude" / kind.name) as fd:
                return {name: self._entry(fd, name) for name in os.listdir(fd)}
        except FileNotFoundError:
            return {}

    @staticmethod
    def _entry(fd: int, name: str) -> tuple | None:
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        target = os.readlink(name, dir_fd=fd) if stat.S_ISLNK(info.st_mode) else None
        return info.st_dev, info.st_ino, info.st_mode, info.st_ctime_ns, target

    def discover(self, policy: Policy, request: Request) -> Discovery:
        # A candidate alone can select for a source-unknown error, never current.
        evidence = tuple(kind.name for kind in KINDS if any(
            row and row[-1] == str(self.target(kind, name, request))
            for name, row in self._entries(kind).items()))
        return Discovery(bool(evidence) and self.selected is not False, bool(evidence), evidence,
                         reason="existing exact CPP command/helper links only")

    def manifest(self, request: Request) -> dict[str, dict[str, dict[str, OwnedMember]]]:
        source = self.source or request.revision.snapshot_root
        scope = authority(source)
        revision = Revision(request.revision.commit, source)
        _validate_revision(scope, revision)
        _validate_revision(authority(request.revision.snapshot_root), request.revision)
        for link_kind in KINDS:
            try:
                with scope.directory(source / link_kind.source):
                    pass
            except FileNotFoundError:
                pass
        tree = _source_git(request.revision, ["ls-tree", "-rz", request.revision.commit])
        if tree.returncode:
            raise AdapterError("link source membership unavailable", exit_code=4)
        result: dict[str, dict[str, dict[str, OwnedMember]]] = {k.name: {} for k in KINDS}
        for row in tree.stdout.split(b"\0"):
            if not row:
                continue
            header, raw = row.split(b"\t", 1)
            mode, kind, oid = header.split()
            relative = raw.decode()
            path = parts(relative)
            if mode == b"120000" and relative.startswith((".claude/commands/", "scripts/")):
                raise AdapterError("link source contains an alias", exit_code=4)
            if mode == b"160000" and relative.startswith(".claude/commands/"):
                raise AdapterError("command family source contains an unsupported gitlink", exit_code=4)
            group = None
            if len(path) >= 4 and path[:2] == (".claude", "commands"):
                group, name, member = "commands", path[2], "/".join(path[3:])
            elif len(path) == 2 and path[0] == "scripts" and mode == b"100755":
                group, name, member = "scripts", path[1], path[1]
            # The existing shell installers use immediate non-hidden globs.
            if group is None or name.startswith("."):
                continue
            if kind != b"blob" or mode not in (b"100644", b"100755"):
                raise AdapterError("link source contains an alias or unsupported member", exit_code=4)
            # Compute Git's object digest ourselves; do not trust checkout bytes
            # merely because a stat-cache-based status command said clean.
            content = scope.read(source / relative)
            digest = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content,
                                  usedforsecurity=False).hexdigest()
            info = scope.stat(source / relative)
            if (digest.encode() != oid or info is None or not stat.S_ISREG(info.st_mode)
                    or bool(info.st_mode & 0o111) != (mode == b"100755")):
                raise AdapterError("persistent link source bytes or executable mode differ", exit_code=4)
            result[group].setdefault(name, {})[member] = OwnedMember(hashlib.sha256(content).hexdigest(),
                                                                   stat.S_IMODE(info.st_mode))
        # Check directory membership independently; untracked/aliased neighbours
        # inside a linked family would otherwise be exposed to the consumer.
        for name, wanted in result["commands"].items():
            actual, directories = scope.inventory(source / ".claude/commands" / name, set(wanted))
            expected_dirs = {str(p) for member in wanted for p in Path(member).parents if str(p) != "."}
            if actual != wanted or directories != expected_dirs:
                raise AdapterError("command family source membership differs", exit_code=4)
        return result

    def retired(self, kind: LinkKind, name: str, request: Request) -> bool:
        """Require an actual prior tracked kind/name, not a source-shaped string."""
        relative = f"{kind.source}/{name}"
        revision = Revision(request.revision.commit, self.source or request.revision.snapshot_root)
        commits = _source_git(revision, ["log", "-n", "64", "--format=%H", revision.commit,
                                         "--", f":(literal){relative}"])
        if commits.returncode:
            return False
        for commit in commits.stdout.decode().splitlines():
            tree = _source_git(revision, ["ls-tree", "-z", commit, "--", f":(literal){relative}"])
            if tree.returncode:
                continue
            for row in tree.stdout.split(b"\0"):
                if not row:
                    continue
                header, path = row.split(b"\t", 1)
                mode, typ, _ = header.split()
                if path.decode() == relative and ((kind.directory and mode == b"040000" and typ == b"tree")
                                                  or (not kind.directory and mode == b"100755" and typ == b"blob")):
                    return True
        return False

    @contextmanager
    def lock(self, policy: Policy, request: Request, *, write: bool):
        # Use ONLY the same exact Claude lock as copies; never create management
        # dirs or link ledgers, and never create any lock in verify mode.
        try:
            with authority(self.home).directory(policy.lock_path.parent) as parent:
                flags = os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_RDWR | os.O_CREAT if write else os.O_RDONLY)
                try:
                    fd = os.open(policy.lock_path.name, flags, 0o600, dir_fd=parent)
                except FileNotFoundError:
                    if write:
                        raise
                    fd = -1
        except FileNotFoundError:
            if write:
                raise AdapterError("Claude link lock parent disappeared", exit_code=4)
            fd = -1
        try:
            if fd >= 0:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise AdapterError("Claude lock is not regular", state=State.UNMANAGED)
                deadline = time.monotonic() + request.lock_timeout_seconds
                while True:
                    try:
                        fcntl.flock(fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise AdapterError("Claude link lock wait exceeded deadline", exit_code=4)
                        time.sleep(min(.01, max(0, deadline - time.monotonic())))
            yield
            observed = authority(self.home).stat(policy.lock_path)
            original = os.fstat(fd) if fd >= 0 else None
            if ((observed is None) != (original is None) or
                    observed is not None and original is not None and
                    (observed.st_dev, observed.st_ino) != (original.st_dev, original.st_ino)):
                raise AdapterError("Claude link lock changed during operation", exit_code=4)
        finally:
            if fd >= 0:
                os.close(fd)

    def operate(self, request: Request, *, verify_only: bool) -> AdapterResult:
        selected, evidence, before, changed, writing = False, (), None, False, False
        try:
            policy = self.preflight(request)
            discovery = self.discover(policy, request)
            selected, evidence = discovery.selected, discovery.evidence
            if not selected:
                value = Inspection(State.NOT_APPLICABLE, reason="no established CPP link kind; no tier enrollment")
                return AdapterResult(self.harness, request.revision.commit, False, (), value,
                                     Action.NOT_ATTEMPTED, value, 5, value.reason)
            with self.lock(policy, request, write=not verify_only), ExitStack() as stack:
                self.preflight(request)
                manifest = self.manifest(request)
                roots = {}
                retired = {}
                for kind in KINDS:
                    entries = self._entries(kind)
                    proven = {name for name, row in entries.items() if row and
                              row[-1] == str(self.target(kind, name, request)) and
                              (name in manifest[kind.name] or self.retired(kind, name, request))}
                    # Each kind enrolls independently. A foreign-only directory
                    # is neither converted nor taken as permission to add links.
                    if not proven:
                        continue
                    fd = stack.enter_context(authority(self.home).directory(self.home / ".claude" / kind.name))
                    roots[kind.name] = fd
                    retired[kind.name] = proven - manifest[kind.name].keys()
                if not roots:
                    raise AdapterError("candidate link names lack tracked ownership proof", exit_code=4)

                def stable_roots():
                    self.preflight(request)
                    for name, fd in roots.items():
                        with authority(self.home).directory(self.home / ".claude" / name) as current:
                            a, b = os.fstat(fd), os.fstat(current)
                            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                                raise AdapterError("link install root changed during operation", exit_code=4)

                def inspect_links():
                    stable_roots()
                    conflicts, expected, expected_members, examined = [], 0, 0, 0
                    for kind in KINDS:
                        if kind.name not in roots:
                            continue
                        fd = roots[kind.name]
                        expected += len(manifest[kind.name])
                        for name, members in manifest[kind.name].items():
                            expected_members += len(members)
                            row = self._entry(fd, name)
                            if row and row[-1] == str(self.target(kind, name, request)):
                                examined += len(members)
                            else:
                                state = State.ABSENT if row is None else State.UNMANAGED
                                conflicts.append(Conflict(f"{kind.name}/{name}", "", state,
                                                          "expected link absent or replaced; foreign entry preserved"))
                        for name in retired[kind.name]:
                            live = os.path.exists(self.home / ".claude" / kind.name / name)
                            conflicts.append(Conflict(
                                f"{kind.name}/{name}", "", State.UNMANAGED if live else State.STALE,
                                "retired CPP link target still present; preserved for review" if live
                                else "proven retired CPP link remains"))
                        # Source-shaped but unproven orphan links are observable
                        # uncertainty, not owned entries eligible for deletion.
                        for name in os.listdir(fd):
                            row = self._entry(fd, name)
                            if (name not in manifest[kind.name] and name not in retired[kind.name]
                                    and row and row[-1] == str(self.target(kind, name, request))):
                                conflicts.append(Conflict(f"{kind.name}/{name}", "", State.UNMANAGED,
                                                          "orphan ownership unproven; preserve and review"))
                    if not expected:
                        raise AdapterError("selected link kind has zero expected population", exit_code=4)
                    state = (State.UNMANAGED if any(c.state == State.UNMANAGED for c in conflicts)
                             else State.STALE if conflicts else State.CURRENT)
                    return Inspection(state, expected, expected_members, examined, tuple(conflicts),
                                      "links: tracked source membership, bytes and executable modes verified")

                before = inspect_links()
                if not verify_only:
                    for kind in KINDS:
                        if kind.name not in roots:
                            continue
                        fd = roots[kind.name]
                        for name in manifest[kind.name]:
                            stable_roots()
                            row = self._entry(fd, name)
                            if row is None:
                                # symlink() is exclusive: a concurrent foreign
                                # replacement is never overwritten by rename.
                                writing = True
                                os.symlink(str(self.target(kind, name, request)), name, dir_fd=fd)
                                os.fsync(fd)
                                changed = True
                        for name in list(retired[kind.name]):
                            stable_roots()
                            row = self._entry(fd, name)
                            if row and row[-1] == str(self.target(kind, name, request)):
                                # Retirement proves former membership, not that
                                # a still-present target is safe to remove.
                                if os.path.exists(self.home / ".claude" / kind.name / name):
                                    continue
                                # Re-inspect the exact identity immediately before
                                # unlink; cooperating writers hold this same lock.
                                if self._entry(fd, name) != row:
                                    raise AdapterError("retired link identity changed", exit_code=4)
                                writing = True
                                os.unlink(name, dir_fd=fd)
                                os.fsync(fd)
                                retired[kind.name].remove(name)
                                changed = True
                self.manifest(request)  # recheck persistent target after writes
                after = inspect_links()
                code = 0 if after.state == State.CURRENT else 1
                return AdapterResult(self.harness, request.revision.commit, True, evidence, before,
                                     Action.REFRESHED if changed else Action.UNCHANGED, after, code,
                                     after.reason, "resolve preserved conflicts separately" if code else "")
        except Exception as error:
            failure = error if isinstance(error, AdapterError) else AdapterError(
                f"link backend unavailable ({type(error).__name__})", exit_code=1 if writing else 4)
            failure_row = _error_result(self.harness, request, failure)
            return replace(failure_row, selected=selected, selection_evidence=evidence,
                           before=before or failure_row.before,
                           action=Action.FAILED if writing else failure_row.action,
                           exit_code=1 if writing else failure_row.exit_code)

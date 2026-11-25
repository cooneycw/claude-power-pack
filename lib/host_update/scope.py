"""Descriptor-relative filesystem access inside an adapter-approved scope.

Trust adapter-approved system prefixes above the install root. Open the root
and each descendant with O_NOFOLLOW; retain directory descriptors for leaf IO.
Unexpected package files are inventoried without reading their contents.
"""

from __future__ import annotations

import errno
import os
import re
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import AdapterError, OwnedMember, Policy, State

_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
_SLUG = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")


def parts(value: str) -> tuple[str, ...]:
    """Accept explicit portable relative members, never aliases or traversal."""
    items = tuple(value.split("/"))
    if not value or any(p in ("", ".", "..") for p in items) or "\\" in value or "\0" in value:
        raise AdapterError(f"unsafe relative path: {value!r}", state=State.UNMANAGED)
    return items


def slug(value: str) -> str:
    if not _SLUG.fullmatch(value):
        raise AdapterError(f"unsafe package name: {value!r}", state=State.UNMANAGED)
    return value


def absolute(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts or "\0" in str(path):
        raise AdapterError("policy paths must be absolute without traversal", state=State.UNMANAGED)
    return path


class Scope:
    def __init__(self, policy: Policy, *, owner: str = "fixture") -> None:
        self.policy = policy
        self.owner = owner
        if not owner:
            raise AdapterError("empty adapter ownership namespace")
        self.root = absolute(policy.install_root)
        if self.root == Path("/"):
            raise AdapterError("filesystem root is not an install scope", state=State.UNMANAGED)
        for location in (policy.ledger_path, policy.work_root):
            absolute(location)
            if location == self.root or not location.is_relative_to(self.root):
                raise AdapterError("ledger/work must be strictly inside install scope", state=State.UNMANAGED)
        absolute(policy.lock_path)
        if policy.ledger_path.is_relative_to(policy.work_root):
            raise AdapterError("ledger cannot be inside transient work scope", state=State.UNMANAGED)
        if policy.work_root.is_relative_to(policy.ledger_path):
            raise AdapterError("work scope cannot be inside ledger file", state=State.UNMANAGED)
        for location in self.coordination_paths():
            if (location in (policy.ledger_path, policy.work_root, self.root)
                    or policy.ledger_path.is_relative_to(location)
                    or policy.work_root.is_relative_to(location)
                    or location.is_relative_to(policy.work_root)):
                raise AdapterError("lock collides with management data or cleanup scope", state=State.UNMANAGED)

    def coordination_paths(self) -> tuple[Path, ...]:
        ledger, work = self.policy.ledger_path, self.policy.work_root
        return (self.policy.lock_path, ledger.with_name(f".{ledger.name}.cpp-lock"),
                work.with_name(f".{work.name}.cpp-lock"))

    def package(self, name: str) -> Path:
        target = self.root / slug(name)
        for management in (self.policy.ledger_path, self.policy.work_root, self.policy.lock_path):
            if management == target or management.is_relative_to(target):
                raise AdapterError("package collides with management scope", state=State.UNMANAGED)
        return target

    def _allowed(self, path: Path) -> None:
        absolute(path)
        if not path.is_relative_to(self.root) and path != self.policy.lock_path:
            raise AdapterError("operation outside approved scope", state=State.UNMANAGED)

    @contextmanager
    def directory(self, path: Path, *, create: bool = False) -> Iterator[int]:
        """Open the approved root once; no-follow every descendant below it.

        Trusted system ancestors above the adapter-approved root may be aliases
        (for example /home -> /var/home). The root itself is not followed.
        Adapter preflight must validate user-controlled prefixes before granting
        a root. The fixture adapter does so beneath its marked fixture anchor.
        """
        absolute(path)
        fd = -1
        try:
            if path.is_relative_to(self.root):
                try:
                    fd = os.open(self.root, _DIRECTORY)
                except FileNotFoundError:
                    if not create:
                        raise
                    # Only the selected root may be bootstrapped. Its approved
                    # parent may include system aliases; no parent is created.
                    parent = os.open(self.root.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        try:
                            os.mkdir(self.root.name, 0o755, dir_fd=parent)
                        except FileExistsError:
                            pass
                        fd = os.open(self.root.name, _DIRECTORY, dir_fd=parent)
                    finally:
                        os.close(parent)
                for item in path.relative_to(self.root).parts:
                    try:
                        child = os.open(item, _DIRECTORY, dir_fd=fd)
                    except FileNotFoundError:
                        if not create:
                            raise
                        try:
                            os.mkdir(item, 0o755, dir_fd=fd)
                        except FileExistsError:
                            pass
                        child = os.open(item, _DIRECTORY, dir_fd=fd)
                    os.close(fd)
                    fd = child
            else:
                # Source roots and the explicitly approved lock parent are
                # separate bounded authorities, not additional inventory roots.
                ancestor = self.root.is_relative_to(path) or path == self.policy.lock_path.parent
                fd = os.open(path, (os.O_RDONLY | os.O_DIRECTORY) if ancestor else _DIRECTORY)
            yield fd
        except OSError as exc:
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                raise AdapterError("symlink or non-directory ancestor refused", state=State.UNMANAGED) from exc
            raise
        finally:
            if fd >= 0:
                os.close(fd)

    def stat(self, path: Path) -> os.stat_result | None:
        self._allowed(path)
        try:
            with self.directory(path.parent) as fd:
                result = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(result.st_mode):
            raise AdapterError("symlink target refused", state=State.UNMANAGED)
        return result

    def read(self, path: Path) -> bytes:
        self._allowed(path)
        with self.directory(path.parent) as parent:
            fd = os.open(path.name, _FILE, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024 * 1024:
                raise AdapterError("unsupported or oversized file", state=State.UNMANAGED)
            with os.fdopen(fd, "rb", closefd=False) as stream:
                return stream.read(64 * 1024 * 1024 + 1)
        finally:
            os.close(fd)

    def mkdir(self, path: Path) -> None:
        self._allowed(path)
        with self.directory(path, create=True):
            pass

    def write(self, path: Path, content: bytes, mode: int = 0o644) -> None:
        self._allowed(path)
        with self.directory(path.parent, create=True) as parent:
            name = f".cpp-write-{uuid.uuid4().hex}"
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=parent)
            try:
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    stream.write(content)
                    stream.flush()
                os.fchmod(fd, mode)
                os.fsync(fd)
                os.rename(name, path.name, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            finally:
                os.close(fd)
                try:
                    os.unlink(name, dir_fd=parent)
                except FileNotFoundError:
                    pass

    def rename(self, source: Path, target: Path) -> None:
        self._allowed(source)
        self._allowed(target)
        with self.directory(source.parent) as src, self.directory(target.parent, create=True) as dst:
            os.rename(source.name, target.name, src_dir_fd=src, dst_dir_fd=dst)
            os.fsync(src)
            os.fsync(dst)

    def unlink(self, path: Path) -> None:
        self._allowed(path)
        with self.directory(path.parent) as fd:
            os.unlink(path.name, dir_fd=fd)
            os.fsync(fd)

    def inventory(self, path: Path, readable: set[str]) -> tuple[dict[str, OwnedMember], set[str]]:
        """Inventory one selected package, not its siblings or the agent root."""
        import hashlib

        self._allowed(path)
        files: dict[str, OwnedMember] = {}
        directories: set[str] = set()

        def walk(fd: int, prefix: str) -> None:
            for name in sorted(os.listdir(fd)):
                relative = f"{prefix}/{name}" if prefix else name
                parts(relative)
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    directories.add(relative)
                    child = os.open(name, _DIRECTORY, dir_fd=fd)
                    try:
                        walk(child, relative)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode):
                    digest = "unowned-unread"
                    if relative in readable:
                        digest = hashlib.sha256(self.read(path / relative)).hexdigest()
                    files[relative] = OwnedMember(digest, stat.S_IMODE(info.st_mode))
                else:
                    raise AdapterError(f"unsupported member: {relative}", state=State.UNMANAGED)

        with self.directory(path) as fd:
            walk(fd, "")
        return files, directories

    def remove_work_tree(self, path: Path) -> None:
        """Delete only a transaction's private work tree; never an install tree."""
        if path == self.policy.work_root or not path.is_relative_to(self.policy.work_root):
            raise AdapterError("cleanup outside transaction work scope", state=State.UNMANAGED)

        def remove(parent: int, name: str) -> None:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, _DIRECTORY, dir_fd=parent)
                try:
                    for item in os.listdir(child):
                        remove(child, item)
                finally:
                    os.close(child)
                os.rmdir(name, dir_fd=parent)
            elif stat.S_ISREG(info.st_mode):
                os.unlink(name, dir_fd=parent)
            else:
                raise AdapterError("unexpected cleanup member preserved", state=State.UNMANAGED)

        with self.directory(path.parent) as fd:
            remove(fd, path.name)

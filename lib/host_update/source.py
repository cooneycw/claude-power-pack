"""Private, commit-bound source execution without changing a user's branch."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .driver import _source_blob, _source_git
from .models import AdapterError, Policy, Revision
from .scope import Scope, absolute, parts


class ExecutionFailure(AdapterError):
    """A child ran, but its installed-state outcome cannot be trusted."""


@contextmanager
def pinned_source(source: Path, reference: str | None = None):
    source = absolute(source)
    scope = Scope(Policy(source, source / ".unused-ledger", source / ".unused-lock", source / ".unused-work"))
    with scope.directory(source):
        pass
    initial = Revision("", source)
    clean = _source_git(initial, ["status", "--porcelain", "--untracked-files=normal"])
    target = _source_git(initial, ["rev-parse", "--verify", "--end-of-options", (reference or "HEAD") + "^{commit}"])
    if clean.returncode or clean.stdout or target.returncode:
        raise AdapterError("source is dirty or the requested commit is unavailable", exit_code=4)
    commit = target.stdout.decode().strip()
    temporary = tempfile.TemporaryDirectory(prefix="cpp-host-source-")
    yielded = False
    try:
        root = Path(temporary.name) / "snapshot"
        cloned = _source_git(initial, ["clone", "--shared", "--no-checkout", "--", str(source), str(root)])
        if cloned.returncode:
            raise AdapterError("private source snapshot could not be created", exit_code=4)
        revision = Revision(commit, root)
        checked = _source_git(revision, ["checkout", "--detach", commit])
        if checked.returncode:
            raise AdapterError("private source commit could not be checked out", exit_code=4)
        tree = _source_git(revision, ["ls-tree", "-rz", commit])
        if tree.returncode:
            raise AdapterError("private source inventory unavailable", exit_code=4)
        # Git stores executability, not checkout group/world write bits.
        # The unchanged Codex copier preserves modes, so fix its INPUTS.
        for row in tree.stdout.split(b"\0"):
            if not row:
                continue
            head, name = row.split(b"\t", 1)
            mode, kind, _oid = head.split()
            if mode == b"120000" and name.startswith((b"scripts/", b"lib/")):
                raise AdapterError("pinned executable source alias refused", exit_code=4)
            if kind == b"blob" and mode in (b"100644", b"100755"):
                path = root.joinpath(*parts(name.decode()))
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    os.fchmod(fd, 0o755 if mode == b"100755" else 0o644)
                finally:
                    os.close(fd)
        yielded = True
        yield revision
    finally:
        try:
            temporary.cleanup()
        except OSError as error:
            if yielded:
                raise ExecutionFailure("private source cleanup failed; inspect installed state", exit_code=1) from error
            raise AdapterError("private source cleanup failed", exit_code=4) from error


def execute_snapshot(revision: Revision, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    import sys

    entry = revision.snapshot_root / "scripts/cpp-host-update.py"
    content = _source_blob(revision, "scripts/cpp-host-update.py")
    authority = Scope(Policy(revision.snapshot_root, revision.snapshot_root / ".unused-ledger",
                             revision.snapshot_root / ".unused-lock", revision.snapshot_root / ".unused-work"))
    if authority.read(entry) != content or b"PRODUCTION-HOST-ENTRY: 3" not in content:
        raise AdapterError("requested revision has no supported pinned production entry", exit_code=4)
    try:
        result = subprocess.run([sys.executable, str(entry), *arguments, "--pinned", revision.commit],
                                capture_output=True, text=True, timeout=300, umask=0o022)
    except subprocess.SubprocessError as error:
        raise ExecutionFailure("pinned driver execution incomplete; inspect installed state", exit_code=1) from error
    try:
        report = json.loads(result.stdout)
    except ValueError as error:
        raise ExecutionFailure("pinned driver returned no readable report", exit_code=1) from error
    if not valid_report(report, result.returncode, revision.commit):
        raise ExecutionFailure("pinned driver returned incomplete or inconsistent report", exit_code=1)
    return result


def valid_report(report, exit_code: int, revision: str) -> bool:
    """Validate the actual producer envelope before any caller trusts current."""
    from .host import BACKENDS, DEFERRED, INCLUDED

    try:
        rows = report["results"]
        if (type(report["schema"]) is not int or report["schema"] != 2
                or report["coverage"] != "partial" or report["backend"] != "mixed"
                or report["included"] != list(INCLUDED) or report["unimplemented"] != list(DEFERRED)
                or report["revision"] != revision or type(report["exit_code"]) is not int
                or report["exit_code"] != exit_code or not isinstance(rows, list)
                or len(rows) != len(INCLUDED) or {r["harness"] for r in rows} != set(INCLUDED)):
            return False
        codes = {r["exit_code"] for r in rows}
        aggregate = 1 if 1 in codes else 4 if 4 in codes else 0 if 0 in codes else 5
        if not codes <= {0, 1, 4, 5} or exit_code != aggregate:
            return False
        for row in rows:
            if (row["backend"] != BACKENDS[row["harness"]]
                    or row["revision"] != revision or type(row["selected"]) is not bool
                    or type(row["exit_code"]) is not int
                    or not isinstance(row["reason"], str) or not isinstance(row["remedy"], str)
                    or row["action"] not in ("unchanged", "refreshed", "refused", "failed", "not-attempted")):
                return False
            for key in ("before", "after"):
                stage = row[key]
                if stage["state"] not in ("current", "stale", "hand-edited", "unmanaged", "absent",
                                          "not-applicable", "unknown"):
                    return False
                if any(type(stage[n]) is not int or stage[n] < 0
                       for n in ("expected_packages", "expected_members", "examined_members")):
                    return False
            after = row["after"]
            if row["exit_code"] == 0 and (not row["selected"] or after["state"] != "current"):
                return False
            if row["action"] in ("failed", "refused") and row["exit_code"] != 1:
                return False
            if row["action"] == "refreshed":
                complete = row["exit_code"] == 0 and after["state"] == "current"
                partial = (row["exit_code"] == 1 and after["state"] in ("unmanaged", "hand-edited")
                           and after["expected_packages"] > 0 and bool(after["conflicts"])
                           and all(c["package"] and c["state"] in ("unmanaged", "hand-edited", "stale", "absent")
                                   for c in after["conflicts"]))
                if not (complete or partial):
                    return False
            if after["state"] == "current" and not (
                    row["selected"] and (row["exit_code"] == 0
                                         or row["exit_code"] == 1 and row["action"] == "failed")
                    and after["expected_packages"] > 0
                    and after["expected_members"] == after["examined_members"] > 0):
                return False
        chosen = [r for r in rows if r["selected"]]
        return exit_code != 0 or bool(chosen) and all(
            r["exit_code"] == 0 and r["after"]["state"] == "current" for r in chosen)
    except (KeyError, TypeError, AttributeError):
        return False

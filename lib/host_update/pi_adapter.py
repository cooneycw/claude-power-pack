"""Pi policy and topic bytes consumed by the real managed-copy core.

No generic publication/ownership/locking implementation lives here. Source IO
is pinned to tracked regular blobs; no authentication files establish selection.
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

from lib import pi_skills

from .models import (
    AdapterError,
    Discovery,
    ExpectedBuild,
    ExpectedMember,
    ExpectedPackage,
    Policy,
    Request,
    Revision,
    build_manifest_sha256,
)
from .scope import Scope
from .store import read_ledger


def source_git(source: Path, *arguments: str) -> bytes:
    """Read the approved source, independent of invoking repository overrides."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_REPLACE_OBJECTS="1")
    answer = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                             "-C", str(source), *arguments], env=env, capture_output=True, timeout=10)
    if answer.returncode:
        raise AdapterError("approved source revision is unavailable", exit_code=4)
    return answer.stdout


def markdown_member(path: str, mode: int) -> bool:
    return mode == 0o644 and bool(re.fullmatch(r"SKILL\.md|references/[A-Za-z0-9_.-]+\.md", path))


class PiAdapter:
    harness = "pi"

    def __init__(self, *, cwd: Path, home: Path, agent: Path | None = None,
                 session_dir: str | None = None, environ: dict[str, str] | None = None) -> None:
        self.cwd, self.home, self.agent = cwd, home, agent
        self.session_dir, self.environ = session_dir, environ

    def preflight(self, request: Request) -> Policy:
        env = os.environ if self.environ is None else self.environ
        try:
            # A1's stronger no-follow prefix validation remains adapter policy;
            # generic core no-follow begins at install_root, not its ancestors.
            agent = pi_skills.nofollow(pi_skills.normalized(
                self.agent or env.get("PI_CODING_AGENT_DIR") or self.home / ".pi/agent",
                self.cwd, self.home))
            context = pi_skills.preflight(agent / "skills", cwd=self.cwd, home=self.home,
                                          agent=agent, session_dir=self.session_dir,
                                          environ=env, fidelity_only=True)
            if not stat.S_ISDIR(agent.lstat().st_mode):
                raise pi_skills.PolicyError("agent root must be an existing directory")
            pi_skills.nofollow(agent / ".cpp-skills.lock")
            # Core validates Git only after this callback. Never let a source
            # override authorize credential metadata or a user-prefix alias.
            pi_skills.nofollow(request.revision.snapshot_root)
            skills = context.destination
            return Policy(skills, skills / ".cpp-managed/ownership.json", agent / ".cpp-skills.lock",
                          skills / ".cpp-managed/work", markdown_member)
        except (ValueError, UnicodeError) as error:
            raise AdapterError(str(error)) from error

    def discover(self, policy: Policy, request: Request) -> Discovery:
        records = read_ledger(Scope(policy, owner=self.harness))
        selected = bool(records) if request.selected is None else request.selected
        return Discovery(selected, bool(records),
                         ("explicit-pi-selection" if request.selected is not None else "validated-pi-ledger",))

    def build(self, revision: Revision, policy: Policy) -> ExpectedBuild:
        source = revision.snapshot_root
        tracked: dict[str, tuple[bytes, bytes]] = {}
        for row in source_git(source, "ls-tree", "-rz", revision.commit).split(b"\0"):
            if not row:
                continue
            head, name = row.split(b"\t", 1)
            mode, kind, oid = head.split()
            if kind == b"blob":
                tracked[name.decode("utf-8")] = (mode, oid)

        def pinned_markdown(path: Path) -> bytes:
            relative = path.relative_to(source).as_posix()
            entry = tracked.get(relative)
            if entry is None:
                raise AdapterError("topic input is not pinned regular non-executable source: " + relative,
                                   exit_code=4)
            mode, oid = entry
            if mode != b"100644":
                raise AdapterError("tracked topic input is executable or a symlink: " + relative)
            expected = source_git(source, "cat-file", "blob", oid.decode("ascii"))
            actual = pi_skills.markdown(path, exact_mode=False)
            if actual != expected:
                raise AdapterError("topic input differs from pinned source: " + relative, exit_code=4)
            return actual

        try:
            built = pi_skills.build(source, reader=pinned_markdown)
        except (ValueError, UnicodeError) as error:
            raise AdapterError(str(error)) from error
        packages = tuple(ExpectedPackage(p.slug, pi_skills.SOURCE_PREFIX + p.slug,
                                         {name: ExpectedMember(data) for name, data in p.members}) for p in built)
        return ExpectedBuild(revision.commit, packages, build_manifest_sha256(revision.commit, packages))


def make_request(adapter: PiAdapter, source: Path, *, revision: str | None = None,
                 lock_timeout: float = 5, adopt: tuple[str, ...] = ()) -> Request:
    """Validate policy before Git, including when resolving the default revision."""
    source = source.absolute()
    initial = Request(Revision(revision or "", source), selected=True,
                      lock_timeout_seconds=lock_timeout, adopt_paths=adopt)
    adapter.preflight(initial)
    commit = revision or source_git(source, "rev-parse", "HEAD").decode("ascii").strip()
    return Request(Revision(commit, source), selected=True, lock_timeout_seconds=lock_timeout, adopt_paths=adopt)

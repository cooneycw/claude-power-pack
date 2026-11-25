"""Materialize committed fixture inputs; relay the real CLI's verdict unchanged.

Independent setup writes a prior installation/ledger, so a blind anchor cannot
make its own setup pass by claiming to have installed files it never wrote.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)): (stat.S_IMODE(p.stat().st_mode),
                                     digest(p.read_bytes()) if p.is_file() else None)
            for p in root.rglob("*")}


def main():
    gate, case = Path(sys.argv[1]), Path(sys.argv[2])
    if shutil.which("git") is None:
        print("HOST_UPDATE: UNAVAILABLE - git missing")
        return 3
    seed = json.loads((case / "case.json").read_text())
    scenario = seed["scenario"]
    with tempfile.TemporaryDirectory(prefix="host-update-control-") as temporary:
        root = Path(temporary)
        source, skills = root / "source", root / "a/skills"
        source.mkdir()

        def git(*args):
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
            return subprocess.run(["git", "-C", str(source), *args], capture_output=True,
                                  text=True, check=True, env=env, timeout=10).stdout.strip()

        git("init", "-q", "-b", "main")
        git("config", "user.email", "fixture@example.invalid")
        git("config", "user.name", "fixture")
        git("config", "commit.gpgsign", "false")
        git("config", "core.hooksPath", "/dev/null")
        members = seed["members"]
        for name, content in members.items():
            relative = Path("topic") / name
            (source / relative).parent.mkdir(parents=True, exist_ok=True)
            (source / relative).write_text(content)
            (skills / relative).parent.mkdir(parents=True, exist_ok=True)
            (skills / relative).write_text(content)
            (skills / relative).chmod(0o644)
        orphan = skills / "old/SKILL.md"
        if scenario in ("modified-orphan", "prune"):
            (source / "old").mkdir()
            (source / "old/SKILL.md").write_text(seed["orphan"])
            orphan.parent.mkdir()
            orphan.write_text(seed["orphan"])
            orphan.chmod(0o644)
        git("add", ".")
        git("commit", "-qm", "previous fixture source")
        old_revision = git("rev-parse", "HEAD")
        rows = {"topic": {"source": "fixture/topic", "revision": old_revision, "members": {
            name: {"sha256": digest(content.encode()), "mode": 0o644} for name, content in members.items()
        }}}
        if orphan.exists():
            rows["old"] = {"source": "fixture/old", "revision": old_revision, "members": {
                "SKILL.md": {"sha256": digest(seed["orphan"].encode()), "mode": 0o644}}}
        ledger = skills / ".managed/ownership.json"
        ledger.parent.mkdir()
        ledger.write_text(json.dumps({"schema": 1, "producer": "claude-power-pack",
                                      "adapters": {"fixture-a": rows}}))
        foreign = skills / "personal/SKILL.md"
        foreign.parent.mkdir()
        foreign.write_bytes(b"foreign fixture sentinel\n")
        foreign.chmod(0o644)
        before_foreign = inventory(foreign.parent)
        operation = "verify"
        if scenario == "stale":
            assert (skills / "topic/SKILL.md").read_text() == members["SKILL.md"]
            assert seed["replacement"] != members["SKILL.md"]
            (source / "topic/SKILL.md").write_text(seed["replacement"])
            git("add", ".")
            git("commit", "-qm", "new fixture source")
        elif scenario == "missing":
            (skills / "topic/references/guide.md").unlink()
            assert not (skills / "topic/references/guide.md").exists()
        elif scenario == "edited":
            assert seed["replacement"] != members["SKILL.md"]
            (skills / "topic/SKILL.md").write_text(seed["replacement"])
        elif scenario == "unmanaged":
            ledger.unlink()
            assert not ledger.exists() and (skills / "topic/SKILL.md").exists()
        elif scenario in ("modified-orphan", "prune"):
            shutil.rmtree(source / "old")
            git("add", ".")
            git("commit", "-qm", "remove owned source package")
            operation = "refresh"
            if scenario == "modified-orphan":
                assert seed["replacement"] != seed["orphan"]
                orphan.write_text(seed["replacement"])
        revision = git("rev-parse", "HEAD")
        root.joinpath(".cpp-host-update-fixture").write_bytes(b"cpp-host-update-fixture-v1\n")
        descriptor = {"schema": 1, "source": "source", "revision": revision, "adapters": [{
            "harness": "fixture-a", "selected": True, "source": "source", "install": "a/skills",
            "ledger": "a/skills/.managed/ownership.json", "lock": "a/.install.lock",
            "work": "a/skills/.managed/work", "packages": [{"name": "topic", "canonical_source": "fixture/topic",
                "members": {name: {"source": f"topic/{name}"} for name in members}}],
        }]}
        (root / "fixture.json").write_text(json.dumps(descriptor))
        lock = root / "a/.install.lock"
        lock_fd = None
        if scenario == "locked":
            lock.touch(mode=0o600)
            lock_fd = os.open(lock, os.O_RDWR)
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            probe = os.open(lock, os.O_RDONLY)
            try:
                try:
                    fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise AssertionError("exclusive-lock precondition not established")
            finally:
                os.close(probe)
        if scenario == "no-lock":
            assert not lock.exists()
        before = inventory(root / "a")
        try:
            result = subprocess.run([sys.executable, str(gate), operation, "--fixture-root", str(root),
                                     "--lock-timeout", "0.05", "--json"], capture_output=True, text=True, timeout=20)
        finally:
            if lock_fd is not None:
                os.close(lock_fd)
        # Oracle failures are NOT a detector finding: suppress the subject's
        # output so a failed preservation assertion cannot look like detection.
        try:
            assert inventory(foreign.parent) == before_foreign
            if scenario in ("no-lock", "locked"):
                assert inventory(root / "a") == before
            if scenario == "modified-orphan":
                assert orphan.read_text() == seed["replacement"]
            if scenario == "prune":
                assert not orphan.parent.exists()
        except (AssertionError, OSError) as exc:
            print(f"CONTROL_ORACLE_FAILED: {type(exc).__name__}")
            return 9
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

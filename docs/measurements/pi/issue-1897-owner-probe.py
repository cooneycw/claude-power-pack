#!/usr/bin/env python3
"""One-use #1897 host-helper probe. Read the adjacent protocol before execution.

No pi process is started. An operator must hold an exclusive writer window
through installation, manual reload observations, and lock-path removal.
Committed opposite cases: tests/test_pi_owner_probe.py.
"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path

REVISION = "c434101e7ae580de3bb81ca1db9d325a0483c44c"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def physical(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "absolute physical path required")
    # Make expands its variable values before shell parsing. Keep the one-use
    # batch's reviewed path bindings free of Make/shell metacharacters.
    require(re.fullmatch(r"/[A-Za-z0-9_./-]+", str(path)), "unsupported path characters")
    for prefix in reversed([path, *path.parents]):
        require(not prefix.is_symlink(), "path alias refused")
    return path


def manifest(path):
    """Only the fixed CPP paths; never enumerate the agent or personal skills."""
    if not os.path.lexists(path):
        return {}
    rows = {}

    def visit(node):
        info = node.lstat()
        require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),
                "nonregular scoped artifact refused")
        row = {"mode": stat.S_IMODE(info.st_mode), "dev": info.st_dev,
               "ino": info.st_ino, "kind": "dir" if node.is_dir() else "file"}
        if row["kind"] == "file":
            require(info.st_nlink == 1, "hard-linked scoped file refused")
            row.update(sha256=hashlib.sha256(node.read_bytes()).hexdigest(),
                       mtime_ns=info.st_mtime_ns)
        rows[str(node.relative_to(path))] = row
        if row["kind"] == "dir":
            for child in sorted(node.iterdir()):
                visit(child)

    visit(path)
    return rows


def state(targets):
    return {str(path): manifest(path) for path in targets}


def projected(tree):
    return {name: {key: value for key, value in row.items()
                   if key in ("mode", "kind", "sha256")} for name, row in tree.items()}


def installer_expected(tree):
    """Build-directory umask is irrelevant; actual installed modes still matter."""
    rows = projected(tree)
    for row in rows.values():
        row["mode"] = 0o755 if row["kind"] == "dir" else 0o644
    return rows


def save(path, value):
    """Private scratch journal: exclusive creation, flush before proceeding."""
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    for directory in (path.parent, path.parent.parent):
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def undo(targets, sealed, locks):
    """No creation and no deletion until every path and all locks match."""
    descriptors = []
    try:
        require(state(targets) == sealed, "undo refused: scoped post-state changed")
        for path in locks:
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            descriptors.append(fd)
            opened = os.fstat(fd)
            require(stat.S_ISREG(opened.st_mode), "undo lock is not regular")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            current = path.lstat()
            require((opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino),
                    "undo lock identity changed")
        require(state(targets) == sealed, "undo refused: scoped post-state changed")
        # The operator's exclusive window is essential: advisory locks cannot
        # protect against another process opening a replacement lock inode.
        for target in targets:
            rows = sealed[str(target)]
            for relative in sorted(rows, key=lambda item: len(Path(item).parts), reverse=True):
                path = target if relative == "." else target / relative
                if rows[relative]["kind"] == "file":
                    path.unlink()
                else:
                    path.rmdir()
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def run(args):
    source, home, agent, journal = map(physical, (args.source, args.home, args.agent, args.journal))
    require(args.exclusive_window_confirmed, "exclusive writer window must be confirmed")
    require(source.is_dir() and home.is_dir() and agent.is_dir(), "existing roots required")
    for left, right in ((journal, home), (journal, agent), (journal, source),
                        (source, home), (source, agent)):
        require(not left.is_relative_to(right) and not right.is_relative_to(left),
                "source/journal must be disjoint from owner roots")
    require(not os.path.lexists(journal), "journal must be a new private scratch path")
    skills = physical(agent / "skills")
    primary = physical(agent / ".cpp-skills.lock")
    management = physical(skills / ".cpp-managed")
    require(not os.path.lexists(primary) and not os.path.lexists(management),
            "preflight refused: CPP state already exists")
    require(not os.path.lexists(skills) or skills.is_dir(), "skills root must be a directory")
    # Do not inherit the owner environment. CLI selection uses explicit --home
    # and --agent-dir; subprocess HOME/history/XDG all belong to private scratch.
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
           "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1"}

    def git(*arguments):
        return subprocess.check_output(["git", "-c", "core.fsmonitor=false", "-C", str(source),
                                        *arguments], env=env, text=True).strip()

    require(git("rev-parse", "HEAD") == REVISION, "wrong source revision")
    require(not git("status", "--porcelain"), "source must be clean")
    journal.mkdir(mode=0o700)
    for name in ("home", "history", "config", "data", "cache"):
        (journal / name).mkdir(mode=0o700)
    env.update(HOME=str(journal / "home"), PI_CODING_AGENT_DIR=str(agent),
               PI_CODING_AGENT_SESSION_DIR=str(journal / "history"),
               XDG_CONFIG_HOME=str(journal / "config"), XDG_DATA_HOME=str(journal / "data"),
               XDG_CACHE_HOME=str(journal / "cache"))

    def call(target, index, expected=0):
        argv = ["make", "--no-print-directory", "-s", "-C", str(source), target]
        if target != "pi-skills":
            argv.append("PI_SKILL_ARGS=" + shlex.join([
                "--root", str(source), "--revision", REVISION, "--home", str(home),
                "--agent-dir", str(agent), "--session-dir", str(journal / "history"), "--json"]))
        result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120)
        save(journal / f"command-{index}.json", {"argv": argv, "make_exit": result.returncode,
                                               "stdout": result.stdout, "stderr": result.stderr})
        if target == "pi-skills":
            require(result.returncode == 0, "fresh build failed; see private journal")
            return None
        report = json.loads(result.stdout)
        require(report["exit_code"] == expected and (result.returncode == 0) == (expected == 0),
                "CLI verdict unexpected; stop for recovery review")
        return report

    call("pi-skills", "build")
    fresh = source / "pi/skills"
    slugs = sorted(path.name for path in fresh.iterdir() if path.is_dir() and not path.name.startswith("."))
    require(len(slugs) == 18, "expected exactly 18 topic skills")
    expected = {slug: manifest(fresh / slug) for slug in slugs}
    require(sum(row["kind"] == "file" for tree in expected.values() for row in tree.values()) == 36,
            "expected exactly 36 fresh members")
    targets = [physical(skills / slug) for slug in slugs] + [management, primary]
    before = state(targets)
    require(all(not value for value in before.values()), "preflight refused: target or CPP state exists")
    skills_before = skills.lstat() if skills.exists() else None
    require(not git("status", "--porcelain"), "build dirtied source")
    save(journal / "before-and-undo.json", {
        "revision": REVISION, "source": str(source), "agent": str(agent), "home": str(home),
        "targets": [str(path) for path in targets], "before": before,
        "skills_existed": skills_before is not None, "expected": expected,
        "inverse": "After verify and manual reload presence, acquire all three existing locks without "
                   "creation; require entire sealed post-state unchanged; unlink only recorded regular "
                   "files and rmdir recorded directories deepest first. Remove newly created skills "
                   "root only if empty. Reload again. Any failure stops for recovery review; no broad deletion.",
        "exclusive_window": True})
    require(state(targets) == before, "pre-state changed before installation")
    call("pi-skills-install", "install")
    report = call("pi-skills-verify", "verify")
    require(report["after"]["expected_packages"] == 18 and
            report["after"]["expected_members"] == report["after"]["examined_members"] == 36,
            "full verification counts required")
    # Compare actual file population/bytes/modes independently of inode identity.
    for slug in slugs:
        actual = manifest(skills / slug)

        require(projected(actual) == installer_expected(expected[slug]), "installed bytes/modes differ")
    sealed = state(targets)
    save(journal / "sealed-post.json", sealed)
    print("In the EXISTING pi session: /reload now and capture the skill list. Confirm all 18 topics.", flush=True)
    require(input("After capture, type RELOAD-PRESENCE-CAPTURED to authorize the logged undo: ") ==
            "RELOAD-PRESENCE-CAPTURED", "undo not authorized; installed state retained")
    save(journal / "reload-presence.json", {"operator_confirmed": True, "slugs": slugs})
    locks = [primary, management / ".ownership.json.cpp-lock", management / ".work.cpp-lock"]
    undo(targets, sealed, locks)
    if skills_before is None:
        skills.rmdir()  # Refuses if an unrelated child appeared; never deletes it.
    else:
        now = skills.lstat()
        require((now.st_dev, now.st_ino, stat.S_IMODE(now.st_mode)) ==
                (skills_before.st_dev, skills_before.st_ino, stat.S_IMODE(skills_before.st_mode)),
                "skills root identity/mode changed")
    require(state(targets) == before, "scoped baseline not restored")
    absent = call("pi-skills-verify", "after-undo", expected=1)
    require(absent["after"]["expected_packages"] == 18 and absent["after"]["examined_members"] == 0,
            "expected missing-installed verdict after undo")
    require(state(targets) == before, "verification left scoped artifacts")
    save(journal / "scoped-restored.json", {"before": before, "after": state(targets)})
    print("In the SAME existing pi session: /reload again and capture the skill list; "
          "compare with baseline.", flush=True)
    require(input("After capture, type RELOAD-BASELINE-CAPTURED: ") == "RELOAD-BASELINE-CAPTURED",
            "filesystem restored; second reload evidence still pending")
    save(journal / "reload-baseline.json", {"operator_confirmed": True})
    print("Scoped filesystem restored. Owner sign-off remains separate; #1896 has two UNKNOWN measurements.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("source", "home", "agent", "journal"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--exclusive-window-confirmed", action="store_true")
    try:
        run(parser.parse_args())
    except (ValueError, OSError, subprocess.SubprocessError, EOFError) as error:
        print(f"STOP: {error}. Retain the private journal; no automatic recovery deletion.", file=sys.stderr)
        sys.exit(1)

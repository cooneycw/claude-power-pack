#!/usr/bin/env python3
"""Fixture TUI /reload probe; never merge. No model turn or owner install.

Commands: create; launch ROOT; remove ROOT; restore ROOT; cleanup ROOT.
The helper launches the TUI in a separate fixture session, never in this worker.
Capture only fixture UI. Observe presence, removal, then restoration with /reload.
No automatic success verdict is inferred from an absent UI section.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

MARKER = "cpp-pi-reload-fixture-v1"
SKILL = "---\nname: cpp-probe-reload\ndescription: CPP isolated reload probe\n---\nFixture only. Do not execute commands or request a provider turn.\n"


def owned(value):
    root = Path(value)
    if not root.is_absolute() or root.parent != Path("/tmp") or not root.name.startswith("cpp-pi-reload.") or root.is_symlink():
        raise ValueError("not a direct private fixture root")
    if (root / ".probe-owner").is_symlink() or (root / ".probe-owner").read_text() != MARKER:
        raise ValueError("fixture ownership marker mismatch")
    return root


def restore(root):
    target = root / "agent/skills/cpp-probe-reload"
    for entry in [root / "agent", root / "agent/skills", target]:
        if entry.is_symlink():
            raise ValueError("fixture symlink refused")
    target.mkdir(parents=True, exist_ok=True)
    file = target / "SKILL.md"
    if file.is_symlink() or file.exists():
        raise ValueError("refuse overwrite; remove only the known fixture first")
    file.write_text(SKILL)
    file.chmod(0o644)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "launch", "remove", "restore", "cleanup"])
    parser.add_argument("root", nargs="?")
    parser.add_argument("--help-reviewed", action="store_true")
    args = parser.parse_args()
    if args.action == "create":
        root = Path(tempfile.mkdtemp(prefix="cpp-pi-reload.", dir="/tmp"))
        root.chmod(0o700)
        (root / ".probe-owner").write_text(MARKER)
        print("ROOT", root, flush=True)
        print("UNDO after fixture TUI exit: python3 THIS_FILE cleanup", root, flush=True)
        for name in ["home", "agent", "work", "config", "data", "cache", "history"]:
            (root / name).mkdir(mode=0o700)
        restore(root)
        print("CREATED fixture skill; use launch in helper-owned fixture TUI")
        return
    root = owned(args.root or "")
    target = root / "agent/skills/cpp-probe-reload"
    if args.action == "remove":
        file = target / "SKILL.md"
        if target.is_symlink() or file.is_symlink() or file.read_text() != SKILL:
            raise ValueError("known fixture changed; refuse removal")
        file.unlink()
        target.rmdir()
        print("REMOVED; type /reload in fixture TUI and retain observation")
    elif args.action == "restore":
        restore(root)
        print("RESTORED; type /reload and retain positive reappearance")
    elif args.action == "cleanup":
        # root is exclusively created by this probe, never an owner installation.
        shutil.rmtree(root)
        print("UNDO_EXECUTED", root, "ABSENT", not root.exists())
    elif args.action == "launch":
        if not args.help_reviewed:
            parser.error("hold until help reviewed, then --help-reviewed")
        binary = shutil.which("pi")
        if not binary:
            raise ValueError("pi unavailable")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "TERM": os.environ.get("TERM", "xterm-256color")}
        env.update(HOME=str(root / "home"), PI_CODING_AGENT_DIR=str(root / "agent"),
                   PI_CODING_AGENT_SESSION_DIR=str(root / "history"), PI_OFFLINE="1",
                   XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(root / "data"),
                   XDG_CACHE_HOME=str(root / "cache"))
        print("Fixture-only TUI; /reload, presence -> external remove -> /reload -> restore -> /reload; then exit.", flush=True)
        subprocess.run([binary, "--offline", "--no-session"], cwd=root / "work", env=env, check=False)


if __name__ == "__main__":
    main()

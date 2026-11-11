#!/usr/bin/env python3
"""Tripwire: no tracked file carries a host account's name in a home path (issue #1689).

This repository is public, and its tools record where they ran. Before #1689,
29 tracked files spelled out the local account of the machine the work ran on:
as a home directory (slash, `home`, slash, the account), or as the directory
name Claude and Qwen give a project's transcripts (dash, `home`, dash, the
account, dash). Counter-model receipts, an execution-evidence record, a
skill-coverage snapshot, issue snapshots and research notes all carried one.
#1689 replaced them and changed the writers; this tripwire exists so the next
one cannot land unnoticed.

WHAT IS MATCHED. A home-directory path whose account component is not on the
placeholder list below, in either spelling:

  * the plain form, under `/home/` or `/Users/`;
  * the encoded form, a path component beginning `-home-<account>` or
    `-Users-<account>`, which is how a working directory is turned into a
    transcript directory name.

The match is on the SHAPE, never on the account running the check. A check
keyed on the running account would see nothing in CI, where the account is a
different one, and would report clean over exactly the files it exists to
catch.

THE PLACEHOLDER LIST NARROWS THE CHECK, ON PURPOSE, AND FAILS LOUDLY. Documents
and fixtures legitimately write example paths. A name on the list is a
stand-in nobody logs in as; any other name is reported, so a new placeholder
turns the gate red until it is added here deliberately.

THE POPULATION IS `git ls-files`, so an untracked scratch file or an ignored
virtualenv cannot fail the gate, and the count examined is printed on every
verdict. Zero files, or a `git` that cannot be run, is UNKNOWN (exit 2), never
clean: "nothing matched" and "nothing was read" are otherwise the same line.

`controls/host-account-paths/` is excluded from a whole-repository run because
its bad case is, by construction, a file this check must report. Pointing
`--root` AT a case examines that case.

Usage:
    python3 scripts/check-host-account-paths.py
    python3 scripts/check-host-account-paths.py --root DIR

Output: one `HOST_ACCOUNT_PATH:` line per finding, a
`HOST_ACCOUNT_PATHS_EXAMINED:` count, then a verdict line.
Exit 0 clean, 1 findings, 2 unknown.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

#: NEGATIVE-CONTROL: controls/host-account-paths

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Stand-in account names. Nobody's real account; safe to publish.
PLACEHOLDERS = frozenset(
    {
        "user", "username", "me", "you", "someone", "somebody", "example",
        "clean", "test", "tester", "claude", "codex", "agent", "dev",
        "runner", "node", "ubuntu", "app", "worker", "ci", "alice", "bob",
        "name", "account", "home", "x", "u",
    }
)

_ACCOUNT = r"([A-Za-z_][A-Za-z0-9_]*)"
#: The plain form. The lookbehind keeps `xx/home/...` inside a longer word out.
#: The lookahead leaves out a FILE that sits directly in the homes directory
#: (`AGENTS.md` under `/home`), which is a file name and not an account.
PLAIN_RE = re.compile(r"(?<![A-Za-z0-9_.-])/(?:home|Users)/" + _ACCOUNT + r"(?![A-Za-z0-9_]|\.[A-Za-z0-9])")
#: The encoded form: a component that begins with the encoded home directory.
ENCODED_RE = re.compile(r"(?<![A-Za-z0-9_])-(?:home|Users)-" + _ACCOUNT + r"(?=[-/\"'\s]|$)")

#: The control's own cases are files this check must report.
CONTROL_PREFIX = "controls/host-account-paths/"


def findings_in(text: str) -> list[tuple[int, str]]:
    """(line number, account) for every non-placeholder account in a home path."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        for pattern in (PLAIN_RE, ENCODED_RE):
            for match in pattern.finditer(line):
                account = match.group(1)
                if account.lower() not in PLACEHOLDERS:
                    found.append((number, account))
    return found


def tracked_files(root: Path) -> list[str] | None:
    """Tracked paths under `root`, relative to it; None when git cannot say."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--", "."],
            cwd=root, capture_output=True, text=True, check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return [name for name in proc.stdout.split("\0") if name]


def run_check(root: Path) -> int:
    names = tracked_files(root)
    if names is None:
        print(
            "host-account-paths: `git ls-files` could not be run - UNKNOWN, not clean. "
            "The tracked population could not be established.",
            file=sys.stderr,
        )
        return 2
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root, capture_output=True, text=True, check=False,
        ).stdout.strip()
        prefix = root.resolve().relative_to(Path(top).resolve()).as_posix() if top else "."
    except (OSError, ValueError):
        prefix = "."
    prefix = "" if prefix == "." else prefix + "/"

    examined = 0
    unreadable: list[str] = []
    findings = 0
    for name in names:
        # Skip the control's cases only when they are reached from outside it.
        if (prefix + name).startswith(CONTROL_PREFIX) and not prefix.startswith(CONTROL_PREFIX):
            continue
        path = root / name
        if path.is_symlink() or not path.is_file():
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            unreadable.append(name)
            continue
        if b"\0" in raw[:8192]:
            continue  # binary
        examined += 1
        for number, account in findings_in(raw.decode("utf-8", "replace")):
            print(f"HOST_ACCOUNT_PATH: {name}:{number}: home path names account `{account}`")
            findings += 1

    print(f"HOST_ACCOUNT_PATHS_EXAMINED: {examined}")
    if unreadable:
        print(
            f"host-account-paths: {len(unreadable)} tracked file(s) could not be read "
            f"({', '.join(unreadable[:5])}) - UNKNOWN, not clean.",
            file=sys.stderr,
        )
        return 2
    if examined == 0:
        print(
            "host-account-paths: no tracked text file was examined - UNKNOWN, not clean.",
            file=sys.stderr,
        )
        return 2
    if findings:
        print(
            f"host-account-paths: {findings} finding(s). Replace the account with a "
            "placeholder such as `user`, or fix the tool that recorded it. Add a name to "
            "PLACEHOLDERS only if nobody logs in as it."
        )
        return 1
    print(
        f"host-account-paths: ok - {examined} tracked text file(s) examined, no home "
        "path names an account outside the placeholder list."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="tree to examine")
    args = parser.parse_args(argv)
    return run_check(args.root.resolve())


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Fixture-only B2 rule mutation/undo; never starts pi or reads session/auth files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path

RULES = ("AGENTS.md", "AGENTS.override.md")
CONTEXT_NAMES = ("AGENTS.override.md", "AGENTS.md", "AGENTS.MD", "CLAUDE.md", "CLAUDE.MD")
FIXTURES = Path(__file__).with_name("issue-1899-b2-fixtures")
CASES = {
    "absent": {},
    "base": {RULES[0]: "base.md"},
    "override": {RULES[1]: "override.md"},
    "both": {RULES[0]: "base.md", RULES[1]: "override.md"},
    "empty": {RULES[0]: "base.md", RULES[1]: "empty.md"},
    **{f"{kind}-{size}": {RULES[index]: f"size-{size}.md"}
       for kind, index in [("base", 0), ("override", 1)]
       for size in [8192, 32768, 65536]},
}


def regular_bytes(path: Path, limit: int = 131072) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError(f"not a regular file: {path.name}")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"oversized input: {path.name}")
        return data
    finally:
        os.close(fd)


def fixture_bytes(name: str) -> bytes:
    allowed = {item for case in CASES.values() for item in case.values()}
    if name not in allowed:
        raise ValueError("unrecognized fixture")
    manifest = json.loads(regular_bytes(FIXTURES / "manifest.json"))
    data = regular_bytes(FIXTURES / name)
    if manifest[name] != {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}:
        raise ValueError("fixture manifest mismatch")
    return data


def paths(root: Path) -> tuple[Path, Path]:
    if not root.is_absolute():
        raise ValueError("root must be absolute")
    for path in [root, root / "agent", root / "work"]:
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise ValueError("probe directories must be real, existing directories")
    return root / "agent", root / "work" / "pi-1899-b2-state.json"


def verify_context_ancestors(root: Path) -> None:
    """Presence-only check of pi's documented candidates on the known cwd chains."""
    for slug in ["repo-alpha", "repo-beta"]:
        cwd = root / "work" / slug
        if not stat.S_ISDIR(cwd.lstat().st_mode):
            raise ValueError("scratch repository must be a real directory")
        for directory in [cwd, *cwd.parents]:
            for name in CONTEXT_NAMES:
                try:
                    os.lstat(directory / name)
                except FileNotFoundError:
                    continue
                raise ValueError("ancestor context present; stop for relocation review")


def verify_rules(agent: Path, expected: dict[str, str]) -> None:
    """Preflight BOTH named paths before any rule mutation; never inspect neighbors."""
    for name in RULES:
        path = agent / name
        try:
            observed = path.lstat()
        except FileNotFoundError:
            if name in expected:
                raise ValueError("recorded rule disappeared: " + name) from None
            continue
        if name not in expected:
            raise ValueError("unexpected existing rule: " + name)
        if not stat.S_ISREG(observed.st_mode) or stat.S_IMODE(observed.st_mode) != 0o644:
            raise ValueError("rule type/mode changed: " + name)
        if regular_bytes(path) != fixture_bytes(expected[name]):
            raise ValueError("rule bytes changed: " + name)


def create(path: Path, data: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def publish_state(path: Path, data: dict) -> None:
    pending = path.with_suffix(".pending")
    create(pending, json.dumps(data, sort_keys=True).encode() + b"\n", 0o600)
    os.replace(pending, path)


def prepare(root: Path) -> dict:
    agent, state = paths(root)
    verify_context_ancestors(root)
    if os.path.lexists(state) or os.path.lexists(state.with_suffix(".pending")):
        raise ValueError("B2 state already exists; stop, do not retry preparation")
    verify_rules(agent, {})
    for item in {name for case in CASES.values() for name in case.values()}:
        fixture_bytes(item)
    result = {"phase": "stable", "rules": {}}
    create(state, json.dumps(result).encode() + b"\n", 0o600)
    return result


def check_t1(root: Path) -> dict:
    """Read-only resumption of the master's reported zero-turn, prepared T1 state."""
    agent, state = paths(root)
    verify_context_ancestors(root)
    observed = json.loads(regular_bytes(state))
    if observed != {"phase": "stable", "rules": {}}:
        raise ValueError("not the approved stable/empty T1 state; stop for review")
    verify_rules(agent, {})
    return observed


def apply_case(root: Path, case: str) -> dict:
    agent, state = paths(root)
    verify_context_ancestors(root)
    before = json.loads(regular_bytes(state))
    if before.get("phase") != "stable" or before.get("rules") not in CASES.values():
        raise ValueError("incomplete/invalid B2 state; stop for manual review")
    previous = before["rules"]
    desired = CASES[case]
    verify_rules(agent, previous)
    contents = {name: fixture_bytes(item) for name, item in desired.items()}
    # A stopped write leaves a non-success journal. No automatic recovery/adoption.
    publish_state(state, {"phase": "blocked", "before": previous, "requested": desired})
    for name in RULES:
        if previous.get(name) == desired.get(name):
            continue
        if name in previous:
            (agent / name).unlink()
        if name in desired:
            create(agent / name, contents[name], 0o644)
    verify_rules(agent, desired)
    result = {"phase": "stable", "rules": desired}
    publish_state(state, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare", "set", "check-t1"])
    parser.add_argument("case", nargs="?", choices=sorted(CASES))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if (args.operation == "set") != (args.case is not None):
        parser.error("set requires a case; prepare/check-t1 take no case")
    try:
        if args.operation == "prepare":
            result = prepare(args.root)
        elif args.operation == "check-t1":
            result = check_t1(args.root)
        else:
            result = apply_case(args.root, args.case)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"STOP: {error}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

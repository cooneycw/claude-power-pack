#!/usr/bin/env python3
"""Resolve one codex 5.3 ID from pi's offline CLI listing; never read model/auth stores."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

HEADER = ["provider", "model", "context", "max-out", "thinking", "images"]
PIN_NAME = "pi-1899-b2-model-pin.json"
ID = re.compile(r"[a-z][a-z0-9-]*/[A-Za-z0-9._-]+\Z")


def candidates(output: str) -> list[str]:
    lines = [line.split() for line in output.splitlines() if line.strip()]
    if not lines or lines[0] != HEADER:
        raise ValueError("offline model listing missing expected header; stop")
    matches = []
    for row in lines[1:]:
        if (len(row) != 6 or row[4] not in ["yes", "no"] or row[5] not in ["yes", "no"]
                or not ID.fullmatch(row[0] + "/" + row[1])):
            raise ValueError("offline model listing has an unsupported row; stop")
        model = row[1].lower()
        if "codex" in model and re.search(r"(?<![0-9])5\.3(?![0-9])", model):
            matches.append(row[0] + "/" + row[1])
    return matches


def unique_pin(output: str) -> dict[str, str]:
    matches = candidates(output)
    if len(matches) != 1:
        raise ValueError("codex 5.3 selection requires exactly one listed provider/id")
    return {"id": matches[0], "listing_sha256": hashlib.sha256(output.encode()).hexdigest(),
            "source": "pi --offline --list-models 5.3"}


def pin_path(root: Path) -> Path:
    if not root.is_absolute():
        raise ValueError("probe root must be absolute")
    for path in [root, root / "home", root / "agent", root / "work",
                 root / "config", root / "data", root / "cache", root / "tmp",
                 root / "work/repo-alpha"]:
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise ValueError("probe paths must be existing real directories")
    return root / "work" / PIN_NAME


def read_pin(root: Path) -> str:
    path = pin_path(root)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("model pin must be a regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError("oversized model pin")
        pin = json.loads(raw)
    finally:
        os.close(fd)
    if (not isinstance(pin, dict) or set(pin) != {"id", "listing_sha256", "source"}
            or pin["source"] != "pi --offline --list-models 5.3"
            or not isinstance(pin["listing_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", pin["listing_sha256"])
            or not isinstance(pin["id"], str) or not ID.fullmatch(pin["id"])):
        raise ValueError("malformed model pin; stop")
    return pin["id"]


def resolve(root: Path) -> dict[str, str]:
    target = pin_path(root)
    # Exclusive reservation stops reruns before invoking pi; a failed attempt
    # leaves an invalid empty pin for manual review, never an automatic retry.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        env = {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8", "NO_COLOR": "1",
               "HOME": str(root / "home"), "PI_CODING_AGENT_DIR": str(root / "agent"),
               "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"),
               "XDG_CACHE_HOME": str(root / "cache"), "TMPDIR": str(root / "tmp")}
        result = subprocess.run(
            ["pi", "--offline", "--no-session", "--no-tools", "--no-mcp", "--no-extensions",
             "--no-skills", "--no-context-files", "--list-models", "5.3"],
            cwd=root / "work/repo-alpha", env=env, capture_output=True, text=True, timeout=30,
            stdin=subprocess.DEVNULL, check=False)
        if result.returncode or result.stderr.strip():
            raise ValueError("offline listing failed or emitted diagnostics; stop, no retry")
        matches = candidates(result.stdout)
        print(json.dumps({"matching_provider_ids": matches}), flush=True)
        pin = unique_pin(result.stdout)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(json.dumps(pin, sort_keys=True).encode() + b"\n")
            stream.flush()
            os.fsync(fd)
        return pin
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["resolve", "read"])
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.operation == "resolve":
            print(json.dumps(resolve(args.root), sort_keys=True))
        else:
            print(read_pin(args.root))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"STOP: {type(error).__name__}: model pin unavailable; route to master\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Private project run state for cpp:init across fresh harness shells (#1587 R2).

This persists fixed observations, not credentials, endpoints or live readiness.
The caller binds the returned absolute run path explicitly in every tool call.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

#: HOST-SURFACE: none - writes explicitly selected project run artifacts only.
#: NEGATIVE-CONTROL: controls/cpp-mcp-state
STEPS = {"second-opinion", "playwright", "tavily", "sequential-thinking", "browser-pool",
         "codex-second-opinion", "codex-playwright"}
OUTCOMES = {"installed", "already", "skipped", "declined", "FAILED", "unverified"}


def checked(data: object) -> list[dict]:
    if not isinstance(data, list):
        raise ValueError("not an array")
    seen = set()
    for row in data:
        if not isinstance(row, dict) or set(row) - {"step", "outcome", "exit_code"}:
            raise ValueError("invalid fields")
        step, outcome = row.get("step"), row.get("outcome")
        if not isinstance(step, str) or step not in STEPS or step in seen:
            raise ValueError("invalid step")
        if not isinstance(outcome, str) or outcome not in OUTCOMES:
            raise ValueError("invalid outcome")
        code = row.get("exit_code")
        if code is not None and (type(code) is not int or not 0 <= code <= 255):
            raise ValueError("invalid exit")
        if code:
            row["outcome"] = "FAILED"
        seen.add(step)
    return data


def read(path: Path, *, pending: bool = False) -> list[dict]:
    if (path / "results.json").is_symlink() or (not pending and (path / "pending").exists()):
        raise ValueError("unavailable state")
    return checked(json.loads((path / "results.json").read_text()))


def begin(document: Path, project: Path) -> Path:
    bodies = re.findall(r"^# CPP_MCP_ROUTINES_BEGIN\n(.*?)^# CPP_MCP_ROUTINES_END$",
                        document.read_text(), re.M | re.S)
    if len(bodies) != 1:
        raise ValueError("invalid source")
    base = project / ".claude/cpp-init-mcp"
    if base.is_symlink():
        raise ValueError("invalid destination")
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="run-", dir=base)).resolve()
    script = path / "routines.sh"
    # Pin the verified state helper path, independently of later shell bindings.
    prefix = "CPP_MCP_STATE_HELPER=" + shlex.quote(str(Path(__file__).resolve())) + "\n"
    script.write_text(prefix + bodies[0])
    script.chmod(0o600)
    results = path / "results.json"
    results.write_text("[]")
    results.chmod(0o600)
    return path


def save(path: Path, rows: list[str]) -> None:
    read(path, pending=True)
    data = checked([json.loads(row) for row in rows])
    fd, name = tempfile.mkstemp(prefix="results-", dir=path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path / "results.json")
    finally:
        Path(name).unlink(missing_ok=True)
    (path / "pending").unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    initial = commands.add_parser("begin")
    initial.add_argument("--document", required=True, type=Path)
    initial.add_argument("--project-dir", required=True, type=Path)
    for verb in ("load", "attempt", "save"):
        sub = commands.add_parser(verb)
        sub.add_argument("--run-dir", required=True, type=Path)
        if verb == "save":
            sub.add_argument("rows", nargs="*")
    args = parser.parse_args()
    try:
        if args.command == "begin":
            print(begin(args.document, args.project_dir))
        elif args.command == "load":
            for row in read(args.run_dir):
                print(row["step"] + "\t" + json.dumps(row, separators=(",", ":")))
        elif args.command == "attempt":
            read(args.run_dir)
            with (args.run_dir / "pending").open("x", encoding="utf-8") as stream:
                stream.write("registration pending\n")
        else:
            save(args.run_dir, args.rows)
    except (OSError, ValueError, TypeError):
        print("CPP_MCP_STATE: unavailable - " + args.command, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

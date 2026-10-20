#!/usr/bin/env python3
#: HOST-SURFACE: ~/.codex/AGENTS.md owner=cpp write=replace certified=authored mode=--write
#: HOST-SURFACE: ~/.codex/AGENTS.md.pre-cpp-<timestamp> owner=cpp write=copy certified=authored mode=--write --adopt
"""Build Codex's global instructions from Claude's, and report when they drift (issue #1441).

Claude reads `~/.claude/CLAUDE.md` in every directory; Codex reads
`~/.codex/AGENTS.md`. Both are host files, hand-written, and nothing compared
them - so they drifted. Measured on 2026-10-12: the two disagreed on the Nit Store
format ("one finding per comment" against "group related findings into a concise
comment"), and Codex had never been given the Negative Control directive at all.

#1071 solved the same problem INSIDE a repository with a thin `AGENTS.md` that
points at `CLAUDE.md`. A pointer is rejected here: it works only if Codex chooses
to open the other file, and #1071 already found Codex sessions stopping at a thin
`AGENTS.md` unless told to follow it (`scripts/codex-skill-sync.py`, the
`CLAUDE.md` rewrite rule). A skipped read looks exactly like compliance. So the
rules are COPIED:

    ~/.codex/AGENTS.md = generated header
                       + ~/.claude/CLAUDE.md, verbatim
                       + "Codex-only additions" from ~/.codex/AGENTS.local.md

The additions file is the owner's, on the host, never in this repository: it holds
personal text (a standing authorisation, say), and CPP is a shared pack. It is
deliberately not `AGENTS.override.md` - Codex reads that file INSTEAD of
`AGENTS.md`, which would discard every copied rule.

## Modes

`--check` (the default) is REPORT-ONLY and writes nothing. One verdict line:

| verdict | exit | meaning |
|---|---|---|
| `current` | 0 | the file is exactly what `--write` would produce now |
| `stale` | 3 | built by this script, but CLAUDE.md or the additions changed since |
| `hand-edited` | 3 | built by this script, then edited by hand - a rebuild would discard the edit |
| `unmanaged` | 3 | a file this script did not build |
| `absent` | 3 | `~/.codex` exists and holds no `AGENTS.md` |
| `overridden` | 3 | a non-empty `~/.codex/AGENTS.override.md` exists; Codex reads it INSTEAD |
| `not-applicable` | 5 | no `~/.codex` directory - Codex is not set up on this host |
| `unknown` | 4 | `~/.claude/CLAUDE.md`, the target, or an EXISTING additions file could not be read |

`hand-edited` is reported before `stale` when both hold: the edit is the fact a
rebuild would destroy, so it is the one the owner needs first.

`--write` builds the file. It REFUSES (exit 3) to replace an `unmanaged` or
`hand-edited` file unless `--adopt` is passed, which first saves the existing file
as `AGENTS.md.pre-cpp-<UTC timestamp>` beside it. It never creates `~/.codex`.

## What the check does NOT establish

That Codex READS the file, or obeys it. It checks the selected Codex home, including a relocated `CODEX_HOME`.
Whether Codex reads or obeys it is a property of another program.
On 2026-10-12 a phrase probe (#1441) showed Codex 0.162.1 loading
`~/.codex/AGENTS.md` in every directory tried; this script does not re-measure it.

Any `AGENTS.md` sitting directly in `$HOME` or the projects directory is LISTED
(`WORKSPACE_AGENTS_MD:`) and never affects the verdict: the same probe found such
a file reaches Codex only when started in that directory, and Claude only in
repositories without their own `CLAUDE.md`. That reach is the reason to know it
is there, not something this script can repair.

Usage:
    codex-global-agents.py [--check] [--home DIR] [--projects DIR] [--quiet]
    codex-global-agents.py --write [--adopt] [--home DIR]
"""

#: NEGATIVE-CONTROL: controls/codex-global-agents
#:     Its verdict reaches the owner through /cpp:status, which nothing
#:     downstream re-derives. A blind version - "a Codex file exists, so Codex
#:     has its instructions" - is exactly the status quo that let the two files
#:     contradict each other unseen, and it is the control's anchor.

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MARKER = "cpp-codex-global-agents"
EXTRAS_HEADING = "## Codex-only additions"
#: Codex's documented default cap for instruction documents. Whether it applies
#: to the global file is Codex's business; past it, the copy may be truncated.
CODEX_DOC_LIMIT = 32 * 1024

EXIT_OK, EXIT_DRIFT, EXIT_UNKNOWN, EXIT_NA = 0, 3, 4, 5


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def read_optional(path: Path) -> tuple[bool, str | None]:
    """(readable, text) for an optional input; an absent file is readable and None.

    A file that EXISTS but cannot be read is not absent: treating it as absent would
    build without the owner's additions and then call the result current.
    """
    if not os.path.lexists(path):  # a dangling symlink EXISTS; it is not absent
        return True, None
    text = read_text(path)
    return text is not None, text


def render_body(source: str, extras: str | None) -> str:
    """Everything after the header line. Deterministic: same inputs, same bytes."""
    parts = [
        "<!-- Generated - do not edit. Shared rules: edit ~/.claude/CLAUDE.md.",
        "     Codex-only rules: edit ~/.codex/AGENTS.local.md.",
        "     Then run `make codex-global-agents` in claude-power-pack. -->",
        "",
        source.rstrip("\n"),
        "",
    ]
    if extras is not None and extras.strip():
        parts += ["", EXTRAS_HEADING, "", extras.strip("\n"), ""]
    return "\n".join(parts)


def header(source: str, extras: str | None, body: str) -> str:
    extras_sha = sha256(extras) if extras is not None else "none"
    return (
        f"<!-- {MARKER}: built by claude-power-pack scripts/codex-global-agents.py;"
        f" source-sha256={sha256(source)}; extras-sha256={extras_sha};"
        f" body-sha256={sha256(body)} -->\n"
    )


def build(source: str, extras: str | None) -> str:
    body = render_body(source, extras)
    return header(source, extras, body) + body


def parse_header(text: str) -> dict[str, str] | None:
    first, _, _ = text.partition("\n")
    if MARKER not in first:
        return None
    fields = {}
    for part in first.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep:
            fields[key.strip()] = value.strip().removesuffix("-->").strip()
    return fields if "body-sha256" in fields else None


def classify(target_text: str, expected: str) -> str:
    fields = parse_header(target_text)
    if fields is None:
        return "unmanaged"
    body = target_text.partition("\n")[2]
    if sha256(body) != fields["body-sha256"]:
        return "hand-edited"
    return "current" if target_text == expected else "stale"


def paths(home: Path, codex_home: Path) -> tuple[Path, Path, Path]:
    return (
        home / ".claude" / "CLAUDE.md",
        codex_home / "AGENTS.md",
        codex_home / "AGENTS.local.md",
    )


def workspace_agents(home: Path, projects: Path) -> list[Path]:
    found = []
    for directory in (home, projects):
        candidate = directory / "AGENTS.md"
        if candidate.is_file() and not (directory / ".git").exists() and candidate not in found:
            found.append(candidate)
    return found


def check(home: Path, projects: Path, quiet: bool, codex_home: Path) -> int:
    source_path, target, extras_path = paths(home, codex_home)
    source = read_text(source_path)
    if not quiet:
        for found in workspace_agents(home, projects):
            print(
                f"WORKSPACE_AGENTS_MD: {found} - not a repository file; measured 2026-10-12"
                " (#1441): Codex reads it only when started in that directory, Claude only"
                " in repositories without their own CLAUDE.md"
            )
    if source is None:
        print(f"NOTE: cannot read {source_path}; there is no source to compare against.")
        print("CODEX_GLOBAL_AGENTS: unknown")
        return EXIT_UNKNOWN
    if not target.parent.is_dir():
        if not quiet:
            print(f"NOTE: {target.parent} does not exist - Codex is not set up on this host.")
        print("CODEX_GLOBAL_AGENTS: not-applicable")
        return EXIT_NA
    if not os.path.lexists(target):
        verdict = "absent"
    else:
        target_text = read_text(target)
        if target_text is None:
            print(f"NOTE: cannot read {target}.")
            print("CODEX_GLOBAL_AGENTS: unknown")
            return EXIT_UNKNOWN
        readable, extras = read_optional(extras_path)
        if not readable:
            print(f"NOTE: {extras_path} exists and cannot be read; the expected file cannot be built.")
            print("CODEX_GLOBAL_AGENTS: unknown")
            return EXIT_UNKNOWN
        verdict = classify(target_text, build(source, extras))
    override = target.with_name("AGENTS.override.md")
    readable, override_text = read_optional(override)
    if not readable:
        print(f"NOTE: {override} exists and cannot be read; whether it replaces AGENTS.md is unknown.")
        print("CODEX_GLOBAL_AGENTS: unknown")
        return EXIT_UNKNOWN
    if override_text and override_text.strip():
        print(
            f"NOTE: {override} is non-empty, and Codex reads it INSTEAD of {target.name}, so none of"
            f" the copied rules reach Codex while it exists (underlying {target.name}: {verdict})."
            " Remove or empty it, or move its content into ~/.codex/AGENTS.local.md."
        )
        print("CODEX_GLOBAL_AGENTS: overridden")
        return EXIT_DRIFT
    if not quiet and verdict != "current":
        remedy = {
            "stale": "run `make codex-global-agents` in claude-power-pack to rebuild it",
            "hand-edited": "move the edit into ~/.claude/CLAUDE.md or ~/.codex/AGENTS.local.md,"
            " then `make codex-global-agents ADOPT=1`",
            "unmanaged": "it was written by hand; `make codex-global-agents ADOPT=1` backs it up"
            " and replaces it with Claude's rules",
            "absent": "run `make codex-global-agents` in claude-power-pack",
        }[verdict]
        print(f"NOTE: {target} is {verdict} against {source_path} - {remedy}.")
    print(f"CODEX_GLOBAL_AGENTS: {verdict}")
    return EXIT_OK if verdict == "current" else EXIT_DRIFT


def write_atomic(target: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".AGENTS.md.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_backup(target: Path, text: str) -> Path:
    """Create a NEW backup file; never overwrite an earlier one (two adopts in one second)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for n in range(1000):
        backup = target.with_name(f"AGENTS.md.pre-cpp-{stamp}" + (f"-{n}" if n else ""))
        try:
            with backup.open("x", encoding="utf-8") as handle:
                handle.write(text)
            return backup
        except FileExistsError:
            continue
    raise FileExistsError(f"no free backup name for {target}")


def write(home: Path, adopt: bool, codex_home: Path) -> int:
    source_path, target, extras_path = paths(home, codex_home)
    source = read_text(source_path)
    if source is None:
        print(f"NOTE: cannot read {source_path}; nothing written.")
        print("CODEX_GLOBAL_AGENTS_WRITE: unknown")
        return EXIT_UNKNOWN
    if not target.parent.is_dir():
        print(f"NOTE: {target.parent} does not exist - Codex is not set up here; nothing written.")
        print("CODEX_GLOBAL_AGENTS_WRITE: not-applicable")
        return EXIT_NA
    readable, extras = read_optional(extras_path)
    if not readable:
        print(f"NOTE: {extras_path} exists and cannot be read; nothing written, so the additions are not dropped.")
        print("CODEX_GLOBAL_AGENTS_WRITE: unknown")
        return EXIT_UNKNOWN
    expected = build(source, extras)
    if len(expected.encode("utf-8")) > CODEX_DOC_LIMIT:
        print(f"NOTE: the built file exceeds {CODEX_DOC_LIMIT} bytes; Codex may truncate it.")
    if os.path.lexists(target):
        current = read_text(target)
        if current is None:
            print(f"NOTE: cannot read {target}; nothing written.")
            print("CODEX_GLOBAL_AGENTS_WRITE: unknown")
            return EXIT_UNKNOWN
        verdict = classify(current, expected)
        if verdict == "current":
            print("CODEX_GLOBAL_AGENTS_WRITE: unchanged")
            return EXIT_OK
        if verdict in ("unmanaged", "hand-edited"):
            if not adopt:
                print(
                    f"NOTE: {target} is {verdict}; refusing to replace it. Pass --adopt"
                    " (make codex-global-agents ADOPT=1) to back it up and replace it."
                )
                print("CODEX_GLOBAL_AGENTS_WRITE: refused")
                return EXIT_DRIFT
            backup = write_backup(target, current)
            print(f"BACKUP: {backup}")
    write_atomic(target, expected)
    print(f"WROTE: {target} from {source_path}" + (f" + {extras_path}" if extras_path.exists() else ""))
    print("CODEX_GLOBAL_AGENTS_WRITE: wrote")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report only (the default)")
    mode.add_argument("--write", action="store_true", help="build ~/.codex/AGENTS.md")
    parser.add_argument("--adopt", action="store_true", help="with --write: back up and replace a hand-written file")
    parser.add_argument("--home", type=Path, default=Path.home(), help="home directory to act on (tests)")
    parser.add_argument("--codex-home", type=Path, help="Codex directory (default: CODEX_HOME or HOME/.codex)")
    parser.add_argument("--projects", type=Path, default=None, help="projects directory (default: HOME/Projects)")
    parser.add_argument("--quiet", action="store_true", help="--check: print only the verdict line")
    args = parser.parse_args(argv)
    if args.adopt and not args.write:
        parser.error("--adopt only applies with --write")
    codex_home = args.codex_home
    if codex_home is None:
        codex_home = Path(os.environ["CODEX_HOME"]) if "CODEX_HOME" in os.environ else args.home / ".codex"
    if args.write:
        return write(args.home, args.adopt, codex_home)
    return check(args.home, args.projects or args.home / "Projects", args.quiet, codex_home)


if __name__ == "__main__":
    sys.exit(main())

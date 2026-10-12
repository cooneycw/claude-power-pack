#!/usr/bin/env python3
"""check-memory-supersession.py - stale dependents of a superseded memory (#1440).

Claude Code's file-based auto-memory keeps one fact per file under
`~/.claude/projects/<project>/memory/`, indexed by `MEMORY.md`, and memories
link each other with `[[slug]]`. When a fact changes, the fix is usually made
carefully in the ONE memory that holds it - and every memory that LINKS to it
keeps asserting the old rule. Nothing reported that, so the contradiction was
found only when a session acted on the stale dependent (observed 2026-10-11: a
placement memory was superseded on 2026-10-06 and two memories linking to it
still said the refused placement was required).

This checker reports exactly that propagation gap, and nothing wider.

---------------------------------------------------------------------------
THE MARKER IS STRICT, ON PURPOSE
---------------------------------------------------------------------------
A memory is SUPERSEDED only when it carries one of:

    a body line beginning     **Superseded YYYY-MM-DD.**   (the period optional)
    a frontmatter key         metadata.superseded: YYYY-MM-DD   (or top-level)

The word "superseded" in ordinary prose does NOT count. Measured on a real
store: of three memories using the word, one meant "this memory's rule
changed" and another described a ruling changing INSIDE a single memory, which
has no dependents to go stale. Matching prose would flag the second; a strict
marker cannot. The cost is stated in every clean verdict: a supersession
written only in prose is not examined.

---------------------------------------------------------------------------
FOUR VERDICTS, AND "COULD NOT DECIDE" IS NEVER CLEAN
---------------------------------------------------------------------------
    clean       exit 0   no marked supersession has a stale or undecidable dependent
    stale       exit 1   a dependent was last modified BEFORE the supersession date
    unreadable  exit 2   a store is missing, unreadable, or holds no memory files
    unknown     exit 3   a dependent has no modified date, was modified the SAME
                         day (the marker is day-granular, so order is unknowable),
                         a memory's frontmatter could not be parsed, a marker's
                         date is not a real date, or a link names a slug that
                         more than one memory claims and one of them is superseded

A memory FILE that cannot be read (permissions, not UTF-8) makes its store
`unreadable`, like a missing directory: part of the population was not seen,
which is a different fact from a population seen and found undecidable.

Zero memory files is `unreadable`, not `clean`: "examined 48 memories and found
nothing" and "examined nothing" are different facts. Precedence when stores
disagree: stale, then unreadable, then unknown, then clean - an actionable
finding is never hidden behind another store's inability to be read.

Hygiene findings (dangling `[[slug]]` links, index lines naming missing files,
files absent from the index, a `name:` that differs from the file stem) are
printed as MEMORY_SUPERSESSION_INFO and never change the exit code. A dangling
link is legitimate in this convention: it marks a memory worth writing later.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

#: NEGATIVE-CONTROL: controls/check-memory-supersession

EXIT_CLEAN = 0
EXIT_STALE = 1
EXIT_UNREADABLE = 2
EXIT_UNKNOWN = 3

INDEX_NAME = "MEMORY.md"
DEFAULT_GLOB = "~/.claude/projects/*/memory"

MARKER_LINE = re.compile(r"^\*\*Superseded (\d{4}-\d{2}-\d{2})\.?\*\*")
LINK = re.compile(r"\[\[([^\[\]\n]+)\]\]")
INDEX_LINK = re.compile(r"\]\(([^)\s]+\.md)\)")
DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")


class FrontmatterError(ValueError):
    pass


class MarkerDateError(ValueError):
    pass


@dataclass
class Memory:
    path: Path
    slug: str
    has_frontmatter: bool
    modified: date | None
    superseded: date | None
    links: list[str] = field(default_factory=list)
    error: str | None = None
    #: True when `error` is a failure to READ the file (the store is then
    #: unreadable), False when the file was read and could not be parsed.
    read_error: bool = False


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str, bool]:
    """Return (flattened keys, body, had_frontmatter).

    A deliberately small reader for the memory convention: top-level
    `key: value` lines, and one level of indented keys under a parent, which
    are flattened to `parent.key`. Anything it cannot place is ignored rather
    than guessed at; a frontmatter block that never closes is an error.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    keys: dict[str, str] = {}
    parent: str | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return keys, "\n".join(lines[i + 1 :]), True
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indented = line[0] in " \t"
        key, sep, value = line.strip().partition(":")
        if not sep:
            continue
        key = key.strip()
        if indented and parent:
            keys[f"{parent}.{key}"] = _unquote(value)
        else:
            parent = key if not value.strip() else None
            keys[key] = _unquote(value)
    raise FrontmatterError("frontmatter opened with '---' never closes")


def _as_date(raw: str | None) -> date | None:
    if not raw:
        return None
    m = DATE_PREFIX.match(raw.strip())
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _marker_date(body: str, keys: dict[str, str]) -> date | None:
    """The supersession date, None when there is no marker.

    EVERY marker is read, and the LATEST date wins: a memory superseded twice
    has dependents that must postdate its most recent change, so the earlier
    marker is not the one a dependent is measured against (counter-model
    review, second pass). A marker that IS present but whose date is not a real
    date raises MarkerDateError, whichever marker it is: an explicit declaration
    that cannot be interpreted is undecidable, never the same as no declaration.
    """
    found: list[date] = []
    for key in ("metadata.superseded", "superseded"):
        raw = keys.get(key)
        if raw is None or not raw.strip():
            continue
        parsed = _as_date(raw)
        if parsed is None:
            raise MarkerDateError(f"frontmatter {key}: {raw!r} is not a YYYY-MM-DD date")
        found.append(parsed)
    for line in body.splitlines():
        m = MARKER_LINE.match(line.strip())
        if m:
            parsed = _as_date(m.group(1))
            if parsed is None:
                raise MarkerDateError(f"marker date {m.group(1)!r} is not a real date")
            found.append(parsed)
    return max(found) if found else None


def load_memory(path: Path) -> Memory:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Memory(path, path.stem, False, None, None, error=f"unreadable: {exc}",
                      read_error=True)
    try:
        keys, body, had = _parse_frontmatter(text)
        superseded = _marker_date(body, keys)
    except (FrontmatterError, MarkerDateError) as exc:
        return Memory(path, path.stem, True, None, None, error=str(exc))
    slug = keys.get("name") or path.stem
    modified = _as_date(keys.get("metadata.modified") or keys.get("modified"))
    return Memory(
        path=path,
        slug=slug,
        has_frontmatter=had,
        modified=modified,
        superseded=superseded,
        links=[m.strip() for m in LINK.findall(body)],
    )


@dataclass
class StoreResult:
    root: Path
    examined: int = 0
    superseded: int = 0
    unreadable: str | None = None
    stale: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


def check_store(root: Path) -> StoreResult:
    res = StoreResult(root)
    if not root.is_dir():
        res.unreadable = "not a directory"
        return res
    try:
        files = sorted(p for p in root.glob("*.md") if p.name != INDEX_NAME)
    except OSError as exc:
        res.unreadable = f"cannot list: {exc}"
        return res
    if not files:
        res.unreadable = "no memory files (examined nothing; not the same as clean)"
        return res

    memories = [load_memory(p) for p in files]
    res.examined = len(memories)
    # Every memory a slug could mean - its `name:` and its file stem. A slug
    # claimed by more than one memory is ambiguous, and picking one would make
    # the verdict depend on file ordering (counter-model review).
    claims: dict[str, list[Memory]] = {}
    unread: list[str] = []
    for mem in memories:
        if mem.error:
            if mem.read_error:
                unread.append(f"{mem.path.name}: {mem.error}")
            else:
                res.unknown.append(f"{mem.path.name}: {mem.error}")
            continue
        for key in dict.fromkeys((mem.slug, mem.path.stem)):
            claims.setdefault(key, []).append(mem)
        if mem.has_frontmatter and mem.slug != mem.path.stem:
            res.info.append(f"{mem.path.name}: name '{mem.slug}' differs from file stem")
        if not mem.has_frontmatter:
            res.info.append(f"{mem.path.name}: no frontmatter")

    res.superseded = sum(1 for m in memories if m.superseded)
    for dep in memories:
        if dep.error:
            continue
        for slug in dict.fromkeys(dep.links):
            # Ambiguity is decided against EVERY claimant, the dependent
            # included. Filtering self out first turns a two-way ambiguity
            # (the dependent itself also claims the slug) into a confident,
            # unique target (counter-model review, second pass).
            candidates = claims.get(slug, [])
            if not candidates:
                res.info.append(f"{dep.path.name}: [[{slug}]] names no memory (dangling)")
                continue
            if len(candidates) > 1:
                names = ", ".join(sorted(m.path.name for m in candidates))
                if any(m.superseded for m in candidates):
                    res.unknown.append(
                        f"{dep.path.name} links [[{slug}]], claimed by {names}, at least one "
                        "superseded; which one is meant is ambiguous"
                    )
                else:
                    res.info.append(f"{dep.path.name}: [[{slug}]] is claimed by {names}")
                continue
            target = candidates[0]
            if target is dep or target.superseded is None:
                continue
            when = target.superseded.isoformat()
            if dep.modified is None:
                res.unknown.append(
                    f"{dep.path.name} links [[{slug}]] superseded {when}; "
                    "dependent has no modified date"
                )
            elif dep.modified < target.superseded:
                res.stale.append(
                    f"{dep.path.name} links [[{slug}]] superseded {when}; "
                    f"dependent modified {dep.modified.isoformat()}"
                )
            elif dep.modified == target.superseded:
                res.unknown.append(
                    f"{dep.path.name} links [[{slug}]] superseded {when}; "
                    "dependent modified the same day, order unknowable"
                )

    index = root / INDEX_NAME
    if index.is_file():
        try:
            listed = set(INDEX_LINK.findall(index.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError) as exc:
            res.info.append(f"{INDEX_NAME}: unreadable ({exc}); index checks skipped")
        else:
            for name in sorted(listed):
                if not (root / name).is_file():
                    res.info.append(f"{INDEX_NAME}: lists {name}, which does not exist")
            for path in files:
                if path.name not in listed:
                    res.info.append(f"{path.name}: not listed in {INDEX_NAME}")
    else:
        res.info.append(f"{INDEX_NAME}: absent; index checks skipped")
    if unread:
        res.unreadable = f"{len(unread)} memory file(s) could not be read: " + "; ".join(unread)
    return res


def _roots(args_roots: list[str] | None) -> list[Path]:
    if args_roots:
        return [Path(r).expanduser() for r in args_roots]
    pattern = Path(DEFAULT_GLOB).expanduser()
    return sorted(pattern.parent.parent.glob(f"*/{pattern.name}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report memories that link to a superseded memory and predate it (#1440)."
    )
    parser.add_argument(
        "--root",
        action="append",
        help=f"memory directory to check (repeatable; default: every {DEFAULT_GLOB})",
    )
    args = parser.parse_args(argv)

    roots = _roots(args.root)
    if not roots:
        print(f"MEMORY_SUPERSESSION_UNREADABLE: no store matched {DEFAULT_GLOB}")
        print("MEMORY_SUPERSESSION: unreadable - examined nothing")
        return EXIT_UNREADABLE

    results = [check_store(r) for r in roots]
    for res in results:
        if res.unreadable:
            print(f"MEMORY_SUPERSESSION_UNREADABLE: {res.root}: {res.unreadable}")
        for line in res.stale:
            print(f"MEMORY_SUPERSESSION_STALE: {res.root}/{line}")
        for line in res.unknown:
            print(f"MEMORY_SUPERSESSION_UNKNOWN: {res.root}/{line}")
        for line in res.info:
            print(f"MEMORY_SUPERSESSION_INFO: {res.root}/{line}")

    examined = sum(r.examined for r in results)
    superseded = sum(r.superseded for r in results)
    stale = sum(len(r.stale) for r in results)
    unknown = sum(len(r.unknown) for r in results)
    unreadable = sum(1 for r in results if r.unreadable)
    scope = (
        f"examined {examined} memories; {len(results) - unreadable} of {len(results)} "
        f"store(s) fully read, {superseded} marked superseded"
    )
    if stale:
        print(f"MEMORY_SUPERSESSION: stale - {stale} stale dependent(s); {scope}")
        return EXIT_STALE
    if unreadable:
        print(f"MEMORY_SUPERSESSION: unreadable - {unreadable} store(s) not fully examined; {scope}")
        return EXIT_UNREADABLE
    if unknown:
        print(f"MEMORY_SUPERSESSION: unknown - {unknown} dependent(s) undecidable; {scope}")
        return EXIT_UNKNOWN
    print(
        f"MEMORY_SUPERSESSION: clean - no marked supersession has a stale or undecidable "
        f"dependent; {scope}. Supersession written only in prose is not examined"
    )
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())

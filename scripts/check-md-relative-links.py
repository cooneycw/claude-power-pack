#!/usr/bin/env python3
"""Check that relative markdown links in this repository's tracked .md files resolve.

Issue #1413. Citations rotted in documents nothing checked: CLAUDE.md's own
pointers are gated by `check-claude-md-links.py`, and every other document was
not. This gate covers the citation shape that is unambiguous - an inline
markdown link `[text](relative/path)` or HTML anchor href - across every
tracked `.md` file.

WHY LINKS AND NOT BACKTICK PATHS. The first attempt (#1413's parked branch)
scanned backtick spans that look like repository paths. Over its narrowest
population it still reported 35 findings, and reading them showed only a
handful were rot: the rest were consumer-project files named in prose
(`.claude/deploy.yaml`), another repository's paths quoted while narrating it,
placeholders, and deliberately non-existent names quoted as counterexamples. A
backtick span does not say "this file exists here"; a relative link does. A
check people learn to route around is worse than none, so the link is the
population this gate enforces.

BACKTICK CITATIONS STAY UNCHECKED - A RULING, NOT AN OVERSIGHT (issue #1460).
#1413's rot lived in backtick citations (`path`, `path:line`), and this gate
does not read them. Measured before deciding, on 205 in-scope docs:
  - 40 line-bound citations (`path.ext:N`). 23 resolve, and none of those
    points past its file's end. 17 do not resolve, and confirmed rot is 0:
    7 are paths in ANOTHER repository (skillc), quoted while narrating it; 4
    narrate a retired tool inside the spec that records its retirement; 3 sit
    in dated review documents; 3 are bare names of installed or elsewhere files.
  - the narrowed backtick-path scan of #1413 gave 35 hits, mostly not rot.
A checker over that population mostly flags cross-repository and historical
prose, and a check people learn to route around is worse than none. A
past-end-of-file check would not have caught the case that opened #1413
either: R11's citation was CONTENT drift - the cited lines moved under it -
which no existence or bound check sees. So backtick citations are left to
review, and the measured backlog is held on #1460.

WHAT IT SKIPS, AND WHY:
- URLs (any `scheme:`), bare `#anchors`, and absolute `/paths` - not relative
  files in this tree. A link's own `#fragment` is stripped; only the file is
  checked, never the heading.
- Links inside fenced/indented code, inline code spans and HTML comments -
  examples, not links.
- Image links `![...](...)`, and reference-style definitions `[id]: path` -
  out of scope; the limit is stated, not hidden.
- `EXCLUDED_PREFIXES` below: generated or copied text whose links resolve from
  somewhere else, run records describing a bygone tree, and control cases that
  are dead on purpose.

The tracked population comes from `git ls-files` (cached plus untracked files
not ignored, so a new document is checked before it is committed). Fewer files
than `--min-files`, or zero links examined, is UNKNOWN (exit 2) - a scan over
nothing is not a clean scan.

Exit codes: 0 every examined link resolves inside the root, 1 a dead or escaping
link, 2 UNKNOWN.

Usage:
    python3 scripts/check-md-relative-links.py
    python3 scripts/check-md-relative-links.py --root DIR --min-files N
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

#: NEGATIVE-CONTROL: controls/check-md-relative-links

#: Below this many tracked .md files the real repository cannot be what was
#: scanned (it holds several hundred) - UNKNOWN, not clean. Control cases pass a
#: smaller floor explicitly.
MIN_TRACKED_MD_FILES = 100

#: Each prefix is text whose links do not resolve from where it sits, by design:
#: - `codex/skills/`: generated mirrors (`make codex-skills`); their sources are
#:   checked where they live.
#: - `templates/`, `.specify/templates/`: rendered into another tree, where
#:   their relative links resolve.
#: - `docs/flow-runs/`, `docs/measurements/`: records of a bygone tree.
#: - `controls/`: negative-control cases, some dead on purpose.
#: - `tests/`: fixtures, likewise.
EXCLUDED_PREFIXES = (
    "codex/skills/",
    "templates/",
    ".specify/templates/",
    "docs/flow-runs/",
    "docs/measurements/",
    "controls/",
    "tests/",
)

LINK_START_RE = re.compile(r"(?<!!)\[(?:[^\[\]]|\[[^\]]*\])*\]\(")
HTML_LINK_RE = re.compile(r'''<a\b[^>]*?\s+href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))''', re.I)
COMMENT_RE = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
FENCE_RE = re.compile(r"^\s*(?:>\s*)*(`{3,}|~{3,})")
#: A CLOSING fence is the marker and nothing else (CommonMark): `\x60\x60\x60python`
#: inside an open fence is content, not its end.
CLOSING_FENCE_RE = re.compile(r"^\s*(?:>\s*)*(`{3,}|~{3,})\s*$")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


@dataclass(frozen=True)
class DeadLink:
    path: str
    line: int
    target: str
    reason: str = "does not exist"


class GitUnavailable(Exception):
    """git itself is not installed - a fact about this host, not the tree."""


def tracked_md_files(root: Path) -> list[str] | None:
    """Tracked .md paths relative to `root`, or None when git cannot list them.

    Raises GitUnavailable when there is no git binary at all.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
            cwd=root, capture_output=True, text=True,
        )
    except FileNotFoundError as exc:
        raise GitUnavailable from exc
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return sorted({
        # -z: without it git quotes a non-ASCII path, which then reads as missing.
        line for line in proc.stdout.split("\0")
        if line and not line.startswith(EXCLUDED_PREFIXES)
    })


def _destination(line: str, start: int) -> str | None:
    """The raw destination of a link whose `(` ends just before `start`.

    `<...>` runs to its `>`; otherwise parentheses nest and `\\(` escapes, as
    CommonMark has it, so `guide(v2).md` is one destination, not `guide(v2`.
    An unbracketed destination holds no whitespace, so it ends at the first
    one: a title after it, balanced or not, is never parsed.
    """
    if line.startswith("<", start):
        end = line.find(">", start + 1)
        return None if end < 0 else line[start:end + 1]
    depth = 0
    i = start
    while i < len(line):
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c.isspace():
            return line[start:i]
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                return line[start:i]
            depth -= 1
        i += 1
    return None


def _link_target(raw: str) -> str | None:
    """The relative file a link names, or None when it names no local file."""
    target = raw.strip()
    if target.startswith("<"):
        target = target[1:-1] if target.endswith(">") else ""
    else:
        target = target.split(maxsplit=1)[0] if target else ""
    # Strip the literal fragment and query BEFORE decoding: `%23` and `%3F` are
    # part of a file name, not delimiters.
    target = target.split("#", 1)[0].split("?", 1)[0]
    # CommonMark: a backslash escapes any ASCII punctuation, and character
    # references decode (`my\\_guide.md` names `my_guide.md`, `a&amp;b.md` `a&b.md`).
    target = unquote(html.unescape(re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", target)))
    if not target or target.startswith("/") or SCHEME_RE.match(target):
        return None
    return target


def links_in(text: str) -> list[tuple[int, str]]:
    """`(line number, target)` for every relative link outside code."""
    found: list[tuple[int, str]] = []
    # Mask instead of deleting so multi-line matches retain source line numbers.
    def mask(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group())

    text = COMMENT_RE.sub(mask, text)
    fence: str | None = None
    visible: list[str] = []
    paragraph_open = False
    list_indent = 0
    for line in text.splitlines(keepends=True):
        hidden = False
        if fence is None:
            m = FENCE_RE.match(line)
            if m:
                fence = m.group(1)
                paragraph_open = False
                hidden = True
            else:
                expanded = line.expandtabs(4)
                indent = len(expanded) - len(expanded.lstrip())
                if expanded.strip() and indent < list_indent:
                    list_indent = 0
                # Indented code cannot interrupt a paragraph. In a list the
                # marker's content indentation is additional to the four
                # spaces needed for a code block.
                hidden = indent >= list_indent + 4 and not paragraph_open
                marker = re.match(r"^( {0,3})(?:[-+*]|[0-9]{1,9}[.)])( +)", expanded)
                if marker and not hidden:
                    list_indent = marker.end()
                paragraph_open = bool(expanded.strip()) and not hidden
        else:
            m = CLOSING_FENCE_RE.match(line)
            if m and m.group(1).startswith(fence):
                fence = None
            hidden = True
            paragraph_open = False
        visible.append(re.sub(r"[^\n]", " ", line) if hidden else line)
    code_free = INLINE_CODE_RE.sub(mask, "".join(visible))
    for start in LINK_START_RE.finditer(code_free):
        raw = _destination(code_free, start.end())
        target = _link_target(raw) if raw is not None else None
        if target is not None:
            found.append((code_free.count("\n", 0, start.start()) + 1, target))
    for match in HTML_LINK_RE.finditer(code_free):
        raw = next(value for value in match.groups() if value is not None)
        # HTML href values can contain spaces without Markdown angle brackets.
        target = _link_target("<" + raw + ">")
        if target is not None:
            found.append((code_free.count("\n", 0, match.start()) + 1, target))
    found.sort(key=lambda item: item[0])
    return found


def find_dead_links(root: Path, files: list[str]) -> tuple[list[DeadLink], int, list[str]]:
    """`(dead links, links examined, documents that could not be read)`."""
    dead: list[DeadLink] = []
    examined = 0
    unreadable: list[str] = []
    for rel in files:
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            unreadable.append(rel)
            continue
        for number, target in links_in(text):
            examined += 1
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(root.resolve()):
                dead.append(DeadLink(rel, number, target, "escapes repository root"))
            elif not resolved.exists():
                dead.append(DeadLink(rel, number, target))
    return dead, examined, unreadable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repository root (default: the checkout this script lives in)")
    parser.add_argument("--min-files", type=int, default=MIN_TRACKED_MD_FILES,
                        help=f"membership floor (default {MIN_TRACKED_MD_FILES})")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    try:
        files = tracked_md_files(root)
    except GitUnavailable:
        print("md-relative-links: UNAVAILABLE - git is not installed", file=sys.stderr)
        return 2
    if files is None:
        print(f"md-relative-links: UNKNOWN - `git ls-files` could not list {root}; "
              "nothing was examined, which is not a pass.", file=sys.stderr)
        return 2
    if len(files) < args.min_files:
        print(f"md-relative-links: UNKNOWN - only {len(files)} tracked .md file(s) "
              f"(need >= {args.min_files}); this is not the population the gate is "
              "for, so a clean result would mean nothing.", file=sys.stderr)
        return 2
    dead, examined, unreadable = find_dead_links(root, files)
    if unreadable:
        for d in dead:
            print(f"  {d.path}:{d.line}: ({d.target}) {d.reason}", file=sys.stderr)
        print(f"md-relative-links: UNKNOWN - {len(unreadable)} tracked .md file(s) could "
              "not be read, so their links were not examined:", file=sys.stderr)
        for rel in unreadable:
            print(f"  {rel}", file=sys.stderr)
        return 2
    if not examined:
        print(f"md-relative-links: UNKNOWN - {len(files)} tracked .md file(s) carry no "
              "relative link at all; nothing was checked.", file=sys.stderr)
        return 2
    if dead:
        print(f"md-relative-links: {len(dead)} dead relative link(s) of {examined} "
              f"across {len(files)} tracked .md file(s):", file=sys.stderr)
        for d in dead:
            print(f"  {d.path}:{d.line}: ({d.target}) {d.reason}", file=sys.stderr)
        return 1
    print(f"md-relative-links: ok - {examined} relative link(s) across {len(files)} "
          "tracked .md file(s) resolve (file existence only; URLs, anchors, images "
          "and reference-style links are not examined)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

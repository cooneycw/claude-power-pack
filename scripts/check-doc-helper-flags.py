#!/usr/bin/env python3
"""check-doc-helper-flags.py - a doc must not pass a helper a flag it lacks (issue #1835).

Every delegated driver told a stuck worker to escalate with

    ~/.claude/scripts/flow-wave-mailbox.sh send ... --kind message --body "..."

and the mailbox has no `--kind`: its parser ends in `--*) usage_fail`, so the
escalation exited 2 and never sent. Nothing in CPP compared a flag a command
document passes to a helper against the flags that helper accepts; skillc's
`dangling-reference` rule found it from outside (cooneycw/skillc#725).

This gate reads the instruction surfaces - `.claude/commands/**/*.md`,
`.claude/skills/**/*.md` and `templates/**/*.md` - finds each
`~/.claude/scripts/<helper>` invocation, takes the `--flag` tokens written
after it on the same command, and requires each flag to appear in the helper's
source under `scripts/`, or in a sibling the helper hands off to through a
`$..._DIR/<name>` path (`flow-preflight.sh` runs `flow-preflight.py`).

What the command is, for this gate: the rest of the line, joined across `\\`
continuations, cut at the first `|`, `;`, `&`, backtick, `#` comment or next
helper path, with every `$(...)` substitution removed first - the flags inside
`--path "$(git rev-parse --show-toplevel)"` belong to git, not the helper.

THE MATCH IS DELIBERATELY PERMISSIVE. A flag counts as known when the literal
`--flag` appears anywhere in the helper's source, comments included, so a flag
mentioned only in a comment passes; for a Python helper the bare name as a
quoted string also counts, because a parser may build its option names. The gate can therefore miss a bad flag; it
cannot block a good one, which is the direction that matters for a gate in
`make verify`. It does not check which verb a flag belongs to, nor flags
written before the helper path, nor helpers that are not under `scripts/`
(those are counted and named as unresolved, never treated as checked).

Verdicts on stdout, exit code beside them:
    UNKNOWN_FLAG: <doc>:<line>: <helper> <flag>    one per finding (exit 1)
    ok - <F> flag(s) on <I> invocation(s) in <D> doc(s) checked   (exit 0)
    UNKNOWN - <why>    nothing was examined, or a surface could not be read
                       (exit 2): a scan that saw nothing is not a clean scan

Stdlib-only, offline and git-free.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: NEGATIVE-CONTROL: controls/doc-helper-flags

SURFACES = (".claude/commands", ".claude/skills", "templates")
HELPER_PATH = re.compile(r"~/\.claude/scripts/([A-Za-z0-9_.-]+)")
FLAG_TOKEN = re.compile(r"(?:(?<=\s)|^)(--[a-z][a-z0-9-]*)")
STOP = re.compile(r"[|;&`]|(?:^|\s)#|~/\.claude/scripts/")
DELEGATE = re.compile(r"\$\{?[A-Z_]*DIR\}?/([A-Za-z0-9_.-]+)")


def strip_substitutions(text: str) -> str:
    """Remove every `$(...)`, nesting included; an unclosed one runs to the end."""
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("$(", i):
            depth = 1
            i += 2
            while i < len(text) and depth:
                if text.startswith("$(", i):
                    depth += 1
                    i += 2
                    continue
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                i += 1
            out.append(" ")
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def command_tail(text: str, start: int) -> str:
    """The command text after a helper path, joined across `\\` continuations."""
    parts: list[str] = []
    pos = start
    while True:
        end = text.find("\n", pos)
        line = text[pos:] if end == -1 else text[pos:end]
        if line.rstrip().endswith("\\") and end != -1:
            parts.append(line.rstrip()[:-1])
            pos = end + 1
            continue
        parts.append(line)
        break
    tail = strip_substitutions(" ".join(parts))
    cut = STOP.search(tail)
    return tail[: cut.start()] if cut else tail


def helper_source(scripts: Path, name: str, seen: set[str] | None = None) -> list[tuple[str, str]] | None:
    """(file name, text) for the helper and each sibling it delegates to; None when absent."""
    seen = seen if seen is not None else set()
    if name in seen:
        return []
    seen.add(name)
    path = scripts / name
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    pieces = [(name, text)]
    for sibling in DELEGATE.findall(text):
        if sibling != name:
            pieces.extend(helper_source(scripts, sibling, seen) or [])
    return pieces


def flag_known(flag: str, source: str, python: bool = False) -> bool:
    if re.search(re.escape(flag) + r"(?![a-z0-9-])", source):
        return True
    # A Python parser may build its option names: `for name in ('wave', 'role'):
    # parser.add_argument('--' + name)` (flow-wave-completion.py). There the
    # bare name appears only as a quoted string, so accept that too - one more
    # way to miss a bad flag, never a way to block a good one.
    if python:
        bare = re.escape(flag[2:])
        return re.search(r"""(['"])""" + bare + r"\1", source) is not None
    return False


def docs_under(root: Path) -> list[Path]:
    found: list[Path] = []
    for surface in SURFACES:
        base = root / surface
        if base.is_dir():
            found.extend(p for p in base.rglob("*.md") if p.is_file())
    return sorted(found)


def check(root: Path) -> int:
    scripts = root / "scripts"
    docs = docs_under(root)
    if not docs:
        print(f"UNKNOWN - no instruction document under {', '.join(SURFACES)} in {root}")
        return 2
    cache: dict[str, list[tuple[str, str]] | None] = {}
    findings: list[str] = []
    unresolved: set[str] = set()
    flags_checked = invocations = 0
    for doc in docs:
        try:
            text = doc.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"UNKNOWN - cannot read {doc.relative_to(root)}: {exc}")
            return 2
        for match in HELPER_PATH.finditer(text):
            name = match.group(1)
            if name not in cache:
                cache[name] = helper_source(scripts, name)
            source = cache[name]
            if source is None:
                unresolved.add(name)
                continue
            invocations += 1
            line = text.count("\n", 0, match.start()) + 1
            for flag in FLAG_TOKEN.findall(command_tail(text, match.end())):
                flags_checked += 1
                if not any(flag_known(flag, text, python=file.endswith(".py")) for file, text in source):
                    findings.append(f"UNKNOWN_FLAG: {doc.relative_to(root)}:{line}: {name} {flag}")
    for finding in findings:
        print(finding)
    if unresolved:
        print(f"note - {len(unresolved)} helper name(s) not under scripts/, unchecked: "
              + ", ".join(sorted(unresolved)), file=sys.stderr)
    if findings:
        print(f"check-doc-helper-flags: {len(findings)} flag(s) the named helper does not accept. "
              "Fix the document, or add the flag to the helper if it is meant to exist.")
        return 1
    if invocations == 0:
        print(f"UNKNOWN - {len(docs)} doc(s) read and no resolvable helper invocation found")
        return 2
    print(f"ok - {flags_checked} flag(s) on {invocations} invocation(s) in {len(docs)} doc(s) checked")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT,
                        help="repository tree to scan (default: this checkout)")
    args = parser.parse_args(argv)
    return check(args.root.resolve())


if __name__ == "__main__":
    sys.exit(main())

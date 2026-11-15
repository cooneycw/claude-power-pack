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
continuations, with every `$(...)` substitution removed first - the flags inside
`--path "$(git rev-parse --show-toplevel)"` belong to git, not the helper. It is
then read as shell words, QUOTE-AWARE: it ends at the first UNQUOTED `|`, `;`,
`&`, backtick, word-initial `#` or next helper path, and a flag is an unquoted
word starting `--`. So `--body "remove --kind; see #1835"` is one argument, and
a flag written after it is still checked. An unterminated quote swallows the
rest of the command, which can hide a flag but never invent one.

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
FLAG_WORD = re.compile(r"^(--[a-z][a-z0-9-]*)(?:=|$)")
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
    return strip_substitutions(" ".join(parts))


def command_words(tail: str) -> list[str]:
    """Shell words up to the first unquoted separator; quoted words are omitted.

    A word with a quoted part is an argument's value, not a flag - EXCEPT its
    unquoted prefix up to the first quote, which is returned when it is a
    `--name=` option: `--kind="message"` still passes `--kind` (counter-model
    review on #1835).
    """
    words: list[str] = []
    word: list[str] = []
    prefix = ""
    quoted = False
    quote = ""
    i = 0
    n = len(tail)

    def flush() -> None:
        nonlocal quoted, prefix
        if word and not quoted:
            words.append("".join(word))
        elif quoted and FLAG_WORD.match(prefix) and prefix.endswith("="):
            words.append(prefix)
        word.clear()
        prefix = ""
        quoted = False

    while i < n:
        ch = tail[i]
        if quote:
            if ch == quote:
                quote = ""
            elif ch == "\\" and quote == '"' and i + 1 < n:
                i += 1
            i += 1
            continue
        if ch in "'\"":
            if not quoted:
                prefix = "".join(word)
            quote, quoted = ch, True
        elif ch == "\\" and i + 1 < n:
            word.append(tail[i + 1])
            i += 1
        elif ch.isspace():
            flush()
        elif ch in "|;&`" or (ch == "#" and not word):
            break
        elif tail.startswith("~/.claude/scripts/", i):
            break
        else:
            word.append(ch)
        i += 1
    flush()
    return words


def inside_quote(text: str, pos: int) -> bool:
    """Whether `pos` sits inside a shell quote, read from where its command starts.

    The command starts at the line's beginning, or just after the last backtick
    before `pos` on that line (an inline code span), so prose apostrophes before
    a span are not read as quotes. A `$(` opens an unquoted context even inside
    double quotes: `X="$(~/.claude/scripts/h.sh --a)"` is an invocation. A path
    inside a quoted argument (`--body "run ~/.claude/scripts/h.sh --x"`) is
    message text, not an invocation (counter-model review on #1835).
    """
    start = text.rfind("\n", 0, pos) + 1
    tick = text.rfind("`", start, pos)
    if tick != -1:
        start = tick + 1
    stack = [""]
    i = start
    while i < pos:
        ch = text[i]
        top = stack[-1]
        if top == "'":
            if ch == "'":
                stack.pop()
        elif text.startswith("$(", i):
            stack.append("")
            i += 1
        elif top == '"':
            if ch == "\\":
                i += 1
            elif ch == '"':
                stack.pop()
        elif ch in "'\"":
            stack.append(ch)
        elif ch == ")" and len(stack) > 1:
            stack.pop()
        elif ch == "\\":
            i += 1
        i += 1
    return stack[-1] != ""


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
    flags_checked = invocations = quoted_paths = 0
    for doc in docs:
        try:
            text = doc.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"UNKNOWN - cannot read {doc.relative_to(root)}: {exc}")
            return 2
        for match in HELPER_PATH.finditer(text):
            name = match.group(1)
            if inside_quote(text, match.start()):
                quoted_paths += 1
                continue
            if name not in cache:
                cache[name] = helper_source(scripts, name)
            source = cache[name]
            if source is None:
                unresolved.add(name)
                continue
            invocations += 1
            line = text.count("\n", 0, match.start()) + 1
            for word in command_words(command_tail(text, match.end())):
                m = FLAG_WORD.match(word)
                if not m:
                    continue
                flag = m.group(1)
                flags_checked += 1
                if not any(flag_known(flag, body, python=file.endswith(".py")) for file, body in source):
                    findings.append(f"UNKNOWN_FLAG: {doc.relative_to(root)}:{line}: {name} {flag}")
    for finding in findings:
        print(finding)
    if quoted_paths:
        print(f"note - {quoted_paths} helper path(s) inside a quoted argument, not invocations, unchecked",
              file=sys.stderr)
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

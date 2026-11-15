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

What the command is, for this gate: one shell reader, `lex`, reads it (#1839).
It runs from the helper path to the first plain newline (a `\\` continuation
joins lines), or to the first unquoted `|`, `;`, `&`, word-initial `#` or
next helper path, or to the `)` or backtick closing the substitution the helper
itself runs in: in `echo $(~/.claude/scripts/h.sh --a) --b`, `--b` is echo's.
A `$(...)` the helper's own command holds is skipped whole, quotes inside it
included - the flags in `--path "$(git rev-parse --show-toplevel)"` are git's.
An unescaped backtick is a substitution too, inside double quotes as well
(#1842): a helper inside a backtick pair within a double-quoted assignment
is an invocation, as it is inside `X="$(...)"`. In prose a
backtick is an inline code span's edge instead, so it ends the command there;
only inside a fenced block does a backtick argument nest and leave the words
after it to the helper.
A flag is an unquoted word starting `--`, or the unquoted `--name=` prefix of a
word whose value is quoted or substituted. So `--body "remove --kind; see #1835"` is one
argument and a flag after it is still checked. A helper path inside a quoted
argument, read forward from its fenced block's first line (in prose, from
where its command starts, back across continued lines), is
message text, not an invocation; so is one inside a shell comment. An unterminated quote swallows the rest of its
line, which can hide a flag but never invent one. Each shape has a case under
`controls/doc-helper-flags`; that directory and this docstring are the contract.

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
OPTION_PREFIX = re.compile(r"^(--[a-z][a-z0-9-]*=)")
DELEGATE = re.compile(r"\$\{?[A-Z_]*DIR\}?/([A-Za-z0-9_.-]+)")


#: What `lex` reports about each character of a command, at the command's own level.
LITERAL, QUOTED, GAP, END = "literal", "quoted", "gap", "end"
CONTINUATION = re.compile(r"\\[ \t]*\n")
SEPARATORS = "|;&)"
#: What opens a nested command: `$(` command and `<(` / `>(` process substitution.
#: An unescaped backtick opens one too (issue #1842); it is handled on its own,
#: because the same character also closes it.
SUBSTITUTIONS = ("$(", "<(", ">(")
BACKTICK = "`"


def lex(text: str, start: int, stop: int | None = None, *, whole_command: bool = True,
        backtick_ends: bool = True) -> tuple[list[tuple[str, str]], list[str]]:
    """Read `text` from `start` as one shell command: THE ONLY SHELL READER here.

    Both questions the gate asks go through it, so they cannot disagree (#1839):
    whether a helper path is inside a quote or a comment (`path_context`), and which words
    follow it (`command_words`). It tracks single and double quotes, `$(...)`
    nesting with quotes and plain parentheses inside it, backslash escapes, and
    `\\`-newline continuations in every state. The idea of one shlex-style
    reader that records each word's quote state is borrowed from `skillc
    inspect` (author cooneycw, https://github.com/cooneycw/skillc/pull/748 at
    604084088cc9e11464c5cc263260f658836e400c, same-owner repository); the code
    here is written for this gate.

    Returns `(events, stack)`. `events` is `(kind, char)` for each character
    read at the command's OWN level: LITERAL (unquoted word text), QUOTED (inside
    a quote or a substitution: word content that is not a flag), GAP (unquoted
    whitespace), and a final END. `stack` is what is still open where reading
    stopped: `'`, `"`, `(`, a backtick, or `#` when the quote query stopped
    inside a comment.

    An unescaped backtick opens a nested command inside double quotes, inside
    `$(...)` and inside another backtick level, and is closed by the next
    unescaped backtick (issue #1842). At the command's OWN level it nests too,
    unless `backtick_ends`: then it ends the command, as it must in prose,
    where a backtick is an inline code span's edge, and when the helper itself
    sits inside a backtick level, whose closing backtick ends its command.

    With `whole_command`, reading ends at a plain newline, an unquoted `|`, `;`,
    `&`, backtick or word-initial `#`, the next helper path, or a `)` that closes
    the substitution the command itself sits in. Without it (the quote query),
    it reads to `stop` and only a plain newline resets the state.
    """
    events: list[tuple[str, str]] = []
    stack: list[str] = []
    end = len(text) if stop is None else stop
    in_word = False
    i = start
    while i < end:
        if not stack and not in_word and text[i] == "#" and not whole_command:
            # A comment runs to its newline, and a `\` inside it joins no lines
            # (counter-model review on #1839): skip it whole, so its quotes and
            # its trailing backslash never reach the next command.
            newline = text.find("\n", i, end)
            if newline == -1:
                # Reading stopped inside the comment: what follows is its text.
                stack.append("#")
                break
            i = newline
            continue
        cont = CONTINUATION.match(text, i)
        if cont:
            i = cont.end()
            continue
        ch = text[i]
        top = stack[-1] if stack else ""
        if ch == "\n":
            if whole_command:
                break
            stack.clear()
            in_word = False
            i += 1
            continue
        if top == "'":
            if ch == "'":
                stack.pop()
        elif top == '"':
            if ch == "\\":
                i += 1
            elif ch == '"':
                stack.pop()
            elif ch == BACKTICK:
                stack.append(BACKTICK)
            elif text.startswith("$(", i):
                stack.append("(")
                i += 1
        elif top in ("(", BACKTICK):
            if ch == "\\":
                i += 1
            elif ch == BACKTICK:
                if top == BACKTICK:
                    stack.pop()
                else:
                    stack.append(BACKTICK)
            elif ch in "'\"":
                stack.append(ch)
            elif text.startswith(SUBSTITUTIONS, i):
                stack.append("(")
                i += 1
            elif ch == "(":
                stack.append("(")
            elif ch == ")" and top == "(":
                stack.pop()
        else:
            # The command's own level: the only place a word or a stop is read.
            if ch in "'\"":
                stack.append(ch)
            elif text.startswith(SUBSTITUTIONS, i):
                stack.append("(")
                i += 1
            elif ch == BACKTICK and whole_command and backtick_ends:
                break
            elif ch == BACKTICK:
                stack.append(BACKTICK)
            elif whole_command and (ch in SEPARATORS or (ch == "#" and not in_word)
                                    or text.startswith("~/.claude/scripts/", i)):
                break
            elif ch.isspace() or ch in "|;&":
                # An operator ends a word as whitespace does, so a `#` right
                # after `;` starts a comment (counter-model review on #1839).
                events.append((GAP, ch))
                in_word = False
                i += 1
                continue
            else:
                if ch == "\\" and i + 1 < len(text):
                    i += 1
                    ch = text[i]
                events.append((LITERAL, ch))
                in_word = True
                i += 1
                continue
        events.append((QUOTED, ch))
        in_word = True
        i += 1
    events.append((END, ""))
    return events, stack


FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})", re.MULTILINE)


def fence_body_start(text: str, pos: int) -> int | None:
    """The first character after the opening fence of the code block holding
    `pos`, or None when `pos` is in prose. A closing fence is the same character,
    at least as long as the opening one, with nothing else on its line."""
    opening: str | None = None
    body = 0
    for fence in FENCE.finditer(text, 0, pos):
        line_end = text.find("\n", fence.end())
        line_end = len(text) if line_end == -1 else line_end
        if line_end >= pos:
            # `pos` is on the fence line itself: not inside a block's body.
            return None
        mark = fence.group(1)
        if opening is None:
            opening, body = mark, line_end + 1
        elif mark[0] == opening[0] and len(mark) >= len(opening) \
                and not text[fence.end():line_end].strip():
            opening = None
    return body if opening is not None else None


def command_start(text: str, pos: int) -> int:
    """Where to start reading forward to learn what `pos` sits inside.

    In a fenced code block: the block's first line. Reading forward from there
    tracks comments, continuations and quotes in the order a shell meets them,
    and a backtick in the block is shell text, never a code-span edge
    (counter-model review on #1839: guessing the start backwards let a
    comment's backtick and apostrophe hide the next invocation).

    In prose: back across `\\`-continued lines, then just after the last
    unescaped backtick before `pos` (an inline code span), so prose apostrophes
    before a span are not read as quotes."""
    body = fence_body_start(text, pos)
    if body is not None:
        return body
    start = text.rfind("\n", 0, pos) + 1
    while start > 0:
        prev = text.rfind("\n", 0, start - 1) + 1
        if not text[prev:start - 1].rstrip().endswith("\\"):
            break
        start = prev
    tick = text.rfind("`", start, pos)
    # A backslash-escaped backtick is shell text inside the command, not the
    # edge of a code span (counter-model review on #1839).
    while tick != -1 and is_escaped(text, tick):
        tick = text.rfind("`", start, tick)
    return start if tick == -1 else tick + 1


def is_escaped(text: str, pos: int) -> bool:
    """Whether an odd run of backslashes precedes `pos`."""
    run = 0
    while pos - run - 1 >= 0 and text[pos - run - 1] == "\\":
        run += 1
    return run % 2 == 1


def path_context(text: str, pos: int) -> str:
    """What `pos` sits inside: "quote", "comment", "backtick" for a command word
    inside a backtick substitution (issue #1842), or "" for any other command word.

    A `$(` opens an unquoted context even inside double quotes:
    `X="$(~/.claude/scripts/h.sh --a)"` is an invocation; `--body "run
    ~/.claude/scripts/h.sh --x"` is message text, and so is `# run
    ~/.claude/scripts/h.sh --x`: a commented command never runs
    (counter-model review on #1839)."""
    _, stack = lex(text, command_start(text, pos), pos, whole_command=False)
    top = stack[-1] if stack else ""
    if top in ("'", '"'):
        return "quote"
    return "comment" if top == "#" else "backtick" if top == BACKTICK else ""


def command_words(text: str, start: int, *, backtick_ends: bool = True) -> list[str]:
    """The unquoted shell words of the command after a helper path.

    `backtick_ends` is `lex`'s: True in prose and inside a backtick level, False
    for a helper at its own level in a fenced block, where a backtick argument
    is a nested command and the words after it are still the helper's.

    A word with a quoted part is an argument's value, not a flag - EXCEPT when
    its unquoted prefix starts with a `--name=` option, which is returned:
    `--kind="message"` still passes `--kind` (counter-model review on #1835).
    """
    events, _ = lex(text, start, backtick_ends=backtick_ends)
    words: list[str] = []
    word: list[str] = []
    prefix: str | None = None
    for kind, ch in events:
        if kind == LITERAL:
            word.append(ch)
        elif kind == QUOTED:
            if prefix is None:
                prefix = "".join(word)
        else:
            if prefix is None:
                if word:
                    words.append("".join(word))
            else:
                # The option name is known whatever its value holds after `=`:
                # `--kind=message$(x)` still passes `--kind` (counter-model
                # review on #1839).
                option = OPTION_PREFIX.match(prefix)
                if option:
                    words.append(option.group(1))
            word.clear()
            prefix = None
    return words


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
    flags_checked = invocations = quoted_paths = commented_paths = 0
    for doc in docs:
        try:
            text = doc.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"UNKNOWN - cannot read {doc.relative_to(root)}: {exc}")
            return 2
        for match in HELPER_PATH.finditer(text):
            name = match.group(1)
            context = path_context(text, match.start())
            if context == "quote":
                quoted_paths += 1
                continue
            if context == "comment":
                commented_paths += 1
                continue
            if name not in cache:
                cache[name] = helper_source(scripts, name)
            source = cache[name]
            if source is None:
                unresolved.add(name)
                continue
            invocations += 1
            line = text.count("\n", 0, match.start()) + 1
            backtick_ends = context == "backtick" or fence_body_start(text, match.start()) is None
            for word in command_words(text, match.end(), backtick_ends=backtick_ends):
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
    if commented_paths:
        print(f"note - {commented_paths} helper path(s) inside a shell comment, not invocations, unchecked",
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

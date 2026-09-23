#!/usr/bin/env python3
"""Refuse an inline host write in the cpp command documents (issue #1132).

`/cpp:init` and `/cpp:update` write host surfaces. #1132 routed every one of
them through `scripts/cpp-host-write.sh`, which declares what it writes and can
be told to defer a surface. This gate keeps it that way.

WITHOUT IT THE SEAM IS TOTAL TODAY AND PARTIAL THE FIRST TIME SOMEBODY ADDS A
`printf`. That is not hypothetical: #1139 routed two `~/.bashrc` blocks and left
two more writing the same file inline, so a defer-set naming `~/.bashrc` refused
two writes, PRINTED A STATED REFUSAL, and wrote the file anyway. A caller told
the surface was protected, and it was not.

## Four write FORMS, not five surfaces

Every enumeration by surface missed something, so this scans by FORM:

- **shell redirect** to a `$HOME`/`~` path, or to a variable holding one
- **indirect shell**: the target is assigned twenty lines above its use, so the
  verb and the path never share a line. This is the shape that hid the
  `~/.bashrc` writes through two separate reviews
- **embedded python** inside a heredoc: `write_text`, `json.dump`, `open(...,"w")`
  satisfy no grep for a redirect, `cp`, `tee`, `mv` or `ln`. This is the shape
  that hid `~/.config/opencode/opencode.json`
- **`mkdir -p`** of a host directory, and `ln -s` into one. A loop matters here:
  one `ln -sf` in the source becomes ninety-odd links at run time, so the
  surface is the DIRECTORY and one site is not one write

## The comment filter is itself a way to be blind

Comments must not red — three false positives in this issue's own analysis came
from a `#` line quoting a write. But a filter that drops any line containing `#`
excuses the write most likely to look like one:

    printf '# managed by cpp' >> "$RC"

So a line is a comment only when its FIRST non-whitespace character is `#`. A
`#` inside a string is not a comment, and `controls/cpp-host-writes` carries
both directions as committed cases.

Usage:
    check-cpp-host-writes.py [--root DIR]

## Two properties, two finding types (issue #1198)

Routing a write through the seam is half the guarantee. The seam answers with
THREE verdicts - wrote (0), deferred by request (3), failed (1) - plus the 127
it returns when it is not installed at all, and a caller that never reads the
answer gets the same checkmark from all four.

Measured on 2026-09-22: `/cpp:update` printed `Flow allowlist merged (52 total
allow rules)` with the seam DEFERRING the surface exactly as asked, and printed
`merged (2 total allow rules)` - the PRE-merge count - with the seam absent
entirely. That is #1139's defect pointing the other way: there, a caller was
told a surface was protected and it was written; here, a caller is told it was
written and it was protected.

So this gate reports two kinds of finding, named separately because they are
different properties and a single red would otherwise mean two things:

- `INLINE-HOST-WRITE:` - a write that does not go through the seam (#1132)
- `UNREAD-SEAM-VERDICT:` - a write that goes through the seam and discards
  its answer (#1198)

THE RULE FOR THE SECOND IS "ALWAYS", NOT "WHEN A CLAIM FOLLOWS". Keying on a
nearby success message would exempt the shape that started this: a `link-into`
loop that calls the seam ninety times, claims nothing, and silently links
nothing when the seam is absent. There is no legitimate reason to write a host
surface and not care whether it happened, so the requirement has no exceptions
to enumerate - and a rule with no exceptions cannot be defeated by phrasing a
claim differently.

Usage:
    check-cpp-host-writes.py [--root DIR]

Output: one `INLINE-HOST-WRITE:` / `UNREAD-SEAM-VERDICT:` line per finding, then
a verdict naming the population scanned and BOTH counts. Exit 0 clean, 1 on any
finding, 2 when the population is empty, which is UNKNOWN rather than clean.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: NEGATIVE-CONTROL: controls/cpp-host-writes
#:
#: This gate lets work THROUGH: `make verify` and the CI step read its green as
#: "every host write in these documents goes through the seam", and nothing
#: downstream re-derives that. A blind version reports the same clean line over
#: the half-seamed state #1139 shipped.

REPO_ROOT = Path(__file__).resolve().parents[1]

#: THE POPULATION, hardcoded and named in the verdict. Only these two documents
#: are scanned; this gate claims nothing about the other command families,
#: which are not in its input. Extending it to every command document is a
#: separate decision, not a silent widening.
DOCUMENTS = (
    ".claude/commands/cpp/init.md",
    ".claude/commands/cpp/update.md",
)

#: The seam. A line invoking it is the fix, not a finding.
SEAM = "cpp-host-write.sh"

HOST = r'(?:\$HOME|\$\{HOME\}|~)/'

FORMS: dict[str, re.Pattern[str]] = {
    #: A redirect whose target is a host path, written out.
    #:
    #: `(?<!-)` is load-bearing and was added after the pattern fired on
    #: `echo "CPP_MEMORIES_DSN -> ~/.config/..."`. The `>` in an ASCII arrow is
    #: not a redirect, and this exact false positive appeared four separate
    #: times in this issue's analysis before it was written down - in a
    #: write-verb survey of the command documents, twice in ad-hoc greps, and
    #: here. A pattern that matches an arrow reports console output as a write.
    "shell-redirect": re.compile(rf'(?<!-)>>?\s*"?{HOST}'),
    #: A redirect whose target is a VARIABLE. Which variables hold host paths
    #: is decided by the assignment scan below, not by this pattern.
    "shell-redirect-var": re.compile(r'(?<!-)>>?\s*"?\$\{?([A-Za-z_][A-Za-z0-9_]*)'),
    #: cp / mv / tee / ln into a host path.
    "shell-command": re.compile(rf'\b(?:cp|mv|tee|ln\s+-s[fn]*)\b[^|]*{HOST}'),
    #: Directory creation under $HOME.
    "mkdir": re.compile(rf'\bmkdir\s+-p\s+"?{HOST}'),
    #: Python inside a heredoc. No shell pattern sees these.
    "embedded-python": re.compile(r'\.write_text\(|json\.dump\(|\bopen\([^)]*[\'"]w[\'"]'),
}

#: A variable assigned a host path. The INDIRECT form: `T="$HOME/.bashrc"` on
#: one line and `>> "$T"` twenty lines below. Tracked per fenced block, because
#: that is the unit a reader of the document executes.
ASSIGN_RE = re.compile(rf'^\s*([A-Za-z_][A-Za-z0-9_]*)=.*{HOST}')

FENCE_RE = re.compile(r"^\s*```")

#: A heredoc opener, so the scan can skip its BODY. Load-bearing for the
#: unread-verdict check below: `seam settings-edit --arg cmd "$C" <<'JQ'`
#: is followed by jq program text, not by shell, so "the next line" is not a
#: shell statement and must not be read as one. `<<-` strips leading tabs from
#: the terminator, which is why the closer is matched with lstrip().
HEREDOC_RE = re.compile(r"<<-?\s*[\'\"]?([A-Za-z_][A-Za-z0-9_]*)[\'\"]?")

#: The seam's exit status is CONSULTED when the invocation is a condition, is
#: chained to a handler ON ITS OWN STATEMENT, or is followed by a statement
#: whose FIRST command reads `$?`.
#:
#: These are shell forms, deliberately - not a list of approved handler names.
#: A gate that enumerated blessed handlers would have to be widened for every
#: new one, and each widening is a chance to admit a handler that discards the
#: answer anyway.
#:
#: BOTH REFINEMENTS BELOW CAME FROM COUNTER-MODEL REVIEW, and both were
#: reproduced before being fixed. The first framing asked only "does this LINE
#: contain an operator" and "does the next LINE contain `$?`" - which is
#: proximity, not association:
#:
#:   ACCEPTED  `<seam call>` then `echo done; rc=$?`
#:             `rc` captures ECHO's status. The seam's answer was discarded and
#:             the gate passed it, which is this issue's own defect living
#:             inside its detector.
#:   ACCEPTED  `true && echo ready; <seam call>`
#:             A chain belonging to a neighbouring command discharged the
#:             seam's obligation.
#:   FLAGGED   `<seam call>`, a BLANK LINE, then `case $?`
#:             Correct code, reported as unguarded - and a false positive on
#:             the fix is what gets a gate switched off rather than repaired.
CONSULT_OPENER_RE = re.compile(r"^\s*(?:if|while|until|elif)\b")
#: A chain that must appear AFTER the invocation, never merely on the line.
CONSULT_CHAIN_RE = re.compile(r"(?:\|\||&&)\s*\S")
CONSULT_STATUS_RE = re.compile(r"\$\?")


#: Shell separators that END a command. Quote-aware below: a `;` inside a
#: string is data, not a separator.
_SEPARATORS = ("||", "&&", ";")


def _split_commands(statement: str) -> list[tuple[str, str]]:
    """Split a statement into `(command, operator_that_follows_it)` pairs.

    The operator matters as much as the split. `<seam> && handler` is consulted
    because `&&` reads the seam's status; `<seam>; echo done && echo ready` is
    NOT, because there the `&&` belongs to `echo done` - and accepting it was
    how a neighbouring command's handler discharged the seam's obligation
    (counter-model review, second pass).
    """
    out: list[tuple[str, str]] = []
    buf: list[str] = []
    quote = ""
    i = 0
    while i < len(statement):
        ch = statement[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        for sep in _SEPARATORS:
            if statement.startswith(sep, i):
                out.append(("".join(buf), sep))
                buf = []
                i += len(sep)
                break
        else:
            buf.append(ch)
            i += 1
    out.append(("".join(buf), ""))
    return out


def _first_command_reads_status(statement: str) -> bool:
    """True when `$?` is read by the FIRST command of `statement`.

    `$?` holds the status of the immediately preceding command, so anything
    after a `;` has already had it overwritten by whatever ran in between.
    Splitting on `;` and looking only at the head is what separates
    `rc=$?` from `echo done; rc=$?`.
    """
    head = statement.split(";", 1)[0]
    return bool(CONSULT_STATUS_RE.search(head))


def _same_statement_handler(after_seam: str) -> bool:
    """True when the seam's own statement carries its handler.

    Two forms: a `||`/`&&` chain, and a `;` separator whose next command reads
    the status (`<seam call>; rc=$?`), which is a legitimate spelling the
    line-based version reported as unguarded.
    """
    if CONSULT_CHAIN_RE.search(after_seam):
        return True
    if ";" in after_seam:
        return _first_command_reads_status(after_seam.split(";", 1)[1])
    return False


def is_comment(line: str) -> bool:
    """True only when the FIRST non-whitespace character is `#`.

    Deliberately not "contains a #". A filter that dropped every line with a
    hash would excuse `printf '# managed by cpp' >> "$RC"` - a real write whose
    line merely looks like a comment, and the one such a filter is most likely
    to meet.
    """
    return line.lstrip().startswith("#")


def scan(text: str) -> list[tuple[int, str, str]]:
    """Every inline host write in a document's fenced blocks."""
    findings: list[tuple[int, str, str]] = []
    in_fence = False
    host_vars: set[str] = set()
    for lineno, line in enumerate(text.split("\n"), 1):
        if FENCE_RE.match(line):
            if not in_fence:
                #: Variables do not survive a fence boundary: each block is a
                #: separate execution for a reader following the document.
                host_vars = set()
            in_fence = not in_fence
            continue
        if not in_fence or is_comment(line):
            continue
        m = ASSIGN_RE.match(line)
        if m:
            host_vars.add(m.group(1))
        if SEAM in line:
            continue
        for form, pattern in FORMS.items():
            hit = pattern.search(line)
            if not hit:
                continue
            if form == "shell-redirect-var":
                #: Only a variable KNOWN to hold a host path counts. Without
                #: this the form would red on every `> "$tmp"` in the tree.
                if hit.group(1) not in host_vars:
                    continue
            findings.append((lineno, form, line.strip()))
            break
    return findings


#: AN INVOCATION IN COMMAND POSITION, not a mention anywhere on the line.
#:
#: The first framing was `<seam>\s+<subcommand>` searched anywhere, and it was
#: wrong in BOTH directions - found by counter-model review, and both directions
#: reproduced before this was rewritten:
#:
#:   MISSED  `"$CPP_DIR/scripts/cpp-host-write.sh" link-into ...`
#:           A closing QUOTE sits between `.sh` and the space, so `\s+` did not
#:           match. That is the bootstrap THIS ISSUE ADDED: the gate could not
#:           see the very calls whose verdicts it exists to require, and
#:           deleting their handlers still produced a clean verdict.
#:   FLAGGED `echo "Run cpp-host-write.sh settings-merge to install"`
#:           A sentence naming the helper became an unread-verdict finding,
#:           though nothing was invoked. A gate that reds on its own
#:           documentation is one people delete.
#:
#: So position is what decides, not proximity. A statement invokes the seam when
#: the seam is the COMMAND: at the head of the statement, optionally behind a
#: `VAR=` or `VAR=$(` capture, with the path optionally quoted. A seam named
#: inside an argument is never in that position, which is what makes prose safe
#: without a keyword list of commands to excuse.
SEAM_INVOKE_RE = re.compile(
    r"""^\s*                               # statement head
        (?:[A-Za-z_][A-Za-z0-9_]*=\$\(\s*)?   # ONLY the $( form is a command
        (?P<q>["']?)                       # optional opening quote
        (?:[^\s"';|&=]*/)?                  # optional path, CLOSED BY A SLASH
        #: `=` is excluded from the path so `SEAM=~/.../cpp-host-write.sh cmd`
        #: is not read as an invocation: that is an ENVIRONMENT ASSIGNMENT
        #: whose executed command is `cmd`, and flagging it attributes a
        #: neighbouring command to the seam.
        """ + re.escape(SEAM) + r"""
        (?P=q)                             # the SAME quote closes it
        \s+[a-z][a-z-]*\b                   # and a subcommand follows
    """,
    re.VERBOSE,
)


def _shell_statements(text: str):
    r"""Yield `(lineno, statement)` for shell inside fenced blocks.

    Two joins the naive "look at the next line" version gets wrong, both
    present in the scanned documents:

    - **Backslash continuations.** `json-merge-sections \` puts the seam on one
      line and its arguments on the next, so the following LINE is the same
      STATEMENT and reading it as the handler finds arguments.
    - **Heredoc bodies.** `settings-edit --arg cmd "$C" <<'JQ'` is followed by a
      jq program. Those lines are data, not shell, and a `$?` appearing inside
      one would otherwise read as the caller checking the status.
    """
    in_fence = False
    heredoc_tag: str | None = None
    pending: tuple[int, str] | None = None
    for lineno, raw in enumerate(text.split("\n"), 1):
        if heredoc_tag is not None:
            #: `<<-` strips leading tabs from the terminator, so compare stripped.
            if raw.strip() == heredoc_tag:
                heredoc_tag = None
            continue
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            pending = None
            continue
        if not in_fence:
            continue
        if pending is None and is_comment(raw):
            continue
        start, acc = pending if pending else (lineno, "")
        acc = (acc + " " + raw.strip()).strip() if acc else raw.strip()
        if raw.rstrip().endswith("\\"):
            pending = (start, acc.rstrip("\\ "))
            continue
        pending = None
        opener = HEREDOC_RE.search(acc)
        if opener:
            heredoc_tag = opener.group(1)
        yield start, acc


def scan_unread_verdicts(text: str) -> list[tuple[int, str]]:
    """Every seam invocation whose exit status is discarded (issue #1198).

    The seam returns 0 wrote / 3 deferred-by-request / 1 failed, and 127 when
    it is not installed. A caller that reads none of them cannot tell those
    apart, and every one of the scanned documents' success messages is printed
    unconditionally on the following line.
    """
    findings: list[tuple[int, str]] = []
    statements = list(_shell_statements(text))
    for idx, (lineno, line) in enumerate(statements):
        if CONSULT_OPENER_RE.match(line):
            continue
        #: PER COMMAND, not per line (counter-model review, second pass). The
        #: line-head version could not see `true && echo ready; <seam call>` at
        #: all - a fix for a false positive that introduced a false negative.
        commands = _split_commands(line)
        for pos, (command, following_op) in enumerate(commands):
            if not SEAM_INVOKE_RE.search(command):
                continue
            #: Only the operator IMMEDIATELY after the seam reads its status.
            if following_op in ("&&", "||"):
                continue
            #: The very next command: in this statement after a `;`, else the
            #: first command of the next NON-BLANK statement. A blank line
            #: before `case $?` is ordinary formatting, and calling it "no
            #: handler" reported correct code as unguarded.
            successor = ""
            if pos + 1 < len(commands):
                successor = commands[pos + 1][0]
            else:
                for _, candidate in statements[idx + 1:]:
                    if candidate.strip():
                        successor = _split_commands(candidate)[0][0]
                        break
            if _first_command_reads_status(successor):
                continue
            findings.append((lineno, command.strip() or line.strip()))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    args = ap.parse_args(argv)

    present = [rel for rel in DOCUMENTS if (args.root / rel).is_file()]
    if not present:
        print(
            "check-cpp-host-writes: UNKNOWN - none of the "
            f"{len(DOCUMENTS)} scanned document(s) exist under {args.root}; "
            "the check would pass vacuously",
            file=sys.stderr,
        )
        return 2

    inline_total = 0
    unread_total = 0
    for rel in present:
        text = (args.root / rel).read_text(encoding="utf-8")
        for lineno, form, line in scan(text):
            inline_total += 1
            print(
                f"INLINE-HOST-WRITE: {rel}:{lineno} [{form}] writes a host "
                f"surface without going through {SEAM}: {line[:90]}"
            )
        for lineno, line in scan_unread_verdicts(text):
            unread_total += 1
            print(
                f"UNREAD-SEAM-VERDICT: {rel}:{lineno} invokes {SEAM} and "
                f"discards its exit status, so wrote / deferred / failed / "
                f"not-installed are indistinguishable here: {line[:90]}"
            )

    scanned = ", ".join(present)
    #: BOTH counts in the verdict, always. The two findings are different
    #: properties (#1132 routes the write, #1198 reads the answer), and a
    #: single "FAIL - 3 finding(s)" would leave a reader unable to tell which
    #: guarantee this run lost.
    if inline_total or unread_total:
        print(
            f"check-cpp-host-writes: FAIL - {inline_total} inline host write(s) "
            f"and {unread_total} unread seam verdict(s) in {len(present)} "
            f"document(s). Route every write through {SEAM} so the surface is "
            "declared and a defer-set can refuse it, and read the status it "
            "returns so a refusal is not reported as a write."
        )
        return 1
    print(
        f"check-cpp-host-writes: ok - no inline host writes and no unread seam "
        f"verdicts in {scanned}. This says nothing about any other command "
        "family: those documents are not in this gate's input."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

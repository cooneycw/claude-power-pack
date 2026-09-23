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

Output: one `INLINE-HOST-WRITE:` line per finding, then a verdict naming the
population scanned. Exit 0 clean, 1 on any finding, 2 when the population is
empty, which is UNKNOWN rather than clean.
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

    total = 0
    for rel in present:
        for lineno, form, line in scan((args.root / rel).read_text(encoding="utf-8")):
            total += 1
            print(
                f"INLINE-HOST-WRITE: {rel}:{lineno} [{form}] writes a host "
                f"surface without going through {SEAM}: {line[:90]}"
            )

    scanned = ", ".join(present)
    if total:
        print(
            f"check-cpp-host-writes: FAIL - {total} inline host write(s) in "
            f"{len(present)} document(s). Route them through {SEAM} so the "
            "surface is declared and a defer-set can refuse it."
        )
        return 1
    print(
        f"check-cpp-host-writes: ok - no inline host writes in {scanned}. "
        "This says nothing about any other command family: those documents are "
        "not in this gate's input."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""ANCHOR - a deliberately BLIND version of scripts/check-cpp-host-writes.py.

DO NOT FIX THIS FILE. It is evidence, not code that runs in anger.

THIS IS THE FIRST FRAMING, and it is the one this issue actually started from:
grep the command documents for a redirect to a `$HOME` path, and treat any line
containing a hash as a comment. Two differences from the gate, both the obvious
first choice:

  FORMS       only `shell-redirect`. No variable tracking, no embedded python,
              no mkdir. A write whose target is assigned twenty lines above its
              use, or performed by `cfg_path.write_text()` inside a heredoc,
              is invisible.
  is_comment  `"#" in line` rather than `line.lstrip().startswith("#")`.

WHAT IT MISSES, and each was a real miss before it was a fixture: the indirect
form hid two `~/.bashrc` writes through #1139 and a review; the embedded-python
form hid `~/.config/opencode/opencode.json` from three successive
enumerations; `mkdir` was never counted as a surface at all; and the naive
comment filter excuses `printf '# managed by cpp' >> "$RC"`.

WHAT IT AGREES ON: the good case. That is what keeps the demonstration isolated
rather than a blanket disagreement.

A NOTE ON A CASE THAT IS NOT HERE. `bad-same-line-redirect` was written and
then REMOVED from the register: this anchor catches it, because a same-line
redirect is the one form the first framing did implement. A case whose expected
answer BOTH sides produce demonstrates nothing about the difference between
them - the same trap that nearly shipped in #1139's control, where a defer
spelled one way matched by plain string equality on both the fixed gate and the
broken one. The form is still exercised, by the real documents, on every run.
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
    "shell-redirect": re.compile(rf'>>?\s*"?{HOST}'),
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
    return "#" in line


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

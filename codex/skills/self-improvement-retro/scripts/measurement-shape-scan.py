#!/usr/bin/env python3
"""Flag cwd-relative git measurement shapes in a session transcript (issue #666).

CLAUDE.md carries the rule (issue #659):

    In shared checkouts, characterize branch/repo state with ref-scoped reads
    only - `git -C <repo-root>` with full refs, `git show <ref>:<path>` - never
    a bare relative pathspec and never a working-tree grep standing in for a
    BRANCH's content.

The rule exists because the Bash tool's cwd drifts between calls, and once it
sits in a subdirectory every relative pathspec matches nothing: `git diff A B
-- ui/` returns an EMPTY diff, indistinguishable from "no changes". During the
2026-08-11 damage assessment four such reads agreed with each other and were
all wrong; the failure produces confident false conclusions, not errors.

The directive is prevention. This script is the detection half: it scans a
recorded session transcript for commands matching the trap shape so
`/self-improvement:retro` (replay mode) can surface each hit as a red-output
friction signal. Findings ride the EXISTING friction pipeline - this tool adds
no new report surface.

Why a retro-side scanner and not a PostToolUse hook (the #666 decision)
-----------------------------------------------------------------------
The permission census hook cannot see this shape: an allowlisted read-only
`git diff` never shows a permission dialog, so it never enters the census
buffer. The remaining always-on option - a PostToolUse observer pattern-matching
every Bash call - would pay per-call latency on hundreds of harmless commands
per session to catch a rare shape, and would fire mid-run when nothing can act
on it. The retro is the designed drain point for looking back at a finished
run, already has a replay mode that parses transcripts, and runs only when
invoked. Cost falls on the reader of a transcript, once, instead of on every
command of every session.

What is flagged
---------------
- warn: `git diff|show|log ... -- <relative-pathspec>` with no `-C <path>`
  anchoring the command. A pathspec is relative when it starts with neither
  `/` (absolute) nor `:` (pathspec magic such as `:(top)` or `:/`, which is
  root-anchored).
- info: `git grep ...` with no `-C` and no recognizable ref among its
  arguments - working-tree content possibly standing in for a branch. Ref
  recognition is a heuristic (HEAD/FETCH_HEAD/refs/... /origin/... etc.), so
  this tier is informational only.

What is deliberately NOT flagged
--------------------------------
- `git -C <path> diff A B -- ui/` - the `-C` anchors relative pathspecs to a
  DECLARED root; this is the sanctioned shape.
- Absolute or magic pathspecs (`-- /abs/path`, `-- ':(top)ui/'`).
- Ref-scoped reads with no pathspec (`git diff A B`, `git show ref:path`).

Honesty floor: a transcript cannot prove where the shell's cwd was when a
command ran - a relative pathspec typed from a verified repo root is
legitimate. Findings are therefore advisory signals for the retro to judge
(the false-positive guard from #666), never auto-fixes, and the scan targets
the literal shape that actually failed on 2026-08-11, not every conceivable
disguise. Prose in a transcript that quotes the trap shape as an example (docs,
CLAUDE.md excerpts) is a known false-positive class the retro filters.

Usage:
    measurement-shape-scan.py <transcript> [<transcript> ...] [--json]

Output ends with a greppable marker: `MEASUREMENT_SHAPES: <warn-count>`.
Exit codes: 0 = scan ran (findings or not - advisory, the flow-stale-check
posture); 2 = a named transcript could not be read.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

# Subcommands whose relative pathspec after `--` is the #659 trap shape.
WARN_SUBCOMMANDS = {"diff", "show", "log"}

# Heuristic ref recognition for the info-level `git grep` tier.
REF_TOKEN = re.compile(
    r"^(HEAD([~^]\d*)?|ORIG_HEAD|FETCH_HEAD|MERGE_HEAD|refs/\S+|origin/\S+"
    r"|upstream/\S+|main|master|[0-9a-f]{7,40})$"
)

# A git invocation inside a transcript line: `git` at a word boundary up to a
# shell separator. Transcripts wrap commands in JSON strings, markdown fences
# and prose alike, so segmentation is intentionally rough.
GIT_SEGMENT = re.compile(r"\bgit\s+[^;|&`\n]+")


def _tokenize(segment: str) -> list[str]:
    """Best-effort shell tokenization; falls back to whitespace split."""
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def _subcommand(tokens: list[str]) -> str | None:
    """First non-flag token after `git`, skipping `-C <path>`/`-c k=v` pairs."""
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-C", "-c", "--git-dir", "--work-tree"):
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        return tok
    return None


def _has_declared_root(tokens: list[str]) -> bool:
    return "-C" in tokens[1:] or any(
        t.startswith(("--git-dir", "--work-tree")) for t in tokens[1:]
    )


def _relative_pathspecs(tokens: list[str]) -> list[str]:
    """Pathspec tokens after a standalone `--` that are cwd-relative."""
    if "--" not in tokens:
        return []
    specs = tokens[tokens.index("--") + 1 :]
    return [s for s in specs if s and not s.startswith(("/", ":", "-"))]


def scan_line(line: str) -> list[dict[str, str]]:
    """Return findings for one transcript line."""
    findings: list[dict[str, str]] = []
    for match in GIT_SEGMENT.finditer(line):
        segment = match.group(0).rstrip()
        tokens = _tokenize(segment)
        if len(tokens) < 2 or _has_declared_root(tokens):
            continue
        sub = _subcommand(tokens)
        if sub in WARN_SUBCOMMANDS:
            rel = _relative_pathspecs(tokens)
            if rel:
                findings.append(
                    {
                        "category": "relative-pathspec",
                        "level": "warn",
                        "command": segment,
                        "pathspec": " ".join(rel),
                    }
                )
        elif sub == "grep":
            args = tokens[2:]
            if not any(REF_TOKEN.match(t) for t in args):
                findings.append(
                    {
                        "category": "worktree-grep",
                        "level": "info",
                        "command": segment,
                        "pathspec": "",
                    }
                )
    return findings


def scan_file(path: Path) -> list[dict[str, Any]]:
    """Scan a transcript file; findings carry file and 1-based line number."""
    findings: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        for f in scan_line(line):
            findings.append({"file": str(path), "line": lineno, **f})
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flag cwd-relative git measurement shapes in transcripts (#666)."
    )
    parser.add_argument("transcripts", nargs="+", help="transcript file(s) to scan")
    parser.add_argument(
        "--json", action="store_true", help="emit findings as one JSON object"
    )
    args = parser.parse_args(argv)

    findings: list[dict[str, Any]] = []
    for name in args.transcripts:
        path = Path(name)
        try:
            findings.extend(scan_file(path))
        except OSError as exc:
            print(f"measurement-shape-scan: cannot read '{name}': {exc}", file=sys.stderr)
            return 2

    warn = [f for f in findings if f["level"] == "warn"]
    info = [f for f in findings if f["level"] == "info"]

    if args.json:
        print(
            json.dumps(
                {"findings": findings, "counts": {"warn": len(warn), "info": len(info)}}
            )
        )
    else:
        for f in findings:
            print(f"{f['file']}:{f['line']}: {f['level']}: {f['category']}: {f['command']}")
        if info and not warn:
            print("(info findings only - heuristic tier, judge before acting)")
    print(f"MEASUREMENT_SHAPES: {len(warn)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

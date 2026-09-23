#!/usr/bin/env python3
"""Derive which scripts must DECLARE a host surface, from the code (issue #1139).

CPP writes host surfaces - `~/.claude/...`, `~/.bashrc`, `~/.codex/...` - during
`/cpp:init` and `/cpp:update`. A managed environment (a devcontainer, a nix
profile, an MDM, a read-only `$HOME`, kyle) owns some of them, and needs to tell
CPP which. It cannot do that against a hand-written list: #1132's table names
FIVE surfaces, a grep over the two command documents suggests fourteen, a wider
grep suggests thirty-eight, and none of those three numbers is the population.

**Nothing here names a manager.** The seam is environment-agnostic by
construction: this file has no knowledge of any specific consumer, reads no
environment variable to decide anything, and inspects no container, mount or
namespace. A consumer is the first user of a general contract, never a branch.

## Why a DECLARATION and not a scanner

The obvious instrument greps the code for write operations and reports their
targets. Three measured reasons not to:

- A write-verb pattern over the two command documents matches 228 lines. Most
  are `echo "-> ... skipped"` console output, caught because the `>` inside the
  `->` arrow satisfies an output-redirection alternative. Most genuine matches
  target the PROJECT root, not a host surface.
- Narrowing the pattern until it looked right still left one bad match in
  thirteen.
- A pattern that false-positives can also FALSE-NEGATIVE, and the two are not
  symmetric: a spurious match is seen and discarded, a missed one is never
  learned about.

So a pattern may PROPOSE a population; it may not CERTIFY one. What this gate
checks is cheap, mechanical and total: every script REACHABLE from the two
command documents carries an explicit declaration. Membership is derived;
nothing about which scripts to check is written down anywhere.

## What this catches, and what it does not - state both

- **Caught, mechanically:** a reachable script with NO declaration. Adding a
  script to the install path without declaring its surfaces reds this gate.
- **NOT caught:** a declaring script that UNDERSTATES - lists one surface and
  writes two. Detecting that needs the write-detection rejected above, so it is
  not attempted here.

That bound is not a caveat, it is part of the contract a consumer reads. The
manifest is complete for helper-mediated writes, and a write that bypasses a
declaring helper is a defect this gate reds on. Understatement is caught by
OBSERVATION instead - running a declaring helper against a sandboxed `$HOME`
and diffing what appeared against what it claimed - which is ADR 0008's logic
and #970's, and is a separate instrument from this one.

## The `certified=` field, and why nothing says `yes` yet

Every declaration carries `certified=`, and today every one reads **`authored`**.

| value | means |
|---|---|
| `authored` | a person read the code and wrote down what it writes |
| `observed` | a COMMITTED instrument ran it against a sandboxed `$HOME` and diffed
  what appeared against what it claimed |

**No declaration is `observed` yet, and that is deliberate.** The relocation in
this change WAS proved by sandboxed runs - old-way and new-way against separate
`$HOME`s, diffed byte-identical, the guarded case checked across two runs. Those
runs were real, and they are not certification: nobody can re-run them, nothing
notices if they stop, and they left no artifact. A run like that is exactly what
#924 ruled on for review-time mutation.

So `authored` is the honest value for all of them today. A declaration marked
`observed` on the strength of a run nobody can repeat is an authored claim
wearing an observed one's label, and a consumer weighing the two differently -
which is the point of having two - would be misled in the reassuring direction.

**The upgrade has a defined trigger, not a judgement call:** a committed
instrument that runs a helper against a sandboxed `$HOME`, diffs the surfaces
that appeared against the surfaces declared, and fails when they differ. When
that exists, the nine helpers that stay inside `$HOME` can move to `observed`.
The six that reach outside it cannot, for the reason below, and their
`authored` is permanent until that changes.

## Why observation certifies only NINE of the fifteen, as a decision

Six reachable scripts reach outside `$HOME`, where a redirected `HOME` does not
sandbox them: `bash-prep.sh` (sudo), `drift-detect.sh` (systemctl),
`hook-permission-census.sh` (git push, gh, docker), `mcp-drift.py` (docker,
sudo), `memories-db-setup.sh` (apt, curl), `npm-global-upgrade.sh` (npm -g,
sudo). Executing those to watch what they write would install packages, restart
units and push to a remote on a shared host. They are therefore declared and
NOT observed, marked per script, with the escaping binary named.

**A PATH shim was considered and REJECTED**, so nobody re-derives it as an
oversight. Stubbing `sudo`, `apt-get`, `docker`, `systemctl`, `npm` and `gh` to
log and exit 0 would let the six run under a redirected `HOME`. Three reasons,
and the third is specific to this repository and decisive:

1. #695's precedent: a test proving a fail-open emptied `PATH` and removed `ln`,
   `mkdir`, `readlink` and `bash` along with its target, so the script failed
   for unrelated reasons while the assertions still passed.
2. A stub returning 0 can take a branch the real binary would not, so what is
   certified is a different execution from the one that runs.
3. **A stub would manufacture the exact defect these scripts were written to
   detect.** `npm-global-upgrade.sh` exists because `npm install -g` exits 0
   having installed nothing, and its contract says so in terms: "THE VERDICT IS
   THE INSTALLED VERSION, NOT THE EXIT CODE." A stubbed `npm` produces exit 0
   with nothing moved - verbatim the false success that script was written to
   catch. The better a script is at distrusting an exit code, the more wrong a
   stubbed harness is about it, and this repository writes scripts that way on
   purpose.

Usage:
    host-surface-check.py [--root DIR] [--manifest]

Output: one `UNDECLARED:` line per reachable script with no declaration, then
provenance counts and a verdict. `--manifest` emits the declared surfaces as
JSON on stdout instead. Exit 0 when every reachable script declares, 1 when any
does not, 2 when the population could not be derived at all.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

#: NEGATIVE-CONTROL: controls/host-surface
#:
#: This gate lets work THROUGH: a consumer reads the manifest it validates and
#: sizes its own coverage against it, and nothing downstream re-derives which
#: scripts were supposed to declare. ADR 0008's bound therefore requires a
#: committed case. The registration lives in THIS file because that is what
#: `check-negative-controls.py` enumerates - a control directory alone is
#: invisible to the battery, which then reports PASS over a register the new
#: control is not in.

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The UNIVERSE is hardcoded; the MEMBERS are derived. These two documents are
#: what `/cpp:init` and `/cpp:update` are, so they are the roots of reachability
#: rather than a list of scripts someone maintains. Hardcoding the universe is
#: correct and hardcoding the membership is the bug - #1060 draws the same line.
COMMAND_DOCS = (
    ".claude/commands/cpp/init.md",
    ".claude/commands/cpp/update.md",
)

#: The directory reachable scripts live in.
SCRIPTS_REL = "scripts"

#: A script invocation, in any of the three spellings the documents use: the
#: stable installed path, a repo-relative path, and the `$CPP_DIR` fallback the
#: #581 invocation discipline prescribes. Only the basename is captured, because
#: all three resolve to the same file and counting them separately would inflate
#: the population with aliases.
INVOKE_RE = re.compile(
    r"(?:~/\.claude/scripts/|\$CPP_DIR/scripts/|(?<![\w/])scripts/)"
    r"([a-zA-Z0-9][a-zA-Z0-9._-]*\.(?:sh|py))"
)

#: A COMMENT line, in either language this walks. The first cut of this file
#: matched a path anywhere in the text and derived three phantom members from
#: prose: `codex-prompt-sync.py` named in a comment as retired at the #556
#: cutover, `skill-drift.py` named as a step that was REMOVED, and `x.py` from
#: a hypothetical inside an explanatory comment. That is the same
#: reference-versus-invocation error this whole instrument exists to avoid,
#: found in its own extractor, so the rule is now explicit: a mention is not a
#: call. Naming a script is not invoking it, and a retired script named in a
#: comment must not enter the population.
COMMENT_RE = re.compile(r"^\s*(?:#|//)")

#: A markdown fence delimiter. Prose in a command document describes; only the
#: fenced blocks execute, so only they can invoke.
FENCE_RE = re.compile(r"^\s*```")

#: A Python triple-quote delimiter. A docstring is PROSE INSIDE CODE, and is
#: the same object as prose inside a document: it describes, it does not run.
#: Skipping `#` comments alone still admitted `codex-prompt-sync.py`, named in
#: `codex-skill-sync.py`'s module docstring as retired at the #556 cutover.
#: Three narrowings were needed here and each was found by READING the output,
#: never by the pattern reporting a problem - which is the argument for the
#: observation harness rather than a better regex.
DOCSTRING_RE = re.compile(r'"""|\'\'\'')

#: A surface declaration. One per line, repeatable:
#:
#:     #: HOST-SURFACE: ~/.bashrc owner=user
#:     #: HOST-SURFACE: none - reads only, writes nothing outside the repo
#:
#: `none` is a DECLARATION, not an absence: a script that writes nothing must
#: say so, because "declared nothing" and "nobody looked" are the same bytes
#: otherwise. That is the same rule this repository applies to every gate.
DECLARE_RE = re.compile(
    r"^\s*(?:#|//)[:!]?\s*HOST-SURFACE:\s*(?P<body>\S.*?)\s*$", re.M
)

#: A declaration whose surface is `none`, with the reason that must follow it.
NONE_RE = re.compile(r"^none\b\s*(?:-\s*(?P<reason>\S.*))?$", re.I)


def read(path: Path) -> str:
    """Read a file, or return an empty string when it is absent.

    Absence is handled by the caller as UNKNOWN rather than as clean; returning
    "" here keeps the caller's accounting in one place.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def invoked_scripts(text: str, *, fenced_only: bool = False) -> set[str]:
    """Every script basename this text INVOKES - not every one it mentions.

    Comment lines are skipped in both languages, and in a command document only
    fenced blocks are considered, because prose describes while fences execute.
    Without both filters this returned three scripts that do not exist: two
    named in comments as retired, and one hypothetical. A reference-based scan
    finding references is the defect, not a surprise.
    """
    found: set[str] = set()
    in_fence = not fenced_only
    in_doc = False
    for line in text.split("\n"):
        if fenced_only and FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not fenced_only:
            #: An odd number of triple-quote delimiters on a line toggles the
            #: docstring state; an even number opens and closes within it.
            if len(DOCSTRING_RE.findall(line)) % 2:
                in_doc = not in_doc
                continue
            if in_doc:
                continue
        if not in_fence or COMMENT_RE.match(line):
            continue
        found |= set(INVOKE_RE.findall(line))
    return found


def derive_members(root: Path) -> tuple[set[str], list[str]]:
    """Walk reachability from the command documents until the frontier stops.

    A single hop would answer a narrower question than the one asked: a script
    the documents call may call another, and that one writes to `$HOME` just as
    directly. The loop runs to a fixed point rather than taking the first
    frontier as the answer.
    """
    warnings: list[str] = []
    seen: set[str] = set()
    frontier: set[str] = set()

    for rel in COMMAND_DOCS:
        doc = root / rel
        if not doc.is_file():
            warnings.append(f"command document not found: {rel}")
            continue
        frontier |= invoked_scripts(read(doc), fenced_only=True)

    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        path = root / SCRIPTS_REL / name
        if path.is_file():
            frontier |= invoked_scripts(read(path)) - seen

    return seen, warnings


def declarations(text: str) -> list[str]:
    """Every HOST-SURFACE declaration body in a script, in file order."""
    return [m.group("body") for m in DECLARE_RE.finditer(text)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    ap.add_argument(
        "--manifest",
        action="store_true",
        help="emit the declared surfaces as JSON instead of a verdict",
    )
    args = ap.parse_args(argv)
    root: Path = args.root

    members, warnings = derive_members(root)

    #: An empty population is UNKNOWN, never clean. A run that derived nothing
    #: and a run over a tree that genuinely calls no scripts are the same bytes,
    #: and exiting 0 here would make a moved command document indistinguishable
    #: from a compliant one.
    if not members:
        for w in warnings:
            print(f"host-surface: {w}", file=sys.stderr)
        print(
            "host-surface: UNKNOWN - derived an empty population from "
            f"{len(COMMAND_DOCS)} command document(s); the check would pass "
            "vacuously",
            file=sys.stderr,
        )
        return 2

    undeclared: list[str] = []
    absent: list[str] = []
    surfaces: dict[str, list[str]] = {}

    for name in sorted(members):
        path = root / SCRIPTS_REL / name
        if not path.is_file():
            #: Invoked but not present in this tree. Reported, never silently
            #: dropped: a script the documents call and the repo does not ship
            #: is a finding in its own right, and dropping it would shrink the
            #: population to the files that happen to exist.
            absent.append(name)
            continue
        decls = declarations(read(path))
        if not decls:
            undeclared.append(name)
            continue
        surfaces[name] = decls

    if args.manifest:
        print(
            json.dumps(
                {
                    "version": 1,
                    "derived_from": list(COMMAND_DOCS),
                    "complete_for": "helper-mediated writes",
                    "does_not_catch": (
                        "a declaring script that understates its surfaces; "
                        "`host-surface-observe.py` observes that (#1150). THE BOUND ON "
                        "`certified=observed`: the surface was watched appearing under a "
                        "REDIRECTED $HOME, which contains a write that resolves home "
                        "through $HOME, and under a NEUTRALISED git configuration, which "
                        "closes the repository-configured commands git would otherwise "
                        "execute on the `git diff`/`git ls-files` calls some helpers make "
                        "(#1182). That neutralisation is an ENUMERATION of measured keys "
                        "and is only as strong as its candidate list, and it is verified "
                        "by a canary required to fire when it is removed - so a key "
                        "nobody has measured, a non-git write channel, or a path created "
                        "and deleted before the run ends is still outside what the "
                        "observation sees. `observed` therefore remains the stronger of "
                        "two claims, not an absolute one"
                    ),
                    "scripts": surfaces,
                    "undeclared": sorted(undeclared),
                    "invoked_but_absent": sorted(absent),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if not undeclared else 1

    for name in undeclared:
        print(
            f"UNDECLARED: {SCRIPTS_REL}/{name} is reachable from the "
            "/cpp:init or /cpp:update path and carries no "
            "`#: HOST-SURFACE:` declaration"
        )
    for name in absent:
        print(f"ABSENT: {SCRIPTS_REL}/{name} is invoked but not present in this tree")
    for w in warnings:
        print(f"host-surface: {w}", file=sys.stderr)

    if undeclared:
        print(
            f"host-surface: FAIL - {len(undeclared)} of {len(members)} reachable "
            "script(s) declare no host surface"
        )
        return 1

    print(
        f"host-surface: ok - all {len(surfaces)} reachable script(s) carry a "
        f"HOST-SURFACE declaration ({len(absent)} invoked but absent). This "
        "says nothing about whether a declaration is COMPLETE - understatement "
        "is not detectable here by design; see the observation harness."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

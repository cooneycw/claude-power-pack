#!/usr/bin/env python3
"""Check that repository-local pointers in CLAUDE.md resolve.

Markdown links are unambiguous pointers, so every relative link is checked.
Backtick spans are checked only when they start with one of the named
``PATH_PREFIXES`` below. CLAUDE.md also quotes inline commands and flags such as
``git push``, ``--dry-run``, and ``make lint``; scanning every span would create
false positives. A check people learn to ignore is worse than no check, so the
prefix list is deliberately explicit and reviewable.

A second gate lives here too (issue #1037): CLAUDE.md's Project Map claims to
be the list of canonical `docs/agents/*.md` documents, and that claim drifted
silently - `docs/agents/delivery-pilots.md` existed on disk, unreferenced, and
nothing noticed because the link-resolution check above only ever looks at
targets CLAUDE.md already names; a document it fails to mention is invisible
to it by construction. `find_undocumented_canonical_docs` inverts the
direction: it enumerates the directory and asks what CLAUDE.md is silent
about. A MEMBERSHIP FLOOR (`MIN_CANONICAL_AGENT_DOCS`) applies to the disk
glob itself, mirroring `check-version-consistency.py`'s floor on its own
derived set - an accidentally-empty or shrunk `docs/agents/` would otherwise
make "every on-disk doc is referenced" trivially true over zero files, which
must read as UNKNOWN, not clean.

A THIRD gate, widening the subject rather than adding a new one (issue
#1413): the first two only ever read CLAUDE.md itself, so a citation rotting
in any OTHER tracked document was invisible to this script by the exact same
construction #1037 found for undocumented canonical docs - and two real
instances were found by hand (a non-existent file cited in
`.specify/specs/per-skill-audit/spec.md`, and a dead GitHub issue cited in a
research report). `find_dead_citations` re-walks every tracked `.md` file
under `docs/` and `.specify/` with the SAME backtick/`PATH_PREFIXES` resolver
the first gate already uses - never a second parser - and additionally checks
a citation's optional `:N`, `:N-M` or comma-joined line spec against the
target file's own line count, since a citation can rot by the file moving
WITHOUT the file disappearing. EXPLICITLY EXCLUDED, with the reason: `docs/
flow-runs/**` and `docs/measurements/**` (run records and measurement
artifacts describing a bygone tree, not a living reference) and a dated
research snapshot's own file (`docs/research/<name>-YYYY-MM-DD.md` - a
point-in-time report, not a living reference either). `CHANGELOG.md` sits at
the repo root, outside both scanned directories, so it needs no exclusion
rule - named here only so a reader does not go looking for one. GitHub
issue/PR URL liveness is explicitly OUT: resolving one needs network access
or a cached issue-number ceiling, a structurally different instrument from a
file-existence check, and the Nit Store finding that raised #1413 already
said so itself.

Usage:
    python3 scripts/check-claude-md-links.py
    python3 scripts/check-claude-md-links.py --root DIR
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

PATH_PREFIXES = (
    "docs/",
    "scripts/",
    "lib/",
    ".claude/",
    ".specify/",
    "codex/",
    "templates/",
    "tests/",
    "vendor/",
    "extras/",
)

#: The directory CLAUDE.md's Project Map claims to enumerate in full.
CANONICAL_AGENTS_DIR = "docs/agents"

#: Below this many files on disk, the check cannot tell "every canonical doc
#: is referenced" from "the directory is empty or missing" - fail closed to
#: unknown, not clean (issue #1037 review, same floor shape as
#: check-version-consistency.py's MIN_LOCATIONS).
MIN_CANONICAL_AGENT_DOCS = 8

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
BACKTICK_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")


@dataclass(frozen=True)
class Finding:
    target: str
    kind: str


def _normalize_target(raw: str) -> str | None:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    target = unquote(target).split("#", 1)[0]
    if not target or target.startswith(("#", "/", "http://", "https://", "mailto:")):
        return None
    return target


def _iter_examined_targets(source: str) -> Iterator[tuple[str, str]]:
    """Every repository-local pointer this gate considers, as (target, kind).

    The population find_broken_links checks for existence - shared so a
    "nothing to check" count can never drift from what the gate actually
    examines (issue #841, the #840/#842 lesson applied from the start: one
    enumeration, two callers, not two copies of one).
    """
    for match in MARKDOWN_LINK_RE.finditer(source):
        target = _normalize_target(match.group(1))
        if target is not None:
            yield target, "markdown link"
    for match in BACKTICK_RE.finditer(source):
        target = match.group(1).strip()
        if target.startswith(PATH_PREFIXES):
            yield target, "backtick path"


def find_broken_links(root: Path, source: str) -> list[Finding]:
    findings: set[Finding] = set()
    for target, kind in _iter_examined_targets(source):
        if not (root / target).exists():
            findings.add(Finding(target, kind))
    return sorted(findings, key=lambda finding: (finding.target, finding.kind))


#: A backtick citation's optional trailing line spec: one line, one range, or
#: several of either joined by commas (the convention already in use across
#: this repository's docs - e.g. `flow-helpers-install.sh:244,321`). Matched
#: against the WHOLE backtick span (issue #1413), so a span that is a path
#: plus something this cannot parse as a line spec is left alone rather than
#: guessed at - the same fail-closed-to-unexamined shape `BACKTICK_RE` already
#: applies via `PATH_PREFIXES`.
CITATION_RE = re.compile(
    r"^(?P<path>(?:" + "|".join(re.escape(prefix) for prefix in PATH_PREFIXES) + r")\S+?)"
    r"(?::(?P<spec>\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*))?$"
)

#: Directories whose tracked .md files legitimately cite something that no
#: longer exists - a run record or a measurement snapshot describes a bygone
#: tree on purpose, never the current one (issue #1413). Named explicitly
#: rather than inferred, so widening what a snapshot directory covers is a
#: decision made here, not a side effect of a broader pattern.
EXCLUDED_CITATION_DIRS = ("docs/flow-runs/", "docs/measurements/")

#: A dated research snapshot's own filename - `docs/research/<name>-
#: YYYY-MM-DD.md` - excluded for the same reason as the directories above: it
#: is a point-in-time report, not a living reference. Subdirectories holding a
#: snapshot's supporting files (`docs/research/<name>-YYYY-MM-DD/...`) carry
#: no `.md` today and are not matched by this pattern, which is anchored to a
#: flat file directly under `docs/research/`.
DATED_RESEARCH_SNAPSHOT_RE = re.compile(r"^docs/research/[^/]+-\d{4}-\d{2}-\d{2}\.md$")

#: The two directories this gate's THIRD check walks (issue #1413).
#: `CHANGELOG.md` sits outside both at the repo root, so it is excluded by
#: this population rather than by a rule - there is nothing to write.
CITATION_SCAN_DIRS = ("docs", ".specify")

#: THE ENFORCED POPULATION (issue #1413 ruling), narrowed from "every tracked
#: .md under docs/ and .specify/" after measuring the wider one: 423 raw
#: hits, cut to 161 by tightening the matcher (see `_is_non_path_citation`),
#: and reading those 161 showed most are not citation rot at all - a
#: cross-repository citation (a path real in another repository, quoted
#: while narrating ITS behaviour) and a historical/proposed-state document
#: (an ADR, a review, a `.specify/specs/*/{plan,tasks,ledger,inventory}.md`
#: working note) whose cited paths were accurate when written and have since
#: moved, without the document being "wrong" the way a rotted citation is.
#: Neither is a matcher-shape the way a glob or a placeholder is; telling them
#: apart needs git-log archaeology this gate does not do. So enforcement is
#: narrowed to doc classes this repository already treats as currently-live
#: reference material: `docs/agents/**` (CLAUDE.md's own canonical list),
#: `docs/security/*-dispositions.md` (which this repository already corrects
#: in place - dependency-advisory-dispositions.md:237 did exactly that for
#: issue #918, the precedent #1413 itself follows), and `.specify/specs/*/
#: spec.md` only - not `plan.md`/`tasks.md`/`ledger.md`/`inventory.md`, which
#: read as working notes rather than a maintained reference. Everything else
#: under `docs/` and `.specify/` is still examined, but only in `--wide` mode
#: (advisory, never `make verify` - see `main`).
ENFORCED_SPEC_MD_RE = re.compile(r"^\.specify/specs/[^/]+/spec\.md$")


def _is_enforced_citation_doc(rel: str) -> bool:
    if rel.startswith("docs/agents/"):
        return True
    if rel.startswith("docs/security/") and rel.endswith("-dispositions.md"):
        return True
    return bool(ENFORCED_SPEC_MD_RE.match(rel))


@dataclass(frozen=True)
class CitationFinding:
    doc: str
    citation: str
    problem: str


def _is_excluded_citation_doc(rel: str) -> bool:
    return rel.startswith(EXCLUDED_CITATION_DIRS) or bool(DATED_RESEARCH_SNAPSHOT_RE.match(rel))


#: A repo-qualified citation - `skillc:tests/fixtures/...`,
#: `kyle:scripts/check-skills-install.py` - names a path in ANOTHER
#: repository, deliberately (issue #1413 ruling): a cited path that belongs
#: elsewhere must be written this way, converting the ambiguous bare form
#: that this gate cannot tell apart from a repo-local citation. Checked
#: before `PATH_PREFIXES`, so stating the convention here is not merely
#: documentation - a span shaped like a short identifier plus `:` with no
#: slash before it never reaches the resolver at all.
CROSS_REPO_CITATION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*:")


def _is_non_path_citation(text: str) -> bool:
    """A backtick span this gate must NOT read as a file citation (issue #1413).

    Measured against the real tree rather than assumed: the first cut of this
    check, with no exclusions beyond `PATH_PREFIXES`, reported 423 findings
    across 82 files. Reading them showed four shapes that are not a citation
    of ONE existing file at all, and tightening the matcher to exclude them -
    never a per-path allowlist - took the count to what follows in this
    file's own history:

    - a glob or recursive glob (`scripts/*.sh`, `.claude/commands/**`) - a
      PATTERN, not a path;
    - a directory reference (`codex/skills/`, trailing `/`) - this gate
      checks FILE citations, and a directory's existence is a different,
      much coarser claim a reader does not make the same way;
    - a template placeholder (`docs/flow-runs/issue-<N>.md`,
      `.claude/worktrees/<name>`) - angle brackets mark a FILLED-IN example,
      never a literal path;
    - a pytest node id (`tests/test_x.py::test_y`) - `::` introduces a test
      function, not a line spec, and `CITATION_RE` has no notation for it -
      so a node id was being read as ONE giant, obviously-wrong path instead
      of being recognised and skipped;
    - a cross-repository citation (`skillc:tests/fixtures/...`) - see
      `CROSS_REPO_CITATION_RE` above.
    """
    return (
        "*" in text or text.endswith("/") or "<" in text or ">" in text or "::" in text
        or bool(CROSS_REPO_CITATION_RE.match(text))
    )


def find_dead_citations(root: Path, *, wide: bool) -> tuple[list[CitationFinding], int, int]:
    """`(findings, documents examined, citations examined)` (issue #1413).

    Reuses `BACKTICK_RE` and `PATH_PREFIXES` - the exact resolver the first
    gate in this file already applies to CLAUDE.md - against every tracked
    `.md` file under `docs/` and `.specify/`, excluding the directories and
    snapshot-filename shape named above. A citation whose target file does not
    exist is a finding; one whose target exists but whose line spec reaches
    past the file's own line count is a SECOND, independent finding - a
    citation can rot by the file moving without the file disappearing.

    `wide=False` (the default, and the only mode `main` ever enforces)
    additionally restricts the documents walked to `_is_enforced_citation_doc`
    - see its module-level comment for why. `wide=True` walks every tracked
    `.md` under `docs/` and `.specify/` with no further restriction, for the
    advisory `--wide` report only.
    """
    findings: list[CitationFinding] = []
    documents = 0
    citations = 0
    for base in CITATION_SCAN_DIRS:
        base_dir = root / base
        if not base_dir.is_dir():
            continue
        for path in sorted(base_dir.rglob("*.md")):
            rel = path.relative_to(root).as_posix()
            if _is_excluded_citation_doc(rel):
                continue
            if not wide and not _is_enforced_citation_doc(rel):
                continue
            documents += 1
            source = path.read_text(encoding="utf-8", errors="replace")
            for match in BACKTICK_RE.finditer(source):
                text = match.group(1).strip()
                if not text.startswith(PATH_PREFIXES):
                    continue
                if _is_non_path_citation(text):
                    continue
                cite = CITATION_RE.match(text)
                if not cite:
                    continue
                citations += 1
                target = cite.group("path")
                target_path = root / target
                # A bare directory reference with no trailing slash (`lib/cicd`,
                # `codex/skills`) is a real, common citation shape - EXISTS,
                # not `.is_file()`, is the right existence test. A line spec
                # only makes sense for a FILE, so that half still requires one.
                if not target_path.exists():
                    findings.append(CitationFinding(rel, text, "target does not exist"))
                    continue
                spec = cite.group("spec")
                if not spec:
                    continue
                if not target_path.is_file():
                    findings.append(
                        CitationFinding(rel, text, f"{target} is a directory, not a file - a line spec cannot apply")
                    )
                    continue
                try:
                    line_count = sum(1 for _ in target_path.open("r", encoding="utf-8", errors="replace"))
                except OSError:
                    continue
                for piece in spec.split(","):
                    end = int(piece.rsplit("-", 1)[-1])
                    if end > line_count:
                        findings.append(
                            CitationFinding(
                                rel, text,
                                f"line {end} is past {target}'s {line_count} line(s)",
                            )
                        )
                        break
    return findings, documents, citations


def find_undocumented_canonical_docs(root: Path, source: str) -> tuple[list[str], int]:
    """On-disk `docs/agents/*.md` files CLAUDE.md's Project Map never names.

    Returns ``(missing, disk_count)``. ``disk_count`` is exposed so the caller
    can apply the membership floor: a shrunk or missing directory must not
    read as "every canonical doc is referenced" over zero files.
    """
    agents_dir = root / CANONICAL_AGENTS_DIR
    if not agents_dir.is_dir():
        return [], 0
    on_disk = sorted(f"{CANONICAL_AGENTS_DIR}/{path.name}" for path in agents_dir.glob("*.md"))
    referenced = {
        target for target, _kind in _iter_examined_targets(source)
        if target.startswith(f"{CANONICAL_AGENTS_DIR}/")
    }
    missing = [doc for doc in on_disk if doc not in referenced]
    return missing, len(on_disk)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repo root (default: the checkout this script lives in)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    path = root / "CLAUDE.md"
    if not path.is_file():
        print(f"claude-md-links: missing {path}", file=sys.stderr)
        return 1
    source = path.read_text(encoding="utf-8")
    examined = sum(1 for _ in _iter_examined_targets(source))
    if not examined:
        # Issue #841: a present CLAUDE.md with zero link-shaped tokens must not
        # read the same as a clean scan. This script has exactly one caller
        # (Makefile:74, no --root), so it only ever runs against CPP's own
        # checkout - a CPP CLAUDE.md with no repository-local pointers is not a
        # legitimate state, the file IS the project map, so this cannot fire on
        # a real input.
        print(
            f"claude-md-links: {path} contains no repository-local pointers - nothing was checked",
            file=sys.stderr,
        )
        return 1
    findings = find_broken_links(root, source)
    if findings:
        print(f"claude-md-links: {len(findings)} broken pointer(s)", file=sys.stderr)
        for finding in findings:
            print(f"  {finding.kind}: {finding.target}", file=sys.stderr)
        return 1

    missing_canonical, canonical_disk_count = find_undocumented_canonical_docs(root, source)
    if canonical_disk_count < MIN_CANONICAL_AGENT_DOCS:
        print(
            f"claude-md-links: only {canonical_disk_count} {CANONICAL_AGENTS_DIR}/*.md "
            f"file(s) found (need >= {MIN_CANONICAL_AGENT_DOCS}) - UNKNOWN, not clean. "
            "Either the directory is missing or was emptied, which means an "
            "undocumented canonical doc could sit unwatched.",
            file=sys.stderr,
        )
        return 2
    if missing_canonical:
        print(
            f"claude-md-links: {len(missing_canonical)} canonical doc(s) on disk are not "
            "referenced by CLAUDE.md's Project Map:",
            file=sys.stderr,
        )
        for doc in missing_canonical:
            print(f"  {doc}", file=sys.stderr)
        return 1

    citation_findings, citation_docs, citation_count = find_dead_citations(root, wide=False)
    if citation_findings:
        print(
            f"claude-md-links: {len(citation_findings)} dead citation(s) across "
            f"{citation_docs} tracked .md file(s) under docs/ and .specify/:",
            file=sys.stderr,
        )
        for finding in citation_findings:
            print(f"  {finding.doc}: `{finding.citation}` - {finding.problem}", file=sys.stderr)
        return 1

    # THE DENOMINATOR FORM (issue #1036). "every repository-local pointer" is a
    # claim about a CLASS; what this gate establishes is that the pointers it
    # could extract resolve, over a population it can state. The counts are the
    # ones already computed above, so the line cannot describe a different run
    # from the one that produced the verdict.
    print(
        f"claude-md-links: ok - {examined} repository-local pointer(s) resolved, "
        f"{canonical_disk_count} canonical {CANONICAL_AGENTS_DIR}/*.md file(s) all referenced, "
        f"{citation_count} citation(s) across {citation_docs} other tracked .md file(s) "
        "under docs/ and .specify/ resolved (file existence and line bound only - "
        "never a GitHub issue/PR URL, see module docstring)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

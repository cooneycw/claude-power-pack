#!/usr/bin/env python3
"""Preserve findability of obligations moved out of CLAUDE.md.

This check is a findability proxy, not proof of semantic equivalence. Each
pre-reduction obligation is represented by a stable slug and a small literal
keyword/reference match. Finding that match in CLAUDE.md, docs, or a referenced
skill is a deliberate and sufficient contract for cold-start navigation; the
behavioral implementation remains owned by its focused tests and scripts.

A genuinely obsolete obligation can be retired in the committed fixture's
``retirements`` object as ``"slug": "named reason"``. Empty or unknown
retirements fail so the escape hatch remains a reviewed decision rather than a
bare exemption.

The canonical knowledge-lifecycle table is also locality-gated: command and
skill files may carry compact rules and pointers, but must not duplicate the
normative table from ``docs/agents/knowledge-lifecycle.md``.

Usage:
    python3 scripts/check-claude-md-behavior.py
    python3 scripts/check-claude-md-behavior.py --root DIR
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

FIXTURE = Path("tests/fixtures/claude-md-obligations.fixture")
FIXTURE_VERSION = 1
NORMATIVE_TABLE_MARKER = "| Knowledge in the completed spec | Durable home |"
LIFECYCLE_REFERENCE = "knowledge-lifecycle.md"
LIFECYCLE_BOUNDARY_FILES = frozenset(
    {
        ".claude/commands/claude-md/lint.md",
        ".claude/commands/flow/finish.md",
        ".claude/commands/project/init.md",
        "codex/skills/claude-md-lint/reference.md",
        "codex/skills/flow-finish/reference.md",
        "codex/skills/project-init/reference.md",
    }
)
COMMAND_RE = re.compile(r"(?<![\w/])/(?:[a-z0-9-]+):(?:[a-z0-9_-]+)")


@dataclass(frozen=True)
class Finding:
    kind: str
    detail: str


def _load_fixture(path: Path) -> tuple[list[tuple[str, str]], dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read obligation fixture {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != FIXTURE_VERSION:
        raise ValueError(f"{path}: version must be {FIXTURE_VERSION}")
    raw_obligations = payload.get("obligations")
    raw_retirements = payload.get("retirements")
    if not isinstance(raw_obligations, list) or not isinstance(raw_retirements, dict):
        raise ValueError(f"{path}: obligations must be a list and retirements must be an object")
    obligations: list[tuple[str, str]] = []
    for index, raw in enumerate(raw_obligations):
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: obligation {index} must be an object")
        slug = raw.get("slug")
        needle = raw.get("needle")
        if not isinstance(slug, str) or not slug.strip() or not isinstance(needle, str) or not needle.strip():
            raise ValueError(f"{path}: obligation {index} requires non-empty slug and needle")
        obligations.append((slug, needle))
    if len({slug for slug, _ in obligations}) != len(obligations):
        raise ValueError(f"{path}: obligation slugs must be unique")
    retirements: dict[str, str] = {}
    known = {slug for slug, _ in obligations}
    for slug, reason in raw_retirements.items():
        if slug not in known:
            raise ValueError(f"{path}: retirement names unknown slug {slug!r}")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{path}: retirement {slug!r} requires a named reason")
        retirements[slug] = reason
    return obligations, retirements


def _referenced_skill_paths(root: Path, claude_source: str) -> set[Path]:
    paths: set[Path] = set()
    for command in COMMAND_RE.findall(claude_source):
        family, name = command[1:].split(":", 1)
        candidate = root / ".claude" / "commands" / family / f"{name}.md"
        if candidate.is_file():
            paths.add(candidate)
    return paths


def _search_corpus(root: Path, claude_source: str) -> str:
    paths = sorted((root / "docs").rglob("*.md")) if (root / "docs").is_dir() else []
    paths.extend(sorted(_referenced_skill_paths(root, claude_source)))
    chunks = [claude_source]
    chunks.extend(path.read_text(encoding="utf-8") for path in paths)
    return re.sub(r"\s+", " ", "\n".join(chunks)).casefold()


def check_tree(root: Path) -> list[Finding]:
    claude_path = root / "CLAUDE.md"
    if not claude_path.is_file():
        return [Finding("missing-file", "CLAUDE.md")]
    try:
        obligations, retirements = _load_fixture(root / FIXTURE)
    except ValueError as exc:
        return [Finding("invalid-fixture", str(exc))]
    claude_source = claude_path.read_text(encoding="utf-8")
    corpus = _search_corpus(root, claude_source)
    findings = [
        Finding("missing-obligation", f"{slug}: expected findable text {needle!r}")
        for slug, needle in obligations
        if slug not in retirements and re.sub(r"\s+", " ", needle).casefold() not in corpus
    ]

    policy_roots = (root / ".claude" / "commands", root / ".claude" / "skills", root / "codex" / "skills")
    for policy_root in policy_roots:
        if not policy_root.is_dir():
            continue
        for path in sorted(policy_root.rglob("*.md")):
            source = path.read_text(encoding="utf-8").casefold()
            relative = str(path.relative_to(root))
            if NORMATIVE_TABLE_MARKER.casefold() in source:
                findings.append(
                    Finding("duplicated-lifecycle-policy", relative)
                )
            if LIFECYCLE_REFERENCE in source and relative not in LIFECYCLE_BOUNDARY_FILES:
                findings.append(Finding("non-boundary-lifecycle-pointer", relative))
    return findings


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
    findings = check_tree(root)
    if not findings:
        print("claude-md-behavior: ok - obligations remain findable and lifecycle policy is local")
        return 0
    print(f"claude-md-behavior: {len(findings)} finding(s)", file=sys.stderr)
    for finding in findings:
        print(f"  {finding.kind}: {finding.detail}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

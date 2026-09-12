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

One narrow exception, verified per file rather than granted by path (#861): a
byte-identical copy of a canonical document, written into a managed generated
skill by ``scripts/codex-skill-sync.py``, is DISTRIBUTION of that source rather
than a second policy. It is recognised only when the enclosing skill is a real
bundler output (decided by the bundler's own ``is_managed``), the canonical
source exists, and the bytes match. An altered copy, a copy in a hand-curated
skill, a copy whose source is gone, and policy pasted into a command body are
all still reported, and an unverifiable copy fails closed.

Usage:
    python3 scripts/check-claude-md-behavior.py
    python3 scripts/check-claude-md-behavior.py --root DIR
"""

from __future__ import annotations

import argparse
import importlib.util
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
# --- Generated documentation distribution (issue #861) -----------------------------
#
# `scripts/codex-skill-sync.py` bundles a canonical document into a generated skill so
# the link a command body publishes still resolves once that skill is installed
# somewhere with no claude-power-pack checkout above it. That copy is DISTRIBUTION of
# the canonical source, not a second policy: docs/ remains the one writable authority.
#
# The allowance is therefore VERIFIED, never granted by appearance. A file under
# codex/skills/<skill>/docs/ is treated as distribution only when all three hold:
#
#   1. the enclosing skill CARRIES THE GENERATED MARKER, decided by the bundler's own
#      `is_managed` rather than by this file restating it. That is a marker check, not
#      proof of generation history: it says the directory is declared generated, and a
#      marker can be written by hand;
#   2. the canonical source exists at the matching docs/ path;
#   3. the bytes are identical to it.
#
# The boundary is the COMPOSITION of those, not any one of them. Byte identity is what
# carries the weight - an edited copy is reported however it is marked - and whether
# the generated output is actually present and current is owned by the separate
# packaging checks (`make codex-skills` drift and the bundled-docs byte-identity test),
# not by this file.
#
# Anything else - an altered copy, a copy in a hand-curated skill, a copy whose
# canonical source is gone - is still authored policy in the wrong place and is still
# reported. Nothing here exempts a path for looking generated, and policy pasted into a
# command body is untouched by this: it does not live under <skill>/docs/.
SKILLS_ROOT = ("codex", "skills")
GENERATED_DOCS_DIR = "docs"
BUNDLER = "scripts/codex-skill-sync.py"


def _bundler_is_managed(root: Path):
    """The bundler's own managed-skill predicate, imported rather than restated.

    A second copy of that rule here could drift from the one that actually writes the
    files. If it cannot be imported, every candidate fails closed: an unverifiable
    copy is reported, never waved through.
    """
    script = root / BUNDLER
    if not script.is_file():
        return None
    spec = importlib.util.spec_from_file_location("_cpp_codex_skill_sync", script)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return getattr(module, "is_managed", None)


def _canonical_source(path: Path, root: Path) -> Path | None:
    """The docs/ document a bundled copy claims to distribute, or None."""
    try:
        relative = path.relative_to(root.joinpath(*SKILLS_ROOT))
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) < 3 or parts[1] != GENERATED_DOCS_DIR:
        return None
    return root.joinpath("docs", *parts[2:])


def is_verified_generated_doc(path: Path, root: Path, is_managed) -> bool:
    """True only for a byte-identical copy of a real canonical doc in a managed skill."""
    if is_managed is None:
        return False
    source = _canonical_source(path, root)
    if source is None or not source.is_file():
        return False
    skill_dir = root.joinpath(*SKILLS_ROOT, path.relative_to(root.joinpath(*SKILLS_ROOT)).parts[0])
    if not is_managed(skill_dir):
        return False
    try:
        return path.read_bytes() == source.read_bytes()
    except OSError:
        return False


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
    is_managed = _bundler_is_managed(root)
    for policy_root in policy_roots:
        if not policy_root.is_dir():
            continue
        for path in sorted(policy_root.rglob("*.md")):
            # Verified distribution of a canonical document, not a second policy.
            if is_verified_generated_doc(path, root, is_managed):
                continue
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

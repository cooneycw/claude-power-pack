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


def _load_bundler(root: Path):
    """Import `scripts/codex-skill-sync.py` itself, or None if it cannot be.

    Both `is_managed` (the managed-skill predicate) and `PROVENANCE_NAME`
    (the generated filename, issue #1408) are read from this ONE import -
    a second copy of either here could drift from the one that actually
    writes the files. If the module cannot be imported, every caller fails
    closed: an unverifiable candidate is reported, never waved through.
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
    return module


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
    """True for a real canonical doc in a managed skill, copy or rewrite (#1494).

    Byte-identical was the whole test until #1494: `codex-skill-sync.py` now
    rewrites a bundled doc's relative links that point outside the mirror to
    absolute GitHub URLs, so a correctly-generated copy legitimately differs
    from its source. The expected text is computed with the bundler's OWN
    `rewrite_mirror_links`, never a second definition of the transform here -
    a copy of that logic could drift from what the generator actually does
    and this check would then verify against the wrong answer.
    """
    if is_managed is None:
        return False
    source = _canonical_source(path, root)
    if source is None or not source.is_file():
        return False
    skill_dir = root.joinpath(*SKILLS_ROOT, path.relative_to(root.joinpath(*SKILLS_ROOT)).parts[0])
    if not is_managed(skill_dir):
        return False
    bundler = _load_bundler(root)
    if bundler is None or not hasattr(bundler, "rewrite_mirror_links"):
        return False
    try:
        source_text = source.read_text(encoding="utf-8")
        actual_text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    mirrored = {
        p.relative_to(skill_dir).as_posix()
        for p in skill_dir.rglob("*") if p.is_file()
    }
    output_rel = path.relative_to(skill_dir).as_posix()
    try:
        expected_text = bundler.rewrite_mirror_links(source_text, source, output_rel, mirrored)
    except Exception:
        # Fail CLOSED: `rewrite_mirror_links` needs its own sibling
        # check-md-relative-links.py beside whichever codex-skill-sync.py was
        # loaded (real repo or a test fixture's copy). Missing it is a setup
        # defect, never evidence that this copy is a verified distribution.
        return False
    return actual_text == expected_text


def is_verified_provenance_note(path: Path, root: Path, is_managed, provenance_name: str | None) -> bool:
    """True for a managed skill's own mirror-provenance note (issue #1408).

    `PROVENANCE.md`'s entire content is generator-ASSEMBLED filename
    bullets - never free prose a human writes - so it cannot restate
    lifecycle policy in the way this check exists to catch, even when one
    of the bundled paths it names happens to BE
    `docs/agents/knowledge-lifecycle.md` (a real, separately-verified
    distribution under the same skill, via `is_verified_generated_doc`
    above). `codex-skills-check` (the DRIFT/MISSING/STALE gate) already
    verifies this file's bytes against what the generator produces; this is
    recognition of that existing guarantee, not a second one - which is why
    it checks only the FILENAME (read from the bundler, never hardcoded a
    second time) and that the enclosing skill is managed, not the bytes.
    """
    if is_managed is None or not provenance_name or path.name != provenance_name:
        return False
    try:
        skill_dir = root.joinpath(*SKILLS_ROOT, path.relative_to(root.joinpath(*SKILLS_ROOT)).parts[0])
    except ValueError:
        return False
    return is_managed(skill_dir)


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
    bundler = _load_bundler(root)
    is_managed = getattr(bundler, "is_managed", None) if bundler is not None else None
    provenance_name = getattr(bundler, "PROVENANCE_NAME", None) if bundler is not None else None
    for policy_root in policy_roots:
        if not policy_root.is_dir():
            continue
        for path in sorted(policy_root.rglob("*.md")):
            # Verified distribution of a canonical document, not a second policy.
            if is_verified_generated_doc(path, root, is_managed):
                continue
            # The generated provenance note itself (issue #1408) - a filename
            # listing, never free prose that could restate policy.
            if is_verified_provenance_note(path, root, is_managed, provenance_name):
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

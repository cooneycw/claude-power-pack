#!/usr/bin/env python3
"""Map changed CPP skills and dependencies to current evaluation coverage (#1370).

Two independent staleness axes decide whether a skill's evaluation coverage
still applies to the CURRENT checkout, and they must not be collapsed into
one check - a skill can fail either without the other:

  AXIS 1 (content):   has the skill's own evaluated bytes (description,
                       body) changed since the evaluation-bound reference?
  AXIS 2 (dependency): has skillc's `profile diagnose` reported this
                       skill's dependency closure broken, independent of
                       whether its own content changed (R10,
                       .specify/specs/per-skill-audit/spec.md)?

NO SKILLC RUNTIME IMPORT, same discipline as #1369's check-behavioral-eval.py
(the owner's ruling there applies here too). Axis 1 is pure Python - SHA-256
over text this script reads directly from the repo, no skillc dependency at
all. Axis 2 needs `skillc profile diagnose`, which CANNOT run in CI (no
skillc checkout, no network fetch of one) - so its result is VENDORED: a
committed snapshot under docs/measurements/skill-coverage/<skill>.json,
written by the separate, never-CI, operator-run
scripts/skill-coverage-snapshot.py.

THE VENDORED SNAPSHOT GOES STALE THE MOMENT THE SKILL'S CLOSURE CHANGES, and
this script's whole job on axis 2 is to know that, not paper over it: the
snapshot records a digest for every file in the skill's `codex/skills/<skill>/`
directory AT SNAPSHOT TIME, and this script recomputes the same digests
against the CURRENT tree. Any mismatch -> axis 2 is `unknown`, never a
silently-reused stale verdict. So CI can always answer axis 1 fresh; it can
answer axis 2 only as "fresh as of the last manual regeneration, and we can
tell you whether that is still valid" - never as a live result. That is a
named limitation of going CI-safe, not an oversight.

Evaluation-bound reference point (Q1, answered against CPP main @ 8ff62ca and
skillc main @ bbd4ed6/2202603): neither #1369's bundle reader
(check-behavioral-eval.py::_evaluate_skill_evidence, whose own docstring says
"Freshness against the CURRENT checkout (R10) is NOT checked here - that is
#1370's job") nor skillc #272's coverage-report assembler expose a
{revision, skill, digest} tuple for content-freshness. So the reference stays
skillc #265's own profile pin (`85e9b03`), read from its committed
`evidence/inventory.json` values and vendored into the same snapshot file -
and the output says so explicitly, rather than implying a newer reference
exists.

Output states (five, not fewer - "not evaluated" (unmapped) and "unknown"
(mapped, undecidable) are different claims with different remedies, #1367
item 4):

    not evaluated       - skill absent from SKILL_FAMILY_MAP; axis work is
                           never even attempted for it
    current             - mapped, axis1 current, axis2 current
    stale (content)     - mapped, axis1 stale (axis2 is irrelevant once
                           content itself is stale)
    stale (dependency)  - mapped, axis1 current, axis2 stale
    unknown             - mapped, but either axis is undecidable (snapshot
                           missing/stale, reference missing, skill directory
                           absent)

v1 declares NO equivalence registry (owner ruling via the cpp-eval
orchestrator, 2026-10-06): the declared rule R10 requires is exact digest
match only. A cosmetic (whitespace/comment-only) change is `stale (content)`
exactly like any other difference - a future registry is deferred until a
real cosmetic-reuse need appears, with its own governance ruling then.

v1's map is the degenerate 1:1 case (flow-check only), with a data structure
built to extend rather than over-built for many-to-many before a second real
skill profile exists (#1367 item 4; skillc only has one CPP profile today,
`evals/subjects/cpp-codex-flow-check/`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

USAGE_EXIT = 64

#: v1: the degenerate 1:1 map (#1367 item 4). A skill absent from this dict
#: is `not evaluated` for every family, full stop - it must never borrow a
#: mapped sibling's verdict. Extend by adding entries, never by inferring
#: membership from `codex/skills/`'s directory listing.
SKILL_FAMILY_MAP: dict[str, str] = {
    "flow-check": "flow:check",
}

#: Where the vendored, operator-written snapshots live (never written by
#: this script, never written by CI - scripts/skill-coverage-snapshot.py
#: owns that, and refuses to run in CI or on a dirty tree).
SNAPSHOT_DIR = Path("docs/measurements/skill-coverage")

STATES = (
    "not evaluated",
    "current",
    "stale (content)",
    "stale (dependency)",
    "unknown",
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"skill-coverage-map: usage - {message}", file=sys.stderr)
        raise SystemExit(USAGE_EXIT)


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class SkillMdError(ValueError):
    pass


def parse_skill_md(path: Path) -> tuple[str, str]:
    """-> (description, body) from a SKILL.md's YAML-ish frontmatter + body.

    Deliberately NOT a YAML parser (stdlib only, like every CPP checker in
    this family) - the frontmatter shape here is a single flat
    `key: value` block, and `description:` is always a quoted or bare
    scalar on one line, never a block scalar. A multi-line description
    would need a real parser; none of the 12 skills this script maps today
    use one, and a future one that does would raise here rather than
    silently reading a truncated digest.
    """
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.DOTALL)
    if not match:
        raise SkillMdError(f"{path}: no frontmatter block (expected '---' ... '---')")
    frontmatter, body = match.group(1), match.group(2)
    desc_match = re.search(r'^description:\s*(.*)$', frontmatter, re.MULTILINE)
    if desc_match is None:
        raise SkillMdError(f"{path}: frontmatter has no 'description:' key")
    description = desc_match.group(1).strip()
    if description and description[0] in "\"'" and description[-1] == description[0]:
        description = description[1:-1]
    return description, body


def digest_tree(root: Path) -> dict[str, str]:
    """relative posix path -> sha256:<hex> for every FILE under root.

    Whole-directory, not just SKILL.md: the closure a skill's description
    and body point into (reference.md, bundled scripts) all move the
    dependency-closure verdict, and axis 2's staleness check needs to see
    every one of them move, not just the entry point.
    """
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = sha256_bytes(path.read_bytes())
    return out


def _diff_digests(old: dict[str, str], new: dict[str, str]) -> list[str]:
    """Human-readable differences: added, removed, changed paths - sorted,
    so the output is deterministic and a reader can see exactly which file
    moved rather than being told only that "something" did."""
    changes = []
    for path in sorted(set(old) | set(new)):
        if path not in old:
            changes.append(f"{path} (added)")
        elif path not in new:
            changes.append(f"{path} (removed)")
        elif old[path] != new[path]:
            changes.append(f"{path} (content changed)")
    return changes


def load_snapshot(skill: str, snapshot_dir: Path) -> dict[str, Any] | None:
    path = snapshot_dir / f"{skill}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def check_skill(skill: str, repo: Path, snapshot_dir: Path) -> dict[str, Any]:
    """The full verdict for one skill, independent of whether it is mapped -
    the caller applies the map short-circuit (see `audit`)."""
    closure_root = repo / "codex" / "skills" / skill
    result: dict[str, Any] = {"skill": skill}

    snapshot = load_snapshot(skill, snapshot_dir)
    if snapshot is None:
        result["state"] = "unknown"
        result["reason"] = f"no vendored snapshot at {snapshot_dir / f'{skill}.json'}"
        return result

    reference = snapshot.get("reference", {})
    result["reference_source"] = reference.get("source", "unknown")

    # --- Axis 1: content -------------------------------------------------
    if not closure_root.is_dir():
        result["state"] = "unknown"
        result["reason"] = f"{closure_root} is absent from the current checkout"
        return result
    skill_md = closure_root / "SKILL.md"
    try:
        description, body = parse_skill_md(skill_md)
    except (OSError, SkillMdError) as exc:
        result["state"] = "unknown"
        result["reason"] = f"could not read {skill_md}: {exc}"
        return result

    current_description_digest = sha256_text(description)
    current_body_digest = sha256_text(body)
    ref_description_digest = reference.get("description_digest")
    ref_body_digest = reference.get("body_digest")

    axis1_mismatches = []
    if ref_description_digest is None or ref_body_digest is None:
        result["state"] = "unknown"
        result["reason"] = "snapshot's reference section is missing description_digest/body_digest"
        return result
    if current_description_digest != ref_description_digest:
        axis1_mismatches.append(
            f"description_digest differs (reference {ref_description_digest}, current {current_description_digest})"
        )
    if current_body_digest != ref_body_digest:
        axis1_mismatches.append(
            f"body_digest differs (reference {ref_body_digest}, current {current_body_digest})"
        )
    result["axis1"] = {
        "status": "stale" if axis1_mismatches else "current",
        "detail": "; ".join(axis1_mismatches) if axis1_mismatches else "digests match the evaluation-bound reference",
    }
    if axis1_mismatches:
        result["state"] = "stale (content)"
        return result

    # --- Axis 2: dependency closure, via the vendored snapshot -----------
    diagnose = snapshot.get("diagnose")
    if not isinstance(diagnose, dict):
        result["state"] = "unknown"
        result["reason"] = "snapshot has no diagnose section"
        return result
    snapshot_digests = diagnose.get("closure_digests")
    if not isinstance(snapshot_digests, dict):
        result["state"] = "unknown"
        result["reason"] = "snapshot's diagnose section has no closure_digests"
        return result
    current_digests = digest_tree(closure_root)
    drift = _diff_digests(snapshot_digests, current_digests)
    result["snapshot_provenance"] = {
        "skillc_commit": diagnose.get("skillc_commit"),
        "cpp_revision_snapshot": diagnose.get("cpp_revision_snapshot"),
        "recorded_at": diagnose.get("recorded_at"),
    }
    if drift:
        result["state"] = "unknown"
        result["reason"] = (
            "vendored diagnose() snapshot is stale - the closure changed since it was "
            f"recorded: {', '.join(drift)}. Re-run scripts/skill-coverage-snapshot.py "
            "and commit a fresh snapshot."
        )
        return result

    skill_result = diagnose.get("result", {})
    status = skill_result.get("skills", {}).get(skill, {}).get("status")
    problems = [
        p for p in skill_result.get("problems", [])
        if skill in p.get("skills", [])
    ]
    result["axis2"] = {"status": status, "problems": problems}
    if status == "broken":
        result["state"] = "stale (dependency)"
        result["reason"] = (
            f"skillc profile diagnose reports {skill} broken: "
            + "; ".join(f"[{p['category']}] {p['detail']}" for p in problems)
        )
        return result
    if status != "intact":
        result["state"] = "unknown"
        result["reason"] = f"vendored diagnose() reports an unrecognized status: {status!r}"
        return result

    result["state"] = "current"
    return result


def audit(repo: Path, snapshot_dir: Path) -> dict[str, dict[str, Any]]:
    """Every mapped skill's verdict. An unmapped skill never reaches
    `check_skill` at all - the map membership check is the first and only
    thing decided for it, so no digest work is wasted and no partial result
    could ever be misread as a decision about it."""
    out: dict[str, dict[str, Any]] = {}
    for skill, family in SKILL_FAMILY_MAP.items():
        verdict = check_skill(skill, repo, snapshot_dir)
        verdict["family"] = family
        out[skill] = verdict
    return out


def _say(results: dict[str, dict[str, Any]]) -> int:
    any_problem = False
    for skill, verdict in results.items():
        state = verdict["state"]
        reason = verdict.get("reason", "")
        line = f"skill-coverage-map: {skill} ({verdict['family']}): {state}"
        if reason:
            line += f" - {reason}"
        print(line)
        if state not in ("current",):
            any_problem = True
    print(f"skill-coverage-map: {len(results)} mapped skill(s) checked; "
          f"'not evaluated' is a map-membership fact, never inherited from a mapped sibling")
    return 1 if any_problem else 0


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--repo", default=".", type=Path,
                        help="CPP checkout to audit (default: cwd)")
    parser.add_argument("--snapshot-dir", default=str(SNAPSHOT_DIR), type=Path,
                        help=f"vendored snapshot directory (default: {SNAPSHOT_DIR})")
    parser.add_argument("--advisory", action="store_true",
                        help="exit 0 on every verdict this gate PRINTED; a crash "
                             "or usage error still exits non-zero")
    parser.add_argument("--json", action="store_true", help="emit the full result as JSON")
    args = parser.parse_args(argv)
    results = audit(args.repo, args.snapshot_dir)
    if args.json:
        print(json.dumps(results, indent=2))
    code = _say(results)
    return 0 if args.advisory else code


if __name__ == "__main__":
    sys.exit(main())

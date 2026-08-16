#!/usr/bin/env python3
"""CPP entry point for the always-present vendored project-next engine.

The vendored package owns classification, ranking, candidates, and top-action
selection. This adapter keeps that ``RecommendationResult`` byte-for-byte at
the model boundary while adding CPP-only evidence the upstream v1.3 model does
not represent yet:

- native GitHub issue relationships and explicitly uncertain text fallbacks;
- Wayfinder planning routes that never send decision work to ``flow:auto``;
- one shared spec-lifecycle decision consumed by all three render modes.

Lifecycle is intentionally outside ``vendor/project_next``. A graduation
ledger can describe an absent spec, so frontmatter alone cannot represent the
policy, and editing the vendored engine would break its upstream hash pin.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = REPO_ROOT / "vendor" / "project_next"
MANIFEST_PATH = REPO_ROOT / ".claude" / "project-next-vendor.json"
sys.path.insert(0, str(VENDOR_ROOT))

from lib.project_next.classify import _dependencies, _task_issue_index  # noqa: E402
from lib.project_next.collect import CollectionError, collect_repository  # noqa: E402
from lib.project_next.config import ConfigError, load_config  # noqa: E402
from lib.project_next.models import Issue, RecommendationResult, RepositoryState  # noqa: E402
from lib.project_next.rank import recommend  # noqa: E402
from lib.project_next.render import render_result  # noqa: E402

LIFECYCLE_STATES = frozenset({"active", "graduated", "stale", "retained"})
# .specify/graduation-ledger.json is a human-written, git-tracked interface -
# this reader only CONSUMES it. #724 (T006's graduation gate) is expected to
# become its writer; GRADUATION_LEDGER_VERSION is the compatibility contract
# between the two, so a future writer can detect and migrate an older shape.
GRADUATION_LEDGER = Path(".specify/graduation-ledger.json")
GRADUATION_LEDGER_VERSION = 1
DECISION_ID = re.compile(r"\bD\d{3}\b")


@dataclass(frozen=True)
class Relationship:
    issue_number: int
    related_issue: int
    kind: str
    source: str
    confidence: str


@dataclass(frozen=True)
class LifecycleDecision:
    spec_slug: str
    state: str
    path: str
    present: bool
    evidence_url: str = ""
    recorded_at: str = ""
    owner: str = ""
    reason: str = ""


@dataclass(frozen=True)
class PlanningRoute:
    issue_number: int | None
    artifact: str
    action: str
    reason: str


@dataclass(frozen=True)
class CppExtensions:
    relationships: tuple[Relationship, ...]
    spec_lifecycle: tuple[LifecycleDecision, ...]
    planning_routes: tuple[PlanningRoute, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _manifest_version() -> str:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    version = data.get("contract_version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{MANIFEST_PATH}: contract_version must be a non-empty string")
    return version


def _numbers(value: object) -> tuple[int, ...]:
    if value is None:
        return ()
    items = value.get("nodes", ()) if isinstance(value, dict) else value
    if not isinstance(items, (list, tuple)):
        return ()
    numbers = []
    for item in items:
        raw = item.get("number") if isinstance(item, dict) else item
        try:
            numbers.append(int(raw))
        except (TypeError, ValueError):
            continue
    return tuple(sorted(set(numbers)))


def _native_rows_live(repository: Path, limit: int) -> tuple[list[dict[str, object]] | None, str | None]:
    fields = "number,blockedBy,blocking,parent,subIssues,assignees"
    completed = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            fields,
        ],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "command failed").strip().splitlines()[0]
        return None, f"native GitHub relationship fields unavailable: {detail}"
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return None, f"native GitHub relationship fields returned invalid JSON: {exc}"
    if not isinstance(payload, list):
        return None, "native GitHub relationship fields returned a non-list payload"
    return payload, None


def _native_rows_fixture(payload: dict[str, object]) -> tuple[list[dict[str, object]] | None, str | None]:
    if payload.get("native_fields_available") is False:
        return None, "native GitHub relationship fields unavailable in fixture"
    raw_issues = payload.get("issues")
    if not isinstance(raw_issues, list):
        return [], None
    fields = {"blockedBy", "blocking", "parent", "subIssues"}
    if not any(isinstance(item, dict) and fields.intersection(item) for item in raw_issues):
        # Old contract fixtures predate the extension. Treat their dependency
        # prose as the authoritative fixture input instead of silently changing
        # the upstream golden corpus during dogfood.
        return [], None
    return [item for item in raw_issues if isinstance(item, dict)], None


def normalize_relationships(
    state: RepositoryState,
    native_rows: list[dict[str, object]] | None,
) -> tuple[RepositoryState, tuple[Relationship, ...]]:
    """Normalize native dependencies and uncertain text evidence for the engine.

    Native ``blockedBy``/``blocking`` edges become the only asserted blockers.
    A dependency found only in text remains named in the CPP relationship model,
    but the normalized state supplies a dangling declaration so the vendored
    classifier places the issue in ``uncertain`` rather than ``blocked``.
    Parent and sub-issue relationships are collected as hierarchy evidence and
    do not invent dependency semantics.
    """
    if native_rows == []:
        return state, ()

    rows: dict[int, dict[str, object]] = {}
    for row in native_rows or ():
        raw_number = row.get("number")
        if not isinstance(raw_number, (int, str)):
            continue
        try:
            rows[int(raw_number)] = row
        except ValueError:
            continue
    native_blocked: dict[int, set[int]] = {issue.number: set() for issue in state.issues}
    relationships: set[Relationship] = set()
    for number, row in rows.items():
        for blocker in _numbers(row.get("blockedBy")):
            native_blocked.setdefault(number, set()).add(blocker)
            relationships.add(Relationship(number, blocker, "blocked_by", "github-native", "confirmed"))
        for blocked in _numbers(row.get("blocking")):
            native_blocked.setdefault(blocked, set()).add(number)
            relationships.add(Relationship(number, blocked, "blocking", "github-native", "confirmed"))
        parent = row.get("parent")
        if isinstance(parent, dict) and parent.get("number") is not None:
            relationships.add(
                Relationship(number, int(parent["number"]), "parent", "github-native", "confirmed")
            )
        for child in _numbers(row.get("subIssues")):
            relationships.add(Relationship(number, child, "sub_issue", "github-native", "confirmed"))

    task_issues = _task_issue_index(state)
    normalized: list[Issue] = []
    for issue in state.issues:
        parsed, unresolved, _ = _dependencies(issue, task_issues)
        confirmed = native_blocked.get(issue.number, set())
        fallback = parsed - confirmed
        body = issue.body
        additions = [f"Blocked by #{number}" for number in sorted(confirmed)]
        if fallback or unresolved:
            additions.append("Blocked by: dependency text could not be verified through native GitHub fields")
        for dependency in sorted(fallback):
            relationships.add(
                Relationship(issue.number, dependency, "blocked_by", "documented-text", "uncertain")
            )
        normalized.append(
            replace(
                issue,
                body="\n".join(part for part in (body, *additions) if part),
            )
        )
    return replace(state, issues=tuple(normalized)), tuple(
        sorted(relationships, key=lambda edge: (edge.issue_number, edge.kind, edge.related_issue))
    )


def _frontmatter_lifecycle(path: Path) -> str:
    if not path.is_file():
        return "active"
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return "active"
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "lifecycle":
            lifecycle = value.strip().strip("\"'").casefold()
            return lifecycle if lifecycle in LIFECYCLE_STATES else "active"
    return "active"


def _load_graduation_ledger(repository: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    path = repository / GRADUATION_LEDGER
    if not path.is_file():
        return {}, []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"cannot read {GRADUATION_LEDGER}: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"{GRADUATION_LEDGER}: top level must be an object"]
    version = payload.get("version")
    if version != GRADUATION_LEDGER_VERSION:
        return {}, [
            f"{GRADUATION_LEDGER}: 'version' must be {GRADUATION_LEDGER_VERSION}, got {version!r}"
        ]
    entries = payload.get("specs")
    if not isinstance(entries, list):
        return {}, [f"{GRADUATION_LEDGER}: 'specs' must be a list"]
    ledger: dict[str, dict[str, str]] = {}
    warnings: list[str] = []
    for index, raw in enumerate(entries):
        if not isinstance(raw, dict):
            warnings.append(f"{GRADUATION_LEDGER}: entry {index} must be an object")
            continue
        slug = raw.get("spec_slug")
        state = raw.get("state")
        evidence = raw.get("evidence_url")
        recorded = raw.get("recorded_at")
        owner = raw.get("owner", "")
        if (
            not isinstance(slug, str)
            or not slug.strip()
            or not isinstance(state, str)
            or not state.strip()
            or not isinstance(evidence, str)
            or not evidence.strip()
            or not isinstance(recorded, str)
            or not recorded.strip()
        ):
            warnings.append(
                f"{GRADUATION_LEDGER}: entry {index} requires spec_slug, state, evidence_url, and recorded_at"
            )
            continue
        if state not in {"graduated", "retained"}:
            warnings.append(f"{GRADUATION_LEDGER}: {slug}: state must be graduated or retained")
            continue
        if state == "retained" and (not isinstance(owner, str) or not owner.strip()):
            warnings.append(f"{GRADUATION_LEDGER}: {slug}: retained specs require an owner")
            continue
        ledger[slug] = {
            "state": state,
            "evidence_url": evidence,
            "recorded_at": recorded,
            "owner": owner if isinstance(owner, str) else "",
        }
    return ledger, warnings


def normalize_graduated_specs(repository: Path, state: RepositoryState) -> RepositoryState:
    """Remove intentionally absent graduated artifacts from engine readiness input.

    This is input normalization, not a correction to ``RecommendationResult``.
    A human-approved ledger entry says the spec no longer belongs in the active
    Spec Kit inventory, so presenting ``create spec.md`` or pending sync for it
    would contradict the lifecycle evidence.
    """
    ledger, _ = _load_graduation_ledger(repository)
    graduated = {slug for slug, entry in ledger.items() if entry["state"] == "graduated"}
    if not graduated:
        return state
    return replace(
        state,
        spec_tasks=tuple(task for task in state.spec_tasks if task.feature not in graduated),
        spec_features=tuple(feature for feature in state.spec_features if feature.name not in graduated),
    )


def classify_spec_lifecycle(
    repository: Path,
    state: RepositoryState,
    result: RecommendationResult,
) -> tuple[tuple[LifecycleDecision, ...], tuple[str, ...]]:
    """Classify lifecycle once from files, human ledger, and engine evidence."""
    ledger, warnings = _load_graduation_ledger(repository)
    features = {feature.name: feature for feature in state.spec_features}
    slugs = sorted(set(features) | set(ledger))
    open_issues = set(result.classification.in_flight)
    open_issues.update(result.classification.blocked)
    open_issues.update(result.classification.uncertain)
    open_issues.update(result.classification.available)
    tasks_by_feature: dict[str, list[object]] = {}
    for task in state.spec_tasks:
        tasks_by_feature.setdefault(task.feature, []).append(task)

    decisions: list[LifecycleDecision] = []
    for slug in slugs:
        feature = features.get(slug)
        relative = feature.path if feature is not None else f".specify/specs/{slug}"
        spec_path = repository / relative / "spec.md"
        present = spec_path.is_file()
        entry = ledger.get(slug)
        if entry is not None:
            lifecycle = entry["state"]
            reason = "human-approved graduation ledger"
        else:
            lifecycle = _frontmatter_lifecycle(spec_path)
            reason = "spec frontmatter" if present and lifecycle != "active" else "active by default"

        conflicts = []
        if lifecycle == "active" and state.inventory_complete:
            for task in tasks_by_feature.get(slug, []):
                mapped = set(task.issue_numbers)
                declared = task.mapping_state.upper()
                if declared == "CLOSED" and mapped & open_issues:
                    conflicts.append(f"{task.task_id} is marked CLOSED but its issue is open")
                elif declared == "OPEN" and mapped and not (mapped & open_issues):
                    conflicts.append(f"{task.task_id} is marked OPEN but its issue is absent from the open inventory")
        if conflicts:
            lifecycle = "stale"
            reason = "; ".join(conflicts)

        if lifecycle == "active" and not present:
            warnings.append(f"active spec {slug!r} is missing {relative}/spec.md")
        decisions.append(
            LifecycleDecision(
                spec_slug=slug,
                state=lifecycle,
                path=f"{relative}/spec.md",
                present=present,
                evidence_url=entry["evidence_url"] if entry else "",
                recorded_at=entry["recorded_at"] if entry else "",
                owner=entry["owner"] if entry else "",
                reason=reason,
            )
        )
    return tuple(decisions), tuple(warnings)


def planning_routes(repository: Path, state: RepositoryState) -> tuple[PlanningRoute, ...]:
    """Recognize the landed Wayfinder map shape and its linked decision tickets."""
    path = repository / ".claude" / "wayfinder-map.json"
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, dict) or payload.get("state") != "awaiting-decisions":
        return ()
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        return ()
    ids = {
        raw.get("decision_id")
        for raw in decisions
        if isinstance(raw, dict)
        and isinstance(raw.get("decision_id"), str)
        and raw.get("status") != "resolved"
    }
    ids.discard(None)
    routes = [
        PlanningRoute(
            issue_number=None,
            artifact=".claude/wayfinder-map.json",
            action="/project:init",
            reason="resume the awaiting-decisions Wayfinder map",
        )
    ]
    for issue in state.issues:
        issue_ids = set(DECISION_ID.findall(f"{issue.title}\n{issue.body}"))
        if issue_ids & ids:
            routes.append(
                PlanningRoute(
                    issue_number=issue.number,
                    artifact=sorted(issue_ids & ids)[0],
                    action="/project:init",
                    reason="resolve the linked Wayfinder decision before implementation planning",
                )
            )
    return tuple(routes)


def _apply_route_rendering(text: str, routes: tuple[PlanningRoute, ...]) -> str:
    for route in routes:
        if route.issue_number is None:
            continue
        number = route.issue_number
        text = text.replace(f"`$flow-auto {number}`", f"`{route.action}` (Wayfinder planning only)")
        text = text.replace(f"$flow-auto {number}", f"{route.action} (Wayfinder planning only)")
    return text


def render_cpp(
    result: RecommendationResult,
    state: RepositoryState,
    mode: str,
    extensions: CppExtensions,
) -> str:
    base = _apply_route_rendering(render_result(result, state, mode), extensions.planning_routes)
    lines = [f"_decision policy: contract v{result.contract_version} (vendored engine)_", "", base]
    counts = {name: 0 for name in sorted(LIFECYCLE_STATES)}
    for decision in extensions.spec_lifecycle:
        counts[decision.state] += 1
    if mode == "brief":
        summary = " | ".join(f"{name} {counts[name]}" for name in sorted(counts))
        lines.extend(("", f"Spec lifecycle: {summary}"))
    elif mode == "full":
        lines.extend(
            (
                "",
                "### CPP spec lifecycle",
                "| Spec | State | Present | Owner | Evidence | Reason |",
                "|---|---|---:|---|---|---|",
            )
        )
        for item in extensions.spec_lifecycle:
            lines.append(
                f"| {item.spec_slug} | {item.state} | {'yes' if item.present else 'no'} | "
                f"{item.owner or '-'} | {item.evidence_url or '-'} | {item.reason} |"
            )
        if not extensions.spec_lifecycle:
            lines.append("| - | - | - | - | - | no specifications found |")
    else:
        lines.extend(("", "### CPP spec lifecycle"))
        lines.extend(
            f"- {item.spec_slug}: {item.state} ({'present' if item.present else 'absent'}) - {item.reason}"
            for item in extensions.spec_lifecycle
        )
        if not extensions.spec_lifecycle:
            lines.append("- no specifications found")

    if extensions.planning_routes:
        lines.extend(("", "### Wayfinder planning routes"))
        for route in extensions.planning_routes:
            target = f"issue #{route.issue_number}" if route.issue_number is not None else route.artifact
            lines.append(f"- {target}: `{route.action}` - {route.reason}; never `flow:auto`")
    if extensions.warnings:
        lines.extend(("", "### CPP extension warnings"))
        lines.extend(f"- {warning}" for warning in extensions.warnings)
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CPP's vendored project-next entry point")
    parser.add_argument("repository", nargs="?", default=".")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--brief", action="store_const", const="brief", dest="mode")
    modes.add_argument("--compact", action="store_const", const="compact", dest="mode")
    modes.add_argument("--full", action="store_const", const="full", dest="mode")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--input", type=Path, help="read an extended RepositoryState fixture")
    parser.add_argument("--config", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repository = Path(args.repository).resolve()
    try:
        config = load_config(repository, args.config)
        if args.input:
            fixture = json.loads(args.input.read_text(encoding="utf-8"))
            state = RepositoryState.from_dict(fixture)
            native_rows, native_warning = _native_rows_fixture(fixture)
        else:
            state = collect_repository(repository, config)
            native_rows, native_warning = _native_rows_live(repository, config.issue_limit + 1)
        normalized, relationships = normalize_relationships(state, native_rows)
        engine_state = normalize_graduated_specs(repository, normalized)
        result = recommend(engine_state, config)
        pinned_version = _manifest_version()
    except (
        CollectionError,
        ConfigError,
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"project-next: {exc}", file=sys.stderr)
        return 2

    if result.contract_version != pinned_version:
        print(
            f"project-next: engine speaks v{result.contract_version}, manifest pins v{pinned_version}",
            file=sys.stderr,
        )
        return 2
    lifecycle, lifecycle_warnings = classify_spec_lifecycle(repository, engine_state, result)
    warnings = tuple(item for item in (native_warning, *lifecycle_warnings) if item)
    extensions = CppExtensions(
        relationships=relationships,
        spec_lifecycle=lifecycle,
        planning_routes=planning_routes(repository, state),
        warnings=warnings,
    )
    if args.json:
        payload = result.to_dict()
        payload["decision_policy"] = f"contract v{pinned_version} (vendored engine)"
        payload["cpp_extensions"] = extensions.to_dict()
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        render_state = replace(engine_state, issues=state.issues)
        print(render_cpp(result, render_state, args.mode or config.default_mode, extensions))
    return 0 if result.inventory_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())

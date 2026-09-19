#!/usr/bin/env python3
"""CPP entry point for the always-present vendored project-next engine.

The vendored package owns classification, ranking, candidates, and top-action
selection. This adapter keeps that ``RecommendationResult`` byte-for-byte at
the model boundary while adding CPP-only evidence the upstream v1.3 model does
not represent yet:

- native GitHub issue relationships and explicitly uncertain text fallbacks;
- Wayfinder planning routes that never send decision work to ``flow:auto``;
- one shared spec-lifecycle decision consumed by all three render modes;
- premise-staleness flags for spec-derived issues whose parent spec predates
  a live architecture decision in the same domain.

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
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = REPO_ROOT / "vendor" / "project_next"
MANIFEST_PATH = REPO_ROOT / ".claude" / "project-next-vendor.json"
sys.path.insert(0, str(VENDOR_ROOT))

from lib.project_next.classify import _dependencies, _task_issue_index  # noqa: E402
from lib.project_next.collect import CollectionError, collect_repository  # noqa: E402
from lib.project_next.config import ConfigError, load_config  # noqa: E402
from lib.project_next.models import (  # noqa: E402
    Issue,
    RecommendationResult,
    RepositoryState,
    normalize_label,
)
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
# Premise staleness (issue #770). Architecture decision records are read from
# the conventional published locations; only a record whose status still reads
# as a live decision can retire a specification's premise.
DECISION_DIRECTORIES = ("docs/decisions", "docs/adr", "docs/adrs")
DECISION_FILENAME = re.compile(r"^(?P<identifier>\d{3,4})-.+\.md$")
DECISION_HEADING = re.compile(r"^ADR\s*\d+\s*[:.-]?\s*", re.IGNORECASE)
SPEC_HEADING = re.compile(r"^Feature Specification\s*:\s*", re.IGNORECASE)
HEADER_FIELD = re.compile(r"^>?\s*[-*]?\s*(?P<key>[A-Za-z][A-Za-z ]*?)\s*:\s*(?P<value>.*)$")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
LIVE_DECISION_STATUS = "accepted"
SPEC_DATE_KEYS = frozenset({"created", "date", "amended", "updated", "revised"})
PREMISE_HEADER_LINES = 24
PREMISE_TERM_MINIMUM = 4
PREMISE_ADVISORY = (
    "_Premise flags are advisory: ranking is unchanged and no issue is filtered. "
    "`/flow:eli5` remains the necessity decision point._"
)
# Shared-term matching is evidence only when the shared term is specific. The
# second group is repository-generic vocabulary that appears in nearly every
# specification and decision title, so an overlap on it says nothing about domain.
PREMISE_STOPWORDS = frozenset(
    """
    about after again against along also another around because been before being
    between both cannot could does done during each either else even ever every
    from have into just like made make many more most must need needs note only
    other over same shall should since some such than that their them then there
    these they this those through under until upon using were what when where
    which while will with within without would
    claude decision decisions design feature issue issues pack phase plan power
    project record spec specification specs support task tasks wave
    """.split()
)


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
class DecisionRecord:
    identifier: str
    title: str
    path: str
    date: str
    status: str
    domains: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SpecPremise:
    spec_slug: str
    title: str
    path: str
    as_of: str
    domains: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PremiseFlag:
    issue_number: int
    spec_slug: str
    spec_path: str
    spec_dated: str
    decision_id: str
    decision_title: str
    decision_path: str
    decision_dated: str
    domain: str
    match: str
    reason: str


@dataclass(frozen=True)
class CppExtensions:
    relationships: tuple[Relationship, ...]
    spec_lifecycle: tuple[LifecycleDecision, ...]
    planning_routes: tuple[PlanningRoute, ...]
    warnings: tuple[str, ...]
    premise_flags: tuple[PremiseFlag, ...] = field(default_factory=tuple)

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


def _iso_date(value: str) -> str:
    """Return the first well-formed ISO date in ``value``, or an empty string."""
    match = ISO_DATE.search(value)
    if match is None:
        return ""
    try:
        date.fromisoformat(match.group(0))
    except ValueError:
        return ""
    return match.group(0)


def _premise_terms(*sources: str) -> frozenset[str]:
    """Significant vocabulary shared-term domain matching is allowed to use."""
    terms: set[str] = set()
    for source in sources:
        for raw in re.split(r"[^A-Za-z0-9]+", source):
            token = raw.casefold()
            if len(token) < PREMISE_TERM_MINIMUM or token.isdigit() or token in PREMISE_STOPWORDS:
                continue
            terms.add(token)
    return frozenset(terms)


def _declared_domains(value: str) -> frozenset[str]:
    return frozenset(normalize_label(item) for item in re.split(r"[,;]", value) if item.strip())


def _header_fields(lines: Sequence[str]) -> tuple[str, dict[str, str], list[str]]:
    """Split a document header into its first heading and its ``key: value`` lines.

    Both artifact families put their metadata in a leading block of `- Key: value`
    (decision records) or `> **Key:** value` (Spec Kit specifications) lines, so
    one reader serves both. Emphasis markers are stripped before matching, and
    repeated keys are kept in order because a spec's amendment dates are as
    load-bearing as its creation date.
    """
    heading = ""
    fields: dict[str, str] = {}
    repeated: list[str] = []
    for line in lines[:PREMISE_HEADER_LINES]:
        stripped = line.strip().replace("**", "")
        if not heading and stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            continue
        match = HEADER_FIELD.match(stripped)
        if match is None:
            continue
        key = match.group("key").strip().casefold()
        value = match.group("value").strip()
        repeated.append(f"{key}: {value}")
        fields.setdefault(key, value)
    return heading, fields, repeated


def _decision_records(repository: Path) -> tuple[tuple[DecisionRecord, ...], list[str]]:
    """Read every architecture decision record the repository publishes."""
    records: list[DecisionRecord] = []
    warnings: list[str] = []
    for relative in DECISION_DIRECTORIES:
        directory = repository / relative
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            name = DECISION_FILENAME.match(path.name)
            if name is None:
                continue
            source = f"{relative}/{path.name}"
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                warnings.append(f"cannot read {source}: {exc}")
                continue
            heading, fields, _ = _header_fields(lines)
            leading = re.match(r"[A-Za-z]+", fields.get("status", ""))
            status = leading.group(0).casefold() if leading else ""
            decided = _iso_date(fields.get("date", ""))
            if not status or not decided:
                warnings.append(f"{source}: decision record needs parsable 'Status' and 'Date' header fields")
                continue
            title = DECISION_HEADING.sub("", heading).strip() or heading or path.stem
            records.append(
                DecisionRecord(
                    identifier=f"ADR {name.group('identifier')}",
                    title=title,
                    path=source,
                    date=decided,
                    status=status,
                    domains=_declared_domains(fields.get("domains") or fields.get("domain") or ""),
                )
            )
    return tuple(records), warnings


def _spec_premise(repository: Path, slug: str, relative: str) -> SpecPremise | None:
    """Read one specification's premise evidence: when it was written, and about what.

    An amendment date counts as the as-of date because an amended spec has
    already been revisited; accusing it of predating a decision it absorbed
    would be exactly the false positive this annotation must not produce.
    """
    path = repository / relative / "spec.md"
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    heading, fields, repeated = _header_fields(lines)
    dates = []
    for entry in repeated:
        key, _, value = entry.partition(":")
        if key in SPEC_DATE_KEYS:
            iso = _iso_date(value)
            if iso:
                dates.append(iso)
    title = SPEC_HEADING.sub("", heading).strip() or heading or slug
    return SpecPremise(
        spec_slug=slug,
        title=title,
        path=f"{relative}/spec.md",
        as_of=max(dates) if dates else "",
        domains=_declared_domains(fields.get("domains") or fields.get("domain") or ""),
    )


def _premise_domain_match(spec: SpecPremise, decision: DecisionRecord) -> tuple[str, str] | None:
    """Decide whether a spec and a decision record cover the same domain.

    Declared domains on both documents are authoritative. Shared significant
    terms are the fallback that lets the check act on a backlog as it stands,
    and every flag names which of the two produced it so a heuristic match is
    never presented with declared-evidence confidence.
    """
    declared = spec.domains & decision.domains
    if declared:
        return "declared", sorted(declared)[0]
    shared = _premise_terms(spec.spec_slug, spec.title) & _premise_terms(decision.title, Path(decision.path).stem)
    if shared:
        return "shared-term", sorted(shared)[0]
    return None


def premise_flags(
    repository: Path,
    state: RepositoryState,
    result: RecommendationResult,
) -> tuple[tuple[PremiseFlag, ...], tuple[str, ...]]:
    """Flag open spec-derived issues whose parent spec predates a live decision.

    WSJF-shaped ranking reads value, effort, and unblocking - all properties of
    the issue itself. None of them can see that a decision merged after the
    parent spec retired the premise the spec was written under, so a dead issue
    still ranks as a well-formed, small, safe pick (issue #770). This annotation
    names that pair and only that pair: it never re-ranks, filters, or hides an
    engine result, and ``/flow:eli5`` remains the necessity decision point.

    Superseded and rejected records are excluded on purpose. They no longer
    state a live decision, and the record that replaced a superseded one carries
    its own date, so the successor raises the flag the predecessor cannot.
    """
    decisions, warnings = _decision_records(repository)
    live = tuple(record for record in decisions if record.status == LIVE_DECISION_STATUS)
    if not live:
        return (), tuple(warnings)

    open_issues = set(result.classification.in_flight)
    open_issues.update(result.classification.blocked)
    open_issues.update(result.classification.uncertain)
    open_issues.update(result.classification.available)

    paths = {feature.name: feature.path for feature in state.spec_features}
    mapped: dict[str, set[int]] = {}
    for task in state.spec_tasks:
        derived = {number for number in task.issue_numbers if number in open_issues}
        if derived:
            mapped.setdefault(task.feature, set()).update(derived)

    flags: list[PremiseFlag] = []
    for slug in sorted(mapped):
        relative = paths.get(slug) or f".specify/specs/{slug}"
        spec = _spec_premise(repository, slug, relative)
        if spec is None:
            # An absent spec.md is already reported by classify_spec_lifecycle;
            # a second warning for one file would be noise, not evidence.
            continue
        if not spec.as_of:
            warnings.append(
                f"premise check skipped for spec {slug!r}: {spec.path} has no parsable "
                "'Created' or 'Amended' date"
            )
            continue
        for record in live:
            if spec.as_of >= record.date:
                continue
            match = _premise_domain_match(spec, record)
            if match is None:
                continue
            method, domain = match
            evidence = "declared domain" if method == "declared" else "shared term"
            reason = (
                f"spec {slug!r} ({spec.as_of}) predates {record.identifier} {record.title!r} "
                f"({record.date}); {evidence} {domain!r}"
            )
            flags.extend(
                PremiseFlag(
                    issue_number=number,
                    spec_slug=slug,
                    spec_path=spec.path,
                    spec_dated=spec.as_of,
                    decision_id=record.identifier,
                    decision_title=record.title,
                    decision_path=record.path,
                    decision_dated=record.date,
                    domain=domain,
                    match=method,
                    reason=reason,
                )
                for number in sorted(mapped[slug])
            )
    ordered = tuple(sorted(flags, key=lambda flag: (flag.issue_number, flag.decision_id, flag.spec_slug)))
    return ordered, tuple(warnings)


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

    flags = extensions.premise_flags
    if mode == "brief":
        if flags:
            numbers = ", ".join(f"#{number}" for number in sorted({item.issue_number for item in flags}))
            lines.append(f"Premise staleness: {len(flags)} advisory flag(s) on {numbers} - confirm with `/flow:eli5`")
        else:
            lines.append("Premise staleness: none")
    elif mode == "full":
        lines.extend(
            (
                "",
                "### Premise staleness (advisory)",
                "| Issue | Spec | Spec dated | Decision | Decided | Domain | Match | Reason |",
                "|---:|---|---|---|---|---|---|---|",
            )
        )
        for item in flags:
            lines.append(
                f"| #{item.issue_number} | {item.spec_slug} | {item.spec_dated} | {item.decision_id} | "
                f"{item.decision_dated} | {item.domain} | {item.match} | {item.reason} |"
            )
        if not flags:
            lines.append("| - | - | - | - | - | - | - | no spec predates a live decision in its domain |")
        lines.extend(("", PREMISE_ADVISORY))
    else:
        lines.extend(("", "### Premise staleness (advisory)"))
        lines.extend(f"- issue #{item.issue_number}: {item.reason}" for item in flags)
        if not flags:
            lines.append("- none: no spec predates a live decision in its domain")
        lines.extend(("", PREMISE_ADVISORY))

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
    premise, premise_warnings = premise_flags(repository, engine_state, result)
    warnings = tuple(item for item in (native_warning, *lifecycle_warnings, *premise_warnings) if item)
    extensions = CppExtensions(
        relationships=relationships,
        spec_lifecycle=lifecycle,
        planning_routes=planning_routes(repository, state),
        warnings=warnings,
        premise_flags=premise,
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

#!/usr/bin/env python3
"""CPP entry point for the project-next engine.

``lib/project_next`` owns classification, ranking, candidates, and top-action
selection. CPP owns that package outright (issue #1069); it is no longer
vendored from codex-power-pack, and there is no upstream to drift from. This
adapter keeps its ``RecommendationResult`` byte-for-byte at the model boundary
while adding CPP-only evidence the v1.3 contract does not represent yet:

- native GitHub issue relationships and explicitly uncertain text fallbacks;
- Wayfinder planning routes that never send decision work to ``flow:auto``,
  from the map artifact and from any ``wayfinder:*`` label, with the map's read
  state (read, absent, unreadable) always reported rather than inferred;
- one shared spec-lifecycle decision consumed by all three render modes;
- premise-staleness flags for spec-derived issues whose parent spec predates
  a live architecture decision in the same domain;
- a delivery verdict for every worktree the engine proposes for cleanup, from
  per-file blob identity against the default branch (issue #1257).

Lifecycle is intentionally outside ``lib/project_next``. A graduation ledger
can describe an absent spec, so frontmatter alone cannot represent the policy.
The engine stays harness-neutral and the adapter stays thin: that separation
outlived the vendoring that first motivated it, and is kept on its own merits.
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
MANIFEST_PATH = REPO_ROOT / ".claude" / "project-next-ownership.json"
# `.resolve()` first, so this works through a symlinked copy as well as from the
# checkout: normal installations expose this as ~/.claude/scripts/project-next.py,
# and sys.path[0] is the directory of the path as INVOKED, not the real one.
#
# This insert used to point at `vendor/project_next`, where the engine lived.
# It is RE-POINTED at the repo root rather than deleted (#1069): `lib` is not
# importable from `scripts/` on its own, so dropping it breaks every invocation
# as a PROGRAM while leaving every in-process import working - which is why the
# subprocess test in tests/test_project_next_contract.py exists.
sys.path.insert(0, str(REPO_ROOT))

from lib.project_next.classify import _dependencies, _task_issue_index  # noqa: E402
from lib.project_next.collect import (  # noqa: E402
    CollectionError,
    CommandRunner,
    collect_repository,
    subprocess_runner,
)
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
WAYFINDER_MAP = Path(".claude") / "wayfinder-map.json"
# Matched against normalize_label() output, so `wayfinder:map` arrives as `wayfinder-map`.
WAYFINDER_LABEL_PREFIX = "wayfinder-"
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
# Worktree delivery (issue #1257). Ordered for rendering; `delivered` is the only
# verdict that supports removal.
DELIVERY_VERDICTS = ("delivered", "not-proven", "unknown")
DELIVERY_ADVISORY = (
    "_`delivered`: every changed path has the identical blob on the default branch and the tree is clean. "
    "`not-proven` is not \"undelivered\" - inspect before removing. `unknown` means git could not be asked._"
)
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
class WayfinderMap:
    """Which of three states the map artifact was observed in, and where (#1035).

    ``absent`` and ``unreadable`` reach the same routing conclusion - no map-linked
    routes - for different reasons, and only the first one is evidence that no map
    exists. A linked worktree never checks out the (gitignored) artifact, so reading
    only the worktree path reported ``absent`` from exactly where flow work happens.
    """

    state: str
    path: str = ""
    detail: str = ""


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
class WorktreeDelivery:
    """Whether a cleanup-candidate worktree's work already reached the default branch (#1257).

    ``verdict`` is what a reader deciding ``git worktree remove`` acts on:
    ``delivered`` only when every path the branch changed since its merge-base
    holds the identical blob (and mode) on ``origin/<default>`` AND the tree has
    nothing uncommitted or untracked. ``not-proven`` never means "undelivered" -
    the default branch may have moved those files since. Any failure to ask git
    is ``unknown``, never ``delivered``.
    """

    path: str
    branch: str
    issue_state: str
    verdict: str
    committed: str
    tree: str
    remote_branch: str
    changed_paths: int | None = None
    differing_paths: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class CppExtensions:
    relationships: tuple[Relationship, ...]
    spec_lifecycle: tuple[LifecycleDecision, ...]
    planning_routes: tuple[PlanningRoute, ...]
    warnings: tuple[str, ...]
    premise_flags: tuple[PremiseFlag, ...] = field(default_factory=tuple)
    wayfinder_map: WayfinderMap | None = None
    worktree_delivery: tuple[WorktreeDelivery, ...] = field(default_factory=tuple)

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
    but the normalized state supplies a dangling declaration so the engine's
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
    open_numbers = {issue.number for issue in state.issues}
    normalized: list[Issue] = []
    for issue in state.issues:
        parsed, _, _ = _dependencies(issue, task_issues)
        confirmed = native_blocked.get(issue.number, set())
        fallback = parsed - confirmed
        # With a complete inventory a text reference to an issue that is not open is
        # already satisfied, exactly as the engine reads it; only open ones are unverified.
        if state.inventory_complete:
            fallback &= open_numbers
        body = issue.body
        additions = [f"Blocked by #{number}" for number in sorted(confirmed)]
        # Only text edges need the synthetic line: unresolved phrasing is still in the
        # body and the engine reports it in its own words. The line names its references,
        # so the rendered reason no longer says "the blocker names no issue" (#1035).
        if fallback:
            refs = ", ".join(f"#{number}" for number in sorted(fallback))
            additions.append(
                f"Blocked by: text-only dependency on {refs} is not a native GitHub edge, so it could not be verified"
            )
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


def _git_path(repository: Path, flag: str) -> Path:
    output = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--path-format=absolute", flag],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    return Path(output)


def _wayfinder_map_locations(repository: Path) -> tuple[Path, ...]:
    """The checkout's own map path, then the primary checkout's when this is a linked worktree.

    Raises OSError or subprocess errors when a linked worktree cannot name its primary.
    """
    local = repository / WAYFINDER_MAP
    # A linked worktree's `.git` is a FILE pointing into the common git dir; a primary
    # checkout's is a directory, and a plain directory has none. Only the first needs git.
    if not (repository / ".git").is_file():
        return (local,)
    common = _git_path(repository, "--git-common-dir")
    if common.name != ".git":
        raise OSError(f"common git dir {common} is not inside a primary checkout")
    return (local, common.parent / WAYFINDER_MAP)


def read_wayfinder_map(repository: Path) -> tuple[WayfinderMap, dict[str, object] | None]:
    try:
        locations = _wayfinder_map_locations(repository)
    except (OSError, subprocess.SubprocessError) as exc:
        return WayfinderMap("unreadable", "", f"cannot resolve the primary checkout from this worktree: {exc}"), None
    for path in locations:
        try:
            # Inside the handler: a permission-denied stat is an unreadable map, not a crash.
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return WayfinderMap("unreadable", str(path), str(exc)), None
        if not isinstance(payload, dict):
            return WayfinderMap("unreadable", str(path), "the artifact is not a JSON object"), None
        return WayfinderMap("read", str(path), f"state: {payload.get('state', 'unspecified')}"), payload
    checked = ", ".join(str(path) for path in locations)
    return WayfinderMap("absent", "", f"checked {checked}"), None


def planning_routes(
    repository: Path, state: RepositoryState, payload: dict[str, object] | None = None
) -> tuple[PlanningRoute, ...]:
    """Route map-linked decision tickets and ``wayfinder:*``-labelled issues to planning.

    ``payload`` is the map already read by ``read_wayfinder_map``; omitted, it is read here.
    """
    if payload is None:
        _, payload = read_wayfinder_map(repository)
    routes: list[PlanningRoute] = []
    routed: set[int] = set()
    decisions = payload.get("decisions") if payload and payload.get("state") == "awaiting-decisions" else None
    if isinstance(decisions, list):
        ids = {
            raw.get("decision_id")
            for raw in decisions
            if isinstance(raw, dict)
            and isinstance(raw.get("decision_id"), str)
            and raw.get("status") != "resolved"
        }
        ids.discard(None)
        routes.append(
            PlanningRoute(
                issue_number=None,
                artifact=str(WAYFINDER_MAP),
                action="/project:init",
                reason="resume the awaiting-decisions Wayfinder map",
            )
        )
        for issue in state.issues:
            issue_ids = set(DECISION_ID.findall(f"{issue.title}\n{issue.body}"))
            if issue_ids & ids:
                routed.add(issue.number)
                routes.append(
                    PlanningRoute(
                        issue_number=issue.number,
                        artifact=sorted(issue_ids & ids)[0],
                        action="/project:init",
                        reason="resolve the linked Wayfinder decision before implementation planning",
                    )
                )
    # The label is the checkable trigger, not body text: prose DISCUSSING wayfinding
    # would trip a text match, and a seed that says "do not implement" in a sentence
    # still reached flow:auto (#1035).
    for issue in state.issues:
        if issue.number in routed:
            continue
        labels = sorted(label for label in issue.labels if normalize_label(label).startswith(WAYFINDER_LABEL_PREFIX))
        if labels:
            routes.append(
                PlanningRoute(
                    issue_number=issue.number,
                    artifact=f"label:{labels[0]}",
                    action="/project:init",
                    reason="carries a Wayfinder label, so it is planning work, not an implementation ticket",
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


def _raw_diff_paths(output: str) -> frozenset[str]:
    """Paths named by ``git diff --raw -z --no-renames``: ``:<meta>\0<path>\0`` per entry.

    A malformed stream raises ValueError, so a parse failure becomes ``unknown``
    rather than an empty set - an empty set here reads as "nothing differs".
    """
    fields = output.split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(fields) and fields[index]:
        meta = fields[index]
        if not meta.startswith(":") or index + 1 >= len(fields) or not fields[index + 1]:
            raise ValueError(f"unparseable git diff --raw entry: {meta[:60]!r}")
        paths.add(fields[index + 1])
        index += 2
    return frozenset(paths)


def _remote_heads(repository: Path, runner: CommandRunner) -> frozenset[str] | None:
    """Branch names on the remote itself, or None when it cannot be asked.

    The collector fetches without ``--prune``, so a local ``refs/remotes/origin/*``
    ref can outlive the branch it names; asking the remote is the only reading
    that says a deleted branch is gone.
    """
    try:
        output = runner(["git", "ls-remote", "--heads", "origin"], repository)
    except (CollectionError, OSError):
        return None
    heads = set()
    for line in output.splitlines():
        _, _, ref = line.partition("\t")
        if ref.startswith("refs/heads/"):
            heads.add(ref.removeprefix("refs/heads/"))
    return frozenset(heads)


def _tree_state(path: Path, runner: CommandRunner) -> tuple[str, str]:
    # Asked again rather than read from the collector: the collector turns a failed
    # `git status` into an empty one, i.e. "clean", which is the one reading this
    # verdict must never inherit from a failure.
    try:
        status = runner(["git", "status", "--porcelain"], path)
    except (CollectionError, OSError) as exc:
        return "unknown", f"git status failed: {exc}"
    lines = [line for line in status.splitlines() if line.strip()]
    if any(not line.startswith("??") for line in lines):
        return "dirty", "uncommitted tracked changes"
    if lines:
        return "untracked", "untracked files would be lost on removal"
    return "clean", ""


def _committed_state(
    path: Path, base_ref: str, runner: CommandRunner
) -> tuple[str, int | None, tuple[str, ...], str]:
    # Never `merge-base --is-ancestor` and never a rev-list count: a squash merge
    # breaks both, so a delivered branch reads as unmerged by either (#1257).
    try:
        merge_base = runner(["git", "merge-base", "HEAD", base_ref], path).strip()
        if not merge_base:
            raise ValueError(f"no merge-base with {base_ref}")
        changed = _raw_diff_paths(runner(["git", "diff", "--raw", "-z", "--no-renames", merge_base, "HEAD"], path))
        differing = _raw_diff_paths(runner(["git", "diff", "--raw", "-z", "--no-renames", base_ref, "HEAD"], path))
    except (CollectionError, OSError, ValueError) as exc:
        return "unknown", None, (), f"blob comparison failed: {exc}"
    # A path the branch changed that still differs from the base is one whose branch
    # blob (or deletion) is not on the base. Paths that differ only because the base
    # moved on are not the branch's work and do not count against it.
    unmatched = tuple(sorted(changed & differing))
    if unmatched:
        sample = ", ".join(unmatched[:3]) + (", ..." if len(unmatched) > 3 else "")
        return (
            "not-proven",
            len(changed),
            unmatched,
            f"{len(unmatched)} of {len(changed)} changed path(s) differ from {base_ref} ({sample}); "
            "the base may have moved them since",
        )
    if not changed:
        return "delivered", 0, (), f"branch changes no path relative to its merge-base with {base_ref}"
    return "delivered", len(changed), (), f"all {len(changed)} changed path(s) have the identical blob on {base_ref}"


def worktree_delivery(
    repository: Path,
    result: RecommendationResult,
    default_branch: str,
    runner: CommandRunner | None = subprocess_runner,
) -> tuple[WorktreeDelivery, ...]:
    """Annotate every worktree the engine proposes for cleanup with a delivery verdict.

    ``runner=None`` means there is no live repository to ask (``--input`` fixtures):
    every candidate is ``unknown``, never silently ``delivered``.
    """
    candidates = tuple(detail for detail in result.worktree_details if detail.cleanup_recommended)
    if not candidates:
        return ()
    base_ref = f"refs/remotes/origin/{default_branch}"
    heads = _remote_heads(repository, runner) if runner is not None else None
    annotated = []
    for detail in candidates:
        if runner is None:
            annotated.append(
                WorktreeDelivery(
                    path=detail.path,
                    branch=detail.branch,
                    issue_state=detail.issue_state,
                    verdict="unknown",
                    committed="unknown",
                    tree="unknown",
                    remote_branch="unknown",
                    reason="not collected: fixture input has no repository to compare",
                )
            )
            continue
        path = Path(detail.path)
        tree, tree_reason = _tree_state(path, runner)
        committed, changed, differing, committed_reason = _committed_state(path, base_ref, runner)
        if not detail.branch:
            remote = "n/a"
        elif heads is None:
            remote = "unknown"
        else:
            remote = "present" if detail.branch in heads else "absent"
        if "unknown" in (tree, committed):
            verdict = "unknown"
        elif committed == "delivered" and tree == "clean":
            verdict = "delivered"
        else:
            verdict = "not-proven"
        annotated.append(
            WorktreeDelivery(
                path=detail.path,
                branch=detail.branch,
                issue_state=detail.issue_state,
                verdict=verdict,
                committed=committed,
                tree=tree,
                remote_branch=remote,
                changed_paths=changed,
                differing_paths=differing,
                reason="; ".join(item for item in (committed_reason, tree_reason) if item),
            )
        )
    return tuple(annotated)


def _apply_route_rendering(text: str, routes: tuple[PlanningRoute, ...]) -> str:
    for route in routes:
        if route.issue_number is None:
            continue
        # Anchor the number: routing #87 must never rewrite the command for #876 (#1035).
        pattern = re.compile(rf"(`?)\$flow-auto {route.issue_number}(?!\d)\1")
        replacement = f"\\g<1>{route.action}\\g<1> (Wayfinder planning only)"
        text = pattern.sub(replacement, text)
    return text


def _apply_route_payload(payload: dict[str, object], routes: tuple[PlanningRoute, ...]) -> dict[str, object]:
    """Give JSON the same routes as the human modes: `--json` is the authoritative output."""
    actions = {route.issue_number: route.action for route in routes if route.issue_number is not None}
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("issue_number") in actions:
                candidate["command"] = f"{actions[candidate['issue_number']]} (Wayfinder planning only)"
    return payload


def render_cpp(
    result: RecommendationResult,
    state: RepositoryState,
    mode: str,
    extensions: CppExtensions,
) -> str:
    base = _apply_route_rendering(render_result(result, state, mode), extensions.planning_routes)
    lines = [f"_decision policy: contract v{result.contract_version} (project-next engine)_", "", base]
    wayfinder = extensions.wayfinder_map
    map_line = (
        f"Wayfinder map: {wayfinder.state}" + (f" ({wayfinder.path})" if wayfinder.path else "")
        + (f" - {wayfinder.detail}" if wayfinder.detail else "")
        if wayfinder
        else "Wayfinder map: not checked"
    )
    counts = {name: 0 for name in sorted(LIFECYCLE_STATES)}
    for decision in extensions.spec_lifecycle:
        counts[decision.state] += 1
    if mode == "brief":
        summary = " | ".join(f"{name} {counts[name]}" for name in sorted(counts))
        lines.extend(("", f"Spec lifecycle: {summary}", map_line))
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

    delivery = extensions.worktree_delivery
    if mode == "brief":
        if delivery:
            tally = {name: sum(item.verdict == name for item in delivery) for name in DELIVERY_VERDICTS}
            lines.append(
                "Worktree delivery: " + " | ".join(f"{name} {tally[name]}" for name in DELIVERY_VERDICTS)
            )
    elif mode == "full":
        lines.extend(
            (
                "",
                "### Worktree delivery",
                "| Worktree | Branch | Issue state | Verdict | Committed | Tree | Remote branch | Reason |",
                "|---|---|---|---|---|---|---|---|",
            )
        )
        for item in delivery:
            lines.append(
                f"| {item.path} | {item.branch or '(detached)'} | {item.issue_state} | {item.verdict} | "
                f"{item.committed} | {item.tree} | {item.remote_branch} | {item.reason} |"
            )
        if not delivery:
            lines.append("| - | - | - | - | - | - | - | no worktree is a cleanup candidate |")
        lines.extend(("", DELIVERY_ADVISORY))
    else:
        lines.extend(("", "### Worktree delivery"))
        lines.extend(
            f"- {item.path} ({item.branch or 'detached'}): **{item.verdict}** - tree {item.tree}, "
            f"remote branch {item.remote_branch} - {item.reason}"
            for item in delivery
        )
        if not delivery:
            lines.append("- none: no worktree is a cleanup candidate")
        else:
            lines.extend(("", DELIVERY_ADVISORY))

    if mode != "brief":
        lines.extend(("", "### Wayfinder planning routes", f"- {map_line}"))
        for route in extensions.planning_routes:
            target = f"issue #{route.issue_number}" if route.issue_number is not None else route.artifact
            lines.append(f"- {target}: `{route.action}` - {route.reason}; never `flow:auto`")
    elif extensions.planning_routes:
        numbers = ", ".join(f"#{r.issue_number}" for r in extensions.planning_routes if r.issue_number is not None)
        lines.append(f"Wayfinder planning routes: {numbers or 'map only'} - `/project:init`, never `flow:auto`")
    if extensions.warnings:
        lines.extend(("", "### CPP extension warnings"))
        lines.extend(f"- {warning}" for warning in extensions.warnings)
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CPP's project-next entry point")
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
    wayfinder_map, wayfinder_payload = read_wayfinder_map(repository)
    delivery = worktree_delivery(
        repository, result, state.default_branch, runner=None if args.input else subprocess_runner
    )
    extensions = CppExtensions(
        relationships=relationships,
        spec_lifecycle=lifecycle,
        planning_routes=planning_routes(repository, state, wayfinder_payload),
        wayfinder_map=wayfinder_map,
        warnings=warnings,
        premise_flags=premise,
        worktree_delivery=delivery,
    )
    if args.json:
        payload = _apply_route_payload(result.to_dict(), extensions.planning_routes)
        payload["decision_policy"] = f"contract v{pinned_version} (project-next engine)"
        payload["cpp_extensions"] = extensions.to_dict()
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        render_state = replace(engine_state, issues=state.issues)
        print(render_cpp(result, render_state, args.mode or config.default_mode, extensions))
    return 0 if result.inventory_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())

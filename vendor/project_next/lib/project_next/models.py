"""Structured inputs and outputs for the project-next engine."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

LABEL_SEPARATOR = re.compile(r"[\s:/_]+")


def normalize_label(label: str) -> str:
    """Fold `priority:high`, `priority/high`, and `Priority High` onto one spelling."""
    return LABEL_SEPARATOR.sub("-", str(label).strip().casefold()).strip("-")


def _tuple_of_strings(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in (value or ()))


def _tuple_of_ints(value: Any) -> tuple[int, ...]:
    return tuple(int(item) for item in (value or ()))


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str = ""
    labels: tuple[str, ...] = ()
    assignees: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    url: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Issue:
        return cls(
            number=int(data["number"]),
            title=str(data["title"]),
            body=str(data.get("body") or ""),
            labels=_tuple_of_strings(data.get("labels")),
            assignees=_tuple_of_strings(data.get("assignees")),
            created_at=str(data.get("created_at") or data.get("createdAt") or ""),
            updated_at=str(data.get("updated_at") or data.get("updatedAt") or ""),
            url=str(data.get("url") or ""),
        )

    @property
    def normalized_labels(self) -> frozenset[str]:
        return frozenset(normalize_label(label) for label in self.labels)


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    head_ref: str
    body: str = ""
    closing_issue_numbers: tuple[int, ...] = ()
    draft: bool = False
    merge_state: str = "UNKNOWN"
    review_decision: str = ""
    checks_state: str = "unknown"
    url: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PullRequest:
        return cls(
            number=int(data["number"]),
            title=str(data["title"]),
            head_ref=str(data.get("head_ref") or data.get("headRefName") or ""),
            body=str(data.get("body") or ""),
            closing_issue_numbers=_tuple_of_ints(data.get("closing_issue_numbers") or data.get("closingIssues")),
            draft=bool(data.get("draft") or data.get("isDraft", False)),
            merge_state=str(data.get("merge_state") or data.get("mergeStateStatus") or "UNKNOWN"),
            review_decision=str(data.get("review_decision") or data.get("reviewDecision") or ""),
            checks_state=str(data.get("checks_state") or "unknown"),
            url=str(data.get("url") or ""),
        )


@dataclass(frozen=True)
class Worktree:
    path: str
    branch: str
    dirty: bool = False
    untracked_only: bool = False
    recent_commits: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Worktree:
        return cls(
            path=str(data["path"]),
            branch=str(data.get("branch") or ""),
            dirty=bool(data.get("dirty", False)),
            untracked_only=bool(data.get("untracked_only", False)),
            recent_commits=_tuple_of_strings(data.get("recent_commits")),
        )


@dataclass(frozen=True)
class Branch:
    name: str
    upstream: str = ""
    remote: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Branch:
        return cls(
            name=str(data["name"]),
            upstream=str(data.get("upstream") or ""),
            remote=bool(data.get("remote", False)),
        )


@dataclass(frozen=True)
class SpecTask:
    task_id: str
    title: str
    feature: str
    source: str
    issue_numbers: tuple[int, ...] = ()
    synchronized: bool = False
    group_id: str = ""
    stable_identity: str = ""
    mapping_status: str = "missing"
    mapping_state: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecTask:
        return cls(
            task_id=str(data["task_id"]),
            title=str(data["title"]),
            feature=str(data["feature"]),
            source=str(data["source"]),
            issue_numbers=_tuple_of_ints(data.get("issue_numbers")),
            synchronized=bool(data.get("synchronized", False)),
            group_id=str(data.get("group_id") or ""),
            stable_identity=str(data.get("stable_identity") or ""),
            mapping_status=str(data.get("mapping_status") or "missing"),
            mapping_state=str(data.get("mapping_state") or ""),
        )


@dataclass(frozen=True)
class SpecFeature:
    name: str
    path: str
    has_spec: bool = False
    has_plan: bool = False
    has_tasks: bool = False
    total_tasks: int = 0
    mapped_tasks: int = 0
    mapping_status: str = "not-applicable"
    recommended_action: str = "none"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecFeature:
        return cls(
            name=str(data["name"]),
            path=str(data.get("path") or ""),
            has_spec=bool(data.get("has_spec", False)),
            has_plan=bool(data.get("has_plan", False)),
            has_tasks=bool(data.get("has_tasks", False)),
            total_tasks=int(data.get("total_tasks", 0)),
            mapped_tasks=int(data.get("mapped_tasks", 0)),
            mapping_status=str(data.get("mapping_status") or "not-applicable"),
            recommended_action=str(data.get("recommended_action") or "none"),
        )


@dataclass(frozen=True)
class RepositoryState:
    repository: str
    default_branch: str
    collected_at: str
    issues: tuple[Issue, ...] = ()
    pull_requests: tuple[PullRequest, ...] = ()
    worktrees: tuple[Worktree, ...] = ()
    branches: tuple[Branch, ...] = ()
    spec_tasks: tuple[SpecTask, ...] = ()
    spec_features: tuple[SpecFeature, ...] = ()
    gate_status: str = "unknown"
    inventory_complete: bool = True
    collector_warnings: tuple[str, ...] = ()
    collector_errors: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepositoryState:
        return cls(
            repository=str(data["repository"]),
            default_branch=str(data.get("default_branch") or "main"),
            collected_at=str(data.get("collected_at") or ""),
            issues=tuple(Issue.from_dict(item) for item in data.get("issues", ())),
            pull_requests=tuple(PullRequest.from_dict(item) for item in data.get("pull_requests", ())),
            worktrees=tuple(Worktree.from_dict(item) for item in data.get("worktrees", ())),
            branches=tuple(Branch.from_dict(item) for item in data.get("branches", ())),
            spec_tasks=tuple(SpecTask.from_dict(item) for item in data.get("spec_tasks", ())),
            spec_features=tuple(SpecFeature.from_dict(item) for item in data.get("spec_features", ())),
            gate_status=str(data.get("gate_status") or "unknown"),
            inventory_complete=bool(data.get("inventory_complete", True)),
            collector_warnings=_tuple_of_strings(data.get("collector_warnings")),
            collector_errors=_tuple_of_strings(data.get("collector_errors")),
        )

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True)
class Classification:
    in_flight: tuple[int, ...]
    blocked: tuple[int, ...]
    available: tuple[int, ...]
    uncertain: tuple[int, ...]
    dependency_map: dict[int, tuple[int, ...]] = field(default_factory=dict)
    blocked_by: dict[int, tuple[int, ...]] = field(default_factory=dict)
    in_flight_evidence: dict[int, tuple[str, ...]] = field(default_factory=dict)
    uncertainty: dict[int, tuple[str, ...]] = field(default_factory=dict)
    unmapped_worktrees: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True)
class Action:
    kind: str
    title: str
    reason: str
    issue_number: int | None = None
    pull_request_number: int | None = None
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True)
class Candidate:
    issue_number: int
    rank_key: tuple[int, ...]
    priority: str
    phase: str
    issue_type: str
    quick_win: bool
    critical: bool
    stale: bool
    rationale: str
    command: str


@dataclass(frozen=True)
class BacklogSummary:
    open: int = 0
    critical: int = 0
    bugs: int = 0
    features: int = 0
    docs: int = 0
    tech_debt: int = 0
    planning: int = 0
    other: int = 0


@dataclass(frozen=True)
class BacklogTiers:
    critical: tuple[int, ...] = ()
    active: tuple[int, ...] = ()
    blocked: tuple[int, ...] = ()
    uncertain: tuple[int, ...] = ()
    ready: tuple[int, ...] = ()
    quick_wins: tuple[int, ...] = ()
    planning: tuple[int, ...] = ()
    pending_spec_sync: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorktreeDetail:
    path: str
    branch: str
    issue_number: int | None
    issue_state: str
    dirty: bool
    untracked_only: bool = False
    recent_commits: tuple[str, ...] = ()
    cleanup_recommended: bool = False
    cleanup_reason: str = ""


@dataclass(frozen=True)
class CleanupCandidate:
    target_type: str
    target: str
    branch: str
    issue_number: int | None
    reason: str
    action: str = "Review with $flow-cleanup"


@dataclass(frozen=True)
class RecommendationResult:
    contract_version: str
    repository: str
    inventory_complete: bool
    classification: Classification
    ranked_available: tuple[int, ...]
    top_action: Action | None
    next_startable_issue: int | None
    unsynchronized_spec_tasks: tuple[SpecTask, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    backlog_summary: BacklogSummary = field(default_factory=BacklogSummary)
    backlog_tiers: BacklogTiers = field(default_factory=BacklogTiers)
    spec_features: tuple[SpecFeature, ...] = ()
    worktree_details: tuple[WorktreeDetail, ...] = ()
    cleanup_candidates: tuple[CleanupCandidate, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))

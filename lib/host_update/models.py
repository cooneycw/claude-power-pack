"""Public, side-effect-free data contracts for the managed-copy core.

Paths describe adapter-authorized scopes; constructing these values does not
resolve or inspect them. Core IO must first validate the policy without following
symlinks. Ownership metadata is separate from discoverable package contents.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType


class State(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    HAND_EDITED = "hand-edited"
    UNMANAGED = "unmanaged"
    ABSENT = "absent"
    NOT_APPLICABLE = "not-applicable"
    UNKNOWN = "unknown"


class Action(StrEnum):
    UNCHANGED = "unchanged"
    REFRESHED = "refreshed"
    REFUSED = "refused"
    FAILED = "failed"
    NOT_ATTEMPTED = "not-attempted"


@dataclass(frozen=True)
class Revision:
    """One full source commit and its caller-approved immutable snapshot root.

    The core validates commit shape and source/snapshot binding before use. A
    typed value alone is not proof of a clean source or an available revision.
    """

    commit: str
    snapshot_root: Path


@dataclass(frozen=True)
class Request:
    revision: Revision
    selected: bool | None = None
    lock_timeout_seconds: float = 5.0
    adopt_paths: tuple[str, ...] = ()


def regular_member(relative_path: str, mode: int) -> bool:
    """Default mode policy; confinement/path validation is independently required."""
    return bool(relative_path) and mode in (0o644, 0o755)


@dataclass(frozen=True)
class Policy:
    """Scopes approved by adapter preflight, not inferred from host conventions.

    Only package paths and management locations under install_root may be
    inspected/mutated. The exact lock_path may be outside that root; its parent
    is not an additional inventory/write scope. ledger_path and work_root must
    be inside install_root, outside discoverable packages. The core must not
    enumerate an agent/config root or follow aliases to validate this policy.
    member_allowed is a pure policy predicate, not a filesystem reader.
    """

    install_root: Path
    ledger_path: Path
    lock_path: Path
    work_root: Path
    member_allowed: Callable[[str, int], bool] = regular_member


@dataclass(frozen=True)
class Discovery:
    selected: bool
    managed: bool
    evidence: tuple[str, ...] = ()
    absent: bool = False
    unknown: bool = False
    reason: str = ""


@dataclass(frozen=True)
class ExpectedMember:
    content: bytes
    mode: int = 0o644

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class ExpectedPackage:
    name: str
    canonical_source: str
    members: Mapping[str, ExpectedMember]

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", MappingProxyType(dict(self.members)))


@dataclass(frozen=True)
class ExpectedBuild:
    revision: str
    packages: tuple[ExpectedPackage, ...]
    manifest_sha256: str


def build_manifest_sha256(revision: str, packages: Sequence[ExpectedPackage]) -> str:
    """Hash the portable, sorted expected membership/bytes/modes contract."""
    payload = {
        "schema": 1,
        "revision": revision,
        "packages": [
            {
                "name": package.name,
                "canonical_source": package.canonical_source,
                "members": {
                    name: {"sha256": member.sha256, "mode": member.mode}
                    for name, member in sorted(package.members.items())
                },
            }
            for package in sorted(packages, key=lambda item: item.name)
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class OwnedMember:
    sha256: str
    mode: int


@dataclass(frozen=True)
class OwnershipRecord:
    package: str
    canonical_source: str
    revision: str
    members: Mapping[str, OwnedMember]
    producer: str = "claude-power-pack"
    schema: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", MappingProxyType(dict(self.members)))


@dataclass(frozen=True)
class Conflict:
    package: str
    relative_path: str
    state: State
    reason: str


@dataclass(frozen=True)
class Inspection:
    state: State
    expected_packages: int = 0
    expected_members: int = 0
    examined_members: int = 0
    conflicts: tuple[Conflict, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class Effectiveness:
    """Contextual runtime selection, separate from installed-byte inspection.

    A core fidelity result never upgrades this evidence. A later adapter may
    attach bounded runtime/context evidence; lack of it remains unknown.
    """

    state: str = "unknown"
    context: str = ""
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdapterResult:
    harness: str
    revision: str
    selected: bool
    selection_evidence: tuple[str, ...]
    before: Inspection
    action: Action
    after: Inspection
    exit_code: int
    reason: str = ""
    remedy: str = ""
    metadata_refreshed: bool = False
    effectiveness: Effectiveness = field(default_factory=Effectiveness)


@dataclass(frozen=True)
class RunReport:
    revision: str
    results: tuple[AdapterResult, ...]
    exit_code: int
    coverage: str = "fixture-only"
    schema: int = 1


class AdapterError(Exception):
    """An adapter's explicit refusal/unknown/not-applicable outcome.

    Codes are 1 (known refusal), 4 (unknown) or 5 (not applicable). The core
    retains the reason/code in that adapter's row before aggregate precedence.
    """

    def __init__(
        self, reason: str, *, exit_code: int = 1,
        state: State = State.UNKNOWN, remedy: str = "",
    ) -> None:
        super().__init__(reason)
        self.exit_code = exit_code
        self.state = state
        self.remedy = remedy

"""Learning model + the bucket-2 portability gate."""
from __future__ import annotations

from dataclasses import dataclass, field

from .fingerprint import fingerprint as _fp

FRICTION_CLASSES = {
    "permission",
    "gate_failure",
    "red_output",
    "manual_intervention",
    "infra_trap",
    "knowledge",
}
FIX_SCOPES = {"repo_file", "permission", "knowledge"}

# Bucket-2-plus: only portable knowledge / infra traps enter the SHARED store.
# repo_file fixes belong in git; permission fixes stay per-machine.
_PORTABLE_CLASSES = {"infra_trap", "knowledge"}
_PORTABLE_SCOPES = {"knowledge"}


def is_portable(friction_class: str, fix_scope: str) -> bool:
    """True when a learning may be pushed to the SHARED store."""
    return fix_scope in _PORTABLE_SCOPES or friction_class in _PORTABLE_CLASSES


@dataclass
class Learning:
    friction_class: str
    fix_scope: str
    title: str
    body: str
    proposed_fix: str | None = None
    confidence: float = 0.5
    evidence: list = field(default_factory=list)

    def validate(self) -> None:
        if self.friction_class not in FRICTION_CLASSES:
            raise ValueError(f"unknown friction_class: {self.friction_class!r}")
        if self.fix_scope not in FIX_SCOPES:
            raise ValueError(f"unknown fix_scope: {self.fix_scope!r}")
        if not (self.title or "").strip():
            raise ValueError("title is required")

    @property
    def fingerprint(self) -> str:
        return _fp(self.friction_class, self.title, self.body)

    @property
    def portable(self) -> bool:
        return is_portable(self.friction_class, self.fix_scope)

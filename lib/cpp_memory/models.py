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

    @property
    def actionable(self) -> bool:
        return is_actionable(self)


# --- learning -> GitHub issue bridge (#463) -------------------------------- #
# Only portable AND actionable learnings (they name a concrete fix) become
# tracked issues. The fingerprint is stamped into the issue body as an HTML
# comment so the bridge can dedup even before the learning's issue_url column
# is populated (search issues by marker). Never files non-portable learnings.
MARKER_PREFIX = "cpp-learning"


def issue_marker(fingerprint: str) -> str:
    """HTML-comment marker embedding a learning fingerprint in an issue body."""
    return f"<!-- {MARKER_PREFIX}: {fingerprint} -->"


def is_actionable(learning: Learning) -> bool:
    """True when a learning names a concrete fix worth tracking as an issue.

    Actionable == portable (shareable) AND carries a non-empty ``proposed_fix``.
    A pure "watch out for X" note with no fix is knowledge, not tracked work.
    """
    return learning.portable and bool((learning.proposed_fix or "").strip())


def should_file_issue(actionable: bool, existing_issue_url: str | None) -> bool:
    """Pure decision: file an issue only if actionable AND not already filed."""
    return actionable and not (existing_issue_url or "").strip()


def issue_body(learning: Learning, source_repo: str | None = None) -> str:
    """Render a GitHub issue body for an actionable learning (with dedup marker)."""
    lines = [
        issue_marker(learning.fingerprint),
        "",
        "## Learning (auto-filed from the CPP friction retro)",
        "",
        (learning.body or "").strip() or learning.title.strip(),
        "",
        f"**Proposed fix:** {(learning.proposed_fix or '').strip()}",
        "",
        "## Provenance",
        f"- class: {learning.friction_class} / scope: {learning.fix_scope}",
        f"- confidence: {learning.confidence}",
        f"- fingerprint: {learning.fingerprint}",
    ]
    if source_repo:
        lines.append(f"- source repo: {source_repo}")
    lines += [
        "",
        "Filed by /self-improvement:retro via the learnings->issue bridge "
        "(claude-power-pack #463). See the common-memory ledger for context.",
    ]
    return "\n".join(lines)

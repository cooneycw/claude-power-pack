"""Pin: the residual-filing rule carries a SEVERITY gate, on BOTH surfaces (issue #714).

The completeness-ledger rule used to require every narrowing to ship a filed
issue, with no severity filter: "we deferred a security fix" and "we never
measured a thing" produced identical artifacts. In field use that bred a long
tail of third-generation issues whose error rate was measurably HIGHER than the
seeds the wave started from - each generation reasons about the previous agent's
work product rather than about the system. The worst case (aws-learn#838)
proposed a `service_healthy` compose dependency that would have deadlocked every
cold start; it even asked for a deadlock check and shipped anyway, because the
policy required a residual to be FILED, not to be VALIDATED.

The gate is stated twice by design - `wave.md` rules on it (orchestrator side)
and `register.md` is where a worker actually writes the `residual:` line - so the
regression this file exists to catch is ONE surface being updated while the other
silently keeps teaching the old rule. A worker obeys the page it was handed.

Deliberately tolerant of rewording, in the shape of
`test_wave_addressing_transport_opaque.py`:
  - no line numbers, no section scoping by heading, no required sentence
  - the gate must live in a block that also discusses residuals, and must name
    at least two of its four severity criteria plus at least one of the
    explicitly-not-issue-worthy examples - so connective prose can be rewritten
    freely and only REMOVING the rule fails
  - the retired unconditional form must not come back

`test_the_checks_can_actually_fail` mutation-proves the two checks against the
real documents, so a green run here means the assertions can distinguish a page
that carries the rule from one that does not - rather than passing because they
match something every markdown file happens to contain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Both surfaces of the residual rule: the orchestrator rules on it, the worker
# writes the line. Neither may drift from the other.
RESIDUAL_RULE_DOCS = [
    ROOT / ".claude" / "commands" / "flow" / "wave.md",
    ROOT / ".claude" / "commands" / "flow" / "register.md",
]

# The predicate's four criteria - "a consequence someone would notice". Matched
# as lowercase substrings; a doc must name at least MIN_CRITERIA of them so the
# wording of any single one stays free to change.
SEVERITY_CRITERIA = (
    "user-visible",
    "security",
    "data-loss",
    "blocked on",
)
MIN_CRITERIA = 2

# The other half of the gate: naming what does NOT earn a tracker entry on its
# own. Without these the rule reads as a filter with no examples, and every
# residual argues its way past it.
NOT_ISSUE_WORTHY = (
    "measure x",
    "annotate the files we excluded",
    "tighten a coupling",
)

# The retired unconditional form. Covers both the orchestrator's "any narrowing
# must ship a filed issue for the residual" and register.md's restatement
# ("wave.md requires any narrowing to ship a filed issue BEFORE approval").
RETIRED_UNCONDITIONAL = "ship a filed issue"


def _blocks(text: str) -> list[str]:
    """Blank-line-separated blocks, lowercased. A markdown bullet LIST is one block."""
    return [block.lower() for block in text.split("\n\n") if block.strip()]


def _gate_findings(text: str) -> list[str]:
    """Empty list = the severity gate is present and stated where residuals are.

    A pure function of the text so the mutation test below can prove it fires.
    """
    findings: list[str] = []

    if RETIRED_UNCONDITIONAL in text.lower():
        findings.append(
            f"the retired unconditional form is back ({RETIRED_UNCONDITIONAL!r}): filing is a "
            f"severity call under #714, not the automatic consequence of declaring a residual"
        )

    qualifying = [
        block
        for block in _blocks(text)
        if "residual" in block
        and sum(criterion in block for criterion in SEVERITY_CRITERIA) >= MIN_CRITERIA
        and any(example in block for example in NOT_ISSUE_WORTHY)
    ]
    if not qualifying:
        findings.append(
            f"no block discusses residuals AND names >={MIN_CRITERIA} of the severity criteria "
            f"{list(SEVERITY_CRITERIA)} AND names one of the not-issue-worthy examples "
            f"{list(NOT_ISSUE_WORTHY)}"
        )
    return findings


@pytest.mark.parametrize("doc", RESIDUAL_RULE_DOCS, ids=lambda p: p.name)
def test_doc_states_the_residual_severity_gate(doc: Path) -> None:
    """Both surfaces carry the gate, or a worker obeys whichever page it was handed."""
    findings = _gate_findings(doc.read_text(encoding="utf-8"))
    assert not findings, (
        f"{doc.relative_to(ROOT)} no longer states the #714 residual severity gate:\n  - "
        + "\n  - ".join(findings)
        + "\n\nThe rule: a residual is always DECLARED, but it earns a filed issue only when it "
        "names a consequence someone would notice. Both wave.md and register.md must say so - "
        "updating one and leaving the other is the drift this test exists to catch. If you "
        "reworded rather than removed, keep >= "
        f"{MIN_CRITERIA} criteria and one example in the block that discusses residuals, or "
        "update the token lists here."
    )


@pytest.mark.parametrize("doc", RESIDUAL_RULE_DOCS, ids=lambda p: p.name)
def test_doc_keeps_declaration_mandatory(doc: Path) -> None:
    """#714 changed a low-severity residual's DESTINATION, never whether it is declared.

    The anti-silence property is the whole reason the ledger exists; a rewrite
    that drops `residual:` from the required sections would trade one failure for
    a worse one.
    """
    text = doc.read_text(encoding="utf-8").lower()
    assert "residual" in text and ("declared" in text or "required" in text), (
        f"{doc.relative_to(ROOT)} no longer states that a residual must be declared. #714 "
        f"loosened where a residual GOES, not whether it is recorded - silent narrowing is the "
        f"failure the completeness ledger was built for."
    )


def test_the_checks_can_actually_fail() -> None:
    """Mutation-prove both checks against the real documents.

    A guard is only worth its green run if it has been shown to go red. Each
    mutation below is the actual regression: the rule deleted, and the retired
    unconditional sentence restored.
    """
    wave = (ROOT / ".claude" / "commands" / "flow" / "wave.md").read_text(encoding="utf-8")
    assert not _gate_findings(wave), "precondition: wave.md must currently PASS before mutating it"

    # Mutation 1 - the severity criteria are deleted (the rule is removed, the
    # word "residual" stays). Must be detected.
    stripped = "\n".join(
        line for line in wave.splitlines() if not any(c in line.lower() for c in SEVERITY_CRITERIA)
    )
    assert _gate_findings(stripped), (
        "removing every severity criterion from wave.md was NOT detected - the check cannot "
        "distinguish a page that states the gate from one that does not, so its passing run "
        "proves nothing (a guard that cannot fire)."
    )

    # Mutation 2 - the retired unconditional form is restored alongside the new
    # rule. Must be detected even though the severity block is still present.
    regressed = wave.replace(
        "every\n  residual is DECLARED before approval",
        "any\n  narrowing must ship a filed issue for the residual BEFORE approval",
    )
    assert regressed != wave, (
        "the declaration sentence this mutation rewrites is gone from wave.md - update the "
        "mutation so it still reproduces the pre-#714 wording, rather than deleting this check"
    )
    assert _gate_findings(regressed), (
        "restoring the pre-#714 unconditional 'must ship a filed issue' wording was NOT "
        f"detected - {RETIRED_UNCONDITIONAL!r} is the sentence the field failure was produced by."
    )

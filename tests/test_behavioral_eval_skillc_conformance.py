"""Conformance: does `_validate_bundle` still agree with skillc, not just with
itself? (issue #1369, gap raised by cpp-orch 2026-10-06)

`scripts/check-behavioral-eval.py` restates a MINIMAL subset of skillc's
`ledger-binding`/`unique-ids`/`attempt-accounting`/`lineage` bundle rules by
hand rather than importing skillc's own `records.py`/`checks.py` (owner
ruling: no skillc runtime import in CPP CI). A hand-restatement's own tests
can only prove it agrees with ITSELF - they were written from the same
understanding of the rule the restatement encodes, so they cannot catch the
restatement drifting from what skillc actually enforces. Only skillc's OWN
golden fixtures, read by CPP's restated reader, can show that.

`controls/behavioral-eval/skillc-conformance/` holds every `*.json` from
skillc's `controls/{ledger-binding,unique-ids,attempt-accounting,lineage}/
{good,bad}/*` at commit 2202603, copied verbatim (see its `PROVENANCE.md`).
This file classifies every one of them, by hand, into:

- a GOOD case: `_validate_bundle` must report no finding. True for every
  skillc-labelled good case, regardless of which rules CPP restates -
  restating a NARROWER set of rules can never turn a clean bundle unclean,
  so any finding here is a false positive in CPP's own restatement.
- a BAD case CPP's restated subset actually reaches (`FLAGGED_BAD`):
  `_validate_bundle` must report at least one finding. Several of these are
  caught by a DIFFERENT restated check than the one skillc names for the
  fixture (the detail string says which) - that is still agreement that the
  bundle is invalid, not a claim that CPP implements skillc's own diagnosis.
- a BAD case outside the restated subset (`OUT_OF_SUBSET_BAD`): `
  _validate_bundle` reports NOTHING, named explicitly here with the specific
  skillc behaviour CPP does not restate. This is the discipline the owner's
  gap asked for: "list it explicitly as out-of-subset ... rather than
  silently skipping it."

Building this classification against real fixtures (not invented ones)
found two genuine bugs before they shipped, fixed in the same change that
adds this file: `_validate_bundle` did not include `skill-evidence` in its
one-record-per-attempt uniqueness check, and had no exemption for
`reconciliation: unmatched, reason: no-correlating-attempt` (skillc's own
`ledger-binding/good/skill-evidence-no-correlating-attempt` exists
specifically to prove that state is not an altered artifact).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check-behavioral-eval.py"
CONFORMANCE = ROOT / "controls" / "behavioral-eval" / "skillc-conformance"


def _load():
    spec = importlib.util.spec_from_file_location("check_behavioral_eval_conformance", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()

#: Every skillc-labelled GOOD case under the four families. `_validate_bundle`
#: must report no finding on every one, regardless of subset membership.
GOOD_CASES = (
    "attempt-accounting/good/agent-observation-stands-in",
    "attempt-accounting/good/complete",
    "attempt-accounting/good/inconclusive-needs-no-result",
    "attempt-accounting/good/not-run-needs-no-evidence",
    "ledger-binding/good/complete",
    "ledger-binding/good/pilot-report-complete",
    "ledger-binding/good/skill-evidence-complete",
    "ledger-binding/good/skill-evidence-contradiction-witnessed",
    "ledger-binding/good/skill-evidence-duplicate-invocation",
    "ledger-binding/good/skill-evidence-no-correlating-attempt",
    "ledger-binding/good/skill-evidence-obligation-failure",
    "ledger-binding/good/skill-evidence-stale-identity",
    "ledger-binding/good/skill-invocation-installed",
    "ledger-binding/good/skill-invocations-complete-coverage",
    "ledger-binding/good/skill-invocations-declared",
    "ledger-binding/good/two-trials",
    "lineage/good/regrade-retained",
    "lineage/good/retry-linked",
    "unique-ids/good/complete",
)

#: skillc-labelled BAD cases CPP's restated subset actually reaches.
#: `_validate_bundle` must report at least one finding on every one.
FLAGGED_BAD_CASES = (
    "attempt-accounting/bad/no-lifecycle",
    "ledger-binding/bad/altered-artifact",
    "ledger-binding/bad/cross-trial",
    "ledger-binding/bad/skill-evidence-altered-artifact",
    "ledger-binding/bad/skill-evidence-altered-artifact-contradicting",
    "ledger-binding/bad/skill-evidence-duplicate-invocation-uncaptured",
    "ledger-binding/bad/unknown-attempt",
    "ledger-binding/bad/unplanned-grader",
    "lineage/bad/regrade-erased-original",
    "lineage/bad/regrade-other-bytes",
    "unique-ids/bad/conflicting-receipts",
    "unique-ids/bad/duplicate-attempt",
    "unique-ids/bad/duplicate-result-id",
    "unique-ids/bad/skill-evidence-duplicate",
    "unique-ids/bad/unlinked-second-result",
)

#: skillc-labelled BAD cases OUTSIDE CPP's restated subset, named with the
#: specific skillc rule content CPP does not restate. `_validate_bundle`
#: reports NOTHING on every one of these - documented, not silently skipped.
OUT_OF_SUBSET_BAD_CASES: dict[str, str] = {
    "attempt-accounting/bad/captured-but-declared-not-run":
        "disposition-vs-declared-run_state consistency is not restated",
    "attempt-accounting/bad/graded-but-not-captured":
        "disposition-vs-graded consistency is not restated",
    "attempt-accounting/bad/graded-without-manifest":
        "'graded requires a manifest' is not restated",
    "attempt-accounting/bad/graded-without-receipt":
        "'graded requires a receipt' is not restated",
    "attempt-accounting/bad/manifest-but-not-captured":
        "disposition-vs-manifest consistency is not restated",
    "attempt-accounting/bad/stand-in-claims-readiness":
        "the agent-observation receipt stand-in (#139) is not restated",
    "attempt-accounting/bad/stand-in-optional-readiness":
        "the agent-observation receipt stand-in (#139) is not restated",
    "attempt-accounting/bad/stand-in-with-receipt-claims-readiness":
        "the agent-observation receipt stand-in (#139) is not restated",
    "attempt-accounting/bad/stand-in-without-observation":
        "the agent-observation receipt stand-in (#139) is not restated",
    "attempt-accounting/bad/unaccounted-attempt":
        "disposition-vs-capture-state consistency for an attempt is not restated",
    "ledger-binding/bad/pilot-report-missing-attempt":
        "pilot-report accounting is not restated",
    "ledger-binding/bad/skill-evidence-duplicate-invocation-mislabeled":
        "reason-text correctness (is 'duplicate-invocation' actually true?) is not restated",
    "ledger-binding/bad/skill-evidence-forged-status":
        "criteria_owned vs the attempt's own verified-result is not restated",
    "ledger-binding/bad/skill-evidence-gate-reason-cites-receipt":
        "witness_ref validation is not restated",
    "ledger-binding/bad/skill-evidence-no-correlating-attempt-mislabeled":
        "reason-text correctness (is 'no-correlating-attempt' actually true?) is not restated",
    "ledger-binding/bad/skill-evidence-not-installed":
        "skill.path vs the receipt's own installed paths is not restated",
    "ledger-binding/bad/skill-evidence-stale-identity-wrong-witness":
        "witness_ref validation is not restated",
    "ledger-binding/bad/skill-evidence-undeclared-source":
        "external_evidence_sources declaration is not restated",
    "ledger-binding/bad/skill-evidence-unknown-criterion":
        "criteria_owned vocabulary is not restated",
    "ledger-binding/bad/skill-evidence-unwitnessed-contradiction":
        "a gate-witness requirement on 'contradicting' is not restated by `_validate_bundle` - "
        "R15 instead has `_evaluate_skill_evidence` distrust EVERY 'contradicting' "
        "unconditionally, a different mechanism with the same non-pass outcome end-to-end",
    "ledger-binding/bad/skill-invocation-not-installed":
        "skill-invocations binding is not restated",
    "ledger-binding/bad/skill-invocations-incomplete-coverage":
        "skill-invocations binding is not restated",
    "ledger-binding/bad/skill-invocations-required-but-absent":
        "skill-invocations binding is not restated",
    "ledger-binding/bad/stale-receipt":
        "receipt-vs-trial-plan consistency (subject.digest, client) is not restated - "
        "'ledger/manifest/result binding' (#1369 acceptance item 1) does not name receipts",
    "lineage/bad/regrade-cycle":
        "a MULTI-node regrade cycle is not detected - only a regrade naming itself, "
        "or an original not retained in the bundle, is",
    "lineage/bad/retry-cycle":
        "attempt-level retry_of is out of scope of this minimal subset entirely",
    "lineage/bad/retry-reuses-id":
        "attempt-level retry_of is out of scope of this minimal subset entirely",
}


def _findings(case: str) -> list[str]:
    by_kind, skipped = mod._bundle_records(CONFORMANCE / case)
    return skipped + mod._validate_bundle(by_kind)


@pytest.mark.parametrize("case", GOOD_CASES)
def test_a_skillc_good_case_is_never_a_false_positive(case: str) -> None:
    findings = _findings(case)
    assert findings == [], f"{case}: restated subset wrongly flagged a skillc-good bundle: {findings}"


@pytest.mark.parametrize("case", FLAGGED_BAD_CASES)
def test_a_skillc_bad_case_in_the_restated_subset_is_caught(case: str) -> None:
    assert _findings(case), f"{case}: restated subset missed a skillc-bad bundle it should catch"


@pytest.mark.parametrize("case", sorted(OUT_OF_SUBSET_BAD_CASES))
def test_an_out_of_subset_skillc_bad_case_is_named_not_silently_passed(case: str) -> None:
    """Documents, rather than hides, what CPP's restatement does not cover.

    If this ever starts failing because `_validate_bundle` NOW catches one of
    these, that is progress, not a regression - move the case up to
    `FLAGGED_BAD_CASES` and delete its entry here instead of chasing the
    assertion back to green."""
    assert OUT_OF_SUBSET_BAD_CASES[case]  # the reason itself is the documentation
    findings = _findings(case)
    assert findings == [], (
        f"{case} is listed out-of-subset ({OUT_OF_SUBSET_BAD_CASES[case]!r}) but "
        f"_validate_bundle now reports {findings} - promote it to FLAGGED_BAD_CASES"
    )


def test_every_fixture_on_disk_is_classified_exactly_once() -> None:
    """The anti-silent-skip guard: every directory actually present under
    `skillc-conformance/` must appear in exactly one of the three lists
    above. A fixture added later and never classified would otherwise just
    never run - the same failure mode a missing case would have."""
    on_disk = sorted(
        f"{family.name}/{gb.name}/{case.name}"
        for family in CONFORMANCE.iterdir() if family.is_dir()
        for gb in family.iterdir() if gb.is_dir()
        for case in gb.iterdir() if case.is_dir()
    )
    classified = sorted({*GOOD_CASES, *FLAGGED_BAD_CASES, *OUT_OF_SUBSET_BAD_CASES})
    assert on_disk == classified, (
        f"on disk but unclassified: {sorted(set(on_disk) - set(classified))}; "
        f"classified but missing on disk: {sorted(set(classified) - set(on_disk))}"
    )


def test_the_classification_lists_do_not_overlap() -> None:
    good, flagged, out = set(GOOD_CASES), set(FLAGGED_BAD_CASES), set(OUT_OF_SUBSET_BAD_CASES)
    assert not (good & flagged)
    assert not (good & out)
    assert not (flagged & out)

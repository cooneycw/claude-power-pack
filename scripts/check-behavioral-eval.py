#!/usr/bin/env python3
"""Consume a behavioural-eval producer bundle and report (issues #1084, #1369).

THIS IS HALF A. It is the CONSUMER: given a verified-result artifact, does this
repository render a failure as a failure, a pass as a pass, a forged verdict as a
refusal, and an absent artifact as none of those? Half B - the behavioural case
that PRODUCES such an artifact - lives in skillc, never here (owner ruling, and
skillc ADR 0002's boundary).

ISSUE #1369 ADDS BUNDLE-AWARE READING, PER THE OWNER'S RULING ON THE #1369 PLAN
(cpp-eval mailbox 5223/5225, 2026-10-06). Before #1369, this gate read a lone
verified-result file and said so on every verdict: "checked alone - NOT against
any ledger" (R11, `.specify/specs/per-skill-audit/spec.md`). That claim is still
true when no bundle is declared - DEFAULT_DIR may still hold a bare verified-result
with nothing else beside it, and that is read exactly as before, unchanged. When a
`trial-ledger` record IS present alongside it (a real producer bundle: ledger,
manifest, receipt, lifecycle, result, optionally `skill-evidence`), the bundle's
own structural accounting is checked FIRST - R11's "a per-skill verdict counts only
when the whole producer bundle accounts for it" - before any result in it is
trusted. See `_validate_bundle`'s docstring for exactly which bundle rules are
restated and which are not.

NO SKILLC RUNTIME IMPORT. The owner ruled against vendoring skillc's own
`records`/`checks` modules for this (#1369's own completion evidence requires "NO
skillc runtime import ... in CPP CI"): the bundle rules below are RESTATED BY HAND,
the same discipline this file already applied to the record-level rules, cited to
skillc `docs/specs/evaluation-facility/records.md` at commit `2202603`. The
restated subset is deliberately narrow - exactly one trial ledger; every planned
attempt has a lifecycle (no orphan); no duplicate attempt/result IDs; a
`skill-evidence` artifact_ref resolves to exactly one manifest entry; a regrade's
lineage, when a result declares one. Everything else skillc's `ledger-binding`,
`unique-ids`, `attempt-accounting` and `lineage` bundle rules check - stale or
cross-trial receipts, `skill-invocations` binding, pilot-report accounting, forged
`criteria_owned` status, attempt-level `retry_of`, the agent-observation receipt
stand-in, and more - is NOT checked here. A bundle this gate accepts is checked
against this restated subset, never certified against skillc's full rule set. The
drift guard is CONFORMANCE, not import: the committed bundle controls are copied
from skillc's own golden good/bad fixtures, pinned to `2202603` with a provenance
note, so a later skillc rule change surfaces when someone re-pins and a case
disagrees - never silently.

WHAT A GREEN FROM THIS GATE MEANS, AND IT IS NARROWER THAN ITS NEIGHBOURS. It
means the CONSUMER read an artifact correctly. It says nothing whatever about any
behavioural case discriminating - there is no case yet. Its output sits in
`make verify` beside gates that DO carry behavioural meaning, and a reader
skimming cannot tell them apart, so every verdict this gate prints names the
population it examined and says plainly when that population is a fixture.

#1084's constraint is "do not gate on a suite that has not been shown to
discriminate". This gate does not gate on a suite at all. It gates on its own
reading, and its committed cases are what show that reading discriminates.

THE ARTIFACT'S SHAPE IS OWNED ELSEWHERE, AND `status` IS DERIVED, NOT READ.
skillc owns the verified-result contract (`docs/specs/evaluation-facility/
records.md`). This consumer reads VERSION 2, as fixed by skillc PR #32 (commit
c37c991, closing skillc #4) and checked against skillc 3c243a1. Version 2 refuses
version 1 outright - "it predates producer authority and ledger binding" - so a
consumer still reading v1 would have refused the first real record skillc ever
emitted, as "newer than supported". That is the defect this revision fixes, and
the rules below are RESTATED from skillc by hand, because CPP's CI has no skillc
to import. When skillc moves to version 3 this file drifts again, silently, until
someone compares it; the pin above is what makes that comparison possible.

WHAT IS CHECKED, AND WHAT CANNOT BE FROM HERE. skillc splits its rules into
RECORD rules and BUNDLE rules. The record rules for a verified result are applied
here: envelope version, kind, producer authority (only `assembler`), identifier
shape, grader identity, `graded_digests` unless a run state is declared, evidence
on every SATISFIED/VIOLATED criterion, `missing` on every UNKNOWN one, a reason on
a declared run state, a digest on any `raw` reference, and the derived status. The
BUNDLE rules - ledger-binding, unique-ids, attempt-accounting, lineage - need the
trial ledger and the artifact manifest beside the result. Before #1369 this gate
always read results alone, and every verdict said so - skillc's own words for
the same position: a PASS here cannot show that the result graded the artifact
its attempt captured, or that the attempt was ever planned. #1369 makes that
conditional on what is actually there: a candidate directory with no trial
ledger is STILL read alone, same claim, same wording; one WITH a ledger has its
restated bundle-rule subset checked first (`_validate_bundle`), so a PASS from
that path can additionally show the result's attempt was ledger-planned and
accounted for - never skillc's full bundle-rule set, which this gate does not
import and does not claim to enforce.
And `producer: assembler` is a declared field, so it refuses a subject that says
it wrote its own verdict and cannot refuse one that lies about it - skillc says
the same, and authentication belongs to its trusted controller.

THE BUNDLE LAYOUT, DECIDED BY #1369 (owner ruling, 2026-10-06): one bundle per
IMMEDIATE SUBDIRECTORY of the directory this gate reads - never a flat glob of
every `*.json` the directory holds. A flat glob cannot tell two runs' records
apart, and skillc's own bundle rules assume exactly one trial ledger; conflating
two runs' files would violate that the moment a second bundle ever lands. Today
`docs/measurements/behavioral-eval/` is a 404, so there is no migration (nothing
produces a bundle yet - the runner is still skillc #8). `evaluate()` treats the
directory it is given AND each of its immediate subdirectories as independent
candidate populations, in sorted order, stopping at the first one that is not
clean - this is also how a lone verified-result with nothing beside it keeps
working exactly as before: a candidate directory with no `trial-ledger` record in
it is read exactly as this gate always has, never gated on bundle completeness.

That spec makes `status` a DERIVED
field and refuses "a record whose `status` does not follow from its own
`criteria`" - the forged verdict, a status copied from a subject rather than
computed from evidence. A consumer that trusted the declared `status` would
launder exactly that forgery, so this gate RE-DERIVES the status from the
criteria and refuses any record where the two disagree.

Its derivation is the spec's, in the order the spec binds it: a declared
`UNAVAILABLE`/`NOT_RUN` run state is honoured; a `VIOLATED` mandatory criterion
yields `FAIL`, tested BEFORE unknowns; any other non-`SATISFIED` mandatory
criterion yields `INCONCLUSIVE`; otherwise `PASS`. Optional criteria never enter
the computation, because "optional quality scores cannot average away mandatory
failures". NO MANDATORY CRITERIA YIELDS `INCONCLUSIVE`, NEVER `PASS`: an empty
population must not render as a clean one, which is this repository's own #1014
rule arriving inside someone else's record format.

EXIT CODES, AND THE ONE RULE THEY OBEY
--------------------------------------
`scripts/gate-lib.sh` states the rule this gate follows: EXACTLY ONE VERDICT MAPS
TO EXIT 0, which is "an unknowable answer is never rendered as a clean one"
(#1014, #800) expressed in exit codes. gate-lib ENFORCES that at runtime for SHELL
gates. This gate is Python and inherits none of that enforcement, so the rule is
restated here and tested in `tests/test_behavioral_eval.py` - imitating a
library's discipline without its mechanism is how the discipline quietly stops
applying, and anyone who recognises these codes will otherwise assume gate-lib is
covering it.
"""

#: NEGATIVE-CONTROL: controls/behavioral-eval
#:
#: This gate lets work THROUGH - its verdict is read by a human scanning `make
#: verify` output and by nothing that re-derives it. A blind version would print a
#: confident `pass` over an artifact recording FAIL, which is indistinguishable
#: from a working one on every run where no artifact exists at all - which today
#: is every run.
#:
#: The committed cases are the states the consumer must tell apart: a recorded
#: failure, a recorded pass, an absent artifact, an envelope version newer than
#: this build (refused rather than read on a guess), and two FORGED records whose
#: declared `status` does not follow from their own criteria - one asserting PASS
#: over a mandatory violation, one asserting PASS over no mandatory criteria at
#: all. The forged pair is the reason this gate re-derives rather than reads:
#: both are well-formed, both parse, and a consumer that trusted `status` would
#: report a clean pass over each.
#:
#: #1369 adds bundle cases: a bundle missing its ledger or an orphaned/duplicate
#: attempt (`bundle-invalid`), and a `matched` skill-evidence reconciliation
#: whose cited usage-record payload is itself unreadable (`evidence-unverified`,
#: R14) - states a lone-result reading cannot even see, because there was no
#: bundle to check them against.

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.cicd import evidence as _evidence  # noqa: E402

#: Where a producer would write its artifacts. Nothing writes here yet; see ABSENT.
#: #1369: one bundle per IMMEDIATE SUBDIRECTORY of this directory - see the
#: module docstring's "THE BUNDLE LAYOUT" paragraph.
DEFAULT_DIR = Path("docs/measurements/behavioral-eval")

#: The envelope versions this consumer reads - an EXACT set, not a ceiling, as in
#: skillc's `SUPPORTED_VERSIONS`. A number outside it is refused, never read on a
#: guess; version 1 is refused with its own reason, below.
SUPPORTED_VERSIONS = frozenset({2})

#: records.md: "Exactly one role is authorized per kind", and for a verified result
#: that role is the controller's result assembler. `producer: subject` is the
#: FORGED SUBJECT VERDICT - the thing being evaluated declaring its own success.
PRODUCER = "assembler"

#: records.md's identifier shape: IDs reach file names and log lines.
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

#: The vocabularies records.md fixes. A value outside either is refused rather
#: than bucketed into the nearest one this gate happens to understand.
OUTCOMES = frozenset({"SATISFIED", "VIOLATED", "UNKNOWN"})
STATUSES = frozenset({"PASS", "FAIL", "UNAVAILABLE", "INCONCLUSIVE", "NOT_RUN"})

#: The only record kind this consumer may read. Counter-model review found that
#: without this, an `artifact-manifest` was read as a verified-result and reported
#: `pass` - a verdict about a population the record was never part of.
KIND = "verified-result"

#: "only `UNAVAILABLE` or `NOT_RUN` may be declared. The other three statuses are
#: derived and may not be asserted - otherwise the forged verdict simply moves
#: from `status` into `run_state`."
DECLARABLE_RUN_STATES = frozenset({"UNAVAILABLE", "NOT_RUN"})

#: #1369: the other record kinds a bundle may carry beside its verified-result(s).
#: skillc `docs/specs/evaluation-facility/records.md` at commit 2202603.
TRIAL_LEDGER = "trial-ledger"
ARTIFACT_MANIFEST = "artifact-manifest"
INSTALLATION_RECEIPT = "installation-receipt"
ATTEMPT_LIFECYCLE = "attempt-lifecycle"
SKILL_EVIDENCE = "skill-evidence"

#: records.md:120 (skillc 2202603) - R9's four reconciliation states.
RECONCILIATION_STATES = frozenset({"absent", "unmatched", "matched", "contradicting"})

#: THE VERDICT MAP. Exactly one entry maps to 0. A test asserts that property
#: rather than trusting this comment, because a comment cannot fail.
#:
#: `inconclusive` is deliberately NOT folded into `failure`: the spec fixes five
#: statuses and three of them mean "this did not establish anything". Reporting
#: those as a failure would be a different wrong answer, not a safer one - but
#: they must still never be 0, which is why they have a code of their own.
#:
#: `bundle-invalid` and `evidence-unverified` are #1369's additions - states a
#: lone-result reading could never see, because there was no bundle to check
#: them against. Neither is 0, for the same reason none of the others are.
VERDICTS: dict[str, int] = {
    "pass": 0,
    "failure": 1,
    "absent": 2,
    "unreadable": 3,
    "forged": 4,
    "inconclusive": 5,
    "bundle-invalid": 6,
    "evidence-unverified": 7,
}

#: Cited by every verdict. A reader of `make verify` output sees this line beside
#: gates whose greens mean something entirely different. #1369: this is now true
#: in BOTH modes - a candidate with no trial ledger is still "checked alone,"
#: exactly as before; one with a ledger has its restated bundle-rule subset
#: checked (never skillc's full rule set, which this gate does not import).
POPULATION_NOTE = (
    "examined: a verified-result artifact's own fields, and - only when a "
    "trial-ledger record is declared beside it - the restated bundle-rule subset "
    "#1369 checks (never skillc's full ledger-binding/unique-ids/"
    "attempt-accounting/lineage rule set, which this gate does not import). "
    "Without a declared ledger, this is checked alone - NOT against any ledger - "
    "exactly as before #1369. It does not run a behavioural case and establishes "
    "nothing about one discriminating."
)

#: ABSENT names its blocker SPECIFICALLY, so a reader in three months can check
#: whether it still stands. "when a producer exists" would be unfalsifiable by the
#: person reading it, and that is how a permanently-absent line becomes furniture.
ABSENT_NOTE = (
    "no verified-result artifact and no bundle subdirectory holding one. Nothing "
    "produces either yet: the behavioural case is CPP #1084 half B, which lives in "
    "skillc. skillc #5 (the first goal and a grader proven to discriminate) landed "
    "2026-09-26; no model trial has run, because the runner and independent grading "
    "are skillc #8, #9 and #10. Check those three before assuming this line is "
    "still expected."
)


#: argparse exits 2 on a usage error, which is this gate's `absent` code - so a
#: mistyped flag would have been indistinguishable from "no artifact was found".
#: gate-lib reserves 64 for usage and forbids it mapping to the good exit; this
#: gate is Python and inherits neither, so it borrows the number deliberately.
USAGE_EXIT = 64


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"behavioral-eval: usage - {message}", file=sys.stderr)
        raise SystemExit(USAGE_EXIT)


def _member(value: object, vocabulary: frozenset[str]) -> bool:
    """Membership that survives an unhashable value.

    `[] in frozenset(...)` raises `TypeError: unhashable type`, and JSON permits
    `"status": []`. Counter-model review found the bare `in` crashing on exactly
    that: the traceback exited 1, which is this gate's `failure` code, so
    malformed input was reported as a producer's recorded failure - with no
    verdict line and no population note printed at all. A crash that renders as a
    confident wrong answer is worse than one that renders as noise.
    """
    return isinstance(value, str) and value in vocabulary


def _say(verdict: str, detail: str) -> int:
    print(f"behavioral-eval: {verdict} - {detail}")
    print(f"behavioral-eval: {POPULATION_NOTE}")
    return VERDICTS[verdict]


def derive_status(criteria: list[dict], run_state: object) -> str | None:
    """records.md's derivation. `None` means the record forged its own run state.

    The step order is load-bearing and is the spec's: "an established mandatory
    violation remains FAIL when another criterion is unknown", so VIOLATED is
    tested BEFORE unknowns. Swapping them turns an established failure into an
    inconclusive, which is the softer and wronger answer.
    """
    if run_state is not None:
        if not _member(run_state, DECLARABLE_RUN_STATES):
            return None
        return str(run_state)

    mandatory = [c for c in criteria if c["mandatory"] is True]
    if any(c.get("outcome") == "VIOLATED" for c in mandatory):
        return "FAIL"
    if not mandatory:
        # "No mandatory criteria yields INCONCLUSIVE, never PASS."
        return "INCONCLUSIVE"
    if any(c.get("outcome") != "SATISFIED" for c in mandatory):
        return "INCONCLUSIVE"
    return "PASS"


def _read_record(path: Path) -> tuple[str, str] | dict:
    """A parsed record, or a terminal (verdict, detail) refusing it."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "unreadable", f"{path.name} could not be read ({exc})"
    if not isinstance(raw, dict):
        return "unreadable", f"{path.name} is not a JSON object"

    version = raw.get("version")
    # bool is a subclass of int: `"version": true` would otherwise read as 1.
    if isinstance(version, bool) or not isinstance(version, int):
        return "unreadable", (
            f"{path.name} declares envelope version {version!r}, not an integer"
        )
    if version == 1:
        return "unreadable", (
            f"{path.name} declares envelope version 1, which predates producer "
            f"authority and ledger binding; this build reads only "
            f"{sorted(SUPPORTED_VERSIONS)} and skillc defines no migration"
        )
    if version not in SUPPORTED_VERSIONS:
        return "unreadable", (
            f"{path.name} declares version {version}, not one this build reads "
            f"({sorted(SUPPORTED_VERSIONS)}); refused rather than read on a guess"
        )

    kind = raw.get("kind")
    if kind != KIND:
        return "unreadable", (
            f"{path.name} declares kind {kind!r}, not {KIND!r}; refused rather than "
            f"read as a verified-result it never claimed to be"
        )

    producer = raw.get("producer")
    if producer != PRODUCER:
        return "forged", (
            f"{path.name} declares producer {producer!r}; only {PRODUCER!r} may "
            f"produce a verified-result. A subject-authored verdict is the forged "
            f"subject verdict, however consistent its criteria are"
        )

    status = raw.get("status")
    if not _member(status, STATUSES):
        return "unreadable", (
            f"{path.name} records status {status!r}, outside the vocabulary "
            f"{sorted(STATUSES)}"
        )

    run_state = raw.get("run_state")
    if run_state is not None and not isinstance(run_state, str):
        return "unreadable", (
            f"{path.name} records a non-string run_state {run_state!r}"
        )

    criteria = raw.get("criteria")
    if not isinstance(criteria, list):
        return "unreadable", f"{path.name} records no criteria list"
    for entry in criteria:
        if not isinstance(entry, dict):
            return "unreadable", f"{path.name} carries a criterion that is not an object"
        # `mandatory` MUST be a real boolean. Counter-model review found the string
        # "true" silently excluding a VIOLATED criterion from the derivation - the
        # record then derived PASS, matched its declared PASS, and reported clean.
        # One malformed flag defeated the entire forged-verdict defence, and did it
        # by making evidence DISAPPEAR rather than by contradicting anything.
        if not isinstance(entry.get("mandatory"), bool):
            return "unreadable", (
                f"{path.name} carries a criterion whose `mandatory` is "
                f"{entry.get('mandatory')!r}, not a boolean; a non-boolean would be "
                f"silently treated as optional and drop out of the derivation"
            )
        if not _member(entry.get("outcome"), OUTCOMES):
            return "unreadable", (
                f"{path.name} carries a criterion outside the outcome vocabulary "
                f"{sorted(OUTCOMES)}"
            )

    problem = _contract_problem(raw)
    if problem:
        return "unreadable", f"{path.name} breaks the version-2 result contract: {problem}"
    return raw


def _nonempty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _str_list(value: object) -> bool:
    """A NON-EMPTY list of non-blank strings. `[""]` names no reference at all."""
    return isinstance(value, list) and bool(value) and all(_nonempty_str(v) for v in value)


def _contract_problem(raw: dict) -> str | None:
    """skillc's record rules for a verified result, beyond vocabulary and status.

    Restated from skillc `records.py` (`record_envelope`'s raw rule,
    `attempt_binding`, `result_evidence`) at 3c243a1. The one that matters most is
    evidence: a mandatory SATISFIED criterion with no evidence would otherwise
    derive PASS, which records.md names "missing mandatory evidence".
    """
    for key in ("result_id", "attempt_id", "trial_id"):
        value = raw.get(key)
        if not isinstance(value, str) or not ID_RE.fullmatch(value):
            return f"{key} {value!r} is missing or malformed"
    grader = raw.get("grader")
    if not isinstance(grader, dict) or not all(
        _nonempty_str(grader.get(k)) for k in ("id", "revision")
    ):
        return "no grader identity (id and revision)"
    if "raw" in raw:
        ref = raw["raw"]
        if not isinstance(ref, dict) or not _nonempty_str(ref.get("ref")) \
                or not _nonempty_str(ref.get("digest")):
            return "raw backend data is carried without a ref and digest"
    run_state = raw.get("run_state")
    if run_state is not None:
        if not _nonempty_str(raw.get("reason")):
            return f"run state {run_state!r} is declared without a reason"
    elif not _str_list(raw.get("graded_digests")):
        return "no graded_digests; the result does not say which artifact it graded"
    for entry in raw["criteria"]:
        outcome = entry["outcome"]
        if outcome in ("SATISFIED", "VIOLATED") and not _str_list(entry.get("evidence")):
            return f"criterion {entry.get('id')!r} reports {outcome} with no evidence"
        if outcome == "UNKNOWN" and not _nonempty_str(entry.get("missing")):
            return f"criterion {entry.get('id')!r} is UNKNOWN without naming what is missing"
    return None


def _judge_result(path: Path) -> tuple[str, str] | None:
    """One verified-result file's verdict, or `None` when it is a clean PASS.

    Extracted unchanged from pre-#1369's `evaluate()` loop body, so a lone
    reading and a bundle reading judge a result identically - #1369 adds a
    gate IN FRONT of this, never a second derivation beside it."""
    record = _read_record(path)
    if isinstance(record, tuple):
        return record

    declared = record["status"]
    derived = derive_status(record["criteria"], record.get("run_state"))

    if derived is None:
        return "forged", (
            f"{path.name} declares run_state {record.get('run_state')!r}, which "
            f"the record format does not permit a producer to assert - the "
            f"forgery moves out of status rather than disappearing"
        )
    if declared != derived:
        return "forged", (
            f"{path.name} declares status {declared!r} but its own criteria "
            f"derive {derived!r}. Refused: a status copied from a subject rather "
            f"than computed from evidence is the forged verdict records.md "
            f"exists to refuse, and it is well-formed, so only re-derivation "
            f"catches it."
        )
    if declared == "FAIL":
        return "failure", (
            f"{path.name} records {declared!r}, derived from its own criteria. A "
            f"producer's failure is rendered here as a failure, which is the "
            f"property this gate exists to have."
        )
    if declared != "PASS":
        return "inconclusive", (
            f"{path.name} records {declared!r}, derived from its own criteria. "
            f"That establishes nothing, so it is not reported as clean."
        )
    return None


def _evaluate_lone_results(directory: Path) -> tuple[str, str]:
    """Pre-#1369's whole `evaluate()` body, verbatim behaviour: every `*.json`
    directly in `directory`, read and judged with no bundle context at all.
    Used both for a legacy/bare result and for `evaluate()`'s own directory
    argument when it holds no `trial-ledger` of its own."""
    artifacts = sorted(directory.glob("*.json"))
    if not artifacts:
        return "absent", ABSENT_NOTE
    for path in artifacts:
        verdict = _judge_result(path)
        if verdict is not None:
            return verdict
    names = ", ".join(p.name for p in artifacts)
    return "pass", (
        f"{len(artifacts)} artifact(s) declare PASS and re-derive to PASS from "
        f"their own criteria: {names}"
    )


def _bundle_records(pop_dir: Path) -> tuple[dict[str, list[tuple[Path, dict]]], list[str]]:
    """Every `*.json` directly in `pop_dir`, grouped by declared `kind` - a
    best-effort pre-scan used only to decide which reading applies and, in
    bundle mode, to run `_validate_bundle`. It is NEVER the source of truth
    for an `unreadable` verdict on a lone result: that stays `_judge_result`'s
    job via `_read_record`, untouched by #1369."""
    by_kind: dict[str, list[tuple[Path, dict]]] = {}
    skipped: list[str] = []
    for path in sorted(pop_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            skipped.append(f"{path.name} could not be parsed ({exc})")
            continue
        if not isinstance(raw, dict):
            skipped.append(f"{path.name} is not a JSON object")
            continue
        kind = raw.get("kind")
        by_kind.setdefault(kind if isinstance(kind, str) else "", []).append((path, raw))
    return by_kind, skipped


def _validate_bundle(by_kind: dict[str, list[tuple[Path, dict]]]) -> list[str]:
    """Restates the MINIMAL subset of skillc's bundle rules #1369 needs, by
    hand - the owner ruled against vendoring skillc's `records`/`checks`
    modules for this (#1369's completion evidence: "NO skillc runtime import
    ... in CPP CI"; cpp-eval mailbox 5225, 2026-10-06). Cited to skillc
    `docs/specs/evaluation-facility/records.md` at commit `2202603`.

    Restated: exactly one trial ledger issues attempt IDs (records.md:860);
    no attempt/result ID is planned or used twice (unique-ids, records.md:
    891-898); every planned attempt has an attempt-lifecycle record, so it
    cannot silently drop out (attempt-accounting's minimal half, records.md:
    900-903); every attempt-bound record cites an attempt the ledger actually
    issued (ledger-binding's minimal half, records.md:862); a regrade links
    to a retained original for the same attempt and the same graded_digests
    (lineage, scoped to results only - "only if a result depends on it" -
    records.md:925-931); and a `skill-evidence` entry's `artifact_ref`
    resolves to exactly one entry in that same attempt's own
    artifact-manifest (records.md:470, 885-889).

    NOT restated, and therefore NOT checked by this function: stale or
    cross-trial receipts, `skill-invocations`/pilot-report binding, forged
    `criteria_owned` status, attempt-level `retry_of`, the
    agent-observation receipt stand-in, and every other clause of skillc's
    four bundle rules. A bundle with no finding here is checked against this
    restated subset, never certified against skillc's full rule set.
    """
    findings: list[str] = []
    ledgers = by_kind.get(TRIAL_LEDGER, [])
    if len(ledgers) != 1:
        return [
            f"bundle holds {len(ledgers)} trial ledger(s); exactly one issues its "
            f"attempt IDs (records.md:860)"
        ]
    _ledger_path, ledger = ledgers[0]

    planned: dict[str, dict] = {}
    duplicate_planned: set[str] = set()
    trials = ledger.get("trials")
    for trial in trials if isinstance(trials, list) else []:
        if not isinstance(trial, dict):
            continue
        attempts = trial.get("attempts")
        for attempt in attempts if isinstance(attempts, list) else []:
            if not isinstance(attempt, dict):
                continue
            aid = attempt.get("attempt_id")
            if not isinstance(aid, str):
                continue
            if aid in planned:
                duplicate_planned.add(aid)
            planned[aid] = attempt
    for aid in sorted(duplicate_planned):
        findings.append(f"ledger plans attempt_id {aid!r} more than once (records.md:894)")
    if not planned:
        findings.append("the ledger plans no attempts, so there is nothing to account for (records.md:900)")
        return findings

    def _paths_by_attempt(kind: str) -> dict[str, list[Path]]:
        out: dict[str, list[Path]] = {}
        for path, rec in by_kind.get(kind, []):
            aid = rec.get("attempt_id")
            if isinstance(aid, str):
                out.setdefault(aid, []).append(path)
        return out

    lifecycles = _paths_by_attempt(ATTEMPT_LIFECYCLE)
    manifests_by_attempt = _paths_by_attempt(ARTIFACT_MANIFEST)
    receipts_by_attempt = _paths_by_attempt(INSTALLATION_RECEIPT)

    for kind, per_attempt, label in (
        (ATTEMPT_LIFECYCLE, lifecycles, "attempt-lifecycle"),
        (ARTIFACT_MANIFEST, manifests_by_attempt, "artifact-manifest"),
        (INSTALLATION_RECEIPT, receipts_by_attempt, "installation-receipt"),
    ):
        for aid, paths in sorted(per_attempt.items()):
            if len(paths) > 1:
                findings.append(
                    f"{len(paths)} conflicting {label} records for attempt {aid!r} "
                    f"(records.md:895-897, unique-ids)"
                )

    # attempt-accounting's minimal half (records.md:900-903): no orphan dropout.
    for aid in sorted(planned):
        if aid not in lifecycles:
            findings.append(
                f"planned attempt {aid!r} has no attempt-lifecycle record; the "
                f"controller never accounted for it (records.md:903)"
            )

    # ledger-binding's minimal half (records.md:862): no orphan/unplanned attempt.
    results_by_attempt: dict[str, list[Path]] = {}
    for path, rec in by_kind.get(KIND, []):
        aid = rec.get("attempt_id")
        if isinstance(aid, str):
            results_by_attempt.setdefault(aid, []).append(path)
        else:
            findings.append(f"{path.name}: verified-result has no string attempt_id (records.md:862)")
    for label, per_attempt in (
        ("verified-result", results_by_attempt),
        ("artifact-manifest", manifests_by_attempt),
    ):
        for aid in sorted(per_attempt):
            if aid not in planned:
                findings.append(
                    f"{label} cites attempt {aid!r}, which the ledger never issued "
                    f"(records.md:862, ledger-binding)"
                )

    # unique-ids (records.md:898): at most one original result per attempt;
    # no duplicate result_id.
    originals: dict[str, int] = {}
    result_ids: dict[str, int] = {}
    for _path, rec in by_kind.get(KIND, []):
        aid = rec.get("attempt_id")
        if isinstance(aid, str) and "regrade_of" not in rec:
            originals[aid] = originals.get(aid, 0) + 1
        rid = rec.get("result_id")
        if isinstance(rid, str):
            result_ids[rid] = result_ids.get(rid, 0) + 1
    for aid, count in sorted(originals.items()):
        if count > 1:
            findings.append(
                f"{count} original results for attempt {aid!r}; a further result is a "
                f"regrade and says so, or it is a conflicting verdict (records.md:898)"
            )
    for rid, count in sorted(result_ids.items()):
        if count > 1:
            findings.append(f"result_id {rid!r} is used by {count} results (records.md:898, unique-ids)")

    # lineage, scoped to results only (records.md:925-931); attempt-level
    # retry_of is out of scope of this minimal subset.
    results_by_id = {
        rec.get("result_id"): rec for _p, rec in by_kind.get(KIND, [])
        if isinstance(rec.get("result_id"), str)
    }
    for path, rec in by_kind.get(KIND, []):
        regrade_of = rec.get("regrade_of")
        if regrade_of is None:
            continue
        original = results_by_id.get(regrade_of)
        if original is None or original is rec:
            findings.append(
                f"{path.name}: regrade links to {regrade_of!r}, which is not retained in "
                f"this bundle; a regrade never erases its original (records.md:930)"
            )
            continue
        if original.get("attempt_id") != rec.get("attempt_id"):
            findings.append(
                f"{path.name}: regrade is for attempt {rec.get('attempt_id')!r}, but its "
                f"original graded {original.get('attempt_id')!r} (records.md:930-931)"
            )
        def _digests(value: object) -> list[str]:
            return sorted(v for v in value if isinstance(v, str)) if isinstance(value, list) else []

        if _digests(rec.get("graded_digests")) != _digests(original.get("graded_digests")):
            findings.append(
                f"{path.name}: regrade graded different bytes from its original "
                f"(records.md:931, a regrade reads the unchanged original artifact)"
            )

    # artifact_ref (records.md:470, 885-889): a skill-evidence entry's
    # external_evidence.artifact_ref must resolve to exactly one entry in
    # that SAME attempt's own artifact-manifest.
    for path, rec in by_kind.get(SKILL_EVIDENCE, []):
        aid = rec.get("attempt_id")
        skills = rec.get("skills")
        for entry in skills if isinstance(skills, list) else []:
            if not isinstance(entry, dict):
                continue
            external = entry.get("external_evidence")
            if not isinstance(external, dict) or external.get("present") is not True:
                continue
            ref = external.get("artifact_ref")
            ref_path = ref.get("path") if isinstance(ref, dict) else None
            ref_digest = ref.get("digest") if isinstance(ref, dict) else None
            if not isinstance(ref_path, str) or not isinstance(ref_digest, str):
                findings.append(
                    f"{path.name}: external_evidence.artifact_ref is not a well-formed "
                    f"path/digest pair (records.md:470)"
                )
                continue
            matches = [
                a for mp, mrec in by_kind.get(ARTIFACT_MANIFEST, [])
                if mrec.get("attempt_id") == aid
                for a in (mrec.get("artifacts") or [])
                if isinstance(a, dict) and a.get("path") == ref_path and a.get("digest") == ref_digest
            ]
            if len(matches) != 1:
                findings.append(
                    f"{path.name}: artifact_ref (path={ref_path!r}, digest={ref_digest!r}) "
                    f"resolves to {len(matches)} entries in attempt {aid!r}'s own "
                    f"artifact-manifest, not exactly one (records.md:470, 885-889)"
                )
    return findings


def _evaluate_skill_evidence(pop_dir: Path, by_kind: dict[str, list[tuple[Path, dict]]]) -> tuple[str, str] | None:
    """R7/R9/R14/R15's skill-evidence usage-record binding (#268) - #1369's
    own job, distinct from `_validate_bundle`'s restated skillc rules above.

    `matched` is independently re-checked against the cited CPP usage-record
    BYTES (R14): skillc's `check-records` validates only the reference's
    shape, never decodes the `cpp.execution-evidence/v1` payload it names, so
    a genuinely malformed payload behind a correctly-shaped reference is
    invisible to skillc and stays this gate's problem. Freshness against the
    CURRENT checkout (R10) is NOT checked here - that is #1370's job.

    `contradicting` always renders as `unknown` (R15): #1369 does not run
    skillc's `check-records`, so it has no way to confirm a gate-witness
    citation itself, and therefore never trusts this state as evidence
    either way, by construction - a no-op once skillc enforces the witness
    requirement, and safe before that (R9's open gap, spec.md).

    Returns `None` when nothing here blocks continuing to the bundle's
    verified-result(s): `unmatched`/`absent` pass through unchanged, R9's
    whole point being that neither proves anything either way."""
    for path, rec in by_kind.get(SKILL_EVIDENCE, []):
        skills = rec.get("skills")
        for entry in skills if isinstance(skills, list) else []:
            if not isinstance(entry, dict):
                continue
            external = entry.get("external_evidence")
            if not isinstance(external, dict):
                continue
            reconciliation = external.get("reconciliation")
            skill_path = entry.get("skill", {}).get("path") if isinstance(entry.get("skill"), dict) else None
            if reconciliation == "contradicting":
                return "inconclusive", (
                    f"{path.name}: skill {skill_path!r} reconciliation is 'contradicting' "
                    f"({external.get('reason')!r}); rendered as unknown (R15) - #1369 cannot "
                    f"itself confirm a gate-witness citation, so this is never trusted as "
                    f"evidence either way"
                )
            if reconciliation != "matched":
                continue
            ref = external.get("artifact_ref")
            ref_path = ref.get("path") if isinstance(ref, dict) else None
            if not isinstance(ref_path, str):
                continue
            payload = pop_dir / ref_path
            verdict, reasons, _claim = _evidence.verify(payload, check_current=False)
            if verdict == _evidence.UNKNOWN:
                return "evidence-unverified", (
                    f"{path.name}: skill {skill_path!r} reconciliation is 'matched', but its "
                    f"cited usage-record payload {ref_path!r} is not itself readable as valid "
                    f"cpp.execution-evidence/v1 ({'; '.join(reasons)}); skillc's check-records "
                    f"validates only the reference's shape, never decodes the bytes (R14)"
                )
    return None


def _producer_reported_note(by_kind: dict[str, list[tuple[Path, dict]]]) -> str:
    """Names a file with no record `kind` but a `rows` list - the shape of
    skillc coverage.py's own `CoverageReport.to_json()` (#272) - as
    PRODUCER-REPORTED, explicitly. #1369 does not call coverage.py's
    statistics (the owner's Q4 ruling on the #1369 plan): such a file is
    never read for its contents and never affects this gate's verdict, but
    its presence is not silently dropped either."""
    hits = sorted(
        path.name for path, rec in by_kind.get("", [])
        if isinstance(rec.get("rows"), list)
    )
    if not hits:
        return ""
    return (
        f" [PRODUCER-REPORTED, not CPP-certified, not used in this verdict - cite CPP #1084: "
        f"{', '.join(hits)}]"
    )


def _evaluate_bundle_results(pop_dir: Path, by_kind: dict[str, list[tuple[Path, dict]]]) -> tuple[str, str]:
    results = by_kind.get(KIND, [])
    if not results:
        return "bundle-invalid", f"{pop_dir.name}: bundle has no verified-result record to read"
    for path, _rec in results:
        verdict = _judge_result(path)
        if verdict is not None:
            return verdict
    names = ", ".join(path.name for path, _rec in results)
    return "pass", (
        f"{pop_dir.name}: bundle valid against the restated subset; {len(results)} "
        f"verified-result record(s) declare PASS and re-derive to PASS from their own "
        f"criteria: {names}"
    )


def _evaluate_population(pop_dir: Path) -> tuple[str, str]:
    """One candidate directory's verdict: a lone reading when it holds no
    `trial-ledger`, exactly as `evaluate()` always behaved; a bundle reading,
    gated by `_validate_bundle` and `_evaluate_skill_evidence`, when it does.
    """
    by_kind, skipped = _bundle_records(pop_dir)
    ledgers = by_kind.get(TRIAL_LEDGER, [])
    if not ledgers:
        return _evaluate_lone_results(pop_dir)

    note = _producer_reported_note(by_kind)
    if skipped:
        return "bundle-invalid", f"{pop_dir.name}: {skipped[0]}" + note
    findings = _validate_bundle(by_kind)
    if findings:
        return "bundle-invalid", (
            f"{pop_dir.name}: bundle fails its own structural rules, restated from skillc "
            f"records.md at 2202603 ({len(findings)} finding(s)); first: {findings[0]}"
        ) + note
    evidence_verdict = _evaluate_skill_evidence(pop_dir, by_kind)
    if evidence_verdict is not None:
        verdict, detail = evidence_verdict
        return verdict, detail + note
    verdict, detail = _evaluate_bundle_results(pop_dir, by_kind)
    return verdict, detail + note


def _candidate_dirs(directory: Path) -> list[Path]:
    """`directory` itself, then each of its immediate subdirectories, in a
    stable order - #1369's "one bundle per immediate subdirectory" layout,
    while still treating `directory` itself as a candidate so a lone result
    with nothing beside it keeps working exactly as before."""
    if not directory.is_dir():
        return []
    return [directory, *sorted(p for p in directory.iterdir() if p.is_dir())]


def evaluate(directory: Path) -> tuple[str, str]:
    """The verdict and its detail. Pure, so the tests drive it with real files.

    #1369: `directory` and each of its immediate subdirectories are
    independent candidate populations, checked in sorted order; the first one
    that is not clean decides the verdict. A candidate with no `trial-ledger`
    is read exactly as pre-#1369's `evaluate()` always did."""
    candidates = [d for d in _candidate_dirs(directory) if any(d.glob("*.json"))]
    if not candidates:
        return "absent", ABSENT_NOTE
    pass_notes: list[str] = []
    for pop_dir in candidates:
        verdict, detail = _evaluate_population(pop_dir)
        if verdict != "pass":
            return verdict, detail
        pass_notes.append(detail)
    return "pass", " | ".join(pass_notes)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--dir", default=str(DEFAULT_DIR),
                        help=f"artifact directory (default: {DEFAULT_DIR})")
    parser.add_argument("--advisory", action="store_true",
                        help="exit 0 on every verdict this gate PRINTED; a crash "
                             "or usage error still exits non-zero")
    args = parser.parse_args(argv)
    verdict, detail = evaluate(Path(args.dir))
    code = _say(verdict, detail)
    # ADVISORY IS APPLIED HERE, AFTER A VERDICT EXISTS, AND NOWHERE ELSE. The
    # Makefile and CI used `|| true`, which also swallowed a traceback - and an
    # uncaught Python exception exits 1, this gate's own `failure` code, so no
    # shell-side filter on the exit code can tell the two apart either. Only the
    # gate knows it reached a verdict. A crash never gets here and keeps its
    # non-zero exit; a usage error exits USAGE_EXIT from the parser above.
    return 0 if args.advisory else code


if __name__ == "__main__":
    sys.exit(main())

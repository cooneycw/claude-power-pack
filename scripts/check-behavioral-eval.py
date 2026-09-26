#!/usr/bin/env python3
"""Consume a behavioural-eval verified-result artifact and report (issue #1084).

THIS IS HALF A. It is the CONSUMER: given a verified-result artifact, does this
repository render a failure as a failure, a pass as a pass, a forged verdict as a
refusal, and an absent artifact as none of those? Half B - the behavioural case
that PRODUCES such an artifact - lives in skillc, never here (owner ruling, and
skillc ADR 0002's boundary).

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
trial ledger and the artifact manifest beside the result, and this gate reads
results alone. So every verdict says "checked alone - NOT against any ledger",
skillc's own words for the same position: a PASS here cannot show that the result
graded the artifact its attempt captured, or that the attempt was ever planned.
And `producer: assembler` is a declared field, so it refuses a subject that says
it wrote its own verdict and cannot refuse one that lies about it - skillc says
the same, and authentication belongs to its trusted controller.

A SEAM LEFT OPEN ON PURPOSE: a real producer will emit a BUNDLE (ledger, receipt,
manifest, result) and this gate refuses any record that is not a verified-result.
How a bundle is laid out under DEFAULT_DIR is not decided yet - the runner is
skillc #8 - so selecting the result out of a bundle is left to whoever lands the
first producer, rather than guessed here.

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

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

#: Where a producer would write its artifacts. Nothing writes here yet; see ABSENT.
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

#: THE VERDICT MAP. Exactly one entry maps to 0. A test asserts that property
#: rather than trusting this comment, because a comment cannot fail.
#:
#: `inconclusive` is deliberately NOT folded into `failure`: the spec fixes five
#: statuses and three of them mean "this did not establish anything". Reporting
#: those as a failure would be a different wrong answer, not a safer one - but
#: they must still never be 0, which is why they have a code of their own.
VERDICTS: dict[str, int] = {
    "pass": 0,
    "failure": 1,
    "absent": 2,
    "unreadable": 3,
    "forged": 4,
    "inconclusive": 5,
}

#: Cited by every verdict. A reader of `make verify` output sees this line beside
#: gates whose greens mean something entirely different.
POPULATION_NOTE = (
    "examined: a verified-result artifact's own fields. This gate reports what a "
    "producer recorded, checked alone - NOT against any ledger, so it cannot show "
    "the result graded what its attempt captured. It does not run a behavioural case "
    "and establishes nothing about one discriminating."
)

#: ABSENT names its blocker SPECIFICALLY, so a reader in three months can check
#: whether it still stands. "when a producer exists" would be unfalsifiable by the
#: person reading it, and that is how a permanently-absent line becomes furniture.
ABSENT_NOTE = (
    "no verified-result artifact. Nothing produces one yet: the behavioural case is "
    "CPP #1084 half B, which lives in skillc. skillc #5 (the first goal and a grader "
    "proven to discriminate) landed 2026-09-26; no model trial has run, because the "
    "runner and independent grading are skillc #8, #9 and #10. Check those three "
    "before assuming this line is still expected."
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


def evaluate(directory: Path) -> tuple[str, str]:
    """The verdict and its detail. Pure, so the tests drive it with real files."""
    if not directory.is_dir():
        return "absent", ABSENT_NOTE
    artifacts = sorted(directory.glob("*.json"))
    if not artifacts:
        return "absent", ABSENT_NOTE

    for path in artifacts:
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

    names = ", ".join(p.name for p in artifacts)
    return "pass", (
        f"{len(artifacts)} artifact(s) declare PASS and re-derive to PASS from "
        f"their own criteria: {names}"
    )


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

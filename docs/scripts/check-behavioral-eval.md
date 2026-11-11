# `check-behavioral-eval` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `check-behavioral-eval` (#1084)

Reads a behavioural-eval verified-result artifact and reports. This is HALF A of
#1084 - the CONSUMER. The behavioural case that produces such an artifact is half
B, which lives in skillc (owner ruling) and never in this repository.

**Its green is narrower than its neighbours' and it says so on every verdict.** A
pass here means a reader read an artifact correctly. It establishes nothing about
a behavioural case discriminating or improving another population. The
output sits in `make verify` beside gates whose greens do carry behavioural
meaning, and a reader skimming cannot tell them apart, so each verdict names the
population it examined and states when that population is a fixture.

**The default population includes the real retained D3 handoff (#1554).**
Its 11 original records describe two attempts with overall INCONCLUSIVE results:
three task criteria SATISFIED and mandatory installation-ready UNKNOWN in each.
The separately declared primary endpoint excludes readiness and reports PASS;
it does not replace those overall results. See
[the handoff record](../measurements/behavioral-eval/README.md) for producer custody,
correction lineage and limits. `absent` describes only the requested directory,
never whether any model trial has run elsewhere.

**Advisory remains the enrollment decision.** The existing #1084 / ADR 0011
policy requires coherent real evidence plus a recorded enrollment decision;
arrival alone does not make the gate blocking. `--advisory` maps a printed
verdict to success while preserving crashes and usage errors as failures.

**Required-record completeness precedes interpretation.** Every captured
lifecycle requires its own manifest and result, and every graded result requires
a manifest. All planned attempts receive these joins before any early
INCONCLUSIVE or PASS interpretation. Every result is checked for unreadable or
forged content before the first historical outcome is selected. Legitimate
not-run, unavailable and inconclusive lifecycle states need no result. This
extends CPP's stated subset, not the full producer validator: private object
bytes, source authentication, other lifecycle consistency and receipt stand-in
rules remain outside this reader. Metadata lives outside candidate record
directories; source hashes bind a reviewed copy without authenticating a forger.

**`status` is DERIVED, not read - and that is the whole of what this consumer
does.** skillc's `verified-result` contract makes `status` a derived field and
refuses "a record whose `status` does not follow from its own `criteria`": the
forged verdict, copied from a subject rather than computed from evidence. A
consumer that trusted the declared `status` would launder exactly that, so this
gate re-derives from the criteria and refuses any disagreement. Two committed
cases are the reason: both declare `PASS`, both are well-formed JSON, and both
parse - one over a mandatory `VIOLATED` criterion, one over no mandatory criteria
at all. No amount of validating the record's SHAPE distinguishes either, which is
also why the control's blind anchor misses both.

The second of those is this repository's own #1014 rule arriving inside someone
else's format: records.md fixes that no mandatory criteria yields `INCONCLUSIVE`,
never `PASS` - an empty population must not render as a clean one.

**Three refusals came from counter-model review and are the ones a single author
would not have written.** All three were well-formed JSON that produced a
confident wrong answer rather than noise:

- A `mandatory` flag carrying the STRING `"true"`. The derivation read it as
  falsy, so a
  `VIOLATED` criterion silently left the population; the record then derived
  `PASS` honestly, matched its declared `PASS`, and reported clean. One typo in a
  producer defeated the whole forged-verdict defence - and it did so by making
  evidence DISAPPEAR, which is why no assertion about agreement between `status`
  and `criteria` could have caught it. `mandatory` must now be a real boolean.
- A record of another `kind` (an `artifact-manifest`) read as a verified-result -
  a verdict about a population the record was never part of. `kind` is now checked.
- A `status` of `[]`, which JSON permits and `in frozenset(...)` raises
  `TypeError` on. The traceback exited 1 - this gate's `failure` code - printing no verdict
  line and no population note, and the advisory `|| true` wrappers swallowed it.
  Malformed input was therefore reported as a producer's recorded failure.
  Membership is now type-checked first.

Exit codes: `pass` 0, `failure` 1, `absent` 2, `unreadable` 3, `forged` 4,
`inconclusive` 5, `bundle-invalid` 6 and `evidence-unverified` 7; a usage error is 64. Exactly one verdict maps to 0, which is
`gate-lib.sh`'s rule - "an unknowable answer is never rendered as a clean one" in
exit codes. gate-lib enforces that for shell gates; this one is Python, so the
rule is restated in the gate and tested, rather than inherited by resemblance.

Two of those codes exist for reasons worth stating. `inconclusive` is not folded
into `failure`: the record format fixes five statuses and three of them mean "this
established nothing", so reporting them as a failure would be a different wrong
answer rather than a safer one - but they must still never be 0. And the usage
code is 64 rather than argparse's default 2, because 2 is this gate's `absent`: a
mistyped flag would otherwise have been indistinguishable from "I looked and found
no artifact".

**Records version 2, and what "checked alone" means.** The consumer was built
against skillc's records version 1. skillc then fixed version 2 (skillc PR #32,
closing skillc #4) and refuses version 1 outright, so every record skillc can now
emit was refused here as "newer than supported" - the gate could not have read
the first real result. It now reads exactly `{2}` and applies skillc's RECORD rules
for a verified result, restated by hand at skillc 3c243a1 because CI has no skillc
to import: producer authority (only `assembler`; `producer: subject` is `forged`),
identifier shape, grader identity, `graded_digests` unless a run state is
declared, evidence on every established outcome, `missing` on every `UNKNOWN`, a
reason on a declared run state, a digest on any `raw` reference, and a boolean
`version` refused. Without a declared ledger it does NOT apply skillc's BUNDLE rules
(ledger-binding, unique-ids, attempt-accounting, lineage), and its verdict says
"checked alone - NOT against any ledger". A bundle with a ledger receives the
stated subset, including the required-record presence clauses above, never the
full producer rule set.

Two committed cases are REAL grader output rather than hand-written:
`good-skillc-graded-pass` and `bad-skillc-graded-failure` wrap skillc's own
`grade_slug.py` report on its reference candidate and on `wrong/example-only`. Each
committed case was also run through skillc's own `check-records` once, by hand,
and every bad case is refused there for the reason its name gives - except
`bad-malformed-mandatory-flag`, which skillc ACCEPTS: its derivation reads
`mandatory is True`, so the string `"true"` drops a `VIOLATED` criterion out of
the population exactly as it did here before counter-model review. That is an
upstream defect, filed as skillc #37, and the reason this gate keeps its own
boolean check rather than deferring to the producer's.

**Advisory by `--advisory`, not `|| true`.** The wrapper passed a crashed gate as
well as a verdict, and no shell-side filter on the exit code can separate them: an
uncaught Python exception exits 1, which is also `failure`. `--advisory` maps a
verdict to 0 only after the gate has printed one, so a traceback keeps its
non-zero exit and a usage error keeps 64.

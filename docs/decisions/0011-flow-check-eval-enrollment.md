# ADR 0011: flow-check behavioural-eval enrollment - remain ADVISORY on skillc #288's limited evidence

- Status: Accepted (decision: ADVISORY)
- Date: 2026-10-23
- Issue: #1371
- Supersedes: draft PR #1393 ("results pending skillc #288", 2026-10-06), whose
  verified citations of #1084's rulings, cost correction and "does not claim"
  list are carried forward here with credit. Its caveats described a state that
  no longer holds (skillc#334 blocking, an undecided pin, stale coverage), so it
  was superseded rather than rebased.
- Related: #1084 (the flip rule), #1367 (the outcome contract), #1368 (the
  per-skill-audit spec), #1370 / #1532 (the coverage snapshot this decision is
  pinned beside), skillc #288 / #279 / #529 (the evidence), skillc #273 (the
  certified-pairing mechanism)
- Enforced by: `docs/measurements/eval-enrollment/flow-check.json` (the
  decision as data) and `scripts/check-eval-enrollment.py` (`make
  eval-enrollment-check`, a step in `make verify` and in CI)

## Decision

**flow-check stays ADVISORY.** `behavioral-eval-check` and the new
`eval-enrollment-check` report; neither blocks a merge.

Advisory is a statement about what the evidence CANNOT show, not a weaker
form of assurance. Nothing in this record, its data file or its consumer says
flow-check is behaviourally assured, and the consumer is built so that it
cannot print that.

## Why: skillc #288 is answered WITH LIMITS

skillc's orchestrator decided skillc #288 on 2026-10-23,
[comment 6371627281](https://github.com/cooneycw/skillc/issues/288#issuecomment-6371627281),
on worker-A's brief,
[comment 6371616650](https://github.com/cooneycw/skillc/issues/288#issuecomment-6371616650):
**answered with limits**. The evidence supports #1371's "remain advisory"
branch. It does not answer the flip: both results are single-arm, so neither of
#1084's Fisher tests can be computed. The flip is **UNPROVEN, not refuted**.

### The evidence

| Result | Source (pinned) | What it shows |
|---|---|---|
| skillc #279, flow:auto Step 6 | [comment 6364683161](https://github.com/cooneycw/skillc/issues/279#issuecomment-6364683161); campaign bound in skillc `1994c73` (#528); CPP `ca3030d` | 5/5, one arm: the agent invokes the finish gate when the workflow reaches it, and never ships past red. 0 non-evaluable attempts |
| skillc #529 D3, flow-check route | [comment 6371486408](https://github.com/cooneycw/skillc/issues/529#issuecomment-6371486408); approval stamped skillc `ab2fa36` (#533), profile merged skillc `d846a693` (#531); CPP `652c0118` | 2/2, one arm: `report-honest`, `no-commit` and `gate-definition-unmodified` SATISFIED, via the bundled skill copy |

### The limits, all four, as skillc states them

1. **#279 is flow:auto, not the flow-check family.** It calls the same
   `flow-finish-gate.sh` from a different skill; this record is scoped to
   flow-check only.
2. **#279's gate path was the installed copy in 5/5.** The bundled route was
   armed but never chosen.
3. **D3 is green-only, n=2.** Every gate stage passed, so "honest" there means
   reporting a pass as a pass. Honesty when a gate FAILS - the case the
   property is really about - was not exercised.
4. **The #1547 STOP leg is unexercised.** No launch failed, so "a launch
   failure, then stop without committing" is unmeasured.

Two more facts bound how far the results reach: they are on different CPP
revisions (`ca3030d`, `652c0118`) and different tasks, so they cannot be
pooled into one arm; and D3's gate copies were witness shims, a declared
treatment deviation.

## The flip rule, unchanged

From #1084's owner ruling,
[comment 6014163660](https://github.com/cooneycw/claude-power-pack/issues/1084#issuecomment-6014163660),
quoted rather than restated:

> **Net flip condition for `behavioral-eval-check`:** rule 1 = DISCRIMINATING
> **and** rule 2 = IMPROVED, on the same certified case and revision. Anything
> else leaves the gate advisory.

1. **Discrimination** - intact pass rate > degraded pass rate on a case
   certified by skillc #273's pairing record, one-sided Fisher at alpha 0.05.
2. **Improvement** - CPP pass rate > no-CPP-baseline pass rate on the same
   certified case, one-sided Fisher at alpha 0.05. A no-effect result is
   **valid evidence** and is rendered as such, but it never flips the gate
   alone - "Require improvement too",
   [comment 6007022667](https://github.com/cooneycw/claude-power-pack/issues/1084#issuecomment-6007022667).

Pairing is never inferred from naming
([comment 6006877171](https://github.com/cooneycw/claude-power-pack/issues/1084#issuecomment-6006877171)).

**Reconciliation with #1084 (#1371 acceptance item 1).** Grader
discrimination is NOT equated with a positive CPP-versus-baseline delta here.
D3 shows the grader can read an honest report in a green case; that is neither
rule 1 (no degraded arm) nor rule 2 (no baseline arm). Where this record and
#1084 could be read to disagree, #1084's text governs.

## #1371's checklist, against the evidence

| Field | Value |
|---|---|
| Criterion validity | Graded against the controller-held witness (D3: stage-by-stage reconciliation with the witnessed run); #279 graded gate use and ship-past-red. #288's own property (`honest_report`) read UNKNOWN on all 5 #279 attempts |
| Observation completeness | 7/7 evaluable (5/5 + 2/2) |
| Repeat evidence | n=5 and n=2, one case each, one arm each - not repeat evidence for any contrast |
| Applicability | flow-check at CPP `652c0118` (D3); #279 applies to flow:auto, not this family |
| Provenance | the comment URLs and skillc shas above; D3's run store is host-local (`~/skillc-evidence/flow-check-route/probe-652c0118-1/`), not a committed bundle |
| Measured cost | #279 ~1.0M tokens / ~3.6 min per attempt; D3 ~162k tokens / ~97 s per attempt |
| Discrimination p and verdict | **UNPROVEN** - no degraded arm |
| Improvement p and verdict | **UNPROVEN** - no baseline arm |
| Certified pairing (skillc #273) | none |
| **Net decision** | **ADVISORY** |

A valid null study would stay valid evidence; there is none here to discard.

## Unknown and stale handling (enforced, not described)

`scripts/check-eval-enrollment.py` reads the decision record and prints one of
six states, each with its own exit code without `--advisory`:

| State | When | Exit |
|---|---|---|
| advisory - evidence current | the record reads, at least one evidence item is for flow-check itself (#279's flow:auto result is context, never this family's evidence), the shipped closure digest equals the evaluated one, and today is on or before `review_by` | 0 |
| unknown | no record; unreadable; unsupported schema; a required field missing or not a usable string; an evidence item without integer counts and at least one evaluable attempt; no evidence item for this family; **a pass-rate threshold anywhere**; **a `blocking` decision** | 2 |
| advisory - STALE (content) | the shipped closure is no longer the content the evidence was taken on - the CPP pin moved past `652c0118` in a way that touches flow-check | 3 |
| advisory - STALE (aged) | today is past `review_by` | 4 |
| advisory - evidence records a FAILURE | an evidence item records a fail | 5 |
| fixture population - not behavioural evidence | the record describes fixtures | 6 |

**Missing or stale evidence never prints behavioural assurance.** No state
prints "pass", "assured" or "blocking", and the record's four limits print
beside every reading. The closure digest is taken over every file under
`codex/skills/flow-check/` - bytes, by the same definition as
`check-skill-coverage-map.py`, plus each file's executable bit, since a helper
made non-executable is the degraded treatment the review trigger names - evaluated
at `652c0118`:
`sha256:65e8fee59a3908a41200ca5f2ff835beb9f812c2a12465023ececfac69bd4a8e`,
identical at `f022a2a3` (#1549), where the coverage snapshot reads current
against skillc profile `cpp-codex-flow-check-652c0118`.

## Expiry and review

- **Review trigger** (skillc #288 comment 6371627281): a **two-arm
  intact-vs-degraded discrimination study** on the flow-check route task. The
  degraded arm removes the bundled `scripts/` or makes it non-executable, a
  declared treatment change, which also exercises the #1547 STOP leg. It
  serves #1084's rule 1 only; rule 2 needs a different task, because the route
  task presupposes the skill. Roughly 6 attempts per arm, about 2M tokens. **Not
  scheduled - the owner decides**, because it is new spend and a path to
  blocking.
- **`review_by`: 2027-01-21**, 90 days from the newest evidence. **Reversal
  trigger, recorded beside the value in the data file:** if it reads STALE
  (aged) twice with nothing else changed, LENGTHEN it; never delete the expiry.
  Set by the cpp-group orchestrator (outbox rev 16).
- **Content-bound.** Any change to flow-check's shipped closure makes the
  record read STALE (content). Re-affirming needs evidence taken on the new
  content, not a re-reading of this record.
- **Model/client-bound** (#1084 comment 6014163660 item 7): "the verdict is
  bound to the evaluated skill content and the model identity. A content
  change makes it stale (#1370's rules), and a model or client change needs
  re-measurement."
- **Family-bound.** flow-check only. Another family needs its own record.

## Cost and cadence

No pass-rate threshold is introduced, and the consumer refuses one in the
record rather than ignoring it. No paid run is authorized by this record or by
#1371; skillc ADR 0005 governs live trials. Cheap validation and freshness stay
in ordinary CI (`eval-enrollment-check` reads JSON and the skill tree - no git,
no network, no skillc). Any future paid cadence needs its own bounded
declaration.

The "$10 cap" an earlier assignment cited is superseded (skillc #287 comment
[6021089903](https://github.com/cooneycw/skillc/issues/287#issuecomment-6021089903),
carried forward from #1393): studies are sized for statistical validity, and
reported, not capped.

## What this record does not claim

- **Not assurance.** "Advisory" never reads as "assured".
- **Not a ruling on what discrimination or improvement mean.** Those are
  #1084's.
- **Not an authorization to run the two-arm study.** That is the owner's, under
  skillc ADR 0005.
- **Not a refutation of the flip.** UNPROVEN, not refuted.
- **Not a close of #1084 or #1367.** #1084 still lacks a case shown to
  discriminate; #1367's outcome still lacks a consumed real producer export.
  Both stay open with their own acceptance.
- **Nothing about any other skill family.**

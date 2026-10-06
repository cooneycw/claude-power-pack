# ADR 0011: flow-check behavioral-eval enrollment - the policy, the flip rule, and a result-free record pending skillc #288

- Status: Proposed (results pending skillc #288; do not treat as Accepted until the PENDING fields below are filled)
- Date: 2026-10-06
- Issue: #1371
- Supersedes: nothing
- Related: #1084 (the owner rulings this record cites verbatim), #1367 (the
  outcome contract this issue delivers a slice of), #1368 (per-skill-audit
  spec), #1370 (the consumer's content/dependency staleness axes, including
  #1388 and #1390/#1392 below), skillc #273 (the certified pairing record
  mechanism), skillc #287/#288 (the study declaration and run this record is
  waiting on), skillc #334 (a live blocker on #288, open)

## TL;DR

This record exists so that when skillc #288 reports a result, landing it on
`behavioral-eval-check` is a **fill-in**, not a design decision made under the
pressure of a number that just arrived. Every section below is written now,
against the rules already ruled on #1084, with no result assumed. Every
field that depends on #288's outcome is marked **PENDING #288**, naming
exactly what goes there.

**Net:** the gate flips to blocking only when BOTH a certified discrimination
result and a certified improvement result land, on the same case and CPP
revision, per #1084's verbatim rulings below. No result exists yet. This
record commits what counts as a PASS, a NULL, and a non-result before anyone
has a reason to prefer one answer over another.

## Policy: what blocking would mean, what stays advisory

`behavioral-eval-check` ([Makefile](../../Makefile), target
`behavioral-eval-check`) reads a verified-result artifact under
`docs/measurements/behavioral-eval/` and reports PASS/FAIL/UNKNOWN for it,
`--advisory` today so no verdict fails the build
(`scripts/check-behavioral-eval.py`). **Blocking** means dropping
`--advisory`: a FAIL or UNKNOWN from a real artifact would then fail CI.

This record's scope is narrow on purpose, matching #1371's bounded acceptance:
**one family (flow-check), one case, one CPP revision.** It does not:
- enroll any other skill or family;
- introduce a pass-rate threshold (#1084's own constraint, restated by #1367);
- treat a null or negative result as grounds to retry with a different design
  until the result changes (skillc #203's "no redesign-until-CPP-wins" rule
  applies here by the same logic).

What stays advisory regardless of this record: every other skill's coverage,
and `behavioral-eval-check` itself for any artifact that is not this specific
certified case.

## The flip rule, cited

#1084's owner ruling, 2026-10-06, comment
[6014163660](https://github.com/cooneycw/claude-power-pack/issues/1084#issuecomment-6014163660),
quoted rather than restated:

> Net flip condition for `behavioral-eval-check`: rule 1 = DISCRIMINATING
> **and** rule 2 = IMPROVED, on the same certified case and revision. Anything
> else leaves the gate advisory.

The two rules, each a one-sided Fisher's exact test at alpha 0.05, per the
same comment:

1. **Discrimination** - intact pass rate > degraded pass rate, over evaluable
   attempts of a case certified by skillc#273's pairing record. DISCRIMINATING
   is p < 0.05; UNKNOWN is too few evaluable attempts (tolerance predeclared
   per study in skillc#287) or an uncertified pairing.
2. **Improvement** - CPP pass rate > no-CPP-baseline pass rate, on the same
   task/grader/revision rule 1 certified. IMPROVED is p < 0.05;
   NO_IMPROVEMENT_SHOWN (p >= 0.05) is **valid evidence, rendered as such, and
   never flips the gate alone** - comment
   [6006877171](https://github.com/cooneycw/claude-power-pack/issues/1084#issuecomment-6006877171)'s
   addendum and comment
   [6007022667](https://github.com/cooneycw/claude-power-pack/issues/1084#issuecomment-6007022667)'s
   owner ruling ("Require improvement too") both apply.

Pairing itself is never inferred from naming, file co-location, or a
self-declared field - skillc#273's own scope note calls that "not
acceptable", and comment 6006877171 repeats the same constraint for this
gate's consumer side.

## Acceptance evaluation (#1371's checklist, against current evidence)

**Criterion validity.** The two Fisher rules above are predeclared, one-sided,
alpha 0.05, with no post-hoc threshold adjustment. Accepted as valid by the
owner ruling that adopted them; not re-litigated here.

**Observation completeness.** PENDING #288. The field to fill: evaluable
attempt counts per arm (intact, degraded, baseline), and the declared
tolerance for non-evaluable attempts (skillc#287's own declaration, cited by
comment 6014163660 as living there, not here).

**Repeat evidence.** PENDING #288. The field to fill: n per arm as actually
run, and whether the power limits held - comment 6014163660's own table
(n=10/arm needs the weaker arm at <= 6/10 to reach significance; n=20/arm
needs <= 15/20) is the standard this record holds #288's n to, not a
suggestion.

**Applicability.** Scoped to flow-check only, at the CPP revision #288's
declaration pins (see Caveats - that pin is not yet fixed, and CPP main has
moved twice since the declaration's design inputs were written).

**Provenance.** PENDING #288. The field to fill: the skillc#273 pairing
record's own identifiers (case id/revision, both trial ids), and the CPP
revision the attempts actually ran against - not assumed to be whatever
revision the declaration names, because the declaration itself flags this as
undecided (see Caveats).

**Measured cost.** See the dedicated note below - the assignment that
produced this record cited a now-superseded figure, and this record does not
repeat it.

**#1084 compatibility.** This record's flip rule is a verbatim transcription
of #1084's ruling, not a reinterpretation. Where #1084's text and this
record could be read to disagree, #1084's text governs and this record is
wrong.

## Grader discrimination and the current producer evidence

skillc's own record of what has been demonstrated so far (not #288, which
has not run):

- skillc#150's live run (PR #201) was **non-discriminating** - both arms
  passed `finish-close-ref`. That result predates and is unrelated to the
  flow-check family this record covers.
- skillc#203's calibration hit **ceiling** on `gate-ran-nothing` (18/18 both
  arms, two effort levels) and **floor** on `helper-different-question`
  (0/18) - neither task usable, and natural skill uptake sat at 0/19 across
  both.
- skillc#237 (PR #293) is a real, significant result (20/20 vs 0/20,
  Fisher p ~= 7.3e-12) but for **selection**, not **outcome** - its own report
  states "Task PASS was 60/60 in every cell" and "selection is not value."
  It satisfies none of #1084's acceptance items and is not cited here as
  discrimination evidence.
- skillc#273 (merged) delivers the **mechanism** - `case.arm`/`case.paired_with`,
  validated reciprocal/complementary/unique, cross-checked against the #150
  degraded-marker convention. It does not itself certify any specific case as
  discriminating; it is the record format a future certified case would use.
- skillc#270 (certify a flow-check case for omitted tests and incomplete
  aggregate gates) is **open** - the case #288 would actually run has not
  been certified yet.

**No valid discrimination result exists today for the flow-check family.**
This record's PENDING fields are not a formality; the evidence genuinely does
not exist yet.

## Unknown/stale handling

Two distinct mechanisms, not to be conflated:

1. **`behavioral-eval-check` itself** (#1084/#1369): reads a verified-result
   record, re-derives status from criteria rather than trusting a declared
   field, and refuses a record that fails schema/producer/evidence checks as
   `forged` or `unreadable` rather than guessing. UNKNOWN there means "this
   record cannot be read as a verdict," never "no verdict exists" - absence
   of any record is reported as its own case (`absent`).
2. **`skill-coverage-map-check`** (#1370): a *different* axis entirely -
   whether flow-check's own *content* (not a verified-result record) matches
   what a skillc profile was evaluated against. This is live and already
   exercised: #1388 (landed) edited flow-check's `reference.md`; the gate
   first read `unknown` because axis1 only digested `SKILL.md` (filed as
   #1390), then correctly read **`stale (content)`** after #1390's fix
   (PR #1392) landed. Current state, measured on main at `84ced91`:
   ```
   skill-coverage-map: flow-check (flow:check): stale (content) - axis1: stale
   [reference.md (content changed)]; axis2: unknown [vendored diagnose()
   snapshot is stale - the closure changed since it was recorded: reference.md
   (content changed). Re-run scripts/skill-coverage-snapshot.py and commit a
   fresh snapshot.]
   ```
   This means: **flow-check's shipped instructions are not currently
   evaluated by any committed skillc profile.** Any #288 run must either
   re-pin and re-validate a profile against current content, or the result
   it produces is a result about *older* instructions than what ships. This
   is a precondition for #288, not a detail - comment 6006871866-era design
   inputs on skillc#287 said the same about the `b8825bd` -> `9661967` move,
   and it has moved further since (`9661967` -> `ea6dbfa` -> `84ced91`).

A valid null result from a well-designed study is never treated as
"unknown" or discarded - comment 6007022667: "A no-effect result is still
**valid evidence**... and is never treated as an invalid bundle."

## Expiry / review conditions

- **Content-bound.** Per #1370's own rule, a flip based on a specific
  flow-check revision expires the moment flow-check's shipped content
  changes again, because the certified case's content reference no longer
  matches what ships. Re-affirming after a content change needs a fresh
  `stale (content)` check to read clean against the new profile, not a
  re-reading of this record.
- **Model/client-bound.** #1084 comment 6014163660 item 7: "the verdict is
  bound to the evaluated skill content and the model identity. A content
  change makes it stale ... and a model or client change needs
  re-measurement."
- **Family-bound.** This record and any resulting flip cover flow-check only.
  A different skill family needs its own #1371-shaped record; nothing here
  is precedent for skipping that.

## Cost - correction to the assignment's framing

This record's assignment cited "the \$10 cap" as a fact to record. That cap
is **superseded**. Owner ruling, skillc#287 comment, 2026-10-06, 16:49Z,
recorded verbatim there:

> the "\$10 cap" on #288 is superseded... size #287/#288 for a valid,
> adequately powered study... do not size it to a budget... nothing is
> shrunk or held for cost, and there is no "over the cap" escalation any
> more.

So this record does **not** carry a cost ceiling. What it does carry: PENDING
#288's declaration, the actual attempts/arms/tokens spent, for transparency
- the same ruling keeps that reporting requirement ("still declare the
expected attempts and token use") even though nothing is capped by it.

The same ruling also approves an **exploratory pilot** ("yes" to running one
once skillc#270's case is certified), sizing-only: it estimates per-arm pass
rates so n can be chosen to sit in the useful power band (comment
6014163660's table), and **no verdict is drawn from it** - the pilot's own
record must say so, per the ruling. The pilot's estimated rates, once it
runs, are an input to sizing #288, not a result this record waits on; the
PENDING fields above are about #288 itself.

## Every result-dependent field, explicit

| Field | Value |
|---|---|
| Discrimination test statistic (p) | PENDING #288 |
| Intact arm: passes / evaluable attempts (c_i / n_i) | PENDING #288 |
| Degraded arm: passes / evaluable attempts (c_d / n_d) | PENDING #288 |
| Discrimination verdict (DISCRIMINATING / NOT_SHOWN / UNKNOWN) | PENDING #288 |
| Improvement test statistic (p) | PENDING #288 |
| CPP arm: passes / evaluable attempts (c_cpp / n_cpp) | PENDING #288 |
| Baseline arm: passes / evaluable attempts (c_base / n_base) | PENDING #288 |
| Improvement verdict (IMPROVED / NO_IMPROVEMENT_SHOWN / UNKNOWN) | PENDING #288 |
| Non-evaluable-attempt tolerance applied | PENDING #288 (declared in skillc#287) |
| Certified case id / revision (skillc#273 pairing) | PENDING #288 |
| CPP revision actually attempted against | PENDING #288 |
| skillc#273 pairing record reference (trial ids, both arms) | PENDING #288 |
| Attempts / tokens / time spent (reported, not capped) | PENDING #288 |
| **Net enrollment decision** (flip to blocking / remain advisory) | **PENDING #288 - DISCRIMINATING and IMPROVED both required** |

## Caveats

- **skillc#334 is an open blocker on #288 itself**, found by code tracing
  (not yet live evidence): a live treated attempt installs the task surface
  and the subject's selected skill files, but never calls
  `skillc/profile.py`'s `Profile.install()`/`verify_installed()` - so the
  validated dependency closure a profile certifies with 0 problems is never
  actually installed into a live attempt. For `cpp-codex-flow-check-ea6dbfa`,
  that closure includes `~/.claude/scripts/flow-finish-gate.sh` and the
  `checkout-scripts`/CPP-checkout dependencies flow-check's own
  `reference.md` calls. A live attempt following those instructions today
  would hit the helper at a path that does not exist (exit 127) and land in
  a fallback path, not the behavior the study means to measure. **Neither
  the pilot nor the main #288 study can produce a meaningful result until
  this is fixed.** Historical runs (#203/#204 family) ran under the same
  gap and should not be compared against without checking it first.
- **The study's CPP pin is not fixed, and CPP main has moved repeatedly.**
  skillc#287's own design-input comments flag the pin as an open decision
  (originally `b8825bd`, noted moving to at least `9661967` for the adopted
  description). Since those comments: #1388 landed (`8e0a34f`, NOT_RUN report
  state - content-only, changes `reference.md`), then #1390/#1392 landed
  (`84ced91`, axis1 now digests the whole closure). **Whatever CPP revision
  #288 actually studies must be stated in its own declaration and must be
  re-validated against a current skillc profile** - per the unknown/stale
  section above, the profile that validates today's content does not exist
  yet as a committed artifact.
- **skillc#270 (the certified case itself) is open.** This record assumes a
  case will exist to run against; it does not assume which one, or that
  omitted-tests/incomplete-aggregate-gates is the final shape.
- **No live model trial is authorized by this record.** Consistent with
  #1371's own exclusions and skillc ADR 0005: preparing this record is not
  an approval to run anything.

## Planned consumer/CI controls (not wired up - plan only, per #1371's acceptance item 4)

#1371 asks for the exact policy above to be testable against valid, failing,
unknown, stale, and fixture-only records, without wiring anything live. The
plan, to implement once #288 reports (or to stub as `xfail`/skip now):

| Control | Fixture shape | Expected verdict |
|---|---|---|
| Valid DISCRIMINATING + IMPROVED | A certified skillc#273 pairing record plus a CPP-vs-baseline result, both p < 0.05 | Flip eligible (still requires the human/owner step this record does not itself authorize) |
| Valid DISCRIMINATING + NO_IMPROVEMENT_SHOWN | Same pairing, improvement p >= 0.05 | Stays advisory; recorded as valid null evidence, not discarded |
| Failing (NOT_SHOWN) | Pairing record where both arms pass/fail together | Stays advisory; not an error, a real finding |
| Unknown (too few evaluable attempts) | A result below skillc#287's declared tolerance | Stays advisory; reported as UNKNOWN, never defaulted to pass |
| Stale (content changed since certification) | A result whose cited case content digest no longer matches current flow-check content (per #1370) | Stays advisory regardless of the result's own verdict; flagged stale first |
| Fixture-only / synthetic | A record built for this control, never a live attempt | Reported as a fixture population, never presented as behavioral assurance (per #1367's own "missing evidence never prints behavioral assurance") |

Implementation is intentionally deferred: wiring a real check against a
non-existent artifact would itself be the inference this whole record exists
to avoid. When #288 lands, this table becomes the test list; each row is a
`tests/test_behavioral_eval_enrollment.py`-shaped case (or extends the
existing `tests/test_behavioral_eval.py`), using the real #288 artifact's
shape as the first fixture rather than a guessed one.

## What this record does not claim

- **Not a ruling on what "improvement" or "discrimination" mean.** Those are
  #1084's, cited verbatim above. This record does not restate them loosely
  and does not add a threshold #1084 did not set.
- **Not an authorization to run #288.** That is skillc ADR 0005's and the
  owner's, separately.
- **Not a statement that flow-check will or should enroll.** The honest
  current answer, stated plainly: no valid discrimination result exists for
  this family yet, #288 cannot yet produce one (skillc#334), and the content
  it would need to validate against keeps moving (#1370/#1388/#1390). This
  record is the fill-in template for whenever that changes, not a prediction
  of the outcome.
- **Nothing about any other skill family.** #1371's own bounded scope; a
  different family needs its own record.

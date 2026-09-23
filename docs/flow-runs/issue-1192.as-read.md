# Issue #1192 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1192
- Read at:      2026-09-23T14:06:34Z
- updatedAt:    2026-09-21T20:57:56Z   (context only - moves on comments and labels)
- Body digest:  4ff6fc75f70b9958ad51a11f75687cdb585d48ca53440dc005f5f2bd829caa6c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3718 of 3718 (cap 16384)

## Body as read
#1152 ships the gate dedup: skip a gate an aggregate already ran. #1147's blast-radius measurement named **kyle** — the fleet's busiest repo — as a repo that would gain a `verify` target and benefit. It does not benefit, and cannot.

## Measured

Run from a CPP checkout against kyle at `974d427`:

```
makefile_grammar_refusal("/home/cooneycw/Projects/kyle") -> 'line 9: an include'
subsumed_gate_ids("finish", BUILTIN_PLANS["finish"], kyle)
  -> ({}, ['the makefile is outside the grammar subsumption requires
           (line 9: an include), so nothing is subsumed and every gate runs'])
```

Positive control, so the refusal is a verdict about kyle and not a function that always refuses: a conforming fixture (`lint:` / `verify: lint`, plain rules and recipes only) returns `None`.

kyle's line 9 is `-include $(COMPOSE_ENV_FILE)`. It is **not removable** — kyle's CLAUDE.md records it as the only route `POSTGRES_PASSWORD` reaches the test environment.

`steps.py:876` gates the entire `make -p -n` query behind that refusal, so nothing downstream is ever consulted.

## This is not a bug, and framing it as one would be wrong

The refusal is deliberate and the docstring says why: the grammar check runs *before* the query precisely so a makefile it cannot reason about never has `make -p -n` executed against it, keeping `$(MAKE)` recursion and MAKEFLAGS-sensitive conditionals from running. That is the conservative direction and it is correct.

**The finding is about the bound's width relative to what #1152 was expected to deliver.** `-include` for optional local config is an ordinary construct, not an exotic one.

## What it cost, concretely

On a live wave, this changed the shape of a shipped target. The worker on kyle #1303 proposed — and I approved — a flat `verify: lint typecheck migration-check migration-collision-check negative-controls test` on the strength of the dedup. The measured cost of being wrong was ~106s unit + ~182s browser re-run at Step 6 **and again** at the Step 7 re-gate: roughly 10-12 minutes per issue across a 37-issue wave sharing one CI agent.

Nothing was lost only because the worker ran the real decision function instead of trusting the design. A repo that did not would silently pay the doubling #1152 exists to remove.

## An aggravating detail

`flow-finish-gate.sh` prints a `SUBSUMED:` line when subsumption happens and **nothing** when it is refused. So "no dedup because your makefile is outside the grammar" and "no dedup needed" are indistinguishable in gate output. A one-line `subsumption REFUSED (<reason>)` would have told the kyle worker on its first run what it took a measurement to discover.

(kyle has since shipped its target as the delta-only form with the refusal cited in-file, so kyle is no longer exposed — but it is exposed *by documentation*, not by tooling.)

## Suggested disposition

Consider admitting `-include` / `include` of a plain path or single variable to the grammar: the stated hazards are `$(MAKE)` recursion and MAKEFLAGS-sensitive conditionals, and an `-include` of an env file is neither.

Failing that, make the refusal **visible at the point of consequence** — emit the refusal reason from the gate, so the bound is discoverable without calling the function.

At minimum, note the bound in #1152's own record, since its benefit does not reach a named intended consumer.

## Provenance

Nit-store record: #864 comment [5764488055](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5764488055). Found by a worker in wave `kyle-improvements` while building a fixture to defend the opposite design; independently reproduced with the positive control above. Filed at the owner's direction.


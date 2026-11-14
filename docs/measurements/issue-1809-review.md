# Delegated lane review (#1809)

## Artifact and dispositions

Three diff-only semantic counter-model passes ran with runtime-measured
`codex/gpt-6.1-terra`, independently from implementing `codex/gpt-6.1-sol`.
The final review reported no defects on
`1a3af24a933fac55776b203efebdfaa526dec80c`, against main
`65921ba3d229a12c885f631beb34b969c1c0743c`. Network and local-credential reach
were unverified; no full-tree sandbox or live delegated execution was claimed.

Three findings were accepted and fixed; none rejected or deferred:

1. New approval records made the old raw status count pass with no product
   implementation. A pre-review product guard excludes this issue's evidence.
   Before the fix, the three metadata-only regressions proceeded; afterward
   they refuse. Product-change positive controls pass both.
2. Compliance used MERGE_BASE from a different tool shell. Its invocation now
   shares the shell that resolves the base. All three fresh-shell regressions
   failed before the fix and pass afterward. Older backstop fixtures install
   the real plan helper; they still execute the complete shell fence.
3. A quality-gate fix could revert product work after review and still ship
   metadata at finish. Both product guards now load one evidence definition:
   this issue's three flow-run paths and directly contained counter-model
   receipt names ending in -issue-N.json. Product-then-revert and receipt-only
   inputs failed on the earlier implementation and refuse afterward. Another
   issue's records/receipts and other flow-run files remain product. The same
   definition closes the pre-existing receipt-only finish hole.

The coordinator authorized the third pass after finding 3. The receipt records
its true count and extra-pass reason. No fourth semantic pass was run.

## Observations and verification

On each of the three shared review surfaces, a recorded model observation
flagged Harness when omitted from an illustrative plan and found no lane
finding for the corresponding fully answered plan with matching tests. This
one paired observation does not prove live Claude reviewer obedience.

Before implementation, each historical Step 3 continued after recorded human
approval even with an omitted listed lane. Each current boundary refuses and
names Harness; complete plans and projects without a lane file pass. Controls
execute the actual documented deterministic boundary in owned linked worktrees,
not a disconnected hard-coded lane parser or a live implementation model.

The reviewed implementation passed 493 related tests and all three strict,
provenance-aware controls. Each control has four BAD and nine GOOD inputs;
historical anchors miss the BAD cases and agree on GOOD cases. Static checks,
vendoring, dependency accounting and link/budget checks passed. The budget's
own known-bad control (101 words against a 100-word declaration) still fails,
the at-budget case passes, and its blind anchor misses the overrun.

## Procedure-only follow-up

The coordinator requested a separate documentation-only trim after the clean
third review and will inspect that delta directly. The receipt remains bound
to the actually reviewed implementation above; ancestry selection does not
claim that subsequent prose was independently model-reviewed.

| Driver | Before | Reviewed expansion | Compact procedure | Cap increase |
|---|---:|---:|---:|---:|
| codex | 7730 | 9283 | 8654 | 924 |
| qwen | 8938 | 10491 | 9862 | 924 |
| gemma | 9547 | 11100 | 10471 | 924 |

The trim moves context to docs/agents/delegated-plan-lanes.md. Every Bash fence
in each driver is byte-identical to the reviewed artifact; removing an approve
invocation is a negative input the comparison detects. Commands, order,
exit handling and STOP conditions remain in the inline procedure. Word caps
increase only by the remaining procedure; other command caps are unchanged.

The exact new plan helper verbs are reconcile, read-issue, begin-run, approve
and compliance. The first three cover only that portion of #1811's other-verbs
row; no other row is addressed. Existing canonical plan/snapshot/evidence
formats are newly produced by this delegated route; the Kyle coordination-note
draft was sent for owner routing, not posted here.

No full suite, finish gate, PR, CI run or merge was performed. The coordinator
owns those admissions and #1803 remains the priority when instructed.

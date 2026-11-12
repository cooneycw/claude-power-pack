# Flow run record - issue #1700

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=dbe9aa1907414f87a9e51a2fae8341fe -->
## Run 1

- Run-id:            dbe9aa1907414f87a9e51a2fae8341fe
- Run-start:         e33525d0f78c98cc613493a852e1bb0a777462a0
- Issue:             #1700
- Base SHA:          e33525d0f78c98cc613493a852e1bb0a777462a0
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, authority model orchestrator-only), by mailbox rev 28 to role cpp-1508 at 2026-11-11T21:55:43-05:00: "GATE: GO-WITH-CONDITIONS #1700" (assignment a1705-1707-583-1700-1710-g4). The change itself is a named exception to the #1673 freeze by the owner's ruling recorded on #1700 at 2026-11-12T00:39Z.
- Recorded at:       2026-11-12T02:56:17Z

### Section B evidence
- Unchanged at e33525d0: `PASSES_HARD_CEILING = 3` in `scripts/counter-model-receipt.py`; `write` refuses `--passes` above it and the validator rejects such a receipt; the gate has two passing enrolment states, receipt and skipped, and does not read `passes`; `flow/auto.md` Step 6 says "never a third time" beside the rule that an accepted fix needs a new review before the receipt.
- Eight runs in wave cpp-improvement reached the cap with a real finding on the last allowed pass (#1694, #1703, #1696, #1708, #1705, #1717, #1707, #1709), recorded on #1700.
- Related: #1707 (same function, lands first), #1710 (its cap rows 608, 664, 665, 666, 706, 732, 734 are this job), #1495, #1400, #1320.
- Coordination issues filed before any edit: cooneycw/kyle #2363, cooneycw/skillc #707, cooneycw/kyle-candidate #10.

### Section C - the approved plan
Rulings: outer bound 6, as one named constant; exactly 3 passes keeps today's form (reason only, line reads receipt:); no new status value (an older pinned gate must still read the receipt as an ordinary one); the other #1710 rows (572, 578, 637, 646, 689) are a second PR.

Gate line: `FLOW_FINISH_GATE_COUNTER_MODEL: escalated: <N> passes, ruled by <who> (<file>)` plus the existing where-suffix, a passing state in finish mode and enrolment-only mode under the same scope requirement as receipt; a ran receipt claiming more than 3 passes with no recorded ruling, or beyond the bound, reads unknown and fails.

Conditions: the writer's red cases committed (no ruling refused; `--passes 5` with no escalation flags refuses as today; a receipt claiming 3 is unaffected; raised cap 7 refuses; passes above the raised cap refuses; an empty or whitespace-only `--escalated-by` or `--escalation-ref` refuses); the tightening row is a control's bad case, shown missed by the current gate, in the existing control if its anchor rules allow and otherwise as a small control with the pre-fix script as anchor; "recorded, not authenticated" said in the receipt docs, the gate comment and the escalated line's documentation, and the line says "ruled by"; `flow/auto.md` Step 6 reworded within 10,410 words with an independent old-versus-new read, stopping if it does not fit; the corpus pass count reads the real number; what the pre-change gate and validator do with an escalated receipt is measured and stated; implementation branches after #1707 merges; make lint, make typecheck, make shellcheck read to the end; two review passes and the orchestrator is asked before a third.

Decided here and left as they are (condition 6): the branch narrowing of enrolment stays (Nit Store row 599), because without it any receipt whose head is an ancestor satisfies the check, reproduced under #1707; and the first-parent selection rule parked from #1707 is NOT adopted in this change, because it alters which merges pass and this change already adds a gate state, so the two rule changes stay separable and the #1707 behaviour, which is tested, stands.

1. `scripts/counter-model-receipt.py` - `write` accepts passes above 3 only with `--escalated-by`, `--escalation-ref`, `--raised-cap` and `--extra-pass-reason`, passes at most the raised cap and the raised cap at most the outer bound; the validator accepts exactly that shape; the corpus pass count reads the real number.
2. `scripts/flow-finish-gate.sh` - `cm_enrolment_evaluate` reads passes and the escalation block of an accepted ran receipt and reports the escalated state or unknown; both modes treat escalated as they treat receipt.
3. `.claude/commands/flow/auto.md` - Step 6 reworded, within budget, to name the outcome when the last allowed pass yields an accepted finding.
4. `tests/test_counter_model_review.py` - the writer and validator cases.
5. `tests/test_flow_finish_gate.py` - the gate states in both modes.
6. `controls/counter-model-enrolment/control.json` - register the tightening bad case and an escalated good case, or a small sibling control if the anchor rules require.
7. `docs/agents/counter-model-evidence.md` - the escalated receipt, its fields and its limit.
8. `docs/scripts/flow-finish-gate.md` - the new line and state.

Scope: 2 scripts, 1 command document reworded within budget, tests, control cases, docs; an estimated 150 to 250 lines. Further docs pages for the receipt writer, or ADR 0007 if it states the ceiling, are touched only where they state the old rule.

Risks: who ruled is recorded and cannot be authenticated; an escalation must not become the easy path; a receipt claiming more than 3 passes with no ruling stops passing, which could red a hand-made receipt somewhere; a consumer whose CI pins an older CPP shows receipt: for an escalated receipt and its older validator rejects the count until the pin moves.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: temporary repositories, attached and detached |
| Harness | will test: the Claude writer path and the shared write flags; Codex mirrors rebuilt; no live Codex run |
| Driver | will test: the /flow:auto wording; the delegated drivers call the same writer and are not separately exercised |
| Coordination | not applicable |
| CI provider | will test: --enrolment-only --branch with an escalated receipt; a live pipeline by this PR's own CI |
| Project state | will test: a repository on the new gate; not covered live: a repository whose CI pins an older gate, measured instead with the pre-change script |

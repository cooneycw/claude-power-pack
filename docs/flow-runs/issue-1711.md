# Flow run record - issue #1711

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=c7ffc866a0c04add95a7a5cadf1e9811 -->
## Run 1

- Run-id:            c7ffc866a0c04add95a7a5cadf1e9811
- Run-start:         5d7a9d5918b0b4c6f50e77a524218badea015c27
- Issue:             #1711
- Base SHA:          5d7a9d5918b0b4c6f50e77a524218badea015c27
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, authority model orchestrator-only), by mailbox rev 56 to role cpp-1508 at 2026-11-12T00:48:39-05:00: "GATE: GO-WITH-CONDITIONS #1711" (assignment a1700hold-1710-1727-1711-g6, item 2)
- Recorded at:       2026-11-12T05:55:00Z

### Section B evidence
- Rows read against origin/main 5d7a9d59 by a survey agent and spot-checked: 613 (STALL_CHECK not reset per poll), 736 (a newline in a step error splits into a second failed step), 682 first half (stderr of a successful protection read becomes context names), 683 (the header claims exit 2 for unknown; fallback single-shot exits 0), 727 (the command documents omit the wait's exits 2 and 5) are present on main.
- Rows 679 and 680 and the fallback `--exit-code` stalled hole moved to #1758; row 431 and the second half of 682 moved to the Nit Store (#1725 comments 6815838308, 6815838574).
- The unnumbered row: in fallback mode a ref that is not a commit is kept as typed and answers not-found; the recorded path answers unknown with "commit ref unreadable; name the full commit SHA".

### Section C - the approved plan
Conditions attached to the approval: no exit code changes; the header says what the code does today for `--exit-code` and names the fallback stalled case as a known defect with its issue number; 736 has a committed control case verified by name, anchors regenerated as the control requires; 682 has the stderr test and its must-not-flip partner; the invalid-ref row is read as the fallback path (unknown with the recorded path's message, a real SHA unaffected), and if it needs more than a few lines stop and report; 727 costs zero net words in `auto.md`, by an equal trim, with an independent old-versus-new read; lands before held PR #1701; two review passes, ask before a third. This change closes #1711.

1. `scripts/flow-ci-status.sh` - reset the stall check per poll; newline-safe failed-step emission; stderr kept out of the protection reads; an unresolvable non-SHA ref answers unknown in fallback mode; header corrected.
2. `tests/test_flow_ci_status.py` - a red test and its must-not-flip partner for each of the four behaviours.
3. `controls/flow-ci-status` - one case: a fetch failure whose error has two lines is one failed step, still precode.
4. `.claude/commands/flow/auto.md` - the wait's exits 2 and 5, zero net words.
5. `.claude/commands/flow/merge.md` - the same, zero net words.
6. `docs/scripts/flow-ci-status.md` - one line per behaviour changed.

Scope: about 40 lines of shell, 150 of tests, one control case, three sentences of documentation.

Risks: the control's run-case changing under held PR #1701, which also adds an error file to it; the two command-document trims; a test pinning today's two-step output.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: pytest in this linked worktree, each red shown on 5d7a9d59 first |
| Harness | will test: command-doc word budgets, Codex mirrors and tests/test_codex_skill_sync.py; a live Codex run is not covered |
| Driver | not applicable: no driver-specific code |
| Coordination | not applicable: no wave, mailbox or registry code |
| CI provider | will test: the Woodpecker lane through stubbed API answers and the protection read through a stubbed gh; not covered: a live pipeline with a multi-line step error, and the Actions lane beyond its existing tests |
| Project state | not applicable: no issue, label or board writes beyond the PR |

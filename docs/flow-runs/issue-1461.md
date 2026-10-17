# Flow run record - issue #1461

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=f965b3827b65499d849fe4e1d14a1dc7 -->
## Run 1

- Run-id:            f965b3827b65499d849fe4e1d14a1dc7
- Run-start:         ca3030dbeba4a145166b61d714861f56e92cd034
- Issue:             #1461
- Base SHA:          ca3030dbeba4a145166b61d714861f56e92cd034
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          master:kyle (mailbox message 6524, replying to plan 6523), with two tightenings
- Recorded at:       2026-10-17T04:30:00Z

### Section B evidence
Commits since filing touching scope: none (93f51dd added local_credentials; ca3030d the implementer path). Merged PRs: #1465, #1466, #1467. Duplicates: none. Measured (codex 0.162.1): a denied read is exit 1/failed with "Permission denied" in aggregated_output; a no-match grep is also exit 1/failed; a sandbox that cannot start emits no command item. 10 of 214 committed default-direction ran receipts carry scope.

### Section C - the approved plan
1. `scripts/counter-model-receipt.py` - completed commands whose output reports Permission denied / Operation not permitted downgrade a claimed full to unverified (with a note naming the count); ordinary non-zero exits do not count. The CLI ALWAYS requires --scope on a default-direction ran write; validate() requires scope when recorded_at >= SCOPE_REQUIRED_FROM (a compatibility window for history, not a security boundary).
2. `.claude/commands/codex/code_review.md` - run the reviewer with LC_ALL=C (and LANG=C) so denial messages arrive in the English form matched.
3. `tests/test_counter_model_review.py` - denial downgrades and no-match grep does not; ran without --scope refused; schema cutoff on both sides; helpers pass --scope.
4. `tests/test_code_review_network_fence.py` - the reviewer env carries LC_ALL=C.
5. `.claude/commands/flow/auto.md` - --scope is required.
Plus regenerated mirrors. The CI step refusing a NEW receipt without scope: done if cheap, else Nit Store.
Risks: text-keyed detection misses odd messages beyond the C locale (errs toward keeping full); a false downgrade from file CONTENT saying "Permission denied" errs safe.

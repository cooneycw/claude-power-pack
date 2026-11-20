<!-- flow-run n=1 id=606280da40cc44b393f5b03321739dfb -->
## Run 1 - issue #1857 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1857
- Read at:      2026-11-20T12:04:33Z
- updatedAt:    2026-11-16T02:22:28Z   (context only - moves on comments and labels)
- Body digest:  0a4c8d8e4c19eb52e5bd34d752cd846fc0f393f13058b4ba22b62b03d2d734ea   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1795 of 1795 (cap 16384)

### Body as read
Tier: 2

## Outcome

`/flow:auto` is numbered by the steps it actually has. Step 5 (retired at #1850) is gone, and Steps 8 (Verify CI) and 9 (Deploy) are one "after merge" step, so the run reports `Step N/7`.

## Why this was deferred

#1850 retired Step 5 and kept its number (owner ruling, 2026-11-16, "freeze the numbers"). A survey on #1850's branch found `/flow:auto` step numbers cited in **55 live files**. That count leaves out history: run records, ADRs and control anchors. The citing files include:
- helper stop lines a run relays, such as `scripts/gh-pr-merge.sh` "Resume /flow:auto Step 7 from its sync sub-step" and `scripts/step3-record-guard.sh`;
- about 12 test files that pin those strings (`tests/test_counter_model_review.py::test_the_step_numbering_is_UNCHANGED` pins `Step 1/9`..`Step 9/9`);
- the delegated drivers and `templates/delegated-driver-core.md` ("its Step 3/9 ELI5 gate");
- `register.md`, `wave.md`, `codex/code_review.md`, `docs/commands-reference.md`, `controls/census.md` and `.claude/verify-coverage.json`.

That is about four times #1850's approved scope.

## Constraints

- History is never rewritten: `docs/flow-runs/`, `docs/measurements/`, `docs/decisions/` and `controls/*/anchors/` keep the numbers they were written with.
- The #775 no-bypass guards keep pinning the ELI5 gate's label at its new number.
- Do this after #1851 (citations by text, not line number), so that renumbering does not also re-anchor every driver-parity citation by hand.

## Acceptance

- [ ] `flow/auto.md` reports `Step 1/7`..`Step 7/7`; no retired step remains.
- [ ] Every live citation names the new number. A grep for the old `/flow:auto` Step 6-9 references, outside the history paths above, finds none.
- [ ] `make verify` is green.

Depends on: #1851
Refs #1850


<!-- end of body -->

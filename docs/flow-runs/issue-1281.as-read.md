# Issue #1281 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1281
- Read at:      2026-09-28T09:56:46Z
- updatedAt:    2026-09-26T16:17:29Z   (context only - moves on comments and labels)
- Body digest:  148255990d0f7b86edd8c9d313f1227d61ef5fd9184a98440cfa2f9def86c1bf   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2466 of 2466 (cap 16384)

## Body as read
Split out of #1259 (finding 6) by owner decision during `/flow:auto 1259`: two new controls with fake worktrees / a fake HTTP server are ticket-sized, and the Nit Store report itself was a prioritisation observation, not a demonstrated defect.

## What is missing

ADR 0008 (`docs/decisions/0008-instrument-negative-control-bound.md`) enumerates two instruments whose own class letters say they need a committed negative control, and neither has one:

| row | instrument | verdict | consumer | class |
|---|---|---|---|---|
| 8 | `scripts/flow-worktree-sweep.sh` | `SWEEP_WORKTREE:` (five conditions per worktree) | removal of OTHER sessions' checkouts (ADR 0006) - destructive | X |
| 14 | `scripts/lane-serveability-check.sh` | `LANE_SERVE_STATUS` | whether `/qwen:auto` and `/gemma:auto` delegate at all (#921) | G |

Measured on `main` at 8dad506, 2026-09-26: `grep -c 'NEGATIVE-CONTROL:'` is `0` for both files. Original report: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741238742

## Why it matters

Row 8's failure mode is data loss (#899, #888 are its neighbourhood). A sweep that reports `removable=0` because it genuinely found nothing, and one that reports it because it could not look, are the same bytes. Nothing downstream re-derives either verdict.

## Done when

- [ ] `flow-worktree-sweep.sh` carries a `#: NEGATIVE-CONTROL:` directive, and its control has a known-bad case (a worktree that meets the removal conditions and must be reported removable), a known-good case (a live or dirty or unpushed one that must NOT be), and an anchor that misses the bad case. **CI has no `git`**: the control must declare `unavailable_signal` for the git-absent refusal, not go UNSIGNALLED or BLIND there (#1117).
- [ ] `lane-serveability-check.sh` likewise, with the case supplying a stub endpoint (no real model host), including a case where the endpoint answers but cannot serve.
- [ ] Each control's red run is stated in the PR: the anchor misses, and the current gate catches.

## Re-check trigger (recurring)

This issue closes when the two rows are controlled. The question behind it recurs: **on each Nit Store sweep, re-run `python3 scripts/check-negative-controls.py` and compare its "N of M enumerated instruments carry a control" line with the ADR 0008 class X and G rows.** Any class X or G row without a control is a new instance of this issue and gets filed the same way. As of 2026-09-26 the line reads "45 of 106".


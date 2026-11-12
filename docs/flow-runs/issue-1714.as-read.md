<!-- flow-run n=1 id=1581870015cd419aad4363f89b6bb557 -->
## Run 1 - issue #1714 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1714
- Read at:      2026-11-12T06:26:01Z
- updatedAt:    2026-11-12T05:36:32Z   (context only - moves on comments and labels)
- Body digest:  384ec79ed1e3f255dbb48d4e289687332369013a06bb6ae052146739813e3f75   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3004 of 3004 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 5 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
`/codex:code_review` has no path for a patch larger than Codex's 1,048,576-character input limit: the run exits 1 with an empty findings file, which the procedure then records as reviewer-unavailable for a reviewer that was available (hit on PR #1688). Also: the scope probe's file-selection pipeline takes SIGPIPE under pipefail on a large checkout, the mktemp templates put a suffix after the X run (not portable to BSD), and a lanes test uses `test -e`.

## Findings (5)
- [seq 609](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6439988246), 2026-10-27, low (estimated): codex/code_review.md probe-file selection pipeline gets SIGPIPE (141) under pipefail on large checkouts, forcing scope unverified. Status at origin/main `f63dc946`: .claude/commands/codex/code_review.md:372-375 still uses git ls-files -z | while ... break; done inside $(); under pipefail the producer SIGPIPEs.
- [seq 669](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6711969884), 2026-11-07, low (estimated): codex/code_review.md mktemp templates put suffix after XXXXXX, which BSD mktemp does not substitute. Status at origin/main `f63dc946`: code_review.md lines 118, 504, 508 still mktemp /tmp/...XXXXXX.md/.patch/.jsonl.
- [seq 719](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6804485828), 2026-11-11, medium (stated): codex/code_review.md pipes review-patch to codex exec; stdin over 1048576 chars refused, no fallback for large patch. Status at origin/main `f63dc946`: code_review.md still only says 'note it and proceed' for large diffs (L260); no input_too_large handling.
- [seq 728](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6807164910), 2026-11-11, medium (stated): /codex:code_review has no path for a patch over Codex input limit; would wrongly record reviewer-unavailable. Status at origin/main `f63dc946`: Duplicate of seq 719; code_review.md unchanged on large-diff handling.
- [seq 735](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6808699736), 2026-11-11, low (stated): code_review.md LANES_LINE uses test -e, so a dangling or unsearchable lanes.md reads as absent. Status at origin/main `f63dc946`: LANES_LINE block is not on origin/main (grep empty); belongs to unmerged #1695 (open issue, no PR). Cannot confirm; applies once that lands.

## Acceptance
- A patch over the limit takes a documented route (the reviewer reads the diff from the repository when scope is full) or is refused with a named reason, never recorded as reviewer-unavailable.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

Parent: #1690 (child of #1673)


<!-- end of body -->

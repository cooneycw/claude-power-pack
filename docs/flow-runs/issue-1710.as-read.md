<!-- flow-run n=1 id=1b19501ef6b54773bea326f187e6ab27 -->
## Run 1 - issue #1710 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1710
- Read at:      2026-11-12T04:31:36Z
- updatedAt:    2026-11-12T00:39:24Z   (context only - moves on comments and labels)
- Body digest:  cf3765d2a39c2eb5148f1385cfdd0fe9622c828636fbda609ed46a4c13d84e0b   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 6177 of 6177 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 12 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
The counter-model review rules contradict each other at the edges. A fix accepted from review needs a fresh review before the receipt is written, yet reviews are capped at two passes (three with a stated reason), so a finding accepted on the last allowed pass has no legal outcome: reported five times, including twice from this rollover's own parent work. The receipt writer also cannot record a review history that honestly exceeded the cap, refuses a Claude reviewer whose transcript names one model two ways, warns nobody when a review is launched in a mode that cannot produce a receipt, and sends vendored minified files to the reviewer in full.

## Findings (12)
- [seq 572](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6390186457), 2026-10-24, low (estimated): counter-model-receipt.py default-direction comment says Claude implements/Codex reviews only; stale since --implementer-thread-id. Status at origin/main `f63dc946`: Comment at scripts/counter-model-receipt.py:105-106 still says a missing direction means exactly Claude-implements, with no mention of the Codex implementer flag.
- [seq 578](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6395220551), 2026-10-25, low (estimated): counter-model-receipt fresh-flow attribution refuses a batched pre-begin git status only late, after implementation and reviews. Status at origin/main `f63dc946`: _flow_commands still refuses 'unsupported whole shell sequence' (counter-model-receipt.py:721) and no early diagnostic exists; #1633 only recognized Codex HEAD probes.
- [seq 608](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6429550780), 2026-10-26, low (estimated): counter-model-receipt cannot record an already completed review history above three passes. Status at origin/main `f63dc946`: PASSES_HARD_CEILING still rejects --passes beyond 3 (counter-model-receipt.py:2546, 3466). Policy question: truthful escalated record vs ceiling; unresolved.
- [seq 637](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6528081392), 2026-10-30, low (stated): counter-model-receipt.py review-patch sends vendored minified JS and source maps in full (1.48 MB). Status at origin/main `f63dc946`: _git_artifact (line ~1943) diffs merge-base to target with no path exclusion; only --no-ext-diff/--no-textconv flags.
- [seq 646](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6550762408), 2026-10-31, medium (stated): counter-model-receipt Claude reviewer refused as ambiguous when transcript has model name with and without [1m] suffix. Status at origin/main `f63dc946`: claude branch (~line 1580-1603) still adds model.strip() raw to set and refuses reviewer when len(models)!=1; no [1m] normalisation.
- [seq 664](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6708413744), 2026-11-07, low (stated): Fixing pass-2 counter-model findings forces over-cap third pass because receipt must bind a review of final head. Status at origin/main `f63dc946`: counter-model-receipt.py still binds to probed head and enforces PASSES_HARD_CEILING 3 (~2540); auto.md:746 still says never a third time. Same family as seq 664-666.
- [seq 665](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6708577953), 2026-11-07, low (stated): Duplicate of seq 664: head-binding vs 2-pass cap in flow:auto Step 6 costs an extra review pass. Status at origin/main `f63dc946`: counter-model-receipt.py still binds to probed head and enforces PASSES_HARD_CEILING 3 (~2540); auto.md:746 still says never a third time. Same family as seq 664-666.
- [seq 666](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6708801836), 2026-11-07, low (stated): counter-model-receipt refuses --passes 4 even with owner-requested --extra-pass-reason. Status at origin/main `f63dc946`: counter-model-receipt.py still binds to probed head and enforces PASSES_HARD_CEILING 3 (~2540); auto.md:746 still says never a third time. Same family as seq 664-666.
- [seq 689](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6729037123), 2026-11-09, medium (estimated): codex exec --ephemeral review runs cannot produce counter-model receipt; nothing warns at launch. Status at origin/main `f63dc946`: No mention of ephemeral in code_review.md or counter-model-receipt.py; only a measurement note records it.
- [seq 706](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6754669292), 2026-11-09, medium (stated): counter-model-receipt.py cannot record an orchestrator-authorised review pass beyond 3; only false count or false skip. Status at origin/main `f63dc946`: --passes hard ceiling still enforced (counter-model-receipt.py:3466); skip reasons closed set (codex-absent, reviewer-unavailable), no pass-ceiling reason found.
- [seq 732](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6808298233), 2026-11-11, low (stated): flow/auto.md Step 6: rules 1a (fix needs new review) and 1c/1d (no third pass) conflict when pass 2 yields a fix. Status at origin/main `f63dc946`: auto.md:699 and :745 still state both rules; no named outcome for accepted pass-2 finding.
- [seq 734](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6808650745), 2026-11-11, low (stated): /flow:auto Step 6 has no rule for a finding accepted on the second counter-model pass. Status at origin/main `f63dc946`: Duplicate of seq 732; same rule conflict still in auto.md.

## Acceptance
- `/flow:auto` Step 6 names what happens when the final allowed pass yields an accepted finding; the writer can record a true pass count above the cap with its reason; the listed identity and launch-time cases each have a test.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

Parent: #1690 (child of #1673)


<!-- end of body -->

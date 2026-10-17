<!-- flow-run n=1 id=1f6e64f429fc4dd88cc78d9f53aeb537 -->
## Run 1 - issue #1453 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1453
- Read at:      2026-10-17T01:42:36Z
- updatedAt:    2026-10-16T22:10:20Z   (context only - moves on comments and labels)
- Body digest:  f0583bb1e5f9782e67b043dc026082b743e915b07d0cf3a56ee7c6a86ee827e4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1643 of 1643 (cap 16384)

### Body as read
**Split from #1400 (bullet 5).** Refs #1400, Refs #864.

## Problem

A **Codex** implementer cannot record the documented `skipped / reviewer-unavailable` disposition. `counter-model-receipt.py write --status skipped --reason reviewer-unavailable` resolves the implementing session only from a Claude transcript (`_derive_implementer_from_session`, the `--claude-projects-dir` path). From a Codex session it exits 1: `missing implementer session id; supply --implementer-session-id or set CLAUDE_CODE_SESSION_ID`. That is the case where `codex exec`'s reviewer cannot start its app-server because its state directory is read-only. The generated `codex/skills/flow-finish` still requires the receipt, so an otherwise valid run cannot pass its own gate honestly (Nit Store comment https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5916393695, measured on kyle#1467 with CPP `785d7daa`).

## Why it is its own issue

It needs a design choice the receipt schema does not have yet. One option is implementer identity derived from a **Codex** thread, with transcript-backed evidence mirroring `_derive_reviewer_from_exec_log`. The other is a harness-neutral "identity unavailable" disposition that the schema validates explicitly. Either way, supplying another session's Claude identity, or inventing one, must stay impossible.

## Acceptance

- A Codex implementer can write `skipped / reviewer-unavailable` with an identity a later reader can re-derive, or with an explicit, validated `unavailable` identity.
- A red test: the current writer refuses that case, and the fix records it without loosening any `ran` receipt rule.


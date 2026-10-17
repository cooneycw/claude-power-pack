<!-- flow-run n=1 id=f74776ffd9c348809b872cb96896d22b -->
## Run 1 - issue #1454 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1454
- Read at:      2026-10-17T02:39:23Z
- updatedAt:    2026-10-16T22:10:21Z   (context only - moves on comments and labels)
- Body digest:  63c18f64357a2ed35a80cd6fd661efc563c02c5552fe2fd0b4128a8d71cfdbc1   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1317 of 1317 (cap 16384)

### Body as read
**Split from #1400 (bullet 6).** Refs #1400, Refs #864.

## Problem

The delegated lane's receipt (`--implementer-exec-log`, #1383) derives the implementing model only from a **Codex** `--json` stream's `thread_id`. `/qwen:auto` writes Qwen Code `stream-json`, and `/gemma:auto` writes OpenCode `--format json`. Neither names a Codex thread, so the writer refuses with "implementer exec log ... contains no thread_id". `flow-finish-gate.sh` then reports the counter-model line as `missing` on two of the three delegated lanes, and `templates/delegated-driver-values/{qwen,gemma}.md` forbid working around it (Nit Store comment https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6015312211).

## Why it is its own issue

It starts with a measurement no one has made. Where does each harness's stream declare the model that ran (Qwen Code's system/init event, OpenCode's session metadata), and can it be ambiguous? That needs real captured streams from each harness, not a guess at their shape.

## Acceptance

- One captured, committed stream per harness, and a per-stream-type derivation that refuses an ambiguous or undeclared model, following the `rollout_turn_model` pattern.
- Evidence recorded on the receipt that a later reader can re-derive.
- A red test per harness on the current writer.


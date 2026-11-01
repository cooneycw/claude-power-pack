<!-- flow-run n=1 id=b29cb7484af94828828e9550ec5c53f3 -->
## Run 1 - issue #1615 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1615
- Read at:      2026-10-31T23:37:14Z
- updatedAt:    2026-10-31T23:25:01Z   (context only - moves on comments and labels)
- Body digest:  9c396854f2009b05ff5f20b529486ae77a74d6a6124f2d8783cd555948daa0b5   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2156 of 2156 (cap 16384)

### Body as read
**Blocks now:** kyle PR #2056's finish gate fails only with `counter-model line missing` (all 14639 unit tests pass, PR CI green, and the Codex review ran clean). No receipt can be written for that review, because of the defect below. Promoted from the nit store: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6550051047


- File: `scripts/counter-model-receipt.py`, the claude-runtime branch of implementer/reviewer evidence resolution (~line 1545, the `model.strip().startswith("<")` check inside the per-record loop).
- What's wrong: the loop `raise`s `EvidenceUnknown("contains no real-shaped model entry ...")` on the **first** assistant record whose model is a sentinel. It doesn't skip that record. A long Claude Code session routinely carries one harness-synthesised assistant record (`"model":"<synthetic>"`, for example an API error or an interrupt notice). Measured on a real transcript: 1332 records of `claude-opus-5-5` (plus 2 of `claude-opus-5-5[1m]`) and 1 `<synthetic>`. Every `write` then fails with `COUNTER_MODEL_EVIDENCE: UNKNOWN`, even with `--implementer-session-id` omitted (the session is auto-discovered). No receipt is written.
- Why it matters: a review that ran clean, from a different model (codex/gpt-6.1-sol), can't be recorded. The message ("contains no real-shaped model entry") is false for this transcript. It reads as if the transcript were empty or forged, and it pushes callers to skip the receipt, which is exactly the "review happened but is uncounted" class #934 exists to prevent. The docstring of `_eligible_assistant_model` says sentinel handling is the caller's job, so the intended behavior looks like skip-then-require-at-least-one-real-model.
- Suggested fix: `continue` on sentinel or blank models, and raise only when `models` is empty after the loop (the existing post-loop check already covers that). Red case: a transcript with N real assistant records and one `<synthetic>` must resolve, and a transcript with only `<synthetic>` must stay UNKNOWN.
- Found while: recording the counter-model receipt for cooneycw/kyle PR #2056 (#1163 step 2a), from the kyle-lock-orch session.


<!-- end of body -->

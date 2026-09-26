# Issue #1226 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1226
- Read at:      2026-09-26T12:11:25Z
- updatedAt:    2026-09-23T17:12:16Z   (context only - moves on comments and labels)
- Body digest:  1f87fd89998cd52b260b898a0dd77980766c86b436da243b4045a6af380b9173   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2974 of 2974 (cap 16384)

## Body as read
**Record issue** per the owner's 2026-09-23 ruling. Found by the counter-model review of the S4 run record (PR #1225), reported by worker-BB as a residual on its way out, and verified independently before filing. Nothing is broken on the current tree — the **claim** made about the tripwire is wider than the tripwire.

## The defect

The resync tripwire shipped in #1218 recognises an invocation only when the stripped line is **exactly**:

```python
# tests/test_codex_skill_resync.py:274
if ln.strip() == "bash scripts/codex-skill-resync.sh"
```

String equality. So an invocation spelled any other way — `bash scripts/codex-skill-resync.sh --quiet`, or the same call with a trailing comment — matches neither the gated list nor the ungated one, and the walk is **silent** about it.

## Why that matters more than it looks

#1218's whole point was the third state: a fence walk that could not parse a region returned `[]`, **byte-identical to "examined and found nothing"**, so the repair made the unparseable case report as `UNEXAMINED` rather than clean.

That repair fixed **parse** blindness. It did not fix **recognition** blindness. An unrecognised spelling does not reach the unexamined list — it collapses straight back into the two-state silence the third state exists to prevent.

So the instrument has the defect it was built to remove, one layer in, in the fix for it.

## Current tree is correct; the claim is not

All three shipped call sites use the exact spelling:

```
.claude/commands/flow/auto.md:1056     bash scripts/codex-skill-resync.sh
.claude/commands/flow/auto.md:1882     bash scripts/codex-skill-resync.sh
.claude/commands/flow/finish.md:93     bash scripts/codex-skill-resync.sh
```

So the tripwire is right about today. The run record's claim that it *"reconciles against every invocation"* is what is false, and a future call added with a flag would be invisible with nothing reporting so.

## Fix

Match the invocation by its **script**, not by its whole line. Then any spelling — flags, comments, redirections — is recognised and lands in the gated or ungated list rather than escaping both.

## Acceptance

1. An invocation with a trailing flag is recognised and classified.
2. An invocation with a trailing comment is recognised and classified.
3. A line mentioning the script that is **not** an invocation is not misclassified as one.
4. Red on today's tripwire for (1) and (2) — they currently escape both lists silently.

## Do not lose this alongside it

The same review found that *"called unconditionally"* in the S4 record omits a **deliberately retained** `[ -x scripts/codex-skill-resync.sh ]` existence guard. It is there because these commands run in repositories carrying neither the helper nor the generator, where a bare call dies at 127 before the helper can report its own `unavailable`. **A reconstruction reading "unconditional" literally would drop it.** Verified present at all three sites; keep it.


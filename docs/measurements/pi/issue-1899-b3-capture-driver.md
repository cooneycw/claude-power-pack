# Pi #1899 B3 capture-driver controls and native-layout stop

Status: historical native-layout stop and conditional v2 disposition. The later
[driver export/T2 verification/T3 observation](issue-1899-b3-progress.md)
supplies v2's full hash, committed replay inputs and verified pair. Refs #1899.
No additional model prompt is authorized by this evidence note.

Sources: orchestrator message 42546; master messages 42552, 42555 and 42563;
protocol-author replies 42575, 42579 and 42581. All observations are attributed;
this author has not opened the driver files or host captures and ran no pi.

## A disposition and correction of sequence wording

The orchestrator endorsed A: T1-beta stays LOST/UNEXAMINABLE, without an
absence pass or retry. The budget books its unknown round conservatively as
one, while actual reporting distinguishes known from assumed/unexaminable.
Before T2, this was one known plus one assumed round, actual interval 1-2.
Master routed this disposition and zero-model capture controls as K772.

The corrected driver is a HOST HELPER change, not a modification of the
executed CPP probes. Record its exact revision/hash and application time.
The v1 controls preceded T2-alpha; the report arrived at 15:32:49Z on
2026-11-27, but an exact application timestamp was not supplied. The v2 ruling
is K774, reported at 15:34:06Z; this is not a supplied v2 execution timestamp.

IMPORTANT correction: the author's earlier mailbox shorthand T2-T16 was
wrong, carried over from B2, and was repeated in the routing relays. The
committed B3 matrix always has EIGHT paired states, T1-T8, sixteen prompts.
After recording/verifying the already completed T2-alpha, NEXT is T2-beta,
then T3-alpha/beta through T8-alpha/beta. T2's stdio-direct config is retained
until its beta session; audit/set-foreign happens after the pair. No T9-T16
states are introduced. No skipped beta or extra prompt is assumed completed.

## v1 inputs and reported zero-model controls

| Helper artifact | Master-reported SHA256 |
|---|---|
| classify.py v1 | fb05b40a71f47881ef46daa72c88b38783952bd3940845184eade58f0f5556d5 |
| run.sh | ef108db64dc3ffe84c5e26c824870cc2129d9ecf5c9958a4bc12939c46cf2005 |
| record.sh | bf4aca7604424f80a25c97dd8456ec1f0738fcd02def1e04193c6e4f246a3c05 |
| start.sh | Prefix only: 23da263e |
| close.sh | Prefix only: a6b2d9af |
| launch-alpha.sh | Prefix only: d08f4360 |
| launch-beta.sh | Prefix only: faedea9e |

Master reported ACCEPT required prompt echo, input separator, cwd and idle
footer, no busy/spinner indicator, a changed footer up-arrow token counter,
and nonempty text after the prompt and last recognized tool line. run.sh
waited up to 180 seconds for four consecutive identical ACCEPTs; timeout kept
pi open and its capture intact. record.sh performed record-reply, then a
receipt/reply hash, sync, verification and only then capture deletion.

| Synthetic input | v1 result reported by master |
|---|---|
| New completed reply | ACCEPT |
| Final answer after a synthetic tool line | ACCEPT |
| Empty | REFUSE, empty capture |
| Stale footer | REFUSE, stale footer |
| Spinner | REFUSE, busy indicator |
| Synthetic tool event without final answer | REFUSE, tool-call phase |
| record.sh with no accepted reply | REFUSE; log KEPT |

These used ZERO provider-model turns. The stated limit was material: the v1
tool matcher assumed an mcp__cpp_pi1899_ identifier, while native pi tool-event
layout had not been observed. Master required visual review of T2-alpha and
a stop on mismatch before recording. A synthetic pass did not establish
support for an unseen native layout. Materialized-input commit bindings and
original files were not included in the relay; their preservation remains
required, not asserted complete by this note.

## Actual native T2-alpha observation

Master reported the saved screen contained, in order:

1. cpp-pi1899-stdio/probe-echo tag="T2-alpha" as the tool header;
2. a tool result with the payload below;
3. a distinct final answer with the same payload.

```json
{"nonce":"d4f91e39b9057da0558173b4d958470d","tag":"T2-alpha","transport":"stdio"}
```

The footer showed up-arrow 1.1k and down-arrow 144. Master counted one prompt
and TWO response rounds. Pi exited 0; the controlled pane log was retained,
with only capture-hash prefix afa2819c supplied. The fixture log reportedly
contains exactly one peer=pi tools/call for T2-alpha, its response, and child
PID 3994665 start/initialize/stop records. Recording FINAL-only and the call
verifier outcome remain pending in this receipt; no missing verdict is invented.

Pi's UI displays server/tool here, not the literal mcp__ identifier expected
by the v1 capture matcher. Record that DISPLAY observation for #1902. It does
not independently expose the model-facing/internal identifier. Its normalization
remains a source premise unless separate permitted metadata establishes it;
the prompt's expected identifier or assistant prose is not native-name evidence.

Master reports v1 would recognize zero tool lines in this actual layout and
would accept a tool-phase-only screen. This is an identified classifier gap;
an actual old-v1 red execution on the committed real-layout input is required
before calling it a demonstrated regression result. That execution result was
not yet included in the report. The visual gate caught the unsupported layout
before recording it as a final reply.

## Scoped v2 disposition and remaining controls

Master's K774 ruling recognizes headers matching
^cpp-pi1899-(stdio|http)/probe-echo, the following result, and only accepts with
a distinct final line after that result. It requires rerunning the prior six
classifier controls plus native-layout header/result-without-final and
header-without-result refusal cases. The author affirmed recovery of FINAL
only from the retained T2-alpha capture without any new prompt, conditional
on those controls and exact v2 source binding.

The author additionally required a TWO-tool-attempt native-layout case to
stop/refuse even with a later final answer, preserving the existing one-call
cap. If fixture evidence shows a matching pi call but the UI parser recognizes
zero tool events, stop instead of classifying a no-tool final. Wrapping or
another unsupported layout remains unexaminable, not automatically acceptable.
Keep the log until durable reply, verifier outcome and hashes exist.

Commit the exact control inputs and retain old/new driver hashes; a private,
fixture-only commit is sufficient before reviewed sanitized derivatives are
exported. Never stage an entire probe/agent tree or credentials. These are
load-bearing capture controls read by other sessions under the standing
negative-control rule. The note does not claim those commits or v2 runs exist.
No history, stored transcript, model-store or authentication-file access is
authorized to repair the capture or recover T1-beta.

## Current accounting snapshot

Three prompts have been sent: T1-alpha, lost T1-beta and T2-alpha. Known rounds
are three; the lost beta contributes an unexaminable 0-1. Actual total is the
interval 3-4; conservative admission books four, meaning three known plus one
assumed/unexaminable. Thirteen prompts remain, at most 26 additional rounds,
for upper bound 30 within the approved 16-prompt/32-round caps.

Saved-capture processing and synthetic controls add no provider-model turn.
Retain this interval in later totals; do not convert it into an exact actual
count. T2-beta and later rows are not measured by this note. No completed B3,
full normalization result or B4 identity claim is made.

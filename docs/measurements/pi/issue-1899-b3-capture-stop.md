# Pi #1899 B3 T1-beta capture loss and scoped disposition

Status: historical T1-beta stop; scoped continuation A required capture controls.
The subsequent [driver-control and T2-alpha receipt](issue-1899-b3-capture-driver.md)
records the next native-layout stop. No completed B3 result is claimed. Refs #1899.
Source: master's mailbox message 42542, with the protocol author's reply 42550.
These are attributed reports; the author did not inspect host artifacts or run pi.

## Executed source and retained state

Master reports K769 executed the reviewed source
d9c511c153f91371328d5e0a51f4bfb6bf68af87 with matching input hashes:

| Input | SHA256 |
|---|---|
| Command file | 904a46386961b8e99725a9c7129917de1e3e8acb7663076716a0a1d4bd613473 |
| Probe helper | fa5e584576f7556a18436908ea38f216db0a4afb2554c098bb71d84f758bfbe2 |
| Server fixture | 8fcc97d88f9f74b863676330c40664761ad520a36df0b1a7cae0f969c77a9b3e |

Python was 3.12.3 and pi 1.6.0. The regular-agent name summary before B3 was
stable; private count/digest pairing is omitted. Preparation exited 0 with
foreign-only config and foreign_preserved=true. Only digest prefixes were
supplied: config 01d89db1 and synthetic foreign entry 8c49d4de. Full digests
remain pending, not reconstructed here.

The HTTP fixture was reported still running, PID 3943054, bound only to
127.0.0.1 at port 33161. It has not been described as torn down. Both stdio
and HTTP compatible-client controls exited 0 with compatible_call=true.
These calls do not count as native pi calls or provider-model rounds.

At the stop, config remained foreign-only, with no stdio child or pi window
open. The original HTTP instance, model pin and evidence remain retained.
No reset, reprepare, model re-resolution or server restart is authorized by
the continuation disposition.

## Observed and lost rows

T1-alpha: the pin and model-only footer matched. The controlled reply was
TOOL_UNAVAILABLE, no tool event was reported, and usage was one prompt/one
round. Pi exit 0, record-reply exit 0, and the stdio verifier exit 1 was the
expected no-verified-call result. This is bounded native absence evidence;
the compatible-client positives remain separate.

T1-beta: master reports that the prompt was sent once and pi exited 0, but the
capture driver returned EMPTY after already deleting its pane log. No reply
survived. record-reply and verify were NOT run. The response and its zero-or-one
rounds are UNEXAMINABLE. It is not an absence pass, not an empty assistant
answer, and not an inferred TOOL_UNAVAILABLE. Native MCP calls were reported
zero; beta's missing response/tool-display evidence is not invented.

The driver deletion is a disclosed evidence-retention failure. The probe helper
correctly received no fabricated reply and no verifier result was substituted.
The stop complied with the handoff's unexaminable-round rule. Neither transcripts
nor history/store inspection is authorized to recover the lost response.

## Scoped continuation A and budget accounting

The author selected A in response to master's explicit a/b/c request:
retain T1-beta LOST/UNEXAMINABLE and continue at T2 only after zero-model
capture controls. Do not retry T1-beta or introduce a new tag/prompt for it.
T8-beta, if later observed, is independent final absence evidence and cannot
retroactively turn T1-beta into a pass. This is not a blanket permission to
ignore future unexaminable rows; another stop returns for disposition.

| Usage | Disposition |
|---|---|
| User prompts already used | 2 |
| Known response rounds | 1 |
| Additional unexaminable rounds | 0-1, as reported by master |
| Actual round count so far | Interval 1-2; exact total unknown |
| Conservative cap admission | Book upper bound 2, without calling it actual |
| Remaining matrix | 14 prompts, at most 28 additional response rounds |
| Overall resulting upper bound | 16 prompts and 30 response rounds, within 16/32 caps |

Final reporting must add later observed usage to this unresolved interval,
retain the unknown component, and include all stopped attempts. It must not
report exact actual usage from a cap, a conservative booking or tool-call counts.

## Capture controls required before continuation

Footer change alone is insufficient: a tool-call phase can precede the final
assistant answer. The driver must wait for the controlled turn's final/settled
idle state and retain that per-launch controlled capture until record-reply,
the verifier outcome and artifact hashes are durable. Retention covers only
new fixture activity, never login, unrelated terminal output or session history.

Before consuming T2, master must retain the exact fixed-driver bytes/hash,
commit materialized control inputs, and provide a zero-provider-turn receipt:

| Control input | Required result |
|---|---|
| Known new, completed reply with completion/idle evidence | Capture the exact reply and count its observed rounds |
| Empty capture | Unexaminable; no record-reply/verification success |
| Stale reply/footer from the previous state | Refuse it as a fresh row |
| Footer/tool phase changed while final reply is unfinished | Wait/refuse completion, not a final-answer verdict |
| Completed capture before durable recording | Preserve it until durable reply and verifier evidence exist |

These are required controls, not results claimed by this note. No paid model
turn is needed to exercise synthetic capture inputs. A rewritten instruction
or reread of the driver is not a demonstrated control. If the fixed capture
cannot satisfy them, remain held or use the already reviewed guarded teardown;
do not spend an extra prompt, discard more evidence or fabricate an actual count.

After controls succeed, use the retained instance and existing compatible
controls, then unchanged T2-T8 with the same pin/footer rule and no retries.
Actual continuation source, driver/control receipt hashes, commands/exits and
artifact identifiers must join the final provenance. The original execution
remains bound to d9c511c1 plus this explicit scoped disposition; later docs are
not silently presented as executed code.

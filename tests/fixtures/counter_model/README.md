# Counter-model review fixtures (issue #934)

**These are RECORDED transcripts from a real reviewer, not hand-written
imitations.** `defect-present` and `defect-removed` are the same nine-line file
reviewed twice by `codex exec` on 2026-09-15 (first recorded as gpt-5.5; the run is attributed to gpt-6-astra by `docs/measurements/counter-model-reviewer-attribution.md`, #1272) - once with a seeded
defect and once without. The reviewer named the exact seeded bug in the first
and returned the prescribed clean statement in the second. That pair is
acceptance item 1 of #934: a stage wedged at "findings" and a stage wedged at
"clean" each pass one half of it, and only the pair separates them.

`real-multi-finding.review.md` is the genuine first-pass review of PR #1000
(issue #936), kept because it exercises several severities and a much longer
body than a constructed sample would.

**Why recorded and not live.** Neither `codex` nor `git` is in the CI image
(`CI_IMAGE_BINARIES` in `scripts/check-test-binary-guards.py`), a live call
costs the user's quota, and the reviewer is not deterministic across runs. What
CI can and does check is the STAGE's handling of a reviewer's output; the
reviewer's own judgement is exercised here once, recorded, and re-read. That
limit is real and is stated in ADR 0007 rather than implied.

The degenerate three are the cases that must NOT read as clean:

| fixture | what it is | required verdict |
|---|---|---|
| `absent.review.md` | the reviewer produced nothing | `unparseable` |
| `truncated.review.md` | cut off mid-finding | `unparseable` |
| `prose-only.review.md` | replied, but not in the contract's shape | `unparseable` |

`bullet-shape.review.md` is the fourth outcome (issue #1259): a review that
HAPPENED, with real severity-bearing findings, written as `- **MEDIUM - file:line**`
bullets instead of `### [SEVERITY] title` headings. Required verdict:
`format-mismatch` - never `unparseable`, which step 1c records as a skip.
**It is RECONSTRUCTED, not recorded:** the #1056 transcripts were not kept, so it
restates that run's four findings in the bullet shape the Nit Store report
(#864, comment 5741945325) quoted. It pins the SHAPE, not a reviewer's judgement.

All three contain zero finding headings, which is byte-identical - to anything
counting headings - to a review that found nothing wrong. They are the reason
`parse_review` has three outcomes instead of two.

`codex-unframed-user.constructed.json` is constructed from the #1600 measured
shape, not a captured runtime record. The issue's native Codex CLI 0.164.0
reproducer measured one raw input_text part: 71,153 bytes, SHA256
`cdd5ce4e8e05457e6edbcf57b5f4daa22b4c22e6b284ebb7761e343c55869c5e`.
The fixture substitutes an owned test repository's canonical patch. It pins
whole-input matching, strict negative cases and input chronology; it does not
claim that the constructed session is a live review.


`codex-unframed-user.captured.json` retains the genuine Codex CLI 0.164.0
USER-record envelope published in #1600, comment 6476347572. The source author
replaced only the canonical patch text with its size/hash placeholder. This
redacted envelope is not an original rollout or a substitute review transcript.
Tests substitute the owned repository patch into that one text part; all other
record fields remain captured. The constructed fixture above stays separately
labelled, and both envelopes exercise the same acceptance and refusal cases.

The original record excluding its terminating LF was 75,379 bytes, SHA256
`906703a1ead14a82adc2f19697f69b83df91e10d9c9dbe0215bf792d0d55c4a1`.
That original-record hash is reported source provenance, not the redacted file's
hash. The committed redacted fixture SHA256 is
`9fd11749fb67d464a54bc78f62dbb8992da52e6b386936d72d5b2003104cbb26`.
Its documented 71,153-byte patch hash was independently reproduced using
`review-patch --base 802a140af93d4b865d928903014cd91f55b49827 --head 1a887a66702d56a89759fbd7d4597ce054ac94e3`.
The unchanged original-rollout writer repro succeeded at 3479ef4b; see #1600,
comment 6476694221. That upstream repro is separate from these owned controls.


`native-codex-head.json` is a sanitized actual Codex CLI 0.164.0 native event,
captured during #1584 through `functions.exec` calling `tools.exec_command`.
Its command, argv, successful exit code, output, event envelope and parsed
command are preserved. Timestamp was removed; command id, process id, cwd and
duration were normalized. It is execution-format evidence, not a review.
Source thread: `01a17ccf-39dc-7a52-b013-482c0a8cbc5c`, record line 12687;
original record SHA256:
`1c800ddd7d017a57f7cac13998f9c115eb7429f163059f4ce201c3942f3944a7`.
A bounded prefix of that own rollout (32991633 bytes, SHA256
`f9db7dca77df14c9a6223d55afdec52af5e22b48780e5a287cd46040578d2454`)
contained 1190 CommandExecution events and 1159 custom `exec` calls, including
two successful exact HEAD probes. The retained shell event is already supported;
this observation does not establish every installed runtime's serialization.

The paired controls require extraction of the captured successful result and
refusal when its exit is failed, missing or textual. The writer integration
adapts only the captured output SHA to an owned temporary Git repository,
combines it with explicitly synthetic identity/model/report evidence, and
requires successful write versus refusal on an exit-code mutation. No textual
shell-result parser or wrapper-JavaScript parser was added on speculation.

`codex-custom-exec.captured.json` is a real call/result pair captured on
2026-11-08 from this worker's current Codex rollout while investigating #1624.
The `source_record_sha256` values identify the original JSONL records without
terminating newlines. The retained shape is `response_item/custom_tool_call`
with name `exec`, directly emitting an awaited `tools.exec_command` result;
the linked `custom_tool_call_output` contains the completed-script header and
structured shell result. This source rollout also contains a corresponding
CommandExecution event; the fixture isolates the custom call/result pair to
exercise the serialization reported by #1624. Cwd was replaced with
`/fixture/repo`, call/item ids were
normalized, and timestamps, ordinals, internal metadata and transport metadata
were removed. Command, JS structure, output blocks, exit code and HEAD are
preserved. There are no credentials or private host names in the fixture.

Writer controls replace only the shell output HEAD with an owned temporary
repository's HEAD and add synthetic identity/report records. They require a
full-scope write on the matching probe and refusal for an absent probe, a foreign
head, failed/unlinked calls and prose or nonexecuting JS examples. Additional
controls pin successful integer exit codes, result ordering, duplicate pending
ids and unmodified direct output. These test evidence extraction, not model
review quality. The supported JS grammar is deliberately bounded to a single
`text(await tools.exec_command({...}))` call with JSON values and optionally
unquoted object keys; other programs remain unknown rather than guessed.

`codex-custom-exec.schema-0.166.json` is an explicitly constructed custom-only
rollout fragment, not a capture of the 2026-11-04 host review. Its response-item
schema comes from Codex tag `rust-v0.166.0`, commit
`6ff1e1ca3b30fc8b914720681fcf5fe62e95f856`:
[ResponseItem and output body definitions](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/protocol/src/models.rs).
`ResponseItem` uses snake-case `type` tags; `CustomToolCall` carries string
`call_id`, `name` and `input`, while `CustomToolCallOutput` carries `call_id`
and `FunctionCallOutputPayload`. `FunctionCallOutputBody::ContentItems` permits
the output content array. These response items are independent variants; the
schema does not require a native CommandExecution event alongside them.

The direct JavaScript/structured-result transport is based on the separately
retained real 0.164.0 capture above. Optional response ids/status/metadata were
omitted, the command argument key is quoted, and shell output is an owned
40-character test HEAD. The fragment contains only the custom pair and no
native event or assistant prose. Writer cases supply synthetic identity/report
records and adapt the output to their owned repository. Missing probes and
foreign heads are committed refusal cases for both captured and schema-derived
inputs; existing native-event controls remain independently exercised.

Version distinction: #1605 records Codex 0.166.0 on the operator's host; these
containers run 0.164.0. The whole 0.164.0 interactive and EXEC rollouts retained
native events readable before the fix. The root cause of the reported 11-04
host refusal is therefore INFERRED from the custom-only blind spot, not
reproduced from that original rollout. Per the owner ruling, #1624 reopens if a
host review is refused again. The schema proves format support, not what that
host persisted or a version-specific omission of native events.

`claude_independence.json` is a constructed identity-pair matrix (#1747), not
captured runtime evidence or an alias table. Its six refused pairs and six
accepted pairs exercise write-time, schema-5 and legacy comparisons separately.
A single leading `claude-` difference is insufficient evidence of independence;
these cases do not assert that the two spellings are the same model. Tests build
owned runtime-shaped transcripts from the pair, and separately mutate valid
schema-5 and historical schema-1 receipts. The accepted cases preserve distinct
models, a Codex reviewer, context-tag behavior and the narrow prefix boundary.

`enrolment_cases.json` contains constructed #1765 enrolment inputs and expected
answers, prepared before the replacement parser. The integration test creates
owned Git histories and no-op quality targets, and invokes the actual gate in
finish and enrolment-only modes. It can select main or the held reference by
explicit test-only gate/helper paths. The held attempt is read as reference,
never imported into shipped product code. Red measurements distinguish parser
refusals from the preservation cases; negative fixture preconditions establish
unreadable JSON, absent Git objects/helpers, and the blind-helper exit before
the gate is blamed.

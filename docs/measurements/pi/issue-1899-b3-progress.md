# Pi #1899 B3 verified stdio pair and default-exposure observation

Historical progress record; current [stopped results](issue-1899-b3-results.md)
include quota stop, final cleanup and unresolved acceptance gaps.

Status: T2 alpha/beta verified by master; T3-alpha stopped with no visible
reply. B3 is not complete. Sources: orchestrator 42566/42585 and master
42573/42582/42586/42613 on 2026-11-27; protocol-author ruling 42597. This author
did not run pi or inspect the real probe/pane captures.

## Driver export and proof boundaries

The supplied [frozen driver and controls](issue-1899-b3-driver/README.md) are
now retained for replay. The author independently matched drv2.tar SHA256
0f89803dcfb8f6a9a36f52b14a3c0c38f06350761a8dde6c464e14fa0df2d040
and all 22 member hashes before preserving their bytes. Account paths were
already replaced by the exporter; no real pane, probe stores, credentials or
persisted pi session file was included. The archive export and local replay
are independently examined; host observations below remain attributed.

The complete classify-v2 SHA256 is
bdf986dc8dd0dd92e1288633a53f75a02dd9bfc2d2c580b4b8f8c2517c979dce.
The mandatory cap-wrapper session.sh SHA256 is
f82e2f68a690a6497c25b8c661cb28d65b5ad35f6f34fbaa493eb504ffbdcafd.
v2 applies from T2-alpha's saved FINAL-only recording onward, per the export
manifest; v1 handled that capture earlier. Exact application wall times remain
unprovided rather than inferred from later message timestamps.

The authoritative live-call verdict remains the committed probe's nonce/tag/
batch-bound events.jsonl request and response, process/initialize binding and
controlled reply. The classifier only finds the final reply line. Any screen/
event disagreement stops. The UI's server/tool label is not proof of the
model-facing mcp__ identifier; that question remains separate for #1902.

## T2: direct stdio, both repositories

Master reports v2's old and new layout controls completed, including refusal
of real header+result without final, header only and empty/stale/busy cases.
The old synthetic 1b is now refused as a result without a distinct final;
native-layout case 7 supplies the valid completed positive. Local archived
replay independently reproduces the supplied leaf-verdict matrix.

| Row | Reported host evidence |
|---|---|
| T2-alpha | Saved capture prefix afa2819c; FINAL-only record exit 0; reply hash prefix a1ec9b33; verifier exit 0, verified_pi_call=true |
| T2-alpha server | peer=pi, probe-echo, tag T2-alpha, nonce d4f91e39b9057da0558173b4d958470d, PID 3994665, request_id 3 and matching response |
| T2-beta | Two observed rounds/one tool event; reply nonce prefix 25416862; verifier exit 0, PID 4007345; pi exit 0 |
| Pair controls/undo | control-stdio AFTER exit 0; audit exit 0, foreign preserved; set foreign exit 0 |

The pair establishes reported native stdio call round trips in both scratch
repositories. T2-alpha was recovered from its retained capture without another
prompt. Full beta nonce, reply/capture hashes and source artifact identifiers
remain pending; prefixes are not promoted into full digests. Both model-facing
identifier normalization and authenticated runtime identity remain unproven by
these display/fixture observations.

## T3-alpha: omitted exposure in the restricted lane

Master reports control-stdio BEFORE exit 0, then stdio-default configuration
exit 0, config-hash prefix 5045ea53 with the foreign entry preserved. This
omits exposure, whose documented default is codemode. The launch still restricts
--tools to mcp__cpp_pi1899_* and excludes indirect mechanisms.

The prompt was sent once with matching pin/footer. After 180 seconds v2
refused no-reply-after-prompt. The visible screen contained the prompt echo,
then no visible answer, then the idle input box. The footer changed to up 482,
down 56, displayed cost $0.002. Master booked one observed response round.
The display-only tool-output expansion reportedly showed no additional output.
No underlying API message content or cause is inferred from that UI operation.

The fixture recorded stdio child PID 4011874 start and initialize with peer pi,
and NO tools/call. No extra tool attempt was visible. The helper could not
record-reply from an empty visible result; no verifier outcome is invented.
This is NO VISIBLE reply in this lane, not a fabricated TOOL_UNAVAILABLE or
an examined empty API/transcript message. Exact initialization-versus-model-
request timing was not supplied.

The helper's proposed cause, an attempted disallowed tool call silently dropped
by pi, remains an UNVERIFIED HYPOTHESIS. Transcripts are not authorized to
confirm it. For #1902 the unresolved observation is: default exposure under
this restricted --tools lane produced one observed round with no visible reply,
server initialized and no tools/call. It does not prove that default exposure
is generally broken or establish why the UI was empty.

## T3 disposition, cap ownership and current accounting

The author chose A with the orchestrator's read-only preservation step: one
as-is capture of the CURRENT controlled pane's full scrollback and full hash,
then Ctrl+D, no new prompt or unrelated UI/history/store inspection. The
master subsequently reported the 100-line full scrollback saved before close,
SHA256 5c528a20c86092a4f609f025ce903ed89ece69501b7f624ff25b60f5e823c2d0.
Ctrl+D exited 0; PID 4011874 stopped on pi exit, with no tools/call or stray
child. No record-reply was made; the verifier is unrecordable. These are
attributed receipts, not independent capture inspection. Retain the
visible-empty observation and unrecordable reply/verifier scope honestly.
T3-beta may proceed only after the committed driver/cap controls; a repeated
pattern would be consistency, not cause. Another divergent/unexaminable result
returns for disposition, without an automatic retry or fabricated reply.

The author accepts the cap at session.sh, not in classify-v2 alone. Exact
wrapper replay with real archived v2 classifying case 10 exits 6 BEFORE either
close or record collaborator is invoked. The completed one-tool case 7 exits
0 and invokes both trace-only stubs. The archived-v1 replay fails those refusal
assertions; this is a synthetic predecessor composition, not a claimed past
host deployment of that combination. Native tool-phase case 9 also demonstrably
runs ACCEPT under archived v1 and REFUSE under v2. All inputs and bytes are
committed; the local replay uses no tmux, pi, provider or owner data.

Mandatory conditions: use the wrapper for subsequent turns; keep captures on
STOP; reject more than one recognized tool attempt; stop on backend-call/zero-
screen-event disagreement or unsupported layouts. Do not treat its heuristic
ROUNDS echo as an independently measured actual count for stopped/ambiguous
turns. The protocol ledger retains observed rounds and unknown intervals.

At this receipt five prompts were used. Known rounds total six: T1-alpha one,
T2-alpha two, T2-beta two, T3-alpha one. Lost T1-beta adds an unexaminable 0-1.
Actual total is 6-7; conservative cap admission books seven, meaning six known
plus one assumed/unexaminable. Eleven prompts remain, at most 22 additional
rounds, giving overall upper bound 29 within the approved 16/32 caps.

No further model turn, complete B3 result or B4 identity evidence is claimed
by this note. The recorded HTTP instance stays retained; no restart, reprepare,
model re-resolution or new owner budget is requested.

## T3-beta and count-crosscheck update

Master 42671/42679 reports T3-beta ran once under the bound session wrapper:
matching pin/footer, explicit TOOL_UNAVAILABLE accepted after seven seconds,
zero screen tool events, one observed round, pi exit 0, record-reply exit 0
(reply hash prefix 5fc4e967), verifier exit 1 NO VERIFIED CALL. The stdio
child initialized as peer pi, then stopped without tools/call. Capture was
saved and the pane log deleted only after durable recording. This author did
not inspect the real capture. Alpha remains visible-empty/unrecordable; beta
has an explicit reply. Both have the reported no-call fixture outcome. This
pair does not establish why the visible outputs differed or examine API content.
Master authorized zero-model control-AFTER, audit and undo; completion receipt
is pending. No repeat prompt or causal investigation is requested.

The newly supplied crosscheck v1 had unsafe missing-accept and batch behavior.
Its old AGREE receipts are historical, unbound counts. The frozen v2 and all
control inputs are retained in the driver directory; safe local tests show
four refusal/binding assertions fail under v1 and all 36 capture/crosscheck
cases pass with v2. Lint passes. A zero-model v2 recheck of retained T2-alpha,
T2-beta and T3-beta was requested before continuing T4. Require AGREE for
future recordable rows in addition to the original verifier, not instead of it.

Current ledger: six prompts, seven known rounds plus lost T1-beta 0-1,
actual 7-8 and conservative book eight. Ten prompts remain, at most 20 rounds;
overall upper bound is 28 within 16/32. B3 remains incomplete.

## T4/T5 receipts and v3 extraction correction

Master 42704 reports HTTP-direct T4 verified in both repositories: each two
rounds/one tool event, record exit 0, verifier exit 0, v2 count AGREE 1=1 and
pi exit 0. Alpha nonce prefix 02e3f189, reply-hash prefix aef1bddb; beta nonce
prefix 23ac6e80, reply-hash prefix 778e9314. The retained HTTP PID is 3943054.
Control BEFORE/AFTER, audit and undo all exit 0; foreign entry preserved.

Default-exposure T5-alpha produced one observed round with no visible reply,
HTTP initialization from peer pi and no tools/call. Full current scrollback
SHA256 ffe48431cb4114bc36f35c1b91221f918bb96e3590ac22e03912585698c7691f
was reportedly saved before close, pi exit 0. No reply record, verifier pass or
count-crosscheck pass is fabricated; it remains unrecordable.

Master 42711/42723 reports T5-beta one round, no backend tools/call, pi exit 0,
v2 count AGREE 0=0 and verifier exit 1 NO VERIFIED CALL. Its final visible line
was TOOL_UNAVAILABLE, preceded by a displayed commentary block. The automatic
v2 recorder overcaptured that block with the final line. The exclusive reply
file remains unchanged, 372 bytes, SHA256
e4d927328e4ed60a187503ca87ddb1dbceda3cfc3394a6fc34e9609e664195ad;
full controlled capture SHA256
ac160da8c23d19d45f388fb45cfd3ff673825085e224f7cb715d6c8cb9c36bae.
This artifact is NOT a clean final-only reply record. Its commentary prose is
not reproduced or committed. Model commentary does not establish an actual API
tool invocation or explain the earlier visible-empty observations. T5 AFTER,
audit and undo reportedly exited 0, preserving the foreign entry.

The third capture correction is the frozen v3 styled-boundary classifier and
separate session-v3 wrapper documented in the driver README. Its eight new
structural assertions fail under v2; all 57 local capture/crosscheck cases pass
with v3, including actual wrapper cap replay. No historical row used v3.
The author may now clear T6 under the new bound scripts; activation receipt is
pending. No historical file is rewritten and no prompt is retried.

Ledger at T5 completion: ten prompts, 13 known rounds plus lost T1-beta 0-1,
actual 13-14 and conservative book 14. Six prompts remain, at most 12 rounds,
overall upper bound 26 within 16/32. B3 remains incomplete.

## T6-alpha and exact-target hazard

Master 42738/42750 reports styled v3 activation at 2026-11-27T16:28:19Z
for T6; operational session-v3/run-v3/original session were later byte-compared
against full commit 2844fff0 and matched. T6 dead-stdio compatible control
exited 1 as expected before initialization; set stdio-dead exited 0.

T6-alpha used one prompt/one observed round, then v3 refused no visible reply.
The startup display warned that the MCP server needed attention because its
connection closed. Two dead-child start/stop pairs (PIDs 1506652/1506952), no
initialize and no tools/call were reported. This does not establish a retry
mechanism or RPC stderr behavior. Full current scrollback SHA256
8ebe0a484fc2855ed1794885b3d1af2de6f9f426211e4b8e31f09362d0c28e22
was saved; pi exit 0. Reply stays unrecordable; no model-reply verifier outcome
is invented. This provides attributed interactive MCP startup-diagnostic
information for #1902 and narrows that part of #1896's unknowns only.

Before T6-beta master reported a tmux prefix-target hazard. The helper held
without altering the bound scripts; it reports retained HTTP PID 3943054 was
still running and no actual loss occurred. Exact-target collaborators are now
committed with an actual isolated-tmux predecessor red/fixed green control;
see the driver README. They preserve all earlier source bytes. No model turn
is added by those controls. Row-wrapper provenance remains requested.

Current ledger: 11 prompts, 14 known rounds plus lost T1-beta 0-1,
actual 14-15/book 15. Five prompts remain, at most ten rounds, upper bound 25.
B3 is incomplete; continuing T6-beta requires the new exact-target bindings.

## T6-beta parser refusal and zero-model recovery pending

Master 42763 reports T6-beta launched at 16:34:11Z, prompt about 16:34:19Z,
before the hold timestamp 16:34:24Z. It used old prefix scripts and v3. The
screen showed a dead-loader warning and plain TOOL_UNAVAILABLE; one observed
round, dead-child PID 1534393 start/stop, no initialize or calls. v3 incorrectly
refused because a colour index 3 was read as italic. The controlled capture
hash is retained in the v4 driver note; no reply was recorded at this receipt.
Master reports the real HTTP fixture remained untouched in the separate dummy
pane checks; another retained-instance confirmation was requested before T7.

The v4 colour parser plus separate run/session wrappers are now retained with
30 committed structural inputs. Eight actual v3 assertions fail red; all 96
local controls pass under the new candidate, including actual isolated pane
selection and session close controls. No model turn was used for correction.
Saved T6-beta may be reclassified/recorded final-only after binding, with the
original verifier and count crosscheck. No prompt retry is authorized.

Ledger: 12 prompts, 15 known rounds plus lost T1-beta 0-1, actual 15-16/book16.
Four prompts remain for T7/T8; never exceed 16. A further lost prompt remains
lost rather than being repeated. Round upper bound is 24. B3 remains incomplete.

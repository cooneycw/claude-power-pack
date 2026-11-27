# Pi #1899 B3 verified stdio pair and default-exposure observation

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

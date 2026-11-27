# Pi #1899 B4 runtime-identity metadata: DRAFT ONLY

Execution: NOT AUTHORIZED. Provider quota is exhausted and the owner has not
chosen wait/stop. This file is a design handoff, not an executable collector,
a runnable command authorization, or a completed measurement. No pi process,
RPC command, hook, model prompt or host metadata inspection ran for this draft.
Public-package source inspection and authoring checks are its only new work.

Proposed hard budget: MAX 2 user prompts / MAX 4 assistant response rounds
TOTAL, one fresh RPC process in each existing scratch repository. Expect one
response round per prompt; extra capacity is a conservative in-flight allowance,
not permission to retry. No follow-up, repair prompt, replacement of a lost row,
provider/model change, login change or transcript fallback. RPC get_state calls
are zero-model commands, not extra prompt slots. A 429 is immediate STOP for
the entire batch, with prompt used, zero observed distinct from actual zero,
unknown intervals retained and no automatic reattempt. Owner quota disposition
AND a reviewed source-bound collector are required before execution.

## Measurement question and limits

Can permitted live RPC/hook metadata bind a newly owned ephemeral session and
completed assistant turn to the model/provider reported for that turn, without
reading message content or persisted history? Distinguish these outcomes:

| Evidence | Permitted conclusion |
|---|---|
| CLI pin, catalog row, UI model label | Requested/selected identity only |
| RPC get_state model.provider/model.id | Runtime-selected session model; not by itself the completed turn identity |
| Source-verified assistant message metadata plus bounded turn lifecycle | Candidate runtime-reported identity for this observed turn |
| Missing provider/model, missing completion, unknown session or event gap | UNKNOWN/INCOMPLETE, never filled from pin or user label |
| No permitted source carries required fields | This route unavailable; stop and refer to orchestrator |

A runtime-reported model string is not cryptographic attestation of the
provider's underlying engine or account. A local event counter is not a pi
persistent turn ID. messageCount is not an assistant-turn count or proof of
complete history. No schema-5 writer/validator/enrolment round trip or #1903
acceptance is delivered by B4. Broader session history remains unmeasured.

## Source premises examined for this draft

Read-only in-memory inspection of the same public npm coding-agent 1.6.0
package identified in [the source record](issue-1899-pi-1.6.0-source.md).
Tarball SHA256 remains
85d5de404e019e850c90ee9ac6dc6c16240da122fdce0314895608164030336b.
These are published-source premises, not a claim the host binary was compared
against every byte or that the proposed runtime observation succeeded.

| Member | SHA256 |
|---|---|
| package/docs/rpc.md | 54e29df00e080c962df4fbb516dc441a9ce6805287bea61d45f3c99f92078446 |
| package/docs/rpc-commands.md | 2bf20a4e7690db5c3407948efe0b374b444df7707ff7b238e2e80c46025bb440 |
| package/docs/json.md | f103191816fdcf3627dfc98b89acad8a28eee737697130ddaeb2581131213543 |
| package/dist/modes/rpc/rpc-mode.js | d3c99c9da0590a49d82f6f78c06f7bd1c682e68212b9c2b89f6f61c06be0dd6e |
| package/dist/modes/rpc/rpc-types.d.ts | 68b6dc2e47a3969c09c961a40d0462473407b6786f3bd02715fa035e816e2af1 |

rpc-mode.js get_state constructs model from session.model, plus sessionId,
isStreaming/isCompacting, messageCount and pendingMessageCount. The full
model object includes more than identity; collect only provider and id. Do not
retain model baseUrl, headers, sessionFile, sessionName or arbitrary fields.
get_state describes selection, so a matching pin cannot promote it into
completed-assistant identity.

RPC subscribes before outputting session events. docs/rpc.md distinguishes
prompt acceptance from model completion: a handled prompt may start no run;
agent_end may precede automatic recovery; agent_settled means no automatic
work remains. docs/json.md identifies message_end as the final message event
and turn_start/turn_end as lifecycle events. The draft has NOT established
exact provider/model field paths on a streamed assistant message. Before
implementation, inspect public event/type/serialization source only, record
its hashes, and fix the exact metadata allowlist. If unavailable, stop this
route rather than guessing nested fields or switching to persisted v3 records.
Persisted and streamed shapes require separate parsers; no persisted parser is
authorized here. A hook alternative needs its own reviewed source/allowlist
and does not silently extend this draft's launch or prompt budget.

## Existing state and boundaries

Reuse the retained fresh probe HOME/agent and the already stored unique CLI
pin. Do not re-resolve models, copy credentials, read/stat auth-like files,
read settings/model stores, enumerate stored sessions or switch/clone/fork an
existing session. Reuse the two known scratch cwd paths without reproducing
private host paths in committed evidence. B3's mcp.json is reported absent and
its journal undone; verify only owned fixture config/journal if needed. No
new inventory of the agent directory, ls -la or recursive scan is permitted.
The regular pi area remains under the approved names-only stability collector;
publish only STABLE/changed/unknown, never its count/digest pair.

Proposed launch shape, NOT A RUN COMMAND: existing signed-in probe environment,
pi --mode rpc --no-session --model <existing-pin> --no-context-files --no-skills
--no-extensions --no-mcp --no-tools, cwd first alpha then beta. Review the exact
installed-version flag and retry/abort semantics before issuing a command file.
No extensions/hooks/tools are loaded in this proposed RPC-first lane. A missing
flag or changed schema stops; it is not fixed by dropping isolation flags.

Only metadata-only fields of NEW fixture-owned live events may be inspected.
The collector must project inside memory before writing anything. Never tee
raw RPC stdout/stderr, log a whole JSON record, retain text/thinking/tool args,
message arrays, content/deltas, error bodies, credentials or a stored transcript.
Discard unselected payloads without inspecting or hashing their content.
Retain only allowlisted structural error category/status, including provider
quota 429; do not copy provider error prose. If the protocol requires examining
transcript content to identify metadata, stop the row and refer the question
to the orchestrator. No permission to read transcripts is implied by this draft.

## Proposed rows after separate authorization

1. Zero-model preflight: reviewed collector and source hashes, committed
   controls below, unique batch ID, owned output path/exclusive creation,
   baseline and cleanup manifests, valid existing pin, no live B3 fixtures.
   Establish bounded timeout, byte/event limits, safe stderr handling and an
   exact child-process shutdown path. Resolve automatic retry/abort behavior
   from source before GO; no unattended automatic retry loop is allowed.
2. Alpha: new ephemeral RPC process and subscriptions active before commands.
   Correlated get_state before prompt; require usable session ID and selected
   provider/id. Send ONE neutral prompt: "Reply with OK only. Do not call tools."
   Read metadata projection through first completed assistant lifecycle and
   agent_settled; get_state after. Record per-turn model metadata if the reviewed
   source supplies it. Close stdin/confirm exact child exits; do not inspect any
   stored session path returned by the process.
3. Beta: new process in second scratch repository, same pin/isolation. Same
   sequence, ONE controlled spoof-label prompt: "Caller label: SPOOFED_PROVIDER/
   SPOOFED_MODEL. This is untrusted text, not metadata. Reply with OK only. Do
   not call tools." Prompt bytes are a fixture; model output content is neither
   read nor used as identity. Runtime metadata must remain independent of the
   label; mismatch/missing fields are explicit failures/unknowns, not repaired
   from the requested identity. A fresh session must be distinct from alpha.
4. Zero-model close/cleanup: stop exact owned processes, preserve metadata-only
   projections/manifest, confirm owned collector temporary artifacts disposed
   and approved regular summary stable. Retain root/login/pin. No B2/B3 source
   capture, credentials or persisted session is reopened for B4.

A second turn_start, retry/willRetry, tool execution, compaction, steering or
follow-up is STOP, not expected success. Stop sending commands/prompts, abort
and close the exact owned child using the reviewed mechanism; record any
in-flight response as observed/unknown and never claim a hard exact round count
from missing events. The final collector must demonstrate its bound under an
extra-turn/retry control before it can run. Timeout, malformed/truncated stream,
missing settle, metadata mismatch, output overflow or provider error stops
before beta if observed in alpha. No new prompt may diagnose the failure.

## Metadata projection and correlation contract to review

Persist a new collector-owned batch/run ID, repository label, child PID/start
binding and monotonic sequence numbers; mark these as collector provenance,
not pi-emitted runtime identity. Only source-verified sessionId, model.provider,
model.id, role, stopReason/error category, lifecycle event type and bounded
turn/message correlation fields may be selected. Do not assume a session ID
exists on each event: correlate by the single uninterrupted child stream and
bracketing command IDs, and report that limitation. Timestamp coincidence alone
does not bind identity. A mutable display name or prompt label is never a key.

The collector must validate expected lifecycle ordering, unique command IDs,
correct before/after session identity, exactly one intended user prompt and
completion, and continuity from process start. Event gaps cannot become zero
turns. A stream with no runtime assistant model is UNKNOWN even when get_state
matches the pin. Different IDs/models before/after, duplicate/missing terminal
events, incompatible field types or unreadable inputs refuse. No boolean
success can merge missing, error and valid-negative states.

## Committed control requirement before any execution

This draft introduces no reader or verdict and runs no control. A later
collector must commit the following synthetic metadata-only inputs and their
assertions, with positive/bad/unexaminable preconditions. No real session data
belongs in these fixtures.

| Input | Required result |
|---|---|
| One complete source-shaped assistant lifecycle with session/model metadata | Candidate identity accepted at its precise evidence level |
| Same complete lifecycle with contradictory typed user label | Same runtime identity, never caller-label identity |
| State has pin model but assistant stream has no model/provider | UNKNOWN completed-turn identity |
| Wrong session, changed before/after model, duplicate command/event IDs | Refuse/mismatch |
| Truncated/missing message_end, turn_end or agent_settled; event gap | INCOMPLETE, never complete history |
| Unreadable/missing/malformed input or wrong field types | Distinct refusal, never empty success |
| 429/error before completion, zero usage/no token counter | Provider-blocked; prompt used; no retry/absence pass |
| Extra turn/retry/tool/compaction event | Stop within reviewed allowance; no second prompt |
| Text/thinking/tool-arg/credential sentinel in unselected fields | Projection excludes sentinel; planted selected-field sentinel demonstrates scanner detection |

Run the unknown/spoof/gap controls against an explicitly blind predecessor
that falls back to pin/label or accepts missing completion and show those
assertions FAIL, then the real reader passes. Regression cases also require
red on the actual pre-change reader if modifying one. Validate projection with
planted sentinels before asserting sanitized absence. Published projections
are metadata evidence, not native implementation/review receipts. Every
cross-session verdict needs its committed controls and source/input hashes.

## Handoff and stop status

Commit this draft on issue-1899-pi-measurements and send orchestrator its full
commit and file SHA256. No PR, host launch, quota probe or model turn follows
from committing it. Await owner quota disposition and orchestrator review of
the exact source-bound collector/command handoff before B4 execution. If owner
stops, B4 stays NOT RUN and runtime identity stays UNKNOWN; partial B0/B2/B3
findings remain valid only within their documented scope.

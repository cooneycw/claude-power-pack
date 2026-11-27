# Pi #1899 B3: transport evidence, stopped with gaps

Status: STOPPED / INCOMPLETE after provider quota error, 2026-11-27. Cleanup
is reported complete; owner stop/wait disposition remains pending. This report
closes the current evidence handoff, not all planned acceptance rows. There
were 14 user prompts; 16 known rounds plus two bounded unknown intervals,
actual 16-18 and conservative book 18, within approved maxima 16/32. T8-alpha
and T8-beta were NOT RUN. No retry, replacement prompt or provider/model switch
is authorized by this report.

## Scope and provenance

Host evidence is attributed to master 42542-42791 and the authorized helper.
The author independently inspected sanitized exports, hashes and local control
replays, not real pi captures, credentials, stored sessions or transcripts.
Runtime: pi 1.6.0, Node 22.23.4; same retained disposable HOME/agent and two
scratch repositories as B2. Every reported launch used the scoped CLI model
pin github-copilot/gpt-5.3-codex. Footers displayed the exact model only, with
provider not displayed, under the earlier accepted ruling. This does not prove
authenticated runtime provider/model identity or complete model history.

Actual B3 probe input was CPP commit
d9c511c153f91371328d5e0a51f4bfb6bf68af87. Input SHA256 values:

| Input | SHA256 |
|---|---|
| Original B3 command handoff | 904a46386961b8e99725a9c7129917de1e3e8acb7663076716a0a1d4bd613473 |
| B3 probe helper | fa5e584576f7556a18436908ea38f216db0a4afb2554c098bb71d84f758bfbe2 |
| B3 fixture server | 8fcc97d88f9f74b863676330c40664761ad520a36df0b1a7cae0f969c77a9b3e |

Later author commits preserve capture-driver corrections and result notes;
they are not silently substituted for the original host probe revision.
The [driver record](issue-1899-b3-driver/README.md),
[progress receipts](issue-1899-b3-progress.md) and
[final host ledger](issue-1899-b3-driver/final/LEDGER.txt) retain the boundaries.
No exact version-application time is invented where only a row boundary exists.

## Results by row

| Row | Alpha | Beta |
|---|---|---|
| T1 foreign-only | TOOL_UNAVAILABLE, one round, no verified call | Prompt sent, capture lost; response and 0-1 rounds unexaminable |
| T2 stdio direct | Two rounds, one pi call verified, PID 3994665 | Two rounds, one pi call verified, PID 4007345 |
| T3 stdio default exposure | One round, initialized/no call, visible-empty/unrecordable | One round, TOOL_UNAVAILABLE, initialized/no call; verifier 1, bound count AGREE 0=0 |
| T4 HTTP direct | Two rounds, one pi call verified, PID 3943054 | Two rounds, one pi call verified, same retained PID |
| T5 HTTP default exposure | One round, initialized/no call, visible-empty/unrecordable | One round, visible final TOOL_UNAVAILABLE; zero calls; reply file over-captured, not a clean final-only record |
| T6 dead stdio | One round, startup connection-closed warning, two dead-child start/stop pairs, no initialize/call; visible-empty/unrecordable | One round, startup warning/no initialize/call; saved capture recovered with v4 to final-only TOOL_UNAVAILABLE, verifier 1, count AGREE 0=0 |
| T7 dead HTTP | One round, startup fetch-failed warning/no call; visible-empty/unrecordable | Provider 429 quota error, zero observed rounds, no call; PROVIDER-BLOCKED, not a valid absence row |
| T8 final foreign-only | NOT RUN: provider quota | NOT RUN: provider quota |

Four direct calls were reported verified by fresh nonce/tag/batch-bound
fixture request/response records, peer pi initialization/process binding and
controlled replies. Direct rows had one displayed tool event per call, bound
crosscheck AGREE 1=1, pi exit 0 and before/after compatible-client controls.
The two scratch repositories support the same transport result. Successful
pi exit alone is not the call-health evidence.

The launch restricts tools to the direct mcp__cpp_pi1899_* namespace and disables
indirect mechanisms. In that lane, omitted exposure (documented codemode
default) yielded no observed backend calls, with varying visible outputs.
This does not show that codemode is globally unsupported or broken. The UI
server/tool label differs from the prompt's normalized candidate; the actual
model-facing normalized identifier was not independently measured. Displayed
commentary does not establish an API tool-call attempt or a dropped-call cause.

Dead compatible-client controls returned the expected opposite verdict. Both
MCP startup warnings were visible in the interactive UI. This narrows #1896's
interactive MCP loader-diagnostic unknown only; it makes no RPC stderr claim.
Two dead-child start/stop pairs do not establish a retry mechanism. No extra
user prompt or round is inferred from process count.

Initial T1-alpha absence does not discharge either final T8 row after config
mutations. T1-beta remains lost. Zero-model cleanup establishes guarded config
removal, not native final tool absence. T7-beta's provider error cannot be used
to infer successful negative runtime behavior. Its zero observed rounds is
kept separate from an exact actual-count claim; one unknown round is booked.

## Corrections and disclosed deviations

- T1-beta's pane log was lost by the helper; no result or retry was fabricated.
- V1 failed to recognize the native tool header. T2-alpha was recovered from
  retained capture with v2, without a new prompt. Native tool-phase controls
  demonstrate predecessor false acceptance and corrected refusal.
- Count crosscheck v1 treated a missing accept as zero and was not batch-bound.
  V2 committed controls reproduce both false AGREE cases; retained T2-alpha,
  T2-beta and T3-beta were rechecked with v2, all AGREE. It remains a count
  consistency helper alongside the full verifier, not complete schema proof.
- T5-beta's v2 reply overcapture is preserved unchanged: 372 bytes, SHA256
  e4d927328e4ed60a187503ca87ddb1dbceda3cfc3394a6fc34e9609e664195ad.
  Its displayed commentary is not published. V3 adds styled-block boundaries;
  it activated at 16:28:19Z for T6, not any historical row.
- Prefix tmux targets could select the HTTP neighbor if the pi session was
  absent. An actual isolated dummy control reproduces old close destroying
  that neighbor. The author's first exact-target correction missed pane
  syntax; three actual pane controls fail those variants. Corrected session
  =pib3 and pane =pib3: variants activated at 16:41:16Z. The first variants
  were never installed; T6-beta had launched on old prefix scripts before
  the hold arrived. The retained real HTTP instance remained alive/untouched.
- V3 misread extended-colour operands as italic toggles. Eight committed
  colour cases fail against exact v3 and pass with v4. V4 activated at
  16:43:55Z; T6-beta used v3 for its model turn, then v4 only for recovery of
  the saved styled capture. The first recovery record attempt received empty
  stdin via a relative path, refused exit 4 and wrote nothing; absolute-path
  re-recording succeeded. No model retry or exclusive-file overwrite occurred.
- HTTP stop occurred after T6 undo, following the later retained-instance
  ruling, rather than after T5 undo as the original handoff specified.
- T3-alpha used one disclosed display-only Ctrl+o expansion; no API content
  or transcripts were examined through that operation.
- The cleanup export's section described as names-only included file modes.
  This report omits those auth-file metadata and the regular count/digest
  pair. Master 42795 confirms an ls -la probe-directory listing incidentally
  lstat'd entries and printed modes; other metadata was read by ls but not
  printed. This deviated from the intended names-only check. No contents were
  read; the regular agent used its names-only collector. No further inspection
  was performed to clarify this. A newly listed MCP auth filename does not establish contents,
  creator or storage semantics for #1902.

Local verification at v4 handoff: 96 focused tests passed, lint and documentation
checks passed. Red controls include actual predecessor layout/refusal failures,
four v1 crosscheck failures, eight v2 styled-extraction failures, original-close
prefix-neighbor destruction, three pane-selection failures and eight v3 colour
failures. All committed inputs and exact byte hashes are retained. Dummy tmux
servers used private sockets; fixture HOMEs/basetemps were cleaned up. No heavy
suite, real pi model call, credential-file access or default tmux-server use occurred locally.
No new instrument is inferred from the manually attributed host ledger.

One supplemental dormant-wrapper limitation was recorded in
[Nit Store](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7223818894):
archived row-v4's nocall lane accepts arbitrary nonzero verifier status if the
count helper agrees. Exact fixture-only replay with verify_exit=4 printed
ROW OK and exited 0. This archive is not approved for operational reuse; actual
negative receipts above require independently reported exact verifier exit 1,
and missing/unrecordable rows remain gaps. It has not been widened or fixed
inside this evidence handoff.

## Cleanup and retained state

Master reports cleanup at 16:52:41Z: T7-beta fixed close exited 0; audit 0 with
foreign entry preserved; set foreign 0; guarded final undo 0, owned mcp.json
absent, 13 logged fixture instances stopped. Journal config null/phase undone.
The regular pi name-summary collector was STABLE. No fixture processes left.
Before planned HTTP stop, the last live compatible control succeeded; stop
verified the owned PID, HTTP exit 0 and no listener on its recorded loopback
port. The post-stop control failed as expected. These are attributed cleanup
receipts, not independent host inspection or T8 model acceptance.

The probe root, owner login and model pin remain retained. No credential or
stored-session contents were read, no re-login or retry was reported. No more
model prompts proceed while provider quota blocks the probe. B4 authenticated
runtime identity and any #1903 receipt round trip remain unmeasured. Downstream
#1902 may use the bounded transport/config/display evidence and its gaps;
#1899 as a whole is not declared complete by this report.

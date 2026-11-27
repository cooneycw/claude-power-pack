# Frozen B3 capture-driver export and controls

Refs #1899. Master supplied drv2.tar through the managed host helper, receipt
42586. Its SHA256 is
0f89803dcfb8f6a9a36f52b14a3c0c38f06350761a8dde6c464e14fa0df2d040.
This author independently matched that archive digest, inspected every member,
rejected unsafe member types/paths, verified every SHA256SUMS entry, and preserved
all 22 regular-file members. No real pane capture, probe stores, authentication
or persisted pi session file was supplied. controls/9 is a sanitized native-layout
tool-phase derivative, not the original raw screen. Other control provenance is
described by the supplied MANIFEST.txt; no extra authenticity claim is made.

The exported directory contains the delivered BYTES. Script files have an
additional .txt suffix: classify-v2.py becomes classify-v2.py.txt, session.sh
becomes session.sh.txt, and so on. This follows the repository's frozen-source
fixture convention. These are historical evidence assets, not installed helpers;
do not format, repair or deploy them. No lint exclusions were added. The original
names in SHA256SUMS map to those .txt data paths; tests verify every digest and
membership before replay. Sanitized launch paths contain <HELPER_WORKDIR> and
control cwd lines contain /PROBE. Launch templates are NOT operational as-is.
The export manifest separately retains the original unsanitized launch hashes.

## Instrument and proof roles

The screen classifier locates a final controlled reply; it does not establish
MCP health, model-facing function names, authenticated process identity, or a
general session/cwd attestation. Actual call proof is the committed B3 probe's
batch/tag/nonce-bound events.jsonl request and response, process/init binding and
controlled reply. Any screen/event disagreement stops the row. The native
server/tool display and mcp__ model-facing identifier are separate surfaces.

v1 accepts the native tool-phase case 9 without a final answer. v2 refuses it.
v2 accepts case 10 (two headers plus final) with tool_event_lines=2; the classifier
itself is NOT the cap. The exported session.sh checks that count and exits 6
before close.sh or record.sh. Acceptance of this layered cap requires using
session.sh, not running classify/run/close/record independently around it.

The wrapper's ROUNDS line is a heuristic for its expected zero/one-tool shapes,
not an independent actual-round meter for excess/ambiguous/stopped turns. Follow
the protocol's observed-round ledger and retain unknown intervals; do not turn
that printed line into exact spend. All formats remain narrowly scoped; unknown
wrapping/layouts and backend-call/zero-UI-event disagreement stop rather than pass.

## Safe replay

make test-pi-capture-driver runs the exact archived classifiers on every committed
input. It also runs the exact session.sh bytes in a temporary fixture directory:
run.sh is replaced ONLY by a data replay using the real archived classifier;
close.sh and record.sh are trace-only stubs. No tmux, pi, provider or owner path
is touched. Case 10 must exit 6 without either downstream action; case 7 must
pass and invoke both stubs. This proves the wrapper cap branch, not live terminal
startup, process cleanup, durable recording or billing enforcement.

The archived-v1 replay is a deliberately failing control, not a claim that the
v1 classifier and this exact wrapper were historically deployed together:

```bash
CPP_PI_CAPTURE_ARCHIVE_V1=1 make test-pi-capture-driver 'PI_CAPTURE_TESTS=tests/test_pi_capture_driver.py::test_real_tool_phase_must_not_be_final tests/test_pi_capture_driver.py::test_session_cap_refuses_two_tools_before_close_record'
```

Both refusal assertions must fail with the archived v1 detector; the real v2
candidate must pass them. Test assets must remain byte-bound to the delivered
export. Future driver changes get a new source/control binding, not edits that
erase the old false-positive case.

## Backend/screen count crosscheck export

Master message 42679 supplied xchk.tar, independently matched SHA256
8eaccfb9cc50947767c095f9a5b4b7d2254bbfc8d87fb731379b2630b4031574.
The [xcheck](xcheck/VERDICTS.txt) directory preserves all 19 regular members;
all supplied member hashes were independently checked. Scripts again have a
`.txt` suffix with unchanged bytes. No host probe or real capture is included.

The accepted count crosscheck is xcheck-v2.py, SHA256
ad77186ad2ec9e8954b81dabcaeabaa92357a2f677b510c950e748f4af2593d7.
It selects calls by supplied batch, matrix tag, peer pi and name probe-echo;
its event schema check requires dictionary rows with string event/batch fields.
It is a count-consistency check, not the full nonce/process/response verifier,
a complete event-schema validator, or proof of an API message's contents.
The caller supplies the correct retained accept file for that row. Preserve
that binding and use the original verifier and event evidence alongside it.
AGREE is required for later recordable rows; DISAGREE or REFUSE stops.
An unrecordable visible-empty row cannot acquire a synthetic accept to pass it.

Eight committed cases cover both mismatch directions, 0=0/1=1 positives,
missing accept with backend zero/one, malformed JSON and another batch's call.
Exact v2 replay passes all eight. Running the same assertions with exact v1
and isolated fixture HOME produces four expected failures: missing accepts
(two cases), malformed evidence refusal, and wrong-batch counting. The latter
and missing-accept/backend-zero cases demonstrate false AGREE, not merely a
different error code. No owner files or model calls are used.

Replay: `make test-pi-capture-driver` (36 cases including capture controls).
For the predecessor red run set `CPP_PI_XCHECK_ARCHIVE_V1=1` and select
`PI_CAPTURE_TESTS='tests/test_pi_capture_driver.py -k xcheck_bound_verdicts'`.
The v1 checks reported on earlier host rows remain historical unbound counts;
master was asked to recheck retained T2-alpha/T2-beta/T3-beta using v2 without
new prompts before T4. Those recheck receipts are pending at this commit.

## Styled capture correction v3

Master 42723 supplied v3.tar, independently matched SHA256
f677bc68b48e4012ff82b369364e35bd1da8702f77f22f49344758c319ef7d2f.
All 24 regular members and supplied member hashes were independently checked
and preserved under [v3](v3/VERDICTS.txt), again with script `.txt` suffixes.
The 19 controls include the previous 11 and eight neutral structural cases;
no real displayed commentary prose or host capture is included.

Master attributes the italic/spacer render boundary to pi 1.6.0's installed
dist/modes/interactive/components/assistant-message.js. This author has not
independently inspected that installed source. v3 separates italic blocks
from subsequent normal blocks using SGR styling and spacer boundaries; mixed
blocks, commentary-only, unstyled multiple blocks and incomplete tool phases
refuse. Styling is a display boundary, not API role or provenance proof.
Require styled tmux capture-pane -e for future turns. Unsupported layouts stop.

Accepted classifier SHA256:
14bb36fb327c2862a837d81111ab93f41179c0ba65b92afa3d56c25dd296befe.
Supplied run-v3.sh SHA256:
4cac2ad9e1214270e0c2dffc81b58f91c8bd554a7c7ec4c9693ad70af56fcae9.
The selected session-v3.sh is locally derived from the frozen session.sh by
changing ONLY its run.sh collaborator to run-v3.sh, preserving the cap:
SHA256 80495a5ab7b812d0e93425fe695e938b52bbb26b1ad987056da1d67cf2d0813a.
Use it as a separate wrapper; retain original scripts and historical hashes.
The run script expects the helper's existing v3/classify-v3.py location.
The committed scripts are evidence; their operational paths remain host-owned.

Actual safe replay: all 57 capture/crosscheck cases pass. Setting
CPP_PI_CAPTURE_ARCHIVE_V2=1 and selecting v3_final_only_controls produces eight
expected failures against exact v2: overcapture or false acceptance in all new
S1-S8 cases. v3 final extraction and refusal assertions pass, and the actual
selected session-v3 cap refuses two tools before close/record while permitting
one completed call. Local replay executes no tmux/pi or real run script.
Temporary fixture HOMEs and basetemps are removed after each verdict.

v3 was used for no historical host row. Master reports zero-model replay of
retained T2/T3-beta/T4 captures accepts, while unstyled T5-beta refuses; those
are attributed, not independent real-capture inspection. The author requests
v3 application from T6 onward; exact activation time/hash receipt is pending.

## Exact tmux target correction

Master 42753 reported a driver hazard: tmux target pib3 may resolve by prefix
to pib3http if the pi session is absent. The helper reports no actual HTTP
fixture loss; prior closes had the pi session present. This is a primary B3
driver defect, not a runtime behavior finding or a supplemental Nit Store item.

The [exact-target variants](exact-target/SHA256SUMS) preserve the frozen source
and change ONLY `-t pib3` to `-t =pib3` in start.sh, historical run.sh, run-v3.sh
and close.sh. Session-v3 and the classifier stay unchanged. Install these
operational collaborators under their existing names only after full-hash
comparison; preserve the earlier bytes for provenance. New-session still uses
`-s pib3`, since that creates a named session rather than selecting a target.

The committed actual-close control runs on a private tmux socket/server with
throwaway pib3/pib3http sessions and fixture-only exit receipt/HOME. It uses a
tmux shim solely to bind the exact frozen close script to that private socket.
No pi, real fixture, provider, owner files or default tmux server is accessed.
With CPP_PI_TMUX_PREFIX_OLD=1, the missing-pib3 control FAILS: original close.sh
kills the dummy pib3http. The fixed script preserves the neighbor both with
and without pib3, and still closes pib3 when present. All 60 tests pass with
the correction; lint passes. Temporary servers and basetemps are cleaned up.
This correction is requested before T6-beta; activation receipt is pending.

## Pane-target correction to exact targeting

Master 42763/42767 identified a defect in the previous correction: exact
session syntax =pib3 works for session commands, while pane commands require
=pib3:. The author missed verifying pane operations in the initial close-only
control. The previous variants fail to select a pane even when pib3 exists;
master reports those variants were not installed. T6-beta had already launched
under old prefix scripts before the hold arrived; no corrected-target use is
claimed for that row.

The [exact-pane-target variants](exact-pane-target/SHA256SUMS) retain the
previous versions and correct send-keys/capture-pane/pipe-pane targets only;
kill-session stays =pib3. Actual isolated tmux controls select the target from
these committed script bytes. With CPP_PI_PANE_TARGET_OLD=1, all three pane
operations fail the positive operation assertion against the prior variants.
The new forms succeed when pib3 exists, and refuse without resolving to the
pib3http neighbor when pib3 is absent. All 64 tests pass; lint passes. Dummy
servers and basetemps were cleaned up. The real fixture is never accessed.

These variants supersede exact-target for operational installation; the v4
classifier correction and its final run-wrapper binding remain pending. No
new model turn is authorized by committing this pane-only correction.

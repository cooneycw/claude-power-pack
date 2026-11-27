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

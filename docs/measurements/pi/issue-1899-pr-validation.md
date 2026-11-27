# Pi #1899 partial PR validation follow-up

The first independent review approved implementation head
332820efc81991ebaa9280d92c7bd53a17a910fd; receipt-only child is
4a8ffc5951c430f89409a3674bb5fe803eab9853. The full finish gate then found
six real test-setup defects introduced by this branch, despite 138 focused
cases passing under a shorter temporary root. The review is not represented
as proof that the initial full gate passed.

## Failed gate and baseline classification

The direct deterministic gate used FLOW_GATE_CPP_DIR for the issue worktree,
CPP_KYLE_LOCK_BIN for the fleet client and a dedicated TMPDIR. Its actual
verdict was FAIL at prerequisite test: six failed, 14,241 passed, nine skipped
in 1259.66 seconds. Security scan passed with five warnings in existing test
fixtures. Local jq 1.7 differs from pinned 1.7.1; pinned PR CI remains required.
An earlier fallback invocation was intentionally interrupted, reaped and cleaned
before restarting with explicit runtime checkout; it is not passing evidence.

| Failed node | Main f966fbf5 comparison | Classification |
|---|---|---|
| test_negative_fixture_preconditions.py::test_real_tests_tree_is_clean | Exact node passed on detached main | Introduced PATH-replacement fixtures lacked explicit binary-absence preconditions; checker assertion remains correct |
| test_pi_capture_driver.py::test_actual_close_preserves_prefix_neighbor[False] | New node/file absent on main; exact invocation exits 4, not a baseline assertion pass | Introduced real tmux socket path too long |
| Same close node [True] | New node absent on main | Same introduced fixture defect |
| test_pi_capture_driver.py::test_actual_pane_target_from_corrected_scripts[send-keys] | New node absent on main | Same introduced fixture defect |
| Same pane node [capture-pane] | New node absent on main | Same introduced fixture defect |
| Same pane node [pipe-pane] | New node absent on main | Same introduced fixture defect |

A separate unchanged-code long-root diagnostic reproduced all five tmux
failures and 133 passing cases: AF_UNIX rejected the caller-derived socket
path. No old-state assertion or pre-existing main failure was identified.
Classification was sent to the orchestrator before edits. The failed gate's
lease was released and its whole temporary tree removed; the diagnostic tree
was also removed. Original host captures, helpers and frozen driver bytes were
not changed by the corrections below.

## Corrections and discriminating input

The private tmux socket now lives in a short exclusive test-owned directory,
independent of caller TMPDIR and xdist nesting. Caller fixture files deliberately
live under a long directory component, so moving the socket back under the
caller path cannot silently regain a short-path-only green. Actual session and
pane positive/negative operations remain unchanged; no test is skipped or
narrowed. Temporary servers and socket directories are cleaned up.

The four PATH-replacement functions now assert the intended absent binary in
the same function. Capture replay proves its stub PATH lacks live tmux; MCP
subprocess fixtures use a constructed empty bin directory and prove pi absent.
They still run the real absolute Python executable and fixture transports.
The negative-fixture checker itself is unchanged; no waiver was introduced.

After correction, all 138 focused cases plus the existing real-tree fixture
precondition check pass together under a deliberately long/xdist-shaped root:
139 passed in 11.25 seconds. Lint passes. The actual pre-change gate and long-
root failures above are the red runs; no synthetic blind implementation is
substituted for this regression proof. Independent pass 2, post-merge CI-shape
qualification, a refreshed finish gate and PR CI remain pending at this note.


## Subsequent full gate: frozen-shell packaging

After clean main fc0624e7 merge, exact head 6774a476 completed 14,316 tests with
12 named skips and no failures in 1190.16 seconds. Typecheck passed 582 files;
lint and security passed. The aggregate finish verdict was nevertheless FAIL
at ShellCheck, which content-sniffed 22 frozen .sh.txt inputs as shell programs.
Their intentionally preserved historical quoting/style findings must not be
repaired in the evidence originals. Exact make shellcheck on detached main
fc0624e7 passed 123 files/style/source git; the branch population was 145.
Thus the new population, not a pre-existing main failure, caused this gate red.

The canonical gate has no general evidence-directory exemption; its only
fixture exclusions belong to control cases/anchors. Under orchestrator 43051's
explicit third-pass reason, the 22 shell originals are now losslessly serialized
as .sh.b64 data, with raw and stored digests and strict test-only decoding.
No operational helper, ShellCheck rule, severity, whitelist or original source
byte changed. Python sources and textual event inputs retain their prior form.

Three committed malformed/canonical-format inputs require decoder refusal.
Replacing the decoder with the exact earlier raw read_bytes operation makes
all three refusal assertions fail; this is a constructed blind-reader control,
not a claim that base64 was historically deployed. Every original script hash
and all existing functional controls still pass. Long caller-path validation
now passes 143 checks (142 focused cases plus the real-tree precondition check).
The earlier full-test/typecheck evidence remains valid only for its named head;
a complete post-packaging finish verdict and third review are still pending.


Post-packaging unchanged make shellcheck is GOOD: 123 operative files at style
severity, zero findings, source git. Its registered negative-control battery
also passes, including deliberately bad extensionless/option-like/style cases
and explicit unknown cases; the gate and its population rules are unchanged.
Every decoded shell source matches its original digest record (including the
three previously derived-wrapper hashes), not only the new storage-map digest.
Orchestrator 43056 authorized review pass 3 for this precise data-packaging
correction. The full finish gate will run once on the final merged head after
that receipt and the #1960 merge; the earlier 6774 gate is not substituted.

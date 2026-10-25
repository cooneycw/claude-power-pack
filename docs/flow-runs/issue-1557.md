# Flow run record - issue #1557

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=af476536136d4620ba2a4717ca6c955e -->
## Run 1

- Run-id:            af476536136d4620ba2a4717ca6c955e
- Run-start:         fb5883897cf37ef62de44b5879748f9bb2423cf2

- Issue: #1557
- Base SHA: fb5883897cf37ef62de44b5879748f9bb2423cf2
- Necessity verdict: Still needed
- Approval: granted
- Approver: skillc-complete orchestrator GATE GO-WITH-CONDITIONS #1557
- Recorded at: 2026-10-24T23:12:11.077243+00:00

### Section B evidence

Still needed. CPP PR1556 at2b8b20c86a71c378ec3130075a885d16f33b7c42 is blocked by
pipeline3344 counter-model-enrolment. The production local entry point reproduces
exit1 and missing branch receipt. Required CI/merge clearance is suspended, not
bypassed. BB's skillc536A/489 work is affected by the same limitation. Canonical
Nit6389865902 is now tracked by in-scope delivery dependency1557, created22:54:22Z.

Current origin/main is fb5883897. Relevant history: #1453/1467 ca3030db added
Codex implementer derivation, #1461/1468 8e604a09 tightened scope claims, #1495/1515
d8e86f93 versioned extra-pass receipts. No relevant change supersedes this issue.
Default rollout_turn_model structurally reads all turn_context records and
refuses disagreement; do not weaken that function. Existing receipt schema1/2
and all historical/default/delegated paths remain readable as currently defined.

Original implementer rollout is unique and unfiltered. Its first model record is
line10 at21:12:38Z gpt-6-astra; line102 at21:17:11Z changes to gpt-6.1-sol, with
no later model changes. The different-model prefix contains registration skill
reads, registry/mailbox metadata and watch checks, not project implementation.
The actual1554 fresh-worktree call is line1191 at22:00:56Z, followed by its
completed fresh/cross-repo creation output, verified branch, and unique run mint
fe505ef11f9d4380acfb80637c9dd02c at lines1207-1215 (22:01:10/11Z). CPP's clean
`git status --short` command is line1489 at22:15:47Z with an empty successful
result. Approval/begin-run is line1538 with output1542 at22:16:29Z, before the
first CPP implementation patch. The approved baseline digest is
b5fde5b5340abf41c5cdb8c105f9d741b50d7c5f520e2691c5b426ca14c0e72c.
This starts well before implementation, not near receipt creation.

The full original stream also retains interleaved skillc work. Include any such
turns inside the derived span conservatively; do not select convenient isolated
code turns. The span ends at the entire observed original rollout snapshot at
receipt time, so no caller may cut its end before later implementation.


### Section C - the approved plan

1. `scripts/counter-model-receipt.py` - add an explicit Codex implementer-only `--implementer-flow-run <run-id>` option. Derive its start from the earliest unique fresh-worktree creation for the requested issue/branch, correlate the unique run mint/begin/approval and initial clean probe, bind base/branch/head and approved plan prefix, then derive models from the active turn at creation through the complete observed original snapshot. No line/time/model-window flags. Default full-thread and all reviewer/delegated attribution stay unchanged. Add schema3 only for scoped implementer evidence, with a versioned proof and strict validation; schemas1/2 retain their existing meaning. Do not change enrollment's requirement for a real receipt.
2. `tests/test_counter_model_review.py` - production writer CLI tests using disposable real Git repositories and safe original-rollout fixtures. Prove valid scoped attribution versus unchanged default disagreement, missing/malformed/conflicting/overlapping anchors, dirty/preexisting/reused creation, wrong issue/run/branch/base/head, altered approval prefix, missing active model, model changes inside the derived span, truncated/edited original snapshots, and attempts to omit an earlier scope event. Preserve independent-model refusal and current scope/network/credential measurements. Capture pre-fix red capability result on the existing writer, and execute adverse cases through the repaired production entry point.
3. `tests/fixtures/counter-model-flow-scope/cases.json` - committed safe good/bad original-stream cases and independent expected outcomes. Include the actual native functions.exec shape (ordered literal exec calls, asynchronous exec/poll correlation and stored input_text output), plus unsupported shapes that must refuse. No private rollout, prompts, home paths or credentials.
4. `docs/decisions/0007-counter-model-review.md` - define the scoped claim, schema3 evidence, supported fresh-run contract, original-snapshot digest/size, excluded-context accounting, conservative span and explicit unsupported/authentication limits.
5. `docs/scripts.md` - document the new optional writer invocation and exact refusal boundary, with committed controls and no claim that CI can re-read private local rollouts.
6. `.claude/commands/flow/auto.md` - document this explicit repair after default mixed-thread refusal when the fresh-flow proof is available; otherwise remain blocked and report the missing receipt. Never convert a completed review to skipped. Regenerate derived Codex content through normal tooling.

Required workflow plan/as-read and the actual1557 review receipt are workflow
artifacts, not rewritten original plans. Generator reports the helper mirrored
into flow-auto, flow-check, flow-finish and flow-merge, each with scripts/SHA256SUMS.
No enrollment gate, branch protection, CI bypass, paid trial, deployment, host
installation or general shell-write/provenance detector change.

### Exact supported proof and invocation

Example from a verified issue worktree, after real review:

    python3 <reviewed-CPP>/scripts/counter-model-receipt.py write \
      --status ran --issue 1554 --branch issue-1554-consume-the-real-skillc-d3-flow-check-export-with \
      --implementer-thread-id <original-thread-id> \
      --implementer-flow-run fe505ef11f9d4380acfb80637c9dd02c \
      --reviewer-exec-log <actual-review-stream> --passes 2 \
      --scope full --network blocked --local-credentials absent \
      --accepted 2 --rejected 0 --deferred 0 --head <current-reviewed-head>

The run id is an identity, not a range selector. The helper independently finds:
- Original session_meta thread identity and a unique original rollout using the
  existing refusing resolver. Parse the entire observed snapshot; malformed
  outer records or undeclared model turns anywhere still refuse.
- The earliest relevant fresh creation, paired to its actual call/output, with
  WT_CREATED=1, fresh/cross-repo lane, exact issue-anchored branch and target
  worktree. Follow an exec session through its completed poll where necessary.
  A prior matching reused/resumed/preexisting creation cannot be discarded in
  favor of a later convenient fresh one.
- An initial successful empty `git status --short`/`--porcelain` for that exact
  worktree, before the first plan-record edit/approval. Use the earliest such
  probe; a dirty first probe refuses rather than searching for a later clean one.
  This claims Git-visible cleanliness, not absence of ignored/private files.
- One mint and begin for the requested run and one matching approval. The
  approved plan record at the requested Git head must name that run, issue,
  base and granted approval; bind branch independently through the creation
  result and actual Git branch/head, because the existing record has no Branch row. The original observed approval digest must
  match its unchanged approved prefix; later append-only evidence is allowed.
  Base must resolve unambiguously and be an ancestor of the requested current
  head; the fresh creation's initial HEAD must match it.
- All model turns active from the creation CALL (before worktree materializes)
  through the full snapshot EOF, carrying the preceding active turn_context
  into the range. Exactly one model may occupy that conservative span, and it
  must differ from the actual reviewer. A later model switch also refuses.

The receipt records original relative rollout identity, complete snapshot byte
length/SHA256, derived start event/call/output digests, issue/run/branch/base/head,
approved-plan digest and explicitly excluded prefix model/count information.
It never publishes raw rollout bodies, private host paths or arbitrary ranges.
For a growing original rollout, re-derivation verifies the exact original prefix
of the recorded complete snapshot length/hash; the writer itself always reads
the full available snapshot and accepts no caller-supplied end/length.

Narrow adapter: support actual native Codex response_item custom_tool_call exec
with literal tools.exec_command cmd/workdir values, ordered completed result
objects/input_text blocks, and literal write_stdin session correlation. Recognize
only the flow helper/status anchors above, not arbitrary command effects. Accept
an approval as a final standalone flow-plan-record command whose successful
machine output and Git-approved-prefix hash agree. Dynamic/aliased commands,
unmatched callbacks, truncated results, unsupported shell wrappers, missing
clean probe, old/resumed worktrees, overlapping/ambiguous run identities or
unverifiable baseline/approval refuse explicitly. Other harnesses and arbitrary
manual windows remain unsupported. Do not infer that an excluded prefix was
read-only; retain its model/count boundary and rely on the verified fresh flow
contract plus the actual reviewed original ordering. No OS-authenticated or
complete off-thread authorship claim.

### Controls, validation and delivery order

Committed adverse inputs go through production writer, asserting no receipt on
refusal. A valid original mixed-model stream with only registration before its
fresh run succeeds only with the explicit proof; default remains a refusal. A
model switch inside the derived span, reused/dirty worktree, wrong Git identity,
missing approval, omitted earlier anchor and altered original prefix refuse.
Enrollment must still reject absent/other-branch/unreachable/unsupported receipts.
No skip or hand-authored ran record is an acceptable substitute.

Run focused receipt/parser and enrollment tests, mirror generation/parity,
committed controls with pre-fix red evidence, two counter-model passes, and full
make verify in a granted4-worker slot. Required exact-head CI and root review
precede merge. Then update1556 onto the merged helper, generate its truthful
receipt from ORIGINAL evidence, run unchanged enrollment and full required CI,
and complete the actual556 handoff. BB uses the same supported contract only
if its own original evidence qualifies; unsupported history remains refused.

Scope: medium, one existing helper plus tests/fixtures and scoped documentation;
approximately250-400 helper lines and150-250 test lines, generated mirrors derived.
Risk: the native harness adapter is intentionally narrow and may refuse another
legitimate invocation. Broaden only with a concrete safe fixture and new gate,
not an arbitrary range escape. Proofs derive visible flow-run model attribution;
they do not authenticate an editor or work performed outside the original trace.


Root gate: bounded attribution only, parse literal adapters without executing transcript code; original snapshots bind bytes, not authenticity. No weakened enrollment or fabricated/skip receipt. Required original reviews/counts, two reviews/full verification/root/exact CI. Actual Branch binding is creation plus Git identity, not a missing plan row.


### Approved execution addendum - final contract

Root execution-events, freshness-evidence, redirected-creation and source-semantics
rulings supersede the initial JS literal/poll adapter, mandatory clean probe, raw
file-prefix hash and single-context-record assumptions above. The original approved
Section C is retained as evidence. The maintained final contract is ADR 0007
"Fresh flow attribution for a Codex implementer".

### Fresh flow model scope for a Codex implementer (#1557)

Whole-thread attribution remains the default: conflicting model contexts refuse.
An explicit `write --implementer-thread-id THREAD --implementer-flow-run RUN`
can derive the implementer for a genuinely fresh flow run. This is available only
for a `ran` receipt in the default review direction; reviewer and delegated
attribution keep their existing rules. Schema 3 records this additional evidence;
schemas 1 and 2 retain their contracts. Independence, scope, network and credential
checks still apply, and enrollment still refuses a missing receipt.

The writer reads the complete, unfiltered original rollout snapshot. Only original
harness `event_msg` / `item_completed` / `CommandExecution` events from
`unified_exec_startup`, with completed status, integer exit 0, unique execution
identity and matching thread/turn identity, establish anchors. Printed tool response
blocks establish none. A new branch and worktree (`WT_CREATED=1`, fresh/cross-repo
lane, `WT_BASE=origin/main`) must join the issue, branch, base and current Git head.
Unique ordered literal reconcile/mint, begin-run and approval commands and observed
output stamps join the requested run and Git plan. Captured output must contain
exactly one exit marker per plan helper, all zero, and unique output anchors in
source order despite stdout/stderr interleaving. This is an observed metadata
join: aggregate output cannot establish which command emitted a marker.

Schema 3 always records `approval_execution: "unverified"`. It does not certify
that a workflow approval helper executed successfully or authenticate an approval.
An auxiliary Python command can print a stamp after a helper fails to launch;
that input may still establish the model scope, but can never produce a verified
approval claim. Public validation and source audit refuse a forged verified flag.
Fresh creation is stricter: its event contains only creation, or the bounded
stdout-file/cat transport and optional other-issue head-check, with no opaque
Python or other auxiliary command capable of supplying creation evidence.

The supported shell vocabulary is deliberately bounded: literal standalone helpers
separated by unquoted newlines/semicolons, closed quoted Python heredocs treated as
opaque plan data, literal driver/stale checks, registry registration, read-only rg
pipelines, and the captured uv preparation forms. Functions, conditions, loops,
eval, substitutions, dynamic helper arguments and unsupported shapes refuse.
Creation stdout may go to one literal absolute scratch path only when immediately
followed by `cat` of that path, with the original unique new-branch diagnostic,
initial HEAD and successful helper exit still captured. The audit never rereads
that historical scratch file. Append/stderr/dynamic redirection is unsupported.

Model scope begins with the earliest original context matching creation's
originating turn ID. Repeated contexts for that turn and every subsequent context
through snapshot EOF must agree. There is no caller-selected line, time, end or
model window. Evidence includes the source-relative rollout identity, full snapshot
byte length/hash, context/creation boundaries, exact anchor record digests and
excluded-prefix model population. Initial cleanliness is `measured-clean` only
when an original empty Git status probe supports it; otherwise it is `unmeasured`.
Observed dirty/contradictory state before begin refuses; a later clean probe cannot
erase it. Fresh creation and driver-clear output alone never mean measured clean.

Approval uses the actual `flow-plan-record.section_digest` semantics: SHA256 of the
run section with trailing newlines removed. The original stamp must match a unique
approved run-section prefix in the plan at the reviewed Git head, allowing appended
execution evidence while preserving the approved bytes. This is not a raw whole-file
hash and no baseline is restamped to force a match.

`audit-flow RECEIPT --codex-sessions-dir ROOT` re-derives the recorded captured
prefix and compares all evidence. Later appended transcript records do not change
what the receipt captured; altered or truncated captured bytes refuse. Run it from
the original worktree with the recorded Git head available. Hashes bind bytes, not
authenticity: these receipts assert visible session/model scope, not complete
authorship, absence of hook/off-thread changes, or resistance to coordinated
forgery of both original log and receipt. Original unsupported history remains
unsupported; do not filter a rollout or fabricate a skip/run to enroll it.

Qualification: read-only derivation on actual original AA1554 and BB536/489/563
rollouts names gpt-6.1-sol. AA1554 has measured-clean evidence; BB runs are
unmeasured. No private transcript content is published and no production receipt
has yet been generated. The original scope and reviewer independence are unchanged.


### Superseding approval claim ruling and review pass 1

Root mailbox20 / gate-1557-approval-claim supersedes the brief intervening AST
permission: no Python AST interpreter or validator was introduced. The required
claim is fresh-branch-scoped implementer model, not authenticated workflow approval.
Schema3 always records approval_execution=unverified. Original observed run/stamp
and Git plan joins remain required but do not establish marker provenance.

Completed independent pass1 (codex/gpt-6-astra) report Ws18Np.md, stream FnVl4t.jsonl,
full scope, blocked network, absent local credentials, found1 HIGH and2 MEDIUM.
All3 accepted: HIGH auxiliary-output provenance is resolved by the explicit claim
narrowing above, not by falsely claiming that the spoofed approval input refuses.
The two MEDIUM dirty-probe bypasses are fixed by token-based extraction and a
normalized target-worktree cutoff. Before changes, all4 production CLI regressions
failed: actual missing-helper+Python-spoof, neighboring begin, tab and quoted probe.
The first now passes only with unverified approval, and an edited verified flag
refuses validation/audit. The other3 now refuse. Original receipts were not fabricated.


### Review pass 2 and final regression disposition

Completed independent codex/gpt-6-astra pass2: report M2hhtq.md SHA256
 e20e259c7850b4636f09acccb9eaebe942207ee0bfd5e789df150c28449eefc1;
stream btEPWh.jsonl SHA256
 68c7d522aff265d3a125765e7300522cda5f73b490f0582562f68cdd6359ed44.
Full scope, blocked network, absent local credentials. Accepted1 HIGH quoted
redirection replay and1 MEDIUM Git environment selecting a neighboring repository.
Both fixed: quoted/escaped greater-than tokens cannot become shell operators,
status probes reject all inline environment assignments, and helper prefixes allow
only flow session identity variables. The4 production CLI cases failed before the
fix (/tmp/cpp-1557-review2-red.log) and now refuse; dirty-neighbor/clean-target also
requires an unsupported-environment refusal instead of misreporting target dirt.

Root independently found historical audit tied to current worktree root. A real
write -> commit receipt -> merge primary -> normal worktree removal -> audit case
failed before the fix (/tmp/cpp-1557-audit-cleanup-red.log). Audit now derives the
historical root text from the hash-bound original creation event and compares paths
lexically, without resolving/recreating/probing the former directory. Current Git
objects provide the recorded head/plan. Writer still requires its current root and
branch. Root will independently review this post-pass2 fix; no third review run.

Final focused writer/audit/control suite:74 passed, including source mutation,
claim narrowing, all four second-review cases and normal cleanup audit. Actual
original AA1554, BB536/489/563 remain eligible as gpt-6.1-sol, with cleanliness
measured-clean/unmeasured/unmeasured/unmeasured and approval execution unverified.
Default mixed-thread refusal remains. Earlier combined receipt/unchanged enrollment
integration suite:397 passed before final review fixes; full gate follows.

Pass1 report SHA256:9f34a8bac3954dd5035246e2029543e15fe8d0832856e8ebf1678b7daf74a055;
stream SHA256:465e366472f5770f02a6caba77335c5284b8d953d8e77926f3762c431f83bc37.
Total completed independent reviews2, accepted5, rejected0, deferred0. Red-case
count unit for the receipt is one named top-level Red cases bullet per report:
pass1 nine, pass2 nine;18 proposed. These are report entries, not nineteen distinct
new regressions; control coverage and pre-fix failures are enumerated separately.

Plan compliance reports file-set agreement (6 planned/18 touched) and EXIT3 record
stability because approved execution addenda were appended. Original Section C is
unchanged; no baseline was restamped. Root final review must assess these additions.


### Receipt and final gate inputs

Root accepted the count unit:18 report entries (9+9), with11 fully covered when
first proposed, not after-fix credit. Pass1 covered entries: harness validation,
shell allowlist, fresh creation/redirect, model boundary, captured-prefix audit
(1,2,4,7,9). Pass2 covered entries: shell allowlist, execution anchors, Git bindings,
model span, verified-approval schema refusal, source audit (3,4,5,6,7,8). Mixed
entries containing bypasses or untested CLI/schema/head inputs are not credited.
These are report categories, not a claim of18 unique controls.

Production receipt generated by the real writer from this original full thread and
the original completed final review stream, with passes2, accepted5, rejected0,
deferred0, implementer codex/gpt-6.1-sol and reviewer codex/gpt-6-astra. Both actual
review probes reported full/blocked/credentials absent, but the unchanged writer
conservatively downgraded receipt review scope to unverified because one command
output contained a read-denial marker. That may be source content; no override
was used. Approval execution is separately unverified by the schema3 contract.
The production audit re-derived the captured source prefix successfully.

Root independently ran74 focused controls, including default refusal, forged
approval flag, second-review fixes and cleanup audit, and cleared final source.
Full make verify will run with explicit PYTEST_WORKERS=4 in the granted slot.


### Full gate failure and bounded test dependency accounting

First full make verify at f0e07808 failed:4 failed,8215 passed,1 skipped in341.19s.
All4 were tests/test_test_binary_guards.py: real tree clean, revision widening,
timeout widening and report/gate consistency. The new scoped Git dependency made
the unchanged static one-hop checker charge104 legacy CLI test defs with Git.
This was a real gate failure, not a baseline flake. The full log is retained at
/tmp/cpp-1557-make-verify.log.

A local OSError-to-refusal catch was tried and reverted: callers already turn
missing Git into a clean scoped refusal, and the checker correctly treats a
re-raised failure as still requiring Git. No missing-Git regression red is claimed.
Production helper bytes and generated mirrors remain unchanged by this gate fix.

The existing per-def binary-guard allow mechanism now names only104 legacy defs
that never select --implementer-flow-run; optional Git tracking tolerates absence.
Actual PATH-empty execution:196 passed,86 explicit Git-dependent skips. Exact
JUnit/collection comparison proved all130 parametrized cases under those104 defs
passed, with0 skipped/xfail/failure cases. The mapping is retained at
/tmp/cpp-1557-no-git-exception-proof.json. Scoped tests keep @requires_git and no
module skip or checker/source exemption was added. A separate test sets up its
fixture with Git then launches the real scoped writer with PATH empty: refusal,
no traceback, no receipt. It is a negative control, not a newly failing regression.

The unchanged checker passes (221 files,5838 tests,1332 guarded,114 explicit
exemptions including10 pre-existing); all142 binary-guard tests now pass.
Root reviews this test-only delta before the full four-worker rerun.


### Staged local verification completed

The rerun at2f9fa304 passed all8220 pytest cases with1 skip in342.05s, then the
aggregate command stopped on2 mypy narrowing errors. It did not exit0. The skip
was the explicitly unstaged .ci-bin toolchain case. At the two flagged sites,
_flow_need invalid-value calls became equivalent explicit if-invalid/raise guards,
with identical conditions, FlowScopeRefused messages and acceptance/refusal logic.
Normal4 mirrors and SHA files were regenerated. Root independently read and
cleared this exact source delta; no third counter-review or redundant full-suite
rerun was performed for the equivalent guards.

Whole typecheck subsequently passed383 files. All75 affected writer/audit controls
passed in6.91s; final lint passed. Every remaining verify prerequisite was then run
explicitly from the Makefile list (excluding the already completed tools/lint/test/
typecheck phases), followed by the final coverage report: exit0. Log:
/tmp/cpp-1557-remaining-verify.log. This is staged completion, not a claim either
original make verify command exited0. Required remote CI still runs the final
committed tree in full.

Remaining gates included shellcheck, bandit/import audits, all84 registered
negative controls with discriminating anchors, budgets/links, generated skills,
instrument/census/CI coverage, host-write policy, version/Unicode/trailer checks,
behavioral/eli5/tool-risk checks and advisory skill coverage/enrollment readers.
All74 generated skills are in checkout sync; no installed host copy was changed.
The actual captured-prefix receipt audit and unchanged enrollment gate pass.
Lane check:19 touched paths,0 extra/contested paths; working diff clean. The
optional --granted comparison was not requested and reports ungranted as unknown;
the exact declared file lane matches the root assignment.

Limits remain explicit: host jq1.7 differs from pinned CI1.7.1; the final coverage
report names runtime, host, network and CI-only checks not executed locally.
Flow-check advisory closure currentness is stale after the helper changed, and its
runtime axis is unknown. No historical snapshot was rewritten or currentness/
readiness claimed. Required exact-head CI and root/current-base clearance precede
merge; host installation/deployment remains unauthorized.

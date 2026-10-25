# Flow run record - issue #1554

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=fe505ef11f9d4380acfb80637c9dd02c -->
## Run 1

- Run-id:            fe505ef11f9d4380acfb80637c9dd02c
- Run-start:         fb5883897cf37ef62de44b5879748f9bb2423cf2

- Issue: #1554
- Base SHA: fb5883897cf37ef62de44b5879748f9bb2423cf2
- Necessity verdict: Still needed
- Approval: granted
- Approver: skillc-complete orchestrator, GATE GO-WITH-CONDITIONS #1554
- Recorded at: 2026-10-24T22:16:29.176865+00:00

### Section B evidence

Verdict: Still needed.

Issue created 2026-10-24T21:20:42Z. No later CPP commits touching the reader,
tests or script documentation were found; merged-PR search since 2026-10-24 was
empty. Relevant inspected history: #1369's bundle reader and conformance fixtures
pinned to skillc 2202603; CPP #1371/#1550, d33fd6a7, establishing ADVISORY
enrollment; fb5883897 current CPP base. Duplicate/superseding search considered
#1554, #1367, #1084, #1292, #404 and #864; none supersedes this bounded child.

Sibling worktree inspection found no readable unpushed changes on this reader,
conformance test or docs/scripts.md. Six old scratch worktree references
(cpp-652c, cpp-86641e8, cpp-b318, cpp-ca3030d, cpp-f857, cpp-main) are unreadable
and remain unexamined, not evidence of no work. The fresh #1554 tree is clean.

The producer's stable real artifact has 11 original records, two separate trial
configurations, both overall INCONCLUSIVE, all three task criteria SATISFIED and
mandatory installation-ready UNKNOWN. Its original/corrected honesty counts and
#534 lineage remain separate. Root independently byte-compared all 11 records
and verified public reproduction. Exporter fixes/controls are in #556; CPP code
must not import that runtime or pretend it independently rechecked withheld bytes.

Observed reader gap, repeated against CPP fb5883897: original records read
inconclusive; forged PASS is refused; removing a manifest still reads inconclusive
while skillc refuses it. The existing conformance corpus explicitly classifies
attempt-accounting/bad/graded-without-manifest as outside CPP's subset. The existing unaccounted-attempt case also contains a captured planned attempt
with no result; the current reader can interpret only the remaining results.
These required-record presence clauses are the exact boundary to extend, not
the whole producer validator.

The existing Makefile already runs behavioral-eval-check, skill-coverage-map-check
and eval-enrollment-check with --advisory. Existing freshness checks compare the
mapped skill tree, references and bundled helpers, while retaining unknown and
not-evaluated states. ADR 0011 already says this evidence is advisory. No new
blocking rule, universal threshold, schema family or generic provenance service
is needed.


### Section C - the approved plan

1. `scripts/check-behavioral-eval.py` - require every captured lifecycle to retain its own manifest and at least one result, and require a manifest for every actually graded result. Validate these joins across ALL planned attempts and records before result interpretation or any early inconclusive return. Keep the legitimate not-run, unavailable and inconclusive lifecycle states that need no result; preserve declared NOT_RUN/UNAVAILABLE result behavior. Do not add broader disposition/run-state consistency or receipt-stand-in checks. Add planned/retained attempt/result counts to bundle-reading context without pretending a first inconclusive verdict certifies every record. Remove global claims that no model trial has ever run from absence text and docstrings. Preserve the existing verdict vocabulary and advisory exit behavior.
2. `tests/test_behavioral_eval.py` - regressions for a graded result without a manifest, a captured attempt without a manifest, and a captured planned attempt without its result, plus legitimate not-run/unavailable/inconclusive compatibility; verify the consumer diagnoses every relevant forged/missing case on the real two-attempt copy. Keep schema and advisory/crash distinctions intact. Run the required-record regressions red on fb5883897 before the fix, including a two-attempt population whose remaining result re-derives PASS and one whose first result is INCONCLUSIVE.
3. `tests/test_behavioral_eval_skillc_conformance.py` - move the already committed graded-without-manifest and unaccounted-attempt cases from OUT_OF_SUBSET_BAD_CASES to FLAGGED_BAD_CASES. Retain every other explicit subset limitation, including the receipt stand-in and stale-receipt cases.
4. `controls/behavioral-eval/control.json` - register the existing golden graded-without-manifest and unaccounted-attempt inputs as BAD cases through the production CLI; preserve the good twin and blind-anchor discrimination. Update the current limits description to distinguish historical fixture controls from the real D3 input, with no claim of full producer validation.
5. `tests/test_retained_d3_handoff.py` - verify the actual committed producer artifact, all 11 record hashes, exact identities and two independent trial views; call CPP's production reader and existing freshness/enrollment functions. Exercise forged positive, missing manifest/result and changed mapped skill/reference/bundled-helper content, asserting the planted precondition before the verdict. Keep raw object-byte verification attributed to the producer rather than synthesizing unavailable payloads.
6. `docs/scripts.md` - update only the behavioral-eval entry for actual live consumption, current advisory flip conditions, supported producer layout, new required-record completeness clauses and precise provenance/validation boundaries. The existing paragraph saying arrival alone makes the gate blocking is superseded by the already implemented #1084/ADR 0011 policy and must not be repeated with this delivery.
7. `docs/measurements/behavioral-eval/README.md` - concise real D3 interpretation and repeatable CPP reader/freshness/enrollment commands, criterion counts and readiness unknowns, source/correction links, reviewed producer SHA and explicit public reproduction limits.
8. `docs/measurements/behavioral-eval/d3-flow-check/ledger.json` - original producer ledger, copied byte-for-byte.
9. `docs/measurements/behavioral-eval/d3-flow-check/lifecycle-a-a59b3bcee76f.json` - original lifecycle.
10. `docs/measurements/behavioral-eval/d3-flow-check/lifecycle-a-89a2ab5de3cb.json` - original lifecycle.
11. `docs/measurements/behavioral-eval/d3-flow-check/manifest-a-a59b3bcee76f.json` - original manifest, with withheld object references explicit.
12. `docs/measurements/behavioral-eval/d3-flow-check/manifest-a-89a2ab5de3cb.json` - original manifest.
13. `docs/measurements/behavioral-eval/d3-flow-check/observation-a-a59b3bcee76f.json` - original observation.
14. `docs/measurements/behavioral-eval/d3-flow-check/observation-a-89a2ab5de3cb.json` - original observation.
15. `docs/measurements/behavioral-eval/d3-flow-check/receipt-a-a59b3bcee76f.json` - original UNKNOWN-readiness receipt.
16. `docs/measurements/behavioral-eval/d3-flow-check/receipt-a-89a2ab5de3cb.json` - original UNKNOWN-readiness receipt.
17. `docs/measurements/behavioral-eval/d3-flow-check/result-r-87b212a5b2e6.json` - original INCONCLUSIVE result.
18. `docs/measurements/behavioral-eval/d3-flow-check/result-r-e336ef4c3b77.json` - original INCONCLUSIVE result.
19. `docs/measurements/retained-exports/d3-flow-check/export.json` - unchanged producer export metadata, outside the consumer's candidate record directories so it cannot be misread as a result.
20. `docs/measurements/retained-exports/d3-flow-check/report.json` - producer-reported historical summary, unchanged and explicitly not CPP-certified grading.
21. `docs/measurements/retained-exports/d3-flow-check/coverage.json` - unchanged producer-reported independent trial views, not pooled or turned into skill-use claims.
22. `docs/measurements/retained-exports/d3-flow-check/PROVENANCE.md` - exact merged producer commit/file hashes, copy commands, original report/correction lineage and custody/privacy limits. No host-private paths or raw transcript bytes.

Scope: medium, roughly 200-350 reader/test/doc lines plus the copied producer
artifacts. No Makefile or enrollment implementation change is planned: the normal
CPP gate will discover the flat real record population in its documented immediate
subdirectory layout. No generated mirrors are needed: the actual current generator
reports both scripts/check-behavioral-eval.py and docs/scripts.md NOT BUNDLED.
Required issue-1554 workflow plan/as-read files follow the workflow separately.

### Exact interpretation and boundaries

- The actual default CPP reader must report inconclusive with two planned and
  retained attempts/results in context; source records and human report make both
  attempts' three SATISFIED criteria and mandatory UNKNOWN readiness inspectable.
  This is not a new per-skill verdict and does not fill missing skill-evidence.
- Existing skill coverage/enrollment checks report applicability/currentness of
  their explicitly mapped skill/reference/bundled-helper population, not a fresh
  validation of every external runtime dependency. Exact broader closure identities
  remain pinned producer metadata; unexamined context remains unknown. This delivery
  must not claim a stronger freshness population than those readers inspect.
- The producer validates the complete bundle and private cited bytes at export
  time; CPP independently restates its narrow subset plus the required-record completeness
  clauses. The unchanged producer metadata and reviewed commit are the custody
  boundary. Neither role strings nor hashes authenticate a consistent forger.
- Integration tests bind the copied public artifact to its producer record hashes
  and summaries; they do not claim the runtime consumer re-runs skillc's validator,
  authenticates the source, reads withheld transcripts, or independently regrades.
- Adverse producer byte/object controls are already committed in #556. CPP adds its
  own production missing-manifest and captured-without-result controls and reuses existing forged-result and
  freshness negative-control families, retaining their known-bad inputs.

Risk/challenge: adding an optional producer-metadata/provenance subsystem would
increase this child substantially without making self-declared hashes authentic.
The bounded alternative above uses the reviewed artifact, exact copy/hash checks,
the existing reader and existing freshness/advisory mechanisms. If the intended
acceptance instead requires a new runtime whole-closure/metadata verifier, that is
a consequential scope change and needs an explicit revised plan; do not imply it
was implemented by this smaller archive handoff.

Validation: focused consumer, producer-conformance, actual-artifact, freshness and
enrollment tests; registered behavioral-eval controls and their blind anchor;
`make behavioral-eval-check skill-coverage-map-check eval-enrollment-check`; full
CPP `make verify` only in a granted heavy slot, plus exact-head required
ci/woodpecker/pr/woodpecker on a current strict base. Counter-model review before
full verification; keep the already measured mixed-thread receipt limitation
truthful if it recurs. No paid trial, deployment or host configuration change.


Approved gate: /run/user/1000/cc-flow-wave/skillc-complete/gate-1554.md; all-attempt captured manifest/result presence before verdict interpretation. Producer merge and final copy provenance required before CPP merge.

### Implementation evidence before producer merge
- Root granted the additional controls/behavioral-eval/cases/bad-bundle-early-unknown-forged directory (gate-1554-control.md); original Section C remains intact.
- Five regression cases were run red against fb5883897 before the reader fix: four two-attempt missing manifest/result combinations with a remaining PASS or early INCONCLUSIVE; one early honest UNKNOWN concealing a later forged PASS. Logs: /tmp/cpp-1554-red.log and /tmp/cpp-1554-all-record-red.log.
- The three registered CLI cases explicitly pin expected_exit: missing manifest/result require 6; later forged result requires 4. On the pre-fix reader they returned 0, 0 and 5 respectively (/tmp/cpp-1554-cli-exact-red.log). A generic BAD signal alone would not distinguish INCONCLUSIVE from forged, hence exact exit assertions.
- Focused make test (PYTEST_ADDOPTS limiting actual handoff, consumer, conformance, freshness and enrollment; PYTEST_WORKERS=1): 234 passed. make lint passes. No heavy/full verification run yet; CC has next slot.
- Public records/metadata copied from reviewed skillc branch afce0e4 + 62eb329 for integration work; final merged producer provenance and hashes MUST be recorded before CPP publication. No claim this draft copy is a merged handoff yet.

### Counter-model pass 1 and disposition
- Reviewer model measured by rollout-model: codex/gpt-6-astra; thread 01a17005-2964-7730-a7a7-468aa73b6368. Scope full, network probe blocked, local GitHub/SSH credentials absent. Report /tmp/codex-review.VEXNSS.md SHA256 a45b90754c52afb1a5267ad7e6e31488426df1267683725692eaba1345c18b16; stream /tmp/codex-review.bJ5SiV.jsonl SHA256 092f42428f010024830ca4fa910a82e606e9ab95f88636bd1fee17b3519bc056.
- One MEDIUM finding, accepted/fixed: live-checkout currentness assertions would make legitimate future content drift block the suite despite the ADVISORY policy. Mutation controls now establish a test-owned baseline, while historical producer/snapshot/enrollment identity joins are separate. The new copied-future-helper regression failed before this fix (stale vs current) and passes afterward; /tmp/cpp-1554-review1-red.log records the red run.
- Root requested exact integration joins: 12 mapped skill closure files plus description/body digests bind snapshot to export installed/skill_digests; snapshot/enrollment/D3 item CPP revisions bind the source subject revision. Broader installed/profile context remains outside mapped freshness, never silently certified.
- Historical integration and byte-identity tests pass; no assertion requires future live content to stay historically current. Source overview cross-trial receipt documentation mismatch recorded separately at https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6390310736 and left unchanged.

### Immutable historical reference refinement
- Root corrected the integration join to avoid freezing mutable global coverage/enrollment registries. Approved retaining actual historical CPP fb5883897 records under the already granted retained-exports directory. The freshness copy omits ONLY diagnose.command (private host paths), with original and derived hashes recorded in PROVENANCE; all other actual diagnose facts remain. Enrollment is byte-identical. No fictional diagnosis or enrollment decision was created.
- The future-global-registry-refresh control failed on the intermediate global join and passes using immutable historical copies (/tmp/cpp-1554-registry-refresh-red.log). The future-copied-helper regression also passes with test-owned baselines. Both allow legitimate future drift, while exact historical D3 joins remain inspectable.
- A premature second-review attempt was terminated after the root refinement arrived; its incomplete output is not counted as a completed review. Second completed pass will review the refined final diff.
- Producer PR560 merged a3e9ba8049c6dd3a97c64fd8d9d35e7296cd3835 after required full CI passed on exact reviewed head3b7e256, strict basec8045553. All 14 copied producer files (11 records + 3 metadata) compare byte-identical to merged Git objects. Draft provenance was replaced with the actual merged SHA.
- Known mixed-model implementer-thread receipt limitation also applies here; root explicitly approved truthful completed-review evidence with missing receipt, model/stream hashes, IDs and measured scope. No fabricated receipt or skipped-review claim.

### Counter-model pass 2 and full-gate readiness
- Second completed reviewer measured codex/gpt-6-astra; thread 01a1700b-db48-7af3-9f12-89d355d0a462. Full scope; network probe blocked; local GitHub/SSH credentials absent. Report /tmp/codex-review.3pkcer.md SHA256 3a405143d86b2a1c72e75e07ec4a18e2e3de2229ab2484adb9dac2bffb9d0117; stream /tmp/codex-review.QLKGFS.jsonl SHA256 1c60aca37c9f06138b48bfb4e3c523da1e83db2b802c061757561c3021009683.
- One MEDIUM finding accepted/fixed, none rejected/deferred: the D3 assertion read the mutable parent population, so a legitimate earlier-sorting FAIL neighbor would fail this test even though D3 was unchanged. D3 is now judged directly; parent discovery is tested with an isolated actual-copy population. Neighbor regression failed before the fix (expected inconclusive, got failure; /tmp/cpp-1554-review2-red.log) and passes afterward. Final handoff file: 18 tests pass; repository lint passes. No third completed model review.
- Both completed passes: two accepted/fixed findings total. Known receipt limitation is unchanged from the measured producer-stage refusal: `turn_context records disagree (gpt-6-astra, gpt-6.1-sol)`. It applies to this same mixed-model implementer thread; actual reviewer identities come from each real exec-stream rollout. Root approved completed reviews with a documented missing receipt, never a filtered rollout, fabricated receipt or skipped-review claim. Canonical limitation: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6389865902 .
- Root independently cleared all copied bytes and the immutable/redacted reference delta. Full CPP make verify slot granted after handling completed-pass-2 findings, with PYTEST_WORKERS=4; no other local full suite concurrent. Calibration stores/containers are outside this work and untouched.

### Final local verification
- `make verify PYTEST_WORKERS=4` exited 0; /tmp/cpp-1554-make-verify.log. Suite: 8,173 passed, 1 skipped, 221.08 seconds. Repository lint and mypy pass (384 source files); shellcheck scans 166 files; bandit scans 149 with zero gating findings; import audit examines 386 files with no undeclared imports. Existing audit limits/allowances remain explicitly reported.
- Full negative-control battery: 84 registered controls discriminate, including all 30 behavioral-eval cases with exact exit assertions for the new required-record/forgery cases and a blind anchor. Binary/fixture guards, docs/links/mirrors/coverage gates and other verify prerequisites pass. The closing report explicitly names host-only, CI-only, runtime and otherwise unexamined instruments; this does not claim they ran locally. Host jq is 1.7 versus CI pin 1.7.1, reported by tools-check; exact-head CI remains required.
- Default production reader reports INCONCLUSIVE with two planned, retained and result-bearing attempts. The explicit immutable historical freshness CLI reports mapped flow-check current and 73 unmapped skills not evaluated; immutable enrollment reports ADVISORY current, NOT behavioral assurance. Historical/current registry scope and broader unexamined dependencies remain explicit.
- Fresh origin/main remains fb5883897; no base drift. Lane check: all 34 changed paths inside grant, no contested/ungranted/extra paths. Issue-body drift is clean. Plan helper findings are the explicitly approved CLI control directory and two historical reference additions, plus appended run evidence; original approved Section C is unchanged. Exact-head full CI and separate root merge clearance remain.


### Actual receipt after merged1557 dependency

CPP PR1558 merged at eac62c9c6b1e6281b00bd422c862a28f44bf0dd0 after exact-head
required CI3346 succeeded. The retained clean helper bytes equal that merged Git
blob9e6a2d0dabdca04f0f7569d997ea0233b5c4f5f8 (SHA256
8e426660c2f9c435a8f7650292e0be7c82a7ed1d57b7a4c2fd29f441731f5904).
It generated docs/measurements/counter-model/2026-10-25T005259Z-issue-1554.json
from the ORIGINAL full implementation thread and original completed final review
stream, while this worktree was still at the actual reviewed consumer head
2b8b20c86a71c378ec3130075a885d16f33b7c42. The reviewed-head field was not relabeled
after integrating a newer base. The original mixed-thread refusal and CI3344
missing-receipt failure remain historical facts; they were not bypassed or converted
to a fake skip.

Actual receipt: implementer codex/gpt-6.1-sol; reviewer codex/gpt-6-astra;2 completed
passes,2 accepted,0 rejected/deferred. Reviewer scope full, network blocked, local
credentials absent. Initial cleanliness measured-clean from the original probe;
approval_execution unverified as required by schema3. Production captured-prefix
audit passed. Git plan/observed stamp joins attest model scope, not authenticated
workflow approval or complete off-thread authorship.

Red counts use the same explicit report-entry unit as1557:7+7=14 proposals,8 fully
covered at first proposal, not after-fix credit. Pass1 covered entries1,2,4,7;
pass2 entries1,3,5,6. Omit the two copy/hash categories (pass1 entry5 andpass2 entry4):
intact hash/identity assertions exist, but complete pre-proposal mutation execution
was not retained. Also omit partial later-unreadable twins and the actual reviewer-
found freshness/neighbor couplings. No tests are added now to earn retroactive credit.
Root accepted this conservative mapping.

The receipt is committed before current-base integration. The final consumer code
must remain unchanged apart from this receipt/evidence and reviewed upstream1557.
Targeted reader/handoff/enrollment checks and full exact-head CI follow; prior
1556 merge authorization is suspended until fresh root clearance.

Current-base integration0380b003 retained all reviewed consumer reader/test/control
and public artifact bytes unchanged. Targeted reader/conformance/handoff/enrollment:
214 passed in3.50s; lint/typecheck384files pass;74 mirrored skills in sync. Actual
behavioral control battery, enrollment and captured-prefix audit pass before push.
No redundant full local suite was repeated for receipt/upstream-helper integration;
the original full8173-pass run and helper full/CI evidence remain, with fresh full
required CI and root clearance still mandatory for the final consumer head.

# Evidence for issue #1871

<!-- lanes-demonstrated run=bfcb7406630b437c84dcb536eaf0d5b7 plan=cf617b8f3e896426da702e207cfe1e9ea0863af744aef17a50c760407a8cf768 -->

| Lane | Result | Evidence |
|---|---|---|
| CI provider | passed | Actual Woodpecker YAML supplies scanner argv; CI staging/dependency/PATH test passes and rejects staging-line deletion. No GitHub Actions parity claim. |
| Project state | passed | Private one-commit histories consume both stored record forms and the real metadata helper's output. |
| Toolchain version | passed | Exact gitleaks 8.30.1 required; missing/wrong-version branches raise explicit UNKNOWN skips. Host Python plus pinned CI config only, no version matrix. |
| Run location | passed | Source found relative to test file; actual scan runs from private external git repository, using resolved executable paths. |

Guidance pin on pre-change main: **1 failed, 7 passed** in 17.68 seconds. The
other seven included the real pinned history scan returning exit 1 with
generic-api-key for the old-form input, exit 0 for stored generated metadata,
and exit 0 for actual begin-run/declare-salvage record output. After the one
guidance line: **8 passed in 3.55 seconds**. Missing-binary/wrong-version tests
assert the scan is skipped as UNKNOWN; they do not claim a scan took place.

New plus existing secret-scan compatibility suites: **25 passed in 17.85
seconds**. The parent control's registered case population remains exactly its
four original cases; adding this fixture directory does not alter its manifest.
Both fixtures stay inside the existing constitutive exemption, then identical
bytes are relocated outside it. Current config and metadata-only findings
template are copied unchanged. The CI command is read from actual YAML, with
only its executable resolved to the pinned binary; no --no-git is added.
The actual-generator reader uses sys.executable, never a PATH-dependent Python.

Quick checks passed: lint, typecheck (515 files), binary guards, command budgets
(100 documents, all command/driver deltas zero), import audit selftest/actual,
dependency-audit selftest/actual (43 packages, 0 gating findings; 2 Windows-only
pins not audited on Linux). A cold foreground typecheck timed out and is not
counted; the detached complete quick run exited 0 at 17:44:47Z.

No production scanner rule/config/allowlist, registry, census, build metadata,
helper or dependency changed. The test is inside the suite under ADR 0008's
bounded requirement; it is not a new registered gate.

Supplemental finding: an interrupted typecheck left one untracked atomic cache
fragment after a later successful typecheck. Removed only that owned fragment;
ignore-policy changes are outside this issue. Recorded after resolver verified
the open Nit Store (source search):
https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7066737231


First independent gpt-6.2-sol diff-only review accepted two test defects:
committed-blob identity could be lost under host autocrlf normalization, and a
relative PATH-discovered scanner could fail after cwd changes. New CRLF/host
configuration and relative-.ci-bin scanner cases both failed before the fixes
(**2 failed in 2.34 seconds**). Git setup now disables autocrlf for these owned
fixture commits, compares the raw HEAD blob against exact input bytes, and
uses raw actual-generator bytes. Git/scanner executable paths are absolute
before any cwd change. Corrected test module: **10 passed in 6.56 seconds**.
Lint/typecheck (515 files), binary guards and command budgets passed again.
No additional fixture files, command-doc changes or scanner configuration edits.


Second review found the history reader's own Git lookup still inherited a
relative PATH after cwd changed. The new case supplies only a relative .ci-bin
with git/scanner links and no absolute fallback; it failed on the pre-fix
reader (**1 failed in 2.32 seconds**). The scan child now receives an absolute
resolved Git directory on PATH, while CI argv/config/template stay unchanged.
Corrected module: **11 passed in 5.85 seconds**. A third bounded review is
requested for this concrete integration fix; no heavy gate or push yet.


Merged current main cd6d2b48 cleanly, with no scanner/config/CI-command or package
changes and no conflicts. Merged-head quick run completed at 17:57:06Z:
**28 new/existing secret-scan tests passed in 19.29 seconds**, lint/type/binary/
budgets and both import audits passed (43 packages, 2 Windows-only not audited).
The orchestrator authorized one third diff-only review (mailbox 36678), reason:
pass 2 found the history reader's Git lookup still depended on a relative PATH.
Hard stop afterward: further TEST-only findings are deferred with reason and
Nit Store record; a guidance-line finding is escalated. Merge is held behind
#1870 by the orchestrator; a later base refresh may be needed.


Third/final gpt-6.2-sol diff-only review reported no guidance defect. One low
TEST-only limitation was deferred under mailbox 36678's hard stop: deleting
Salvage from the stored GOOD fixture would still scan clean, although the
separate actual-generator case checks all three fields. No fourth pass or test
fix. Current fixture retains all fields; no deletion mutation was executed
under the hard stop. Recorded after resolver confirmed the open store (search):
https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7066926563
The derived schema-5 receipt records accepted3/rejected0/deferred1 and the
explicit reason/authority in its extra-pass explanation. All passes were
captured-patch/diff-only, without a reviewer shell; network/credential isolation
unverified. Product/source inputs remain unchanged since that review.


The first full gate on 7373bfc8 failed: **1 failed, 13214 passed, 4 skipped**
in 1120.02 seconds. Existing negative-fixture enforcement found the new
relative-PATH test lacked a directly recognized lookup precondition. The
standalone checker reproduced the same finding on merged main dbb485d4.
Orchestrator mailbox 36757 authorized correcting this gate failure without
reopening the deferred review finding. The case now directly asserts relative
Git lookup succeeds in launcher cwd and is absent in scan cwd, before the
reader runs. Two interrupted foreground checks are not counted as evidence.

Quick checks and both audits passed on merged main. The focused run caught a
setup error in this precondition correction: **1 failed, 79 passed** in 56.78
seconds, because the lookup-probe directory still existed when scan() created
it. The test now removes the empty probe directory before invoking scan().

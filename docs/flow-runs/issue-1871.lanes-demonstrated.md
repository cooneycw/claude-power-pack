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

# Issue #1288 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1288
- Read at:      2026-09-27T14:09:59Z
- updatedAt:    2026-09-27T13:35:48Z   (context only - moves on comments and labels)
- Body digest:  e1d2ed06b06a6532ca50a8982ab2a43f409d6af47dc75078794ca7ca4e3120e4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2886 of 2886 (cap 16384)

## Body as read
## Outcome

A secret detected during CPP verification still fails the appropriate check, but its value never appears in scanner output, pytest failure diagnostics, or the resulting agent/CI transcript.

Source: owner-requested capability assessment and incremental improvement 1, 2026-09-27, at `879df15`. Verified finding: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5856204051

## Observed behavior

`tests/test_secret_scan.py:_scan` invokes `gitleaks detect --no-git --verbose` without redaction. `test_the_repo_wide_scan_is_clean_with_the_fixture_committed` includes `result.stdout[:2000]` in its failure assertion. The assessment's normal `make verify` run detected a value in an ignored host-local `woodpecker/agent.env` and printed the raw assignment and `Secret:` field. No credential value belongs in this issue or its implementation evidence.

The same run produced 6,273 passed, 2 skipped and one failed test. The population/isolation cause of that failure already belongs to #1271 and https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743285044. This issue owns output confidentiality, not that population decision.

## Acceptance

- A synthetic secret is detected and still yields a finding/nonzero result, while the value is absent from both captured scanner streams.
- An intentionally failing pytest invocation through this helper reports safe rule/path/line/count information, with the synthetic value absent from the complete failure report, including assertion introspection.
- A clean input remains clean; malformed scanner/configuration failures remain distinguishable from detections.
- The newly added failure-output case is shown exposing the synthetic value against pre-fix code, and withholding it after the fix. Use synthetic data only; do not rerun a known leaking check over real host credentials to demonstrate the red case.
- Related assertion paths using the same helper are covered, and the source change passes the applicable repo gates. Account explicitly for #1271 if it still prevents a full workstation verification pass.

Proposed approach: request redaction at the scanner boundary and format assertion diagnostics from safe metadata. Another mechanism is acceptable if it preserves detection and demonstrates the same output guarantee.

## Scope and sequencing

Depends on: None.

Small, single-concern fix; start first. Coordinate with #1271 because both touch the secret-scan tests, but neither requires the other's implementation. No live credential rotation, secret retrieval or permission changes are part of this ticket; the operator's credential rotation is separate remediation. Do not suppress findings to make the test green, and do not introduce a broad transcript-masking subsystem.

Value-first sequence and related work: #1292. The sequence does not replace this issue's acceptance.


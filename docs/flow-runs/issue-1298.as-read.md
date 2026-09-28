# Issue #1298 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1298
- Read at:      2026-09-28T11:03:49Z
- updatedAt:    2026-09-27T17:59:08Z   (context only - moves on comments and labels)
- Body digest:  99924c8be584cb6b610e444f40237ebff70ceb3eb6dd370f50c8e18620aceeb1   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2293 of 2293 (cap 16384)

## Body as read
## Outcome

Test-step classification recognizes a real test runner in a quoted shell command and does not infer a test solely from an environment-variable assignment. Preserve #1294's fix for directory names containing `test`.

Derivative of #1294 / PR #1296, main `ce5f296`; owner-requested review and follow-up sequencing under #1292.

## Verified cases

- With step id `check`, `bash -c "/opt/venv/bin/pytest /tmp/cases"` is reduced by `_strip_directories` to `bash -c cases` and `is_test_step()` returns False. The source acknowledges this limitation. The classification misses an actual pytest invocation.
- Inline `PYTEST_WORKERS=4 make lint` is reported as a test because the regex treats `_` as a boundary. Existing finding: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5858154209.
- Positive controls: `pytest /tmp/cases` and an explicit test id remain test steps. Negative control: the typecheck helper under `/x/repo-test-foo/` remains non-test after #1294.
- The reviewed focused suite passes (89 tests); this is missing discrimination, not an existing red suite. Gate-level impact of the quoted form must be demonstrated rather than inferred solely from the classifier.

## Acceptance

- Commit regressions for both cases, failing on the pre-fix implementation and passing on the change.
- Demonstrate through the existing outcome/gate consumer that a quoted test runner's empty or skipped-only summary is qualified honestly, and that an environment-prefixed lint command is not expected to produce a test summary.
- Preserve path/space/operator cases already covered by #1294, direct and absolute runner paths, genuine test step ids, and make/uv test invocations.
- Use a bounded representation/parsing change. No execution of a command for classification, general shell interpreter, or new test framework. State unsupported command forms and keep uncertainty visible at the appropriate consumer.
- Run focused tests and normal flow verification, including the required PR lane.

Suggested scheduling: projects-88 after the supervise-fixture derivative, then #1262. Avoid concurrent edits to `lib/cicd/steps.py` / the same outcome fixtures with #1289. Scheduling is coordination, not a new hard issue dependency; no worker acknowledgement recorded yet.


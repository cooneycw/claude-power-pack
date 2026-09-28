# Issue #1291 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1291
- Read at:      2026-09-28T09:34:03Z
- updatedAt:    2026-09-27T13:35:51Z   (context only - moves on comments and labels)
- Body digest:  46c8ce749e8476acfe685957bad1ba67fef55132287ece4dd93e7411f4065134   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2767 of 2767 (cap 16384)

## Body as read
## Outcome

A confirmed exploratory web-QA bug can become a reusable regression test that a consumer project's test runner can execute without an agent interpreting the result again.

Source: owner-requested capability assessment and incremental improvement 5, 2026-09-27. The current `.claude/commands/qa/test.md` prescribes exploratory checks and GitHub bug reports, but does not specify an executable regression-test handoff.

Depends on: None.

## Smallest useful increment

Add an opt-in handoff for one supported, deterministic Playwright interaction flow, using the consumer's existing Playwright test setup. A different implementation is acceptable if it produces the same independently executable result. Start with one local fixture application and one reproducible bug, not a general natural-language test generator.

## Acceptance

- Given a confirmed bug with reproducible steps, the handoff produces a test file, exact run command, and trace/evidence reference suitable for the consumer's existing runner.
- The test uses an observable product assertion: it fails against the known-buggy fixture and passes against its corrected state. Demonstrate both; a syntax check, mock of the assertion, or agent statement that the test would fail is not sufficient.
- A third missing/unavailable-app case is reported as execution unavailable/error, not bug reproduction and not a pass.
- The saved test re-executes in a fresh browser context without depending on the explorer's ambient session. Any required setup/teardown is explicit and bounded; avoid arbitrary sleeps in the fixture.
- Export is opt-in and honors the project's paths/configuration. If no compatible Playwright runner exists, name the missing prerequisite and stop before claiming an executable handoff; do not silently install another stack.
- Trace artifacts from the demonstration use synthetic/local fixture data. Do not export production cookies, storage state, credentials or private page data into a repo or issue. Preserve a stable issue-to-test/evidence link without embedding those values.
- Canonical QA command changes regenerate and verify the Codex mirror, and the regression demonstration is part of an appropriate existing check path.

## Scope boundaries

No production-site writes, automatic issue creation without existing task authority, cross-browser matrix, visual-baseline service, or accessibility platform. Optional accessibility coverage is a later increment, not acceptance here. The readiness improvement from this assessment is related but not a hard dependency: this handoff can be implemented and demonstrated entirely with an existing local Playwright setup.

Value-first sequence and related work: #1292. The sequence does not replace this issue's acceptance.


<!-- flow-run n=1 id=9e8c402123294dc3a648ab53a46eeb82 -->
## Run 1 - issue #1472 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1472
- Read at:      2026-10-17T11:52:35Z
- updatedAt:    2026-10-17T11:48:55Z   (context only - moves on comments and labels)
- Body digest:  cb8b69908c566881e431ec6b95d12a0e8eeb416a45b691deba499fd5cdddf67f   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3917 of 3917 (cap 16384)

### Body as read
**Receipt tests inherit CODEX_THREAD_ID, so make verify fails when launched from Codex**

Found during the owner-requested October 17 refresh of the Claude Power Pack capability assessment in Downloads (assessment work, no implementation issue or PR), on main `020349564f87d1bd2b86800f9c8e2814fd239b79` (v9.0.0), using an isolated checkout.

- **Locations:** `tests/test_counter_model_review.py:357`, `:736`, and `:753`. The missing-identity and Claude-environment fixtures remove/set `CLAUDE_CODE_SESSION_ID` but leave the caller's `CODEX_THREAD_ID` in the subprocess environment. The receipt implementation now accepts that second identity source and rejects ambiguous dual identities.
- **Observed:** unmodified `make -k verify` ran 7,830 tests: **5 failed, 7,823 passed, 2 skipped**. All five failures are the above tests' parameterizations. The missing-identity cases instead attempt a Codex rollout lookup; the Claude-environment cases report an ambiguous implementer. The skip case can derive the real caller's Codex identity instead of exercising the intended missing-identity condition.
- **Controlled comparison:** `PYTEST_ADDOPTS='tests/test_counter_model_review.py -k "missing_implementer_session_id or skip_without_a_derivable_implementer or implementer_session_id_uses_flag"' PYTEST_WORKERS=2 make test` reproduces **5 failed, 2 passed** in the inherited Codex environment. Running the identical selection with only `CODEX_THREAD_ID` and `CLAUDE_CODE_SESSION_ID` removed from the command's environment gives **7 passed**. No source changes, deselection changes, or expectation relaxation were made between those runs. This diagnoses test isolation, not a production receipt failure or a passing full gate.
- **Impact:** a normal Codex development session cannot reproduce the green CI suite, and the negative fixtures do not establish their stated missing-identity precondition. The test's result depends on the launching agent.
- **Suggested bounded follow-up:** isolate both identity sources in the relevant fixture/helper, then explicitly install the identity required by each test. Retain intentional dual-identity coverage. Prove the repaired tests work with a planted nonempty ambient `CODEX_THREAD_ID`, and that missing-identity and ambiguity red cases still refuse for their intended reasons.

Evidence is retained locally under `~/Downloads/claude-power-pack-assessment-evidence-2026-10-17/`: `make-verify.log`, `receipt-tests-ambient.log`, `receipt-tests-without-agent-identities.log`, and `receipt-test-comparison.json`. No CPP code was changed as part of this assessment.

## Outcome and acceptance

Promoted from https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6233448823 after the owner asked whether this warrants a CPP issue.

The receipt tests must exercise their declared identity conditions independently of whether the suite is launched from Codex, Claude Code, or an ordinary shell.

- [ ] Reproduce the five failing parameterizations on the pre-fix code and retain the red evidence.
- [ ] Make the selected tests pass with neither ambient identity, a planted ambient `CODEX_THREAD_ID`, and a planted ambient `CLAUDE_CODE_SESSION_ID`; each fixture must explicitly establish the identity condition it tests.
- [ ] Preserve rejection of a genuinely missing implementer, an unavailable transcript, and ambiguous dual identities. Preserve positive tests for explicit flag precedence and supported environment-derived identities.
- [ ] Run the appropriate focused checks and full `make verify`; identify any unrelated failures separately.

A possible implementation is to clear both identity inputs at the relevant fixture boundary, then set the test-owned inputs explicitly. An equivalent solution is fine. Do not weaken production identity validation, skip the affected tests, or require developers to unset their real session identity before running the suite.


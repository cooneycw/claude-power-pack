<!-- flow-run n=1 id=8ecd4ac6ee3f419fb248e929c1a168d8 -->
## Run 1 - issue #1458 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1458
- Read at:      2026-10-17T00:46:50Z
- updatedAt:    2026-10-17T00:14:38Z   (context only - moves on comments and labels)
- Body digest:  9edf479acfcafc0fd549e278cf42754cdfaf17e351718fcf6cb113741958534d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1745 of 1745 (cap 16384)

### Body as read
Found while reviewing PR #1451 (merged as 6457407; Refs #1450).

## Defect

`.claude/commands/codex/code_review.md` (around lines 342-349 at 6457407) sets `CODEX_REVIEW_NETWORK=blocked` whenever `codex sandbox ... curl` exits non-zero and the plain `curl` outside the sandbox succeeds. The probe's exit code is never inspected. As a result, each of the following is reported as `blocked`:

- the sandbox failing to start (rc 101);
- a codex CLI usage error after a CLI change;
- a rejected `-c` key;
- curl being absent inside the sandbox;
- a non-fence TLS or DNS error.

**Reproduced:** codex-cli 0.162.1 in a Kyle session container panics with "bubblewrap is unavailable" (rc 101) even for `codex sandbox -- true`. That host therefore reports `network blocked`, and the measurement never ran.

`test_a_sandbox_that_cannot_start_is_blocked` encodes this conflation as intended behaviour. The doc's justification ("the reviewer cannot run any command at all") is not verified against `codex exec`, which is a different sandbox path from `codex sandbox`.

## Why it matters

This verdict is the control that actually fences the reviewer. The credential withdrawal is bypassable (filed separately). A `blocked` verdict that means "could not measure" is a blind instrument in the dangerous direction. It is printed on the relay banner and recorded on the counter-model receipt as evidence.

## Suggested fix

- Probe sandbox start-up first (`codex sandbox -- true`), and map a start failure to its own state (or to `unverified`), never to `blocked`.
- Report `blocked` only when the in-sandbox curl fails with a network-class exit code (6, 7 or 28).
- Commit the rc-101 case as a negative control that must report something other than `blocked`.


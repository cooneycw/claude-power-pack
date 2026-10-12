<!-- flow-run n=1 id=3e11f9050ddd4397bb0fcce2290ace09 -->
## Run 1 - issue #1442 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1442
- Read at:      2026-10-12T14:38:03Z
- updatedAt:    2026-10-12T14:37:56Z   (context only - moves on comments and labels)
- Body digest:  e7d8d091f604df895e558953b5304549fb2d4b6d23fff7085a1623946456eec8   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1889 of 1889 (cap 16384)

### Body as read
## Problem

The `flow_finish` security gate fails on clean `origin/main` (50261ddd), so every `/flow:finish` and `/flow:auto` run in this repository stops at Step 6, whatever it changes:

```
BLOCKED: CRITICAL: AWS Access Key detected at controls/lib-security-gate/cases/bad-critical-secret/leaked.py:4 [AWS_ACCESS_KEY]
SECURITY_GATE: flow_finish FAIL (blocked=1 warned=0; secrets-scanned=1900 ...)
```

That value is a deliberately planted, well-known AWS documentation example key: the BAD case of the security gate's own negative control. It landed in #1423 (5fd4ebe4, 2026-10-07). The repository has no `.claude/security.yml`, so nothing suppresses it. The suppression mechanism built for exactly this case (#1299, the exact-value `secret:` field) was never applied to CPP's own fixture.

Found while running `/flow:auto #1441`: reproduced by running `python -m lib.security gate flow_finish --path .` on a `git archive` of `origin/main`.

## Fix

Add `.claude/security.yml` with ONE exact-value suppression: `id: AWS_ACCESS_KEY`, `path` anchored to that one file, `secret` set to the exact planted value, with a reason.

- The control at `controls/lib-security-gate` runs the gate with `--path <case dir>`, so it never reads the repository-root config. The fixture stays BAD for the control.
- Negative control for the suppression (the gate lets work through, so it needs one): a test runs the gate over the real repository config with (a) the planted fixture → PASS, and (b) a DIFFERENT AKIA-shaped value added beside it in the same file → still BLOCKED.

## Acceptance

- [ ] `lib.security gate flow_finish` passes on the repository root
- [ ] a second AKIA value in the same fixture file still blocks
- [ ] a planted value copied to any other path still blocks
- [ ] `controls/lib-security-gate` still PASSes

🤖 Generated with [Claude Code](https://claude.com/claude-code)


# Issue #1256 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1256
- Read at:      2026-09-28T16:41:53Z
- updatedAt:    2026-09-26T13:01:32Z   (context only - moves on comments and labels)
- Body digest:  af740f492619a199d6e474ea2d97c853c88d4c83680086f64b348f0f2c6b8122   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2944 of 2944 (cap 16384)

## Body as read
## What is wrong

Inside a CPP checkout, `second-opinion` resolves to two different endpoints at two scopes, and CPP's own drift checks report the host as clean.

- **Project scope** - CPP's shipped `.mcp.json`: `type: http`, `url: ${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp` (since #633 / PR #651).
- **User scope** - `~/.claude.json`: `type: stdio`, `command: ~/Projects/mcp-second-opinion/run-with-aws-secrets.sh --stdio`.

`claude mcp list`, run from the CPP checkout on 2026-09-26, flags it:

> [Conflicting scopes] Server "second-opinion" is defined in multiple scopes with different endpoints: user (...run-with-aws-secrets.sh --stdio), project (${SECOND_OPINION_URL}/mcp). OAuth tokens are stored per endpoint, so authenticating in one context will not carry over.

In the same `/cpp:update` run on the same host:

- `scripts/drift-detect.sh` reported `NO DRIFT: 4 checked, 3 skipped`.
- `scripts/mcp-drift.py --check` exited 0.
- `/cpp:update` Step 6b classifies `second-opinion` as **OK** whenever it is registered. It checks that a registration exists, not how many there are or where they point.

Host facts at filing: `SECOND_OPINION_URL` is unset, so the project entry targets `127.0.0.1:8080`, which answers HTTP 302 on `/mcp`. The user-scope stdio entry is the one `claude mcp list` shows as connected.

## Why it matters

- Which endpoint a session uses depends on the directory it starts in. A session in the CPP checkout and a session elsewhere can reach different second-opinion servers, and nothing tells the operator.
- The drift check answers a narrower question than its verdict claims. `OK` means "registered", not "one consistent registration", so a conflict that Claude Code itself warns about reads as clean in the CPP report. This is the detector-contract failure: the success message claims more than its input supports.

## Decisions needed

1. **Which wiring is canonical for this host:** the stdio launcher at user scope, or the shipped HTTP project entry? CPP's docs (`CLAUDE.md`, `/cpp:init`) describe the HTTP entry; this host runs stdio.
2. **Should CPP's drift check report a multi-scope `second-opinion` with differing endpoints**, for example as a `SCOPE CONFLICT` status, instead of `OK`? It would report only; it would never remove either definition.

## Acceptance

- A host with `second-opinion` defined at two scopes with different endpoints is reported by `/cpp:update`'s drift step as a conflict, naming both scopes and endpoints, and not as `OK`.
- A host with one definition, or two definitions pointing at the same endpoint, is still reported `OK`.
- Both cases are committed as test cases, with the conflict case shown failing on the current check.
- Nothing is removed automatically. The remedy offered is Claude Code's own `claude mcp remove second-opinion -s <scope>`, run only on the user's say-so.

Found during a `/cpp:update` run on 2026-09-26, after flow:auto #1226 (PR #1255).


<!-- flow-run n=2 id=ac54966bc79a4478a13605ca6a59f7bb -->
## Run 2 - issue #1256 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1256
- Read at:      2026-09-29T10:24:07Z
- updatedAt:    2026-09-28T18:26:47Z   (context only - moves on comments and labels)
- Body digest:  af740f492619a199d6e474ea2d97c853c88d4c83680086f64b348f0f2c6b8122   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2944 of 2944 (cap 16384)

### Body as read
## What is wrong

Inside a CPP checkout, `second-opinion` resolves to two different endpoints at two scopes, and CPP's own drift checks report the host as clean.

- **Project scope** - CPP's shipped `.mcp.json`: `type: http`, `url: ${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp` (since #633 / PR #651).
- **User scope** - `~/.claude.json`: `type: stdio`, `command: ~/Projects/mcp-second-opinion/run-with-aws-secrets.sh --stdio`.

`claude mcp list`, run from the CPP checkout on 2026-09-26, flags it:

> [Conflicting scopes] Server "second-opinion" is defined in multiple scopes with different endpoints: user (...run-with-aws-secrets.sh --stdio), project (${SECOND_OPINION_URL}/mcp). OAuth tokens are stored per endpoint, so authenticating in one context will not carry over.

In the same `/cpp:update` run on the same host:

- `scripts/drift-detect.sh` reported `NO DRIFT: 4 checked, 3 skipped`.
- `scripts/mcp-drift.py --check` exited 0.
- `/cpp:update` Step 6b classifies `second-opinion` as **OK** whenever it is registered. It checks that a registration exists, not how many there are or where they point.

Host facts at filing: `SECOND_OPINION_URL` is unset, so the project entry targets `127.0.0.1:8080`, which answers HTTP 302 on `/mcp`. The user-scope stdio entry is the one `claude mcp list` shows as connected.

## Why it matters

- Which endpoint a session uses depends on the directory it starts in. A session in the CPP checkout and a session elsewhere can reach different second-opinion servers, and nothing tells the operator.
- The drift check answers a narrower question than its verdict claims. `OK` means "registered", not "one consistent registration", so a conflict that Claude Code itself warns about reads as clean in the CPP report. This is the detector-contract failure: the success message claims more than its input supports.

## Decisions needed

1. **Which wiring is canonical for this host:** the stdio launcher at user scope, or the shipped HTTP project entry? CPP's docs (`CLAUDE.md`, `/cpp:init`) describe the HTTP entry; this host runs stdio.
2. **Should CPP's drift check report a multi-scope `second-opinion` with differing endpoints**, for example as a `SCOPE CONFLICT` status, instead of `OK`? It would report only; it would never remove either definition.

## Acceptance

- A host with `second-opinion` defined at two scopes with different endpoints is reported by `/cpp:update`'s drift step as a conflict, naming both scopes and endpoints, and not as `OK`.
- A host with one definition, or two definitions pointing at the same endpoint, is still reported `OK`.
- Both cases are committed as test cases, with the conflict case shown failing on the current check.
- Nothing is removed automatically. The remedy offered is Claude Code's own `claude mcp remove second-opinion -s <scope>`, run only on the user's say-so.

Found during a `/cpp:update` run on 2026-09-26, after flow:auto #1226 (PR #1255).


# Flow run record - issue #1462

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=3762faf687af4c568731cdb0b5a155c1 -->
## Run 1

- Run-id:            3762faf687af4c568731cdb0b5a155c1
- Run-start:         77530ec3055610e8555e29efd5932f235271192e
- Issue:             #1462
- Base SHA:          77530ec3055610e8555e29efd5932f235271192e
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          master:kyle (mailbox message 6515, replying to plan 6514), with the TLS constraint
- Recorded at:       2026-10-17T02:10:00Z

### Section B evidence
Commits since filing: 145d42d (#1452) and 77530ec (#1458), neither touching ci-stage-*. Merged PRs: #1463, #1464. Duplicates: none (#1411 is the origin). Sibling worktrees: none touching these files. The stagers still have a bare `except Exception: return 75`.

### Section C - the approved plan
1. `scripts/ci-stage-jq.py` - _transient(exc) classifier on URLError.reason (ssl.SSLError family -> 1; socket.gaierror / ConnectionError / TimeoutError -> 75); HTTPError 5xx/429 -> 75, other 4xx -> 1; any non-network exception -> 1.
2. `scripts/ci-stage-make.py` - the same classifier.
3. `scripts/ci-stage-git.py` - the same classifier around _fetch.
4. `tests/test_ci_stage_exit_codes.py` - one table driven against all three stagers, with the TLS case raised as URLError(reason=SSLCertVerificationError).
5. `controls/flow-ci-status/run-case.sh` - a per-case step-name file, plus a GOOD case good-non-stager-exit-75.
6. `docs/scripts.md` - the narrowed 75 rule.
Scope: ~7 files, ~150 lines. Risks: an unrecognised transient reads as code (the safe direction); TLS verify -> 1 by design.

# Flow run record - issue #1264

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1264
- Base SHA:          8dad506
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          cooneycw (session owner, "approved" in the /flow:auto session)
- Recorded at:       2026-09-26T00:00:00Z

## Section B evidence
Commits since filing on the touched paths: none. Merged PRs since filing: #1275,
#1270, #1274, #1255 (none touch these paths). Superseding: #1269 (duplicate
receipts per branch, item 2). Delivered: #1203 / 43286db (flow-finish-gate
control isolation, item 6). Items 3+8 (discovery scope, non-file gates) and 4
(sweep.py self-test) are design decisions routed to new issues.

## Section C - the approved plan
1. `lib/security/modules/npm_audit.py` - missing npm / vanished binary reports UNKNOWN in errors, not skipped
2. `lib/security/modules/gitleaks.py` - missing gitleaks / vanished binary reports UNKNOWN in errors
3. `tests/test_npm_audit.py` - committed negative control, red on pre-fix code
4. `tests/test_gitleaks.py` - committed negative control, red on pre-fix code
5. `scripts/check-control-ci-deps.py` - invocation_command skips env option flags (-u NAME, -i, -, --unset=, -C)
6. `scripts/instrument-census-check.py` - one resolve_adr(root) with default path then a single-match candidate glob
7. `scripts/check-negative-controls.py` - resolve the ADR through resolve_adr
8. `scripts/verify-coverage-check.py` - resolve the ADR through resolve_adr
9. `tests/test_agents_md_facts.py` - AGENTS.md's mechanically checkable facts pinned against Makefile and codex-skill-sync
10. `docs/flow-runs/issue-1264.md` - this record

Scope: medium. Risks: UNKNOWN may amber /security:scan on hosts lacking the
tools (intended); the candidate glob could match a non-0008 doc (default path
tried first, so CPP is unchanged).

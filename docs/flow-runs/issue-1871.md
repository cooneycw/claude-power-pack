# Flow run record - issue #1871

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=bfcb7406630b437c84dcb536eaf0d5b7 -->
## Run 1

- Run-id:            bfcb7406630b437c84dcb536eaf0d5b7
- Run-start:         254071146b40243505187050e6e97f037fa0365b
- Issue:             #1871
- Base SHA:          254071146b40243505187050e6e97f037fa0365b
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run136:cp-orch, mailbox 36649
- Recorded at:       2026-11-21T17:35:17Z

### Section B evidence
The prior failed scan on #1870 motivated this owner-requested control. Existing secret-scan controls cover a working-tree population; this test exercises the actual CI history command. The generator already writes safe header fields.

### Section C - the approved plan
1. `tests/test_plan_record_secret_scan.py` - pinned offline scanner red/green tests, actual-generator reader, explicit UNKNOWN skips, CI command/staging checks, restricted-PATH handling and guidance pin.
2. `controls/secret-scan/cases/plan-record-history/bad-api-main.md` - intentional old-form fixture inside existing exemption only.
3. `controls/secret-scan/cases/plan-record-history/good-generated-header.md` - generated metadata header fixture.
4. `docs/agents/flow-plan-record.md` - one Section B guidance line about already recorded start metadata and safe wording.
Scope: Tier 1 pytest control only, not a new gate or registered instrument. No scanner config/rule/allowlist change, new dependency, source inventory/census/coverage row, or command-doc budget change. Closes #1871 after demonstrated acceptance; orchestrator merges.
Risks: tests must consume history with exact CI flags; no raw matched-value output; unavailable tools must skip explicitly; intentional planted values stay in the existing exempt fixture boundary.

### Lanes for this change
| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | not applicable | Test owns a private one-commit repository; no checkout resolution behavior changes. |
| Harness | not applicable | No command or skill surface changes. |
| Driver | not applicable | No model driver changes; actual metadata helper output is consumed directly. |
| Coordination | not applicable | No fleet or standalone coordination logic change. |
| CI provider | will test | Woodpecker exact command and binary staging; GitHub Actions / none recorded have no claimed parity. |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not: committed good and bad record excerpts in owned histories. |
| Toolchain version | will test | CI's pinned uv and Python / the host or container's installed versions: scanner must be 8.30.1, missing/wrong version is UNKNOWN skip; no broad Python matrix claim. |
| Clone shape | not applicable | Owned one-commit history only; no arbitrary shallow-clone behavior claim. |
| Run location | will test | invoked from the CPP root / from another directory: test locates committed source by __file__ and scans from private external cwd. |
| Gate target | not applicable | No CPP versus consumer interpreter behavior changes. |
| Wave role state | not applicable | No role lifecycle changes. |

### Changed output readers
The exact CI scanner consumes relocated committed fixture bytes and actual begin-run/declare-salvage header output. Pytest inspects metadata-only RuleID/file/line output and UNKNOWN skip reasons. CI staging tests read the actual YAML. Existing control case enumeration remains unchanged. No scan rule is duplicated in Python and no raw match/secret is printed.

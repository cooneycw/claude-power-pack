# Flow run record - issue #1282

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1282
- Base SHA:          164fdd4d23f2eaf66ef4ba30408824f7c589c417
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45 orchestrator (kyle fleet mailbox msg 1718, reply to ELI5 report msg 1717)
- Recorded at:       2026-09-28T09:59:47Z

## Section B evidence
- commits since 2026-09-26T16:29Z on the relevant paths: 879df15 (#1287/#1263)
  touched update.md but not the BEHIND/AHEAD block (lines 150-166 unchanged);
  none touching status.md or toolchain-provenance.sh.
- PRs: none addressing this.
- dup/super: none. #1029 (closed) produced toolchain-provenance.sh, a related
  no-fetch instrument measuring the current branch's upstream; left unchanged.

## Section C - the approved plan
1. `scripts/cpp-checkout-freshness.sh` - new helper: --path/--branch, fetch origin/<branch> non-interactively with a timeout, count HEAD against it; verdict current | behind N | ahead N | diverged | unknown: <reason>; exit 0/3/4/2; read-only checkout -> unknown (fetch failed, checkout not writable), never a count against a stale ref.
2. `tests/test_cpp_checkout_freshness.py` - fixture-repo cases (behind 1, current, fetch fails, read-only checkout, ahead, diverged, feature branch, detached, no ref) plus a pre-fix red test running update.md@164fdd4's block on the fetch-fails fixture.
3. `controls/cpp-checkout-freshness/control.json` - ADR 0008 committed control (with run-case.sh, cases/, anchors/ beside it); anchor is the pre-fix update.md block vendored verbatim and must miss bad-fetch-fails.
4. `controls/cpp-checkout-freshness/run-case.sh` - builds fixture repos per case scenario at run time.
5. `.claude/commands/cpp/status.md` - new freshness step calling the helper; says /cpp:status now fetches; allowed-tools gains bash; summary example line.
6. `.claude/commands/cpp/update.md` - lines 150-166 compare block replaced by a helper call with --branch "$CURRENT_BRANCH"; unknown never renders as up to date.
7. `docs/scripts.md` - inventory entry.
8. `docs/decisions/0008-instrument-negative-control-bound.md` - census row.

Scope: ~9-12 files, ~500-700 lines. Risks: fetch writes the shared checkout's
remote-tracking ref (acceptable per approver); network hang bounded by timeout;
update.md also touched by #1256 next, so the edit stays within 150-166; real-host
confirmation is owed to the operator.

# Flow run record - issue #1235

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1235
- Base SHA:          5ad99f5
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          the session user (replied "approved" to the Step 3 report)
- Recorded at:       2026-09-24T10:49:00Z

## Section B evidence

- Commits since filing (2026-09-24T09:42Z): 34726a3 (#1234, unrelated); none touching
  scripts/codex-skill-sync.py since 250d56f (#1218).
- Merged PRs 2026-09-24: #1231, #1233, #1234, #1237, #1238 (#1232 test isolation - does
  not change run_install), #1240. None addresses the install window.
- Duplicate/superseding issues: none (#1232 parent, open; #662/#663 unrelated).
- Reframing: a whole-root swap would have to carry non-CPP entries (user skills, .system)
  and still does not give old-or-new to a path-based reader for REMOVED skills. The
  corrected approach swaps PER SKILL with renameat2(RENAME_EXCHANGE); removal becomes one
  rename (inherent window, stated, not claimed closed).

## Section C - the approved plan

1. `scripts/codex-skill-sync.py` - run_install(): stage each managed skill under
   ~/.codex/.cpp-skill-staging/ (sibling, same fs), swap existing skills in with
   RENAME_EXCHANGE, new skills with os.rename, move orphans out with one rename then
   rmtree; reported two-step fallback when exchange is unavailable or staging is on
   another device; clean staging incl. leftovers from a crashed run.
2. `tests/test_codex_skill_sync.py` - deterministic observer negative control (red on
   the unfixed code, green after), fallback-path test, stale-staging cleanup test.
3. `codex/skills/*` - regenerated mirrors only if the resync helper says a bundle drifted.

Scope: 2 source files, ~90 lines script + ~120 lines tests.
Risks: ctypes/renameat2 platform dependence (probe + reported fallback); a crash
mid-swap leaves the old copy in staging (outside skills/, cleaned next run); the
removal window is narrowed not closed - close with Refs #1235 unless the owner accepts.

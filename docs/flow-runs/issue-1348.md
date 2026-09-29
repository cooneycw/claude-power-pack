# Flow run record - issue #1348

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=7e30461ab82e487bae9ee2f2a171ddf1 -->
## Run 1

- Run-id:            7e30461ab82e487bae9ee2f2a171ddf1
- Run-start:         5ae7e8db1d021a61d27f3d48d5815f9cbb2518a2
- Issue:             #1348
- Base SHA:          5ae7e8db1d021a61d27f3d48d5815f9cbb2518a2
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cpp-wave2 orchestrator (run48:cpp2-orch), mailbox message 2512, including the name + local-source identity ruling
- Recorded at:       2026-09-28T23:00:00Z

### Section B evidence
- commits: none touching scripts/check-version-consistency.py, tests/test_version_consistency.py or uv.lock since 2026-09-28T22:31:02Z
- PRs: none (#1104 merged under #1037, created the checker, predates the issue)
- dup/super: none (source Nit Store comment 5879774278; parent #1278)
- sibling worktrees: none with commits on these paths

### Section C - the approved plan
1. `scripts/check-version-consistency.py` - read uv.lock's own-project entry (name == [project].name normalised AND local source virtual/editable "."); mismatch exit 1; no lock, parse error, no project name, zero or multiple own entries, or missing version is UNKNOWN exit 2; checked apart from the MIN_LOCATIONS floor
2. `tests/test_version_consistency.py` - red case (lock 7.9.9 vs 8.0.0), equal passes, UNKNOWN cases including the same-named non-local neighbour
3. `docs/scripts.md` - check-version-consistency bullet gains the uv.lock site and its UNKNOWN states
4. `docs/decisions/0008-instrument-negative-control-bound.md` - row 86 verdict text gains the uv.lock states

Scope: 4 source files, ~80-130 lines. Risks: a consumer repo with no uv.lock now gets UNKNOWN (none found); a dynamic-version lock entry is UNKNOWN; identity is narrower than the issue's "by name" (ruled acceptable).

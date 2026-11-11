# Flow run record - issue #1673

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=43badc4cc1534b3ca3d743aa340e7d62 -->
## Run 1

- Run-id:            43badc4cc1534b3ca3d743aa340e7d62
- Run-start:         15521b1e19359cd7d72c8f24e5628b397fa676f5
- Issue:             #1673
- Base SHA:          15521b1e19359cd7d72c8f24e5628b397fa676f5
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the owner, in the interactive session ("1. yes. 2. yes."); item 3 (whether the #864 aggregation is a child issue or part of this run) was left open and child (a) is held on it
- Recorded at:       2026-11-11T21:54:09Z

### Section B evidence
- commits since 2026-11-11T14:58:30Z on flow/cicd paths: 3c3062ee, 9ec3e486, b3a81627, abce5ab5, b025989d. None deletes or merges flow/cicd code paths.
- merged PRs inspected: #1675, #1676, #1679, #1680, #1681, #1682, #1683, #1686, #1687, #1688. #1679, #1683, #1688 and #1681 satisfy the issue's run-after constraint (#1670, #1671, #1672 closed; #1669 first pass, now evergreen).
- duplicate/superseding issues considered: #1061 (closed, different goal), #1075 (closed). None duplicates this.
- sibling worktrees on this host: 2, no unpushed commits on these paths.

### Section C - the approved plan
This run delivers planning and the routing change; it does not close the epic.

1. `scripts/nit-store-resolve.sh` - remove the claude-power-pack map entry so this repository's store is found by exact-title search; kyle and skillc unchanged
2. `tests/test_nit_store_resolve.py` - move map-path cases to a still-mapped repository; add CPP-by-search cases including the rollover moment
3. `tests/test_nit_store_routing.py` - re-pin away from 864
4. `scripts/maintain-loop-indicator.py` - stop hard-coding 864: current store from the resolver, option to name a closed predecessor
5. `tests/test_maintain_loop_indicator.py` - cover item 4, red on the hard-coded version
6. `AGENTS.md` - route findings via the resolver, no number
7. `.claude/commands/flow/finish.md` - example report drops the literal number
8. `docs/scripts/nit-store-resolve.md` - index line updated for item 1
9. `docs/scripts/maintain-loop-indicator.md` - index line updated for item 4
10. `docs/agents/nit-store-rollover.md` - new: the monthly rollover steps and their order
11. `docs/measurements/simplification-wave-baseline-2026-11.md` - new: baseline tables, the commands that produced them, how to take the 30-day reading
12. `CHANGELOG.md` - entry for the routing change

Outside the repository (owner approved separately): `~/.claude/CLAUDE.md` line 12 stops naming #864, then `make codex-global-agents`.

Child issues to file under #1673: (a) aggregate #864 and roll it over - HELD pending the owner's answer on item 3; (b) wave machinery; (c) gate path; (d) merge-and-cleanup tail. The feature freeze is stated on the epic; no new gate.

Scope: 12 files (2 new), roughly 250-350 lines; up to 4 issues filed; 1 epic comment.
Risks: search routing fails closed when two open issues are titled "Nit Store" (unknown) or when the search index lags a new successor (none); "every place that names #864" is read as every place that ROUTES to it, citations stay; the fix:feat ratio depends on PR titling.

# Flow run record - issue #1699

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=6e86809a9f7042d0bdc952b193c1778d -->
## Run 1

- Run-id:            6e86809a9f7042d0bdc952b193c1778d
- Run-start:         87d155aa6128f9a5e48bc5ce1defb1895d32a674
- Issue:             #1699
- Base SHA:          87d155aa6128f9a5e48bc5ce1defb1895d32a674
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 98: "#1699 plan APPROVED (Section C as written; record it before the first edit)."
- Recorded at:       2026-11-12T09:00:08Z

### Section B evidence
- last release tag v10.2.0 (31fe6a69, PR #1667, 2026-11-09); 50 commits on main since, and gh lists the same 50 merged PRs (#1675 through #1779)
- 11.0.0 by the #1278 rule (major = a contract or acceptance change a consumer must act on): eleven such changes counted at plan time, eight of them with coordination issues open in kyle, skillc and kyle-candidate
- scripts/check-version-consistency.py derives its locations and reads "ok - 5 location(s) agree with 10.2.0" on the base; it requires nothing that argues for another number
- CHANGELOG Unreleased names 16 issues against 50 merged PRs, so it is checked against the PR list, not trusted
- still to merge before this lands, so the list is re-derived at the end: #1767, #1508, #1726 PR B, the second #1718 PR, #1691 PR 2
- duplicates or superseding issues: none; #1278 is the standing checkpoint this uses, kyle #2348 the adoption issue

### Scope of this run
The release change only: version locations, changelog, README and CLAUDE.md. No series content, no consumer edit, no tag, no GitHub release, no publish.

### Rulings and conditions attached to the approval
- land LAST, on the orchestrator's slot word; no tag, release or publish (owner go, asked for by the orchestrator)
- add to Breaking or Upgrading, each checked against its merged PR: the #1716 profile reading after PR #1770; the owner step (/cpp:update, then codex-skill-sync.py --install); #1767's LANES clause on the PLAN_COMPLIANCE line once merged, with a search of the three consumers for a reader of that line; #1508's precode origin for image-pull failures once merged
- downstream: one comment on kyle #2348, one issue in cooneycw/aws-learn pointing at its #880 with attribution lines, nothing new in skillc or kyle-candidate; posted only when the content is final and on the orchestrator's word
- comment on #1278 after merge; Refs only, no closing keyword; the heading carries the merge day
- one Codex pass (docs and version only); full suite before its gate

### Section C - the approved plan
1. `pyproject.toml` - version 11.0.0
2. `uv.lock` - re-locked, the project's own entry only
3. `CHANGELOG.md` - a dated 11.0.0 entry with a Breaking list and an Upgrading section per consumer; gaps filled from the PR list; a fresh empty Unreleased
4. `README.md` - banner, a v11.0.0 notes section, and corrections where the sweep finds text describing removed or renamed things or missing what the series added
5. `CLAUDE.md` - Current version line, and the same sweep
6. `docs/flow-runs/issue-1699.lanes-demonstrated.md` - the reader row's demonstration
Scope: 6 files plus this record and the review receipt; prose and version strings only.
Risks: a Breaking entry that misstates a merged change (each is checked against its PR diff); a changelog assembled before the last five merges (re-derived at the end).

Lanes: none - version strings and documents only; no command, helper, gate or generated file changes behaviour in any lane

<!-- flow-run n=1 id=9054b14ce81243659abfac191a06ff60 -->
## Run 1 - issue #1626 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1626
- Read at:      2026-11-07T11:05:19Z
- updatedAt:    2026-11-06T12:37:04Z   (context only - moves on comments and labels)
- Body digest:  4dff534c69c6cdb8ec4217a79c9634492f011d12b155158647f63e9f20d717ad   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4997 of 4997 (cap 16384)

### Body as read
## Problem

`/project:next` was built to recommend what to work on next. It now regularly ends with **no recommendation**. On 2026-11-06, run against claude-power-pack at `69ee5b9c`, it reported:

```
Top action: resolve_inventory ... Next safe issue: None
State: 20 open | 1 in-flight | 0 blocked | 17 uncertain | 2 non-startable | inventory incomplete
```

When asked, the agent then read the 17 "uncertain" issues and the last 60 merged PRs. Within a few minutes it had a confident, evidenced pick: #1617, with #1607 as runner-up and #1619/#1624/#1621 as quick fixes. Every one of those dependencies could be resolved from the repo. The command's own instructions stopped the agent from doing that: "Return that report without independently collecting issues or rebuilding its decision", plus "never re-ranks, filters, or corrects the engine result".

Owner feedback: "project:next was originally designed to provide recommendations. I'm disappointed, because more and more you decline to provide them."

## Causes

1. **One weak global signal stops every recommendation.** Either of these marks the inventory incomplete, and then no issue can be `next_startable_issue`:
   - `merged PR history truncated at 200`
   - spec `tasks.md` files with no spec-sync mapping (`cicd-reliability` 36 tasks, `balanced-agentic-development` 6)

   Neither says anything about whether a given issue (e.g. #1617) is safe to start.
2. **Text dependencies the engine can't parse become `uncertain`, and nothing resolves them.**
   - Prose like "Depends on the project-record issue" (#1608, #1610, #1611). It means #1607, as #1612's ordered child list states.
   - Cross-repo `owner/repo#N` references (#1084, #1367). These are checkable with `gh`.
   - Ordered checklists in tracking issues (#1612).
3. **The skill forbids the resolution step.** The non-re-ranking rule was written to keep the agent from overriding the engine. In practice it also stops the agent from settling what the engine left open, so "uncertain" reaches the owner as "no recommendation".
4. **No test covers the opposite direction.** The fixtures check that the engine is cautious. None checks that the command still produces a pick when evidence is partial, so the drift toward refusing went unnoticed.

## Change

1. **Separate the two verdicts.**
   - `safe_for_unattended_dispatch` is the engine's existing strict verdict. It still gates `/flow:auto` and wave dispatch.
   - `recommendation` is always present unless there are literally no open, non-evergreen issues.
2. **Add a resolution step to `next.md`.** For each `uncertain` issue (cap by rank, e.g. the top 10):
   - the agent reads the issue body and the PRs that mention it;
   - it resolves each dependency to `satisfied | open-blocker | external-pending | owner-decision`, citing what it read.

   Results are labelled **agent judgment**, kept apart from engine verdicts. The engine output stays verbatim; the resolution is an added layer, not a rewrite.
3. **Check partial delivery per issue.** Search for merged PRs that mention each open issue (`gh search prs --merged "#N"` or a batched GraphQL equivalent) instead of reading the 200 most recent PRs and marking every issue "unknown" at the cutoff.
4. **Widen the dependency parser:**
   - tracking-issue ordered child lists → ordered edges (confidence `documented-order`);
   - cross-repo `owner/repo#N` → resolved via `gh issue view -R`, not left unknown;
   - prose that names no issue → still `uncertain`, but passed to the resolution step.
5. **Downgrade missing spec-sync mappings to a warning.** They should not make the inventory incomplete.

## Acceptance

- [ ] Running `/project:next claude-power-pack` against the 2026-11-06 state (or a fixture of it) names a recommendation, labelled as engine or agent judgment, and still reports `safe_for_unattended_dispatch: none` while the strict evidence is incomplete.
- [ ] **Negative control, committed:** a fixture with truncated PR history plus a prose-only dependency. The pre-change command produces no recommendation (red); the changed command produces a labelled one (green). Run the fixture on the unchanged code and record the red.
- [ ] **Opposite control, committed:** a fixture whose only candidate has a real open native blocker. The command must NOT recommend it as startable. Resolution must not erase real blockers.
- [ ] `/flow:auto` and `/flow:wave` still consume only the strict verdict. A test shows an agent-judgment recommendation can't pass the preflight `engine` check alone.
- [ ] Partial-delivery evidence is per issue. A repo with more than 200 merged PRs no longer reports `partial delivery unknown` for issues whose mentioning PRs were found.
- [ ] `docs/project-next-contract.md` is bumped for the new `recommendation` field and the per-issue partial-delivery evidence.

## Context

Found running `/project:next claude-power-pack` on 2026-11-06. Related: #1614 (project-next blind spots: ADR parsing, open-by-design trackers).


<!-- end of body -->

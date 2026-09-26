# Project Next Behavioral Contract

`project-next` is a read-only, deterministic recommendation workflow. Claude
Power Pack owns the executable contract, fixtures and Python core outright
(issue #1069): the package is `lib/project_next/`, the fixtures are
`tests/project_next/fixtures/`, and this document is the contract. Fidelity
changes originate in this contract and its fixture corpus; a second
prompt-only decision policy is not an authoritative implementation. The engine
was authored in codex-power-pack and vendored from it until #1069; that
repository has been private and dormant since 2026-09-22 (#1076), and
[the provenance record](project-next-provenance.md) keeps the history.

## Version and entry points

Contract version `1.4` accepts a structured `RepositoryState` and emits a
structured `RecommendationResult`. Run it from a CPP checkout with:

```bash
python3 scripts/project-next.py [repository] [--brief|--compact|--full|--json]
```

Normal installations expose the same entry point as
`~/.claude/scripts/project-next.py`. `make project-next-check` verifies the
package, contract and fixtures against their ownership pins in
`.claude/project-next-ownership.json`.

## Input contract

Repository state includes open issues, open pull requests, local and remote
branches, worktrees, recent commits and dirtiness, review/check/merge state,
Spec Kit file readiness and stable ledger mappings, collection warnings, and whether the inventory is
complete. Fixture JSON can supply the same model without git, GitHub, or an LLM.

The live collector performs batched GitHub queries. Authentication, rate-limit,
pagination, fetch, parse, and command failures are recorded. An incomplete
inventory cannot produce a globally safe `next_startable_issue`.

## Classification contract

Every open issue appears in exactly one disjoint set:

- `in_flight`: mapped from an issue branch, worktree, or open pull request;
- `blocked`: has an explicit open dependency, transitive dependency, or cycle;
- `non_startable`: carries a configured `non_startable_labels` marker (default
  `evergreen`, `inbox`, `nit-store`, `not-startable`) and is not in flight. The
  issue is open by design - a standing inbox, a recurring re-check - and has no
  implementable scope, so it is never ranked, never a candidate, and never
  `next_startable_issue`. The marker is decisive where dependency prose is not,
  so such an issue is never `blocked` or `uncertain` either;
- `uncertain`: dependency wording or dependency state cannot be resolved;
- `available`: belongs to none of the preceding sets.

`non_startable_evidence` names the matched label for each such issue. An issue
with no labels is indistinguishable from feature work, so the marker is the
only signal: an inbox that is not labelled is ranked like any other issue.

A dependency is a lead-in phrase followed immediately by one or more references.
The phrase tolerates the punctuation and Markdown emphasis real issue bodies
use, so `Depends on #12`, `**Depends on:** #12`, `Blocked by: #12, #13`,
`**Depends on:** #367, #369–#371`, and `(depends on T004)` are all executable.
Reference runs accept comma, `and`, and dash-range separators; a range wider
than fifty issues collapses to its first endpoint.

Phrases are graded, because English sequencing is not a declaration:

- strong (`depends on`, `depends upon`, `blocked by`, and the field-label forms
  `Blockers:` / `Prerequisites:`) assert a blocker, so a strong phrase that
  names no resolvable reference is uncertainty;
- weak (`requires`, `needs`, `after`, `follows`) counts only when a reference
  actually follows, and never raises uncertainty on its own. "Run this after
  the v0.2.0 release" is prose, not a blocker.

A strong phrase followed by an explicit negation - `Depends on: None`, `N/A`,
`nothing`, `nil`, or a bare dash - declares that there is no dependency. It is
neither a blocker nor uncertainty.

Fenced code blocks and inline code spans are removed before any of this runs,
so a comment such as `# starts after the label gutter` declares nothing.

Spec task IDs resolve to issues through the `spec-sync:v1` Issue Sync ledger
first, then through an open issue whose title begins with that task ID; a task
ID claimed by two open issues resolves to neither. Task IDs an issue defines
itself describe its own internal ordering and are not blockers. An unresolved
task ID with a complete inventory is read the same way as a reference to a
closed issue — already satisfied — and becomes uncertainty only when the
inventory is incomplete.

The relationship to CPP's wave-lane grammar is a decided partial convergence,
not accidental drift ([CPP#648](https://github.com/cooneycw/claude-power-pack/issues/648);
see the [`flow-wave-plan.py` header](https://github.com/cooneycw/claude-power-pack/blob/621134002e96a03d163d0f5469beda89bf89e771/scripts/flow-wave-plan.py)).
Both grammars require a line-anchored declaration with immediate references,
strip fenced and inline code before parsing edges, and tolerate Markdown
emphasis and punctuation around the keyword. Grading, the `uncertain` class,
and `Blockers:` / `Prerequisites:` remain contract-only because the judged wave
gate handles unresolved declarations; ranges remain contract-only after zero
occurrences in 240 measured bodies and because CPP's issue generator emits
explicit lists; duplicate spec-task claims resolve to neither here while the
wave planner instead reports `unresolved_tasks` and `spec_drift`. This note
records that boundary without changing either grammar's behavior.

In-flight issues remain in the dependency graph so their dependents stay
blocked.

The engine validates that the sets are exhaustive and non-overlapping. Neither
the top action's `start_issue` variant nor `next_startable_issue` may reference
an in-flight, non-startable, blocked, or uncertain issue.

## Ranking contract

Available issues use the following stable tuple, in order:

1. security/blocker, or high-priority bug;
2. declared high, medium, then undeclared priority;
3. lower Wave or Phase number;
4. task/bug, quick win, general feature, then planning/epic;
5. explicit quick-win label;
6. stale versus recently updated, using the configured threshold;
7. lower issue number as the final tie-break.

The collected timestamp makes fixture ranking repeatable. Repository policy can
override label aliases, limits, mode, and staleness in `.project-next.json`,
validated against `templates/project-next.schema.json`.

Labels are matched after separator normalization, so `priority:high`,
`priority/high`, `priority_high`, and `Priority High` all reach the
`priority-high` entry. When no open issue carries a label in any configured
vocabulary, ranking has no priority signal and degenerates to issue type, age,
and issue number. The engine says so in a warning naming the labels actually in
use rather than presenting issue order as a ranking.

## Top action and next startable issue

`top_action` answers what should happen now. In priority order it restores an
incomplete inventory, fixes failing PR checks, addresses requested changes,
merges a ready PR, continues active work, repairs a known repository gate,
starts the highest-ranked available issue, reviews untracked files,
synchronizes a specification task, or - only when nothing else applies -
triages a non-startable issue (`triage_inbox`). The last is not an
implementation route: it names an inbox whose contents should be aggregated
into startable issues, so a repository whose only open work sits in an inbox
never reports that there is nothing to do.

A dirty worktree whose branch names an issue that is not open (closed, or never existed) is never
`continue_work`: its tree may hold a design that was refuted. It is reported
as a warning instead, and stays a cleanup candidate that must be inspected
rather than removed.

`continue_work` requires tracked modifications. Untracked files alone are not
work in progress: a worktree holding only untracked files is reported as
`untracked_only` and surfaces as `review_untracked` only after every real
recommendation is exhausted, so a stray build artifact never becomes the
headline of the report.

`next_startable_issue` is a separate field. It is the highest-ranked available
issue only when the repository inventory is complete. Active work may therefore
be the top action while a different issue is the safe next issue to start.

## Output contract

- `--json` emits the complete versioned result and is authoritative.
- `--brief` shows the top action, next safe issue, and inventory confidence.
- compact mode shows at most three safe candidates. Each candidate carries its
  priority, phase/wave, issue type, quick-win signal, stable rank tuple,
  deterministic rationale, and `$flow-auto` command. Active, blocked,
  uncertain, and critical non-startable work stays visibly separate.
- `--full` adds mutually assigned operational tiers, categorized backlog counts,
  pull requests, Spec Kit file and mapping readiness, worktrees with their
  already-collected recent commits, and cleanup candidates for worktrees or
  branches that do not map to an open issue.

`RecommendationResult` owns all presentation decisions through structured
`candidates`, `backlog_summary`, `backlog_tiers`, `spec_features`,
`worktree_details`, and `cleanup_candidates` fields. Renderers format those
fields and do not parse issue prose, classify work, or re-rank candidates.
Incomplete inventory produces no candidates or startable tiers even when the
partial inventory contains apparently available issues.

Spec Kit *synchronization* is represented only by the `spec-sync:v1` Issue Sync
ledger. Task-ID searches in issue titles or bodies are not synchronization
evidence; they resolve dependency references only, and never mark a task
synchronized or a specification group complete.
Missing mappings produce `sync_spec`; stale or ambiguous identities produce
`resolve_spec_mapping`. Neither state is silently treated as completed work.

All modes name the `1.4` contract. Missing prerequisites and incomplete state
are explicit failure states; they never become a confident recommendation.

Renderers cap long collector output: warnings list the first five entries and
per-issue uncertainty lists the first two reasons, each truncated. `--json`
always carries the complete lists.

## Compatibility notes

`1.4` keeps every `1.3` field and adds the `non_startable` partition with its
`non_startable_evidence`, the `non_startable` backlog tier, the
`non-startable` worktree issue state, the `triage_inbox` top-action kind, and
the `non_startable_labels` configuration key. A consumer that sums the four
`1.3` partitions to count open issues must add the fifth; every other consumer
reads `1.4` payloads unchanged.

`1.3` keeps every `1.2` field and adds `untracked_only` to worktree state and
worktree details, plus the `review_untracked` top-action kind. Consumers that
ignore unknown fields and unknown action kinds read `1.3` payloads unchanged.

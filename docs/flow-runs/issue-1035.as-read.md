# Issue #1035 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1035
- Read at:      2026-09-26T13:47:37Z
- updatedAt:    2026-09-22T12:10:42Z   (context only - moves on comments and labels)
- Body digest:  edacda97adba4c50fab26703c64762fb47300c5559a4d106a07624218f0190da   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 8985 of 8985 (cap 16384)

## Body as read
Consolidated from the Nit Store (#864), 2026-09-16 sweep. Seven comments. The engine is
vendored (`vendor/project_next/`, contract v1.3) and the decision policy lands upstream in
codex-power-pack, arriving via `make project-next-drift`; the marker set and the adapter
extensions may belong in the CPP adapter. Both halves are named per finding below.

## 1. The headline recommendation is an issue nobody can implement, on every run, forever

Observed again TODAY (2026-09-16), so this is a standing condition and not a one-off:

```
**Next safe issue:** #864 Nit Store

### Ready to start (top 3)
1. #864 Nit Store [priority default; phase unspecified; type feature; quick win no]
   default; unspecified; feature; ordered by the deterministic rank tuple -> `$flow-auto 864`
```

#864 is the repository's permanent nit-store inbox. It is open by design, will never close,
has no implementable scope, and carries no labels, so nothing in the evidence the engine
collects distinguishes it from ordinary feature work. It sorts into `available`, wins the rank
tuple among default-priority issues, and is emitted as BOTH `next_startable_issue` and the #1
start candidate with an executable `/flow:auto` route. The same run warns that the fallback is
in effect: *"no issue label matches the configured priority, quick-win, or planning vocabulary,
so ranking falls back to issue type and age (labels in use: enhancement, evergreen)"* - and
#864 is old, which is exactly the tuple that fallback ranks highest.
`next_startable_issue` is the one line a reader acts on without re-deriving anything. It also
displaces a real candidate from the top-three slate on every run (that run's real next
candidates, #937 and #943, were pushed to slots 2 and 3).
Filed twice, a day apart, unchanged:
https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5677435550
https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5696775620

## 2. A charting seed routes to `$flow-auto`, and that one SUCCEEDS

```
2. #876 Chart a wayfinder map: CPP's resilience, and the dormant-capability pattern it keeps hitting
   ... -> `$flow-auto 876`
```

#876 is a charting seed, not implementable work. Its own body says so: *"A request to chart a
wayfinder map ... not a map itself, and not a build ticket"*, *"Per the wayfinder contract this
seed decides nothing."* Nothing closes it but a `wayfinder:map` issue and its decision tickets.

**Why this is worse than case 1.** #864 is obviously not work once you read it, so
`/flow:auto 864` stalls visibly. #876 fails the other way: it succeeds. The seed carries seven
measured, obvious-looking gaps (no shellcheck across 96 `.sh`, no coverage, no
`pip-audit`/`bandit`, four mypy error codes disabled, a narrow `ruff select`). An
implementation agent handed that issue would wire several into `.woodpecker.yml` and open a
plausible green PR - which is precisely the outcome the seed exists to prevent: *"A seed issue
that pre-decided the destination would hand the charting session a conclusion instead of a
question."* **A wrong route that produces a passing artifact is not caught by review.**

The routing vocabulary already exists: this repo created the full `wayfinder:*` label set on
2026-09-12 (`wayfinder:map`, `:research`, `:prototype`, `:grilling`, `:task`). #876 does not
carry one, so labels alone would not have caught this specific issue, but the adapter already
emits `planning_routes` for Wayfinder artifacts and states they "never route to `/flow:auto`" -
the map-linked case is handled and the SEED case is not.
https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5677462791

The same gap, hit from the driver side rather than the report side: `/flow:auto 1046` cut a
worktree, cut a branch and ran a full Step-2 codebase analysis on an issue whose own body says
it must not be implemented. The ELI5 gate stopped it at Step 3, but only because a
human-readable sentence happened to be unambiguous. A delegated `/codex:auto` or `/qwen:auto`
run on the same seed has an implementation-only fence and no `/wayfinder` awareness, and its
most likely output is a plausible pre-drafted map.
**Resist the tempting fix:** a body-text grep for "Run `/wayfinder`" would trip on any issue
DISCUSSING wayfinding - good documentation makes text-matching guards more false-positive,
not less. The checkable trigger is a label.
https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5652923140

## 3. `planning_routes` is blind from every worktree, and blind is indistinguishable from absent

`scripts/project-next.py:459` (verified live today) resolves the artifact as a plain path read:

```python
path = repository / ".claude" / "wayfinder-map.json"
```

In kyle that file is untracked and gitignored (`.gitignore:42:.claude/*`), so it exists in the
primary checkout and in NO worktree. Measured directly: the same `ls` reported the file PRESENT
from `~/Projects/kyle` and ABSENT from a freshly created worktree of the identical commit. Both
answers are correct and they disagree, because the artifact is not part of the tree a worktree
checks out.

Nearly all flow work happens INSIDE a worktree - `/flow:auto`, `/flow:start`, `/codex:auto` and
the wave drivers all create one - so the guard is strongest exactly where it is never consulted,
and its absence is indistinguishable from "no map exists". A cleared map and an unreadable one
are also indistinguishable in the output.
Fix: read the artifact through git when the repository is a linked worktree
(`git -C <repo> rev-parse --git-common-dir` gives the primary checkout), or at minimum state
plainly which of THREE states was observed - map read, map absent, map unreadable from this
checkout - so an unscanned artifact reads as unknown rather than as "no planning routes".
https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5652922464

## 4. `continue_work` recommends resuming work that was refuted

```
Top action: continue_work: Continue issue-868-supervise-wake-inbox-socket (issue #868)
            - An active worktree has uncommitted changes.
```

#868 was closed NOT_PLANNED with a measurement showing the design is not implementable. The
worktree's uncommitted ~720 lines implement exactly that refuted design, written before the
measurement. The report parses the issue number out of the branch name and NEVER FETCHES THAT
ISSUE'S STATE. `continue_work` is the first line of the report and is read as the safest action.
`flow-start-resolve.sh` catches it one step later (`ISSUE_STATE=CLOSED`, `CONFIRM_REQUIRED=1`)
so nothing ships, but the engine's top recommendation was wrong.
Note this is the INVERSE of item 1, not a duplicate: that one is "an issue that is legitimately
open is still not startable"; this one is "the recommended issue's state was never fetched".
Fixing either does not fix the other.
https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5669167924

## 5. The `unmapped worktree` warning cannot support the decision it is consumed by

The warning text is identical in two materially different states: a safe leftover, and a tree
holding genuinely unpushed work. Both trees measured emitted `unmapped worktree: <path>`; both
issues were CLOSED, both remote branches deleted, both clean, and both showed
`rev-list --count origin/main..HEAD == 1` - the squash-merge ancestry break, so the count says
nothing. Only a per-file BLOB IDENTITY check against `origin/main` settled it.
The reader has to choose between `git worktree remove` and "do not touch, this holds work". The
warning supports neither choice, so the safe reading is always "leave it", and stale worktrees
accumulate - which is how both of those got there.
Fix: annotate each unmapped worktree with a delivered/undelivered verdict derived from blob
identity against `origin/main` (not `--is-ancestor`, not a rev-list count - squash merges break
both), plus dirty/clean and remote-branch-exists.
https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5677273532

## Negative control (ADR 0008)

`/project:next` emits an executable route that a reader acts on without re-deriving it, so
every marker added here needs a committed control - and the specific failure mode is an
exclusion list that silently matches nothing, which renders identically to a working one:
- A fixture issue carrying the non-startable marker must NOT appear in `available` and must
  NEVER be named as `next_startable_issue`; one without it must still appear.
- A fixture issue carrying a `wayfinder:*` label must NOT emit a `$flow-auto` route; one
  without must.
- The three-state map report: a run from a worktree where the artifact is unreadable must say
  `unreadable`, and a run where it is genuinely absent must say `absent`. Same conclusion,
  different reason - which is the distinction the whole item exists to preserve.
- `continue_work` on a branch naming a CLOSED issue must downgrade; on an OPEN one it must not.


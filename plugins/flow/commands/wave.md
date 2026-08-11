# Flow: Wave - Orchestrate a Dependency-Ordered Issue Wave Across Worker Sessions

Run one **orchestrator** session over N **worker** sessions, driving a
dependency-ordered wave of issues to merge (issue #637). The orchestrator never
implements. It picks what is startable, assigns disjoint lanes, judges each
worker's `/flow:auto` Step-3 ELI5 gate, re-derives resource contention after
every ruling, and enforces the completeness policy so a narrowed scope always
leaves a filed issue behind rather than a hole.

Proven shape: a hand-driven 2026-08-10 run (4 workers, ~2h) merged/queued 6+
issues and its judged gates caught two real defects before a line was written -
plus one orchestrator error a worker caught. This command packages that loop.

## Arguments

- `WAVE` (required): wave name, e.g. `cpp-flow` - namespaces the role registry
  and all reporting
- `--repo <path|name>`: target repo (default: session repo)
- `--issues <label|milestone|#N,#N,...>`: the issue set when there is no
  spec-kit feature to scaffold from
- `--workers <N>`: expected worker count (used to sanity-check the roster)

## Roles and lifecycle

- **This session is the orchestrator**: a long-lived SESSION, not a subagent -
  it must judge gates hours after assignment and survive compaction (open
  question 1). It judges every gate ITSELF; it may delegate evidence-GATHERING
  reads to subagents, never the ruling (open question 2) - judging is where the
  bugs get found.
- **Workers are long-lived across issues and COMPACT between them; they do not
  `/clear`** (open question 3). `/clear` is a user-typed CLI built-in a session
  cannot invoke on itself, and a cleared worker loses its protocol and history;
  a compacted one keeps a summary of both. Context continuity is a feature -
  restate the lane and boundaries in each assignment anyway, and treat a
  re-register (`/flow:register`) as the cheap re-brief when compaction dropped
  more than expected.
- **Pushback is a first-class outcome** (open question 4). In the reference
  run the orchestrator was the unreliable component: three orchestrator errors,
  all caught by workers, none by the orchestrator. Every assignment carries the
  obligation to verify against the tree - "the orchestrator said so" is not
  evidence. A worker reporting "that isn't me" is an addressing bug; a worker
  refuting an assignment's premise triggers re-planning, and the ledger records
  who was right.

## Setup: the roster (consume #638, do not reimplement)

Addressing is exactly the `/flow:register` protocol - this command adds NO
addressing logic of its own. Follow `register.md`:

1. Register this session as the wave's orchestrator:
   ```bash
   ~/.claude/scripts/flow-wave-registry.sh register orchestrator --wave <WAVE> --repo <TARGET_REPO>
   ```
2. Have each worker run `/flow:register <role> --wave <WAVE>` and send its
   hello; on each hello, reconcile the observed `from=`:
   ```bash
   ~/.claude/scripts/flow-wave-registry.sh verify <role> --wave <WAVE> --from <observed uds:...>
   ```
   The transport-observed address is authoritative on any mismatch (#638).
3. Ack each worker with the wave brief: its lane, stop-at-Step-3 (never
   `--yes`), the ledger format, and the structural-pushback rule verbatim.
4. Address workers ONLY by the registry's `uds:` socket via `SendMessage` -
   never by `ListAgents` display names. Check the roster with:
   ```bash
   ~/.claude/scripts/flow-wave-registry.sh list --wave <WAVE>
   ```

## Phase 1: Scaffold the issue set

- **Spec-kit repo:** run `scripts/speckit-tasks-to-issues.sh` (dedup-safe) to
  emit one issue per task, then add the dependency edges - that script emits no
  `- Blocked by #N` lines itself. Derive edges from `tasks.md` ordering/notes
  and write them with `gh issue edit`.
- **Edge edits are ADDITIVE and IDEMPOTENT** (#637 gate condition): read the
  current body, append a `- Blocked by #N` line ONLY when no equivalent edge
  line is already present, and never rewrite or reflow the surrounding body
  text. Re-running Phase 1 over an already-edged issue set must change
  nothing. (Concretely: `gh issue view N --json body`, check with a line-match
  for `Blocked by #M`, and on miss `gh issue edit N --body` with the original
  body plus the appended line - no other diff.)
- **No spec:** take the `--issues` label/milestone/list as the set; edges are
  whatever `- Blocked by #N` lines the bodies already carry.

## Phase 2: The orchestration loop

Loop until every wave issue is merged or explicitly parked.

### 1. Plan (and re-plan)

```bash
gh issue list --state all --json number,title,body,state --limit 200 > /tmp/<scratch>/wave-issues.json
~/.claude/scripts/flow-wave-plan.py /tmp/<scratch>/wave-issues.json --in-flight <N,N or ''> --verdicts "$XDG_RUNTIME_DIR/cc-flow-wave/<WAVE>/verdicts.json"
```

Pass `--in-flight` with the currently ASSIGNED issues (assignment state is
yours, not the listing's): `path_contention_active` then names only the
collisions that can happen NOW, which is what keeps the warning believable
(#645 - flagging every open issue that mentions a shared file trains everyone
to ignore the flag). Pass `--verdicts` with the wave's ruling ledger, every
run (see the verdict-ledger protocol under gate judging).

The planner is a pure function over the listing: Blocked-by graph + transitive
closure, `startable` set, `path_contention` index, `serialized_resources`
flags. **Exit 3 means the graph is BROKEN, not empty** - a Blocked-by cycle's
members are listed in `cycles`; fix the edges before assigning anything.
Never read an exit-3 plan's empty startable set as "wave done".

**Edge-grammar relationship to the project-next contract v1.3 (issue #648 - a
DECIDED partial convergence, data not accident; also recorded in the planner
header).** ADOPTED from the contract: fenced/inline code is stripped before
edge parsing (a sample inside a fence never fabricates an edge - the #607
negative-space rule finished; path/serialized/migration detection still reads
the RAW body, since backticked paths are deliberate signal), and
Markdown-emphasis tolerance in declaration position (`**Blocked by:** #12`
declares an edge; line anchor + immediate-refs unchanged). DELIBERATELY
DISTINCT, with reasons: grading + the `uncertain` class (the wave lane is
JUDGED - an unresolvable "Blockers:" phrase goes to the orchestrator's gate,
never into a fabricated edge or a new output class); `Blockers:`/
`Prerequisites:` field labels (their contract value IS the declined grading
semantics); dash-ranges (zero occurrences in 240 measured real bodies;
speckit-tasks-to-issues emits the planner's native list grammar); spec-task
duplicate-claim resolves-to-neither (the planner surfaces `unresolved_tasks` +
`spec_drift` loudly instead). A wave and a next-pick can still disagree ONLY
on those distinct features - by decision, not drift.

The `path_contention` index exists because contended files that nobody's lane
names are invisible until two workers are in one (six queued issues all naming
one `cli.py`, in no declared lane, visible only by grepping every body). Treat
any path claimed by more than one near-term-startable issue as a serialized
resource and order it explicitly - widest change first, since it sets the
conventions the later ones inherit. `Serialized-resource: <name>` body lines
are the precise override for non-path resources.

### 2. Assign

For each idle registered worker, pick the next startable issue subject to:

- **Lane disjointness**: no two in-flight issues sharing a contended path or
  serialized resource. Two contention classes need different handling (#637):
  - **Collide on creation** (migration revision ids, a fixture filename, an
    enum value): serialize - only one holder in flight at a time.
  - **Collide on convention** (a shared file both can extend with NO merge
    conflict, e.g. one `cli.py` growing two option-naming styles): serializing
    is not enough - either give ONE worker ownership of the file for the wave's
    duration, or hand every toucher the same written convention in its
    assignment. CI cannot catch this class; the file just quietly gets worse.
- The assignment message carries: issue number + scope, the lane and its
  boundaries, known hazards, the conditions format, and the
  verify-against-the-tree obligation.

### 3. Judge the Step-3 gate

The worker runs `/flow:auto <N>` (never `--yes`) and pauses at the ELI5 gate.
Judge it with verification, not trust:

- Re-run the necessity evidence yourself against the tree (`git log --since`,
  merged PRs, duplicate search) - verify the worker's claims, and expect the
  worker to have verified yours.
- Sort every task in the issue into **delivered / in-scope / residual**; any
  narrowing must ship a filed issue for the residual BEFORE approval.
  "Another issue mentions it" is not coverage; "nothing residual" is a recorded
  judgment naming what delivered each excluded task.
- Rule with explicit conditions; make required regression tests and fixture
  constraints gate conditions, not suggestions.

**After ANY verdict that touches scope - including approve-with-conditions,
since conditions can widen an issue's footprint - re-run the planner BEFORE
the next assignment** (#637; refined by field evidence):

```
verdict issued -> planner re-run -> contention diff checked -> next assignment
```

The trigger belongs where scope is RULED ON, not where work is handed out.
The reference failure: a gate approval ("evict the stale cache entries")
turned a pure compiler fix into a migration-bearing change while another
worker already held a migration - two `0009`s chained off one parent, caught
only by a worker's status report. An assignment-time-only check reproduces
exactly that bug. Diff the new plan's `serialized_resources` and
`path_contention_active` against the previous run; a new overlap with an
in-flight issue means pausing or re-scoping one side NOW, not at its merge.

**The verdict ledger (#645).** Every gate ruling is APPENDED to the wave's
ledger - the canonical location is the wave's runtime namespace, beside the
#638 registry:

```
$XDG_RUNTIME_DIR/cc-flow-wave/<WAVE>/verdicts.json
```

NOT session scratch: rulings must outlive any single orchestrator session (a
successor resuming after a /clear or crash needs them, or every hold silently
evaporates exactly when things are already going wrong), and the runtime dir
dies at reboot when the wave dies too - the same lifetime symmetry as the
registry. It is a JSON array of entries
`{"issue": N, "ruling": "hold"|"approved"|"approved-with-conditions",
"holds_behind": [N]?, "adds_serialized": [marker]?, "reason": str, "ts": str}`;
write via tmp-file + rename (concurrent sessions share the wave dir). Append:

- a `hold` when you rule an issue waits (name what it waits behind);
- every approval - and when a CONDITION changes the issue's footprint (adds a
  migration, claims a serialized resource), carry it in `adds_serialized`:
  the issue's body never changes, so the ledger is the ONLY way the next
  re-plan can see the new footprint (the two-`0009`s failure).

A later entry for the same issue SUPERSEDES the earlier one - overriding a
ruling is a recorded act with a reason, never a silent contradiction. The
planner reads the ledger on every run: **exit 4 means an issue you are about
to assign (or already assigned) contradicts an unsuperseded hold**. Do not
assign - honor the hold, or append the explicit superseding entry, then
re-plan. The plan JSON is still emitted on exit 4 (the exit-3 contract's
loud-but-never-obstructive rule).

### 4. Verify the PR

When the worker reports CI green: check the PR diff against the gate
conditions actually landed (named tests exist and assert the pinned behavior),
confirm the required checks are green, and take the completeness ledger. Check
the worktree HEAD against `origin/main` yourself (`git -C <wt> rev-list
--count HEAD..origin/main`) rather than trusting reports - **stale-base
discipline**: with N workers merging, main moves under everyone; three of four
workers were caught behind at least once in the reference run.

### 5. Release the next issue

On ledger acceptance the worker proceeds to merge (Step 7-9), then gets its
next assignment from the CURRENT plan (step 1 re-ran after the verdict).

## Hazards (confront, do not assume away)

- **One CI agent serializes the wave.** N workers produce N queued Woodpecker
  pipelines on one agent; wall-clock scales with the queue, not the worker
  count. Tell workers this so a slow pipeline is not misread as a failing one,
  and cap in-flight PRs (2-3 on a single-agent host) rather than maximizing
  parallel implementation.
- **Test parallelism is uncapped where it matters.** Nothing in the gate path
  caps pytest workers, so every unattended gate inherits a project's
  `-n auto`-style default and N sessions compete with N x nproc workers on the
  host also running the CI agent. Filed as #640 (manifest-level cap); until it
  lands, stagger gate runs on one host.
- **The #635 stash race: do not build on an untraced path.** `/flow:auto`
  Step 6 documents a stash push -> merge -> pop sequence, and stashes live in
  the COMMON git dir - all worktrees share one stack - so concurrent sessions
  stashing simultaneously can swap uncommitted work silently. There is also
  negative evidence that the stash branch may be RARELY REACHED in practice
  (#635 discussion): do not assume it is the branch concurrent sessions
  actually take, and do not harden or depend on it without first tracing which
  Step-6 branch real runs hit. Until #635 settles it, the wave-level
  mitigation is scheduling: avoid co-scheduling issues likely to hit the
  Step-6 merge window simultaneously, and prefer letting a worker merge
  `origin/main` early (Step 4) over relying on the Step-6 stash path.
- **The orchestrator is the unreliable component.** Verify before ruling,
  expect verified pushback, and record who was right.

## Reporting

Maintain a compact wave ledger (in-context, plus a summary message on each
change): per issue - worker, state (queued / assigned / at-gate / implementing
/ PR-open / merged / parked), gate verdict + conditions, ledger outcome,
residuals filed. Per wave close: issues merged, residuals filed, defects
caught at gates, orchestrator errors caught by workers (count them - the
number is the health metric of the judging, in both directions).

## Notes

- Worker-side mechanics are unchanged `/flow:auto`; this command is purely the
  orchestrator's loop. The role/address handshake is `/flow:register` (#638);
  dependency-graph fixes for `project:next` are #607; the shared behavioral
  contract for gate judging is #636. This command consumes all three and
  duplicates none.
- The planner is deterministic and network-free by design: feed it a fresh
  `gh issue list` snapshot each time; re-running it is the whole cost of the
  dynamic contention rule, which is why the rule is affordable.
- Naming: the unit of work is a wave (matching spec-kit's
  `spec-sync:v1:...:wave-N` markers). `flow:fleet` was the runner-up.

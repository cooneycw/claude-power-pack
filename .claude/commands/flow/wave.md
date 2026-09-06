# Flow: Wave - Orchestrate a Dependency-Ordered Issue Wave Across Worker Sessions

Run one **orchestrator** session over N **worker** sessions, driving a
dependency-ordered wave of issues to merge (issue #637). The orchestrator never
implements. It picks what is startable, assigns disjoint lanes, judges each
worker's `/flow:auto` Step-3 ELI5 gate, re-derives resource contention after
every ruling, and enforces the completeness policy so a narrowed scope always
leaves a recorded residual candidate behind rather than a hole.

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
addressing logic of its own. Follow `register.md`.

**Registration is ORDER-INDEPENDENT (issue #670)** - these happen in any
order; the registry file creates the wave on first touch, whoever touches it
first:

- Register this session as the wave's orchestrator:
  ```bash
  ~/.claude/scripts/flow-wave-registry.sh register orchestrator --wave <WAVE> --repo <TARGET_REPO>
  ```
- Each worker runs `/flow:register <role> --wave <WAVE>` - before or after the
  orchestrator exists. A worker that registers first reports
  `registered; orchestrator not yet in roster; hello deferred` and is NOT
  stalled; its registration stands on its own.

Then, on FIRST CONTACT in either direction, verify the observed address:

- Orchestrator registered first: each worker sends its hello on registering.
- Worker registered first: its roster entry reads `[live, unverified]` - a
  PENDING HANDSHAKE. On registering, and on each `list`, initiate contact
  with every such worker at its recorded bootstrap address; the worker's REPLY
  is its deferred hello.

On each hello (or reply), reconcile the observed `from=`:

```bash
~/.claude/scripts/flow-wave-registry.sh verify <role> --wave <WAVE> --from <observed-address>
```

Pass the `from=` value verbatim - it is an OPAQUE transport-stamped token, not a
path (#675). `uds:/run/user/1000/cc-socks/12345.sock` and
`bridge:session_01RLE...` are both valid and are stored unchanged.

The transport-observed address is authoritative and becomes canonical (#638).
`verify` distinguishes two ways that happens (#674): `address_filled` when the
recorded value was `unknown` and observation supplied one - unflagged, and the
ONLY outcome on a transport where self-derivation cannot run - and
`mismatch-corrected` when a recorded real address was contradicted, which stays
loud and warrants investigation. `filled` is not a lesser grade than `verified`.

Ack each worker with the wave brief: its lane, stop-at-Step-3 (never
`--yes`), the ledger format, and the structural-pushback rule verbatim.

Address workers ONLY by the address the registry holds, via `SendMessage` -
never by `ListAgents` display names, which do not map to roles and mutate
mid-session. Check the roster with:

```bash
~/.claude/scripts/flow-wave-registry.sh list --wave <WAVE>
```

## Setup: the wave policy (consume #699, do not reimplement)

**Declare the policy ONCE, before assigning anything.** Until #699 the
brief above was retyped into every message, and everything in it died with a
worker's `/clear` - the one thing the registry exists to survive. It is now
declared data the registry inherits to every role:

```bash
~/.claude/scripts/flow-wave-registry.sh policy set --wave <WAVE> \
  --repo <TARGET_REPO> \
  --driver flow:auto \
  --authority implement \
  --authority-model orchestrator-only \
  --gate "stop at /flow:auto Step 3; orchestrator judges; --yes forbidden" \
  --ledger "delivered / in-scope / residual" \
  --merge-authority worker \
  --deploy-policy "woodpecker-only"
```

Three of these fields exist because of a specific failure, and skipping them
re-creates it:

- **`--authority`.** Against CPP's standing "file issues, don't implement" rule,
  whether this wave writes code is the single most consequential wave-level
  fact. Undeclared, it took a user round-trip and then had to be restated in
  both worker briefs; both workers correctly refused to infer it from being
  handed an issue number, and nothing in the registry could tell them.
- **`--authority-model`.** A worker asked whether it needed BOTH its user's go
  and the orchestrator's before writing code, and held pending an answer.
  Requiring two signatures is how a wave stalls. Declare it once rather than
  renegotiating it per worker.
- **`--gate` / `--ledger`.** The ledger format was the ONE structured element in
  the reference wave's brief, and it is the one thing that did not drift all
  day - both workers produced directly comparable output. That is the argument
  for this whole feature, so it is recorded rather than retyped.

Amending is a one-flag `policy set` (it merges, and bumps `rev`). After any
amendment the helper - and every later `list` - names the live roles still
carrying the older rev: they are running on superseded rules until each
re-registers, and **re-registering IS the re-brief**, so the fix is a message
saying "re-register", not a retype of the policy.

Assignments then carry the LANE and issue-specific conditions only; the protocol
is already recorded. Grant a worker's file lane as DATA (`--files a,b,c` on its
register) rather than as a sentence in a message - the roster checks declared
file lanes for overlap, and the reference wave's every real collision was
file-level while the orchestrator held the paths in prose.

## Setup: the delivery lane (consume #676, do not reimplement)

The roster says WHERE a worker is. It does not deliver, and on 2026-08-11 that
was the whole failure: the harness rejected every orchestrator->worker
`SendMessage` (it routes only to subagents the calling session spawned), so a
written assignment sat undelivered ~2h while both sessions correctly stood by.
Follow the delivery preference order in `register.md` - `SendMessage` first,
then the mailbox, and a human relay only as a named last resort.

**Arm the inbox watch at setup, before the first assignment.** One background
Bash call covers every `inbox-*.md` in the wave, so a hello, a status report, or
a worker's pushback wakes this session instead of waiting for the next time
somebody looks:

```bash
~/.claude/scripts/flow-wave-mailbox.sh watch --role orchestrator --wave <WAVE> --timeout 1800
```

Re-arm after each wake, for as long as the wave runs. Exit 5 is a plain
timeout, never evidence a worker died - re-arm and read the roster.

**Route these four over the lane whenever `SendMessage` cannot reach a worker**
(all of them failed to reach one in the reference run): the registration ack +
wave brief, each ASSIGNMENT, each gate VERDICT with its conditions, and each
re-plan notice that changes a worker's lane.

```bash
~/.claude/scripts/flow-wave-mailbox.sh send --to <role> --wave <WAVE> --body-file <file>
```

Sends append, so an assignment already waiting is never overwritten by the
verdict that follows it. Confirm delivery from the roster's side rather than
assuming: `flow-wave-mailbox.sh list --wave <WAVE>` shows each box's rev,
cursor and unread count, so an assignment a worker has NOT consumed is visible
as a nonzero `UNREAD` instead of being invisible until someone asks. A worker
with unread mail and no progress is a worker whose watch is not armed - fix
that rather than relaying by hand.

## Setup: the transition lexicon (consume #701, do not reimplement)

The registry says WHO (#638), the mailbox says it ARRIVED (#676), the policy
says the RULES (#699). None of them says what a message DOES. That layer was
free prose, and every miscommunication in the reference wave happened there
while the machine-readable markers never once misfired.

**Reserved tokens carry the TRANSITION; prose carries the ARGUMENT.** The
vocabulary is deliberately tiny - only the speech acts with a wrong-answer cost:

| Token | Carries | Enforced |
|---|---|---|
| `GATE: GO #N` | approval of a judged gate | names its subject issue |
| `GATE: HOLD #N behind #M[, #M]` | a hold | names what it waits behind |
| `GATE: GO-WITH-CONDITIONS #N` | conditional approval | `- <condition>` lines beneath it; optional `serializes: <marker>` |
| `LANE: GRANT\|EXTEND <role> <paths>` | a file lane | names role AND paths |
| `LANE: REVOKE <role> [paths]` | withdrawing a lane | names the role |
| `MERGE: AUTHORIZED #N when <check>` | conditional merge authority | a NAMED check - "when CI passes" is refused |
| `STATE: as-of <commit>` | any wave-state assertion | the stamp is mandatory |
| `RATIFY \| OVERRULE #N <reason>` | answer to a reported deviation | issue + reason |
| `PUSHBACK <argument>` | a refutation | must carry its argument |
| `LEDGER` | the completeness ledger | `delivered:` / `in-scope:` / `residual:` |

Each requirement is a specific failure made unrepeatable. `GATE`/`LANE` are
separate tokens because one message carrying "you are unblocked for Step 4"
beside "hard stop at Step 3 stands" nearly passed an unjudged gate - the lane
was open, the gate was not, and only a worker's caution caught it. `LANE: GRANT`
must name paths because a fence ("explicitly NOT yours") was read as its own
inverse. `MERGE` must name the check because `ci/woodpecker/pr/woodpecker` is
not the push pipeline. `STATE` must be stamped because four broadcasts were true
when composed and wrong when read.

**The tokens are READ BACK - that is the whole reason this exists.** A lexicon
nobody validates is prose with extra steps, and a reflexive `GATE: GO` prints
exactly what a considered one prints. Two mechanisms make a token load-bearing:

1. **`send` refuses a malformed transition.** The mailbox validates every
   message, so a broken token fails at the sender rather than in a reader's
   inbox. A message with NO token always delivers (prose is not the target), and
   a missing validator fails OPEN - a wave must never stall on its own linter.
2. **A gate verdict is RECORDED by parsing it, never by hand:**

   ```bash
   ~/.claude/scripts/flow-wave-lexicon.sh record --wave <WAVE> --body-file <verdict-file>
   ```

   This derives the #645 ledger entry from the token - ruling, `holds_behind`,
   `adds_serialized` - and appends it to `verdicts.json`. A gate therefore cannot
   be recorded as judged without a parseable verdict. Because
   `flow-wave-plan.py --verdicts` exits 4 on an unsuperseded hold and unions
   `adds_serialized` into `serialized_resources`, an unparseable verdict changes
   PLANNER BEHAVIOUR, not just a log line: `serializes: <marker>` on a
   conditional approval is what makes the two-`0009`s migration collision visible
   to the next re-plan, which in the reference wave was caught only by a worker's
   status report.

Validate a draft before sending it (`validate` is read-only):

```bash
~/.claude/scripts/flow-wave-lexicon.sh validate --body-file <file>
```

**What the lexicon must NOT cover: the reasoning.** The highest-value messages in
the reference wave were a worker's design-ruling requests, its correction of
misattributed credit, and its catch of the crossed lane/gate message. None would
survive schematisation, and a vocabulary that crowds them out costs more than it
saves. If a line is an argument, leave it as prose - `--no-lexicon` on `send` is
the escape when a prose line happens to open with a reserved word.

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
  verify-against-the-tree obligation. The PROTOCOL (gate point, ledger format,
  authority model, merge authority) is not retyped here - it is declared wave
  policy (#699), and the worker re-reads it by re-registering.
- **Declare the lane, do not just describe it** (#699). Give the file lane as
  `--files a,b,c` for the worker's next register, so the roster can warn when
  two lanes overlap. The reference wave's worst orchestrator error was a message
  that fenced a worker's file lane out of one file and, three paragraphs later,
  assigned it the issue whose fix lived in that file - a contradiction nothing
  could check because the lane existed only as prose.
- **Route by declared role facts, not by guess.** `list` now shows each role's
  `model=` and `perm=`; a session in a prompting permission mode cannot take
  unattended work, and the hardest issue should not go to the smallest model.
  Both were previously visible only in message metadata, if at all.
- **An assignment is not assigned until it is DELIVERED.** Send it by the
  preference order (`SendMessage`, else the mailbox), and treat the worker's
  acknowledgement - not your own send - as the transition to in-flight. An
  issue marked assigned in your ledger whose box still shows `UNREAD` is the
  2026-08-11 failure reproducing: the plan looks healthy from both ends while
  nothing moves.

### 3. Judge the Step-3 gate

The worker runs `/flow:auto <N>` (never `--yes`) and pauses at the ELI5 gate.
Judge it with verification, not trust:

- Re-run the necessity evidence yourself against the tree (`git log --since`,
  merged PRs, duplicate search) - verify the worker's claims, and expect the
  worker to have verified yours.
- Sort every task in the issue into **delivered / in-scope / residual**; every
  residual is DECLARED before approval. "Another issue mentions it" is not
  coverage; "nothing residual" is a recorded judgment naming what delivered each
  excluded task.
- **Where a declared residual GOES is a severity call, not a reflex (#714).**
  Record a `pre-existing-oos` candidate when the residual names a consequence
  someone would notice - a user-visible behavior, a correctness or security
  risk, a cost or data-loss exposure, or work another issue is already blocked
  on. Do not file an ordinary residual issue while the wave is active. Otherwise
  the ledger's `residual:` line plus the PR description is the whole of its
  record. Not issue-worthy on their own: "measure X", "annotate the files we excluded",
  "tighten a coupling we just introduced", "consider whether Y is still needed".
  This changes a low-severity residual's DESTINATION, never whether it is
  declared - the anti-silence property the rule exists for is untouched, and it
  is still the gate, not the worker, that rules on the sort.
  The evidence is depth, not volume: the 2026-08-11 aws-learn wave turned 5 seed
  issues into 26 and drained the backlog fine, but error rate rose with each
  generation, because a residual reasons about the previous agent's WORK PRODUCT
  rather than about the system or a user need. Gen-2 caught real defects in code
  the wave had just written (tests firing live AWS calls under production
  credentials); gen-3 produced aws-learn#838, which proposed flipping a compose
  dependency to `service_healthy` on a pattern match against how the other
  services were gated. As written it would have deadlocked every cold start - the
  healthcheck it would have waited on aggregates a heartbeat only the gated
  service can write. It even asked for a deadlock check, and shipped anyway,
  because the policy required a residual to be FILED, not to be VALIDATED.
- **A residual proposing a change to a system you have not run carries its
  verification, or is recorded as a QUESTION rather than a directive (#714).**
  "Change X to Y" asserts you checked what Y does here; if you did not, the
  honest form is "does X need Y? - unverified, nothing checked about <what Y
  depends on>". Stamp a residual's generation when you record one: a residual
  descended from another residual is a signal to write it down rather than file
  it, and it is the stamp that makes that visible to whoever triages it.
- Rule with explicit conditions; make required regression tests and fixture
  constraints gate conditions, not suggestions.

**Route every declared residual through the executable ledger (#719).** The
prose sorting rules above remain the operative mask and fallback, while the tool
enforces their state transitions. A worker or reviewer must not run
`gh issue create` for a residual during an active wave. Record it instead:

```bash
scripts/flow-wave-residuals.py record --wave <WAVE> \
  --root-issue <ROOT_ISSUE> --source-issue <SOURCE_ISSUE> \
  --classification <current-issue-failure|active-pr-defect|pre-existing-oos|emergency|speculative|duplicate> \
  --consequence <TEXT> --evidence <TEXT> --generation <N> \
  [--dedupe-of <CANDIDATE_ID>] [--source-link <TEXT> ...]
```

`current-issue-failure` routes to `fix-before-close`, and `active-pr-defect`
routes to `fix-current-pr`; neither can enter promotion. `pre-existing-oos` is
eligible only after final-tree review. `emergency` still requires explicit
human override. `speculative` stays ledger-only. `duplicate` requires
`--dedupe-of`; the tool merges evidence and every retained source into the
canonical candidate instead of minting another canonical candidate. Recording
after close is refused, so repeating the command cannot silently reopen a wave.

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
write via tmp-file + rename (concurrent sessions share the wave dir).

**Do not hand-write the entry - parse it out of the verdict you issued** (#701):
`flow-wave-lexicon.sh record --wave <WAVE> --body-file <verdict-file>` derives
`ruling`, `holds_behind` and `adds_serialized` from the `GATE:` token and appends
under flock. Hand-writing it is what lets a ledger entry drift from the ruling
actually delivered, and it re-opens the gap the token exists to close: a verdict
that does not parse then records perfectly well anyway. Append:

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

## Phase 3: Close, promote, and report issue economy

After every wave PR has landed and the final tree has passed its required
checks, revalidate each recorded consequence and its reproducible evidence
against that exact tree. Then freeze the ledger at the tested commit:

```bash
scripts/flow-wave-residuals.py close --wave <WAVE> --at-commit <FINAL_SHA>
```

`close` is idempotent. Re-closing at a later final-tree commit revalidates the
ledger and invalidates a promotion tied to the stale tree; `record` cannot
un-close it. Deduplicate before promotion, and offer only a candidate whose
final-tree evidence still reproduces. The human making the decision runs one
promotion command for the one candidate they choose:

```bash
scripts/flow-wave-residuals.py promote --wave <WAVE> \
  --candidate-id <ID> --approved-by <HUMAN_IDENTITY>
```

For a generation-2+ security, data-loss, or work-blocking emergency, the human
must additionally supply both `--emergency-override` and
`--override-reason <TEXT>`. No generation is auto-promoted. Promotion records
the audit decision but deliberately does not call `gh issue create`; after a
successful promotion, the approving human may file that one issue manually.

Every close summary takes its original seed count from the orchestrator, since
the offline tool has no GitHub access:

```bash
scripts/flow-wave-residuals.py metrics --wave <WAVE> --seed-count <N>
```

Report all six returned fields: `seed_count`, `recorded`, `duplicates`,
`promoted`, `amplification`, and `promotion_rate`. With zero seeds,
`amplification` is the string `not-applicable`, never a numeric ratio.

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
- **An idle session is not a stalled one, and neither is visible without the
  lane (#676).** A worker that registered, stood by, and re-reported
  "registered" on every wake is behaving CORRECTLY - it has no way to learn an
  assignment exists. Before diagnosing a worker as stuck, check
  `flow-wave-mailbox.sh list --wave <WAVE>`: unread mail means delivery
  happened and the watch is not armed; an empty box means the assignment was
  never sent, however finished it looks in your own ledger. Two hours were lost
  on 2026-08-11 reading this exact state as "both sessions healthy".
- **Read the `watch=` column on every sweep (#778) - it is the fastest of these
  checks and the only one that is one look.** The rule above is correct and was
  followed all evening by the orchestrator that still missed this: it requires
  REMEMBERING to cross-reference two tools, per worker, continuously, against a
  failure that is silent and has no deadline. `flow-wave-registry.sh list` now
  renders that cross-reference for you - `watch=ABSENT` (never armed),
  `watch=stale(42m)` (died, or busy between wakes), `unread=N since <ts>`, and
  `** NEVER READ **` when a role has consumed nothing at all - plus a
  `WATCH:` summary and the `FLOW_WAVE_WATCH_UNARMED` / `FLOW_WAVE_UNREAD`
  contract lines. On 2026-09-05 a `kyle-completion` worker was `[live,
  verified] brief=current` and deaf for over an hour; its six-issue assignment
  was delivered and never read, your ledger said assigned, its roster entry
  said free, and the only tell was a cursor at 0 spotted by accident. Treat
  `watch=ABSENT` on a role you are about to assign as a BLOCKER: tell it to arm
  the watch before you send, because nothing you send will wake it.
- **The orchestrator is the unreliable component.** Verify before ruling,
  expect verified pushback, and record who was right.

## Reporting

Maintain a compact wave ledger (in-context, plus a summary message on each
change): per issue - worker, state (queued / assigned / at-gate / implementing
/ PR-open / merged / parked), gate verdict + conditions, ledger outcome,
residuals recorded. Per wave close: issues merged, residuals RECORDED and the
subset of them PROMOTED (report both - one number cannot show whether the #714
severity gate is working, and a wave whose two counts are equal has stopped
applying it), duplicate links, seed count, amplification, promotion rate,
defects caught at gates, and orchestrator errors caught by workers (count them -
the number is the health metric of the judging, in both directions).

## Notes

- Worker-side mechanics are unchanged `/flow:auto`; this command is purely the
  orchestrator's loop. The wave POLICY - implementation authority, gate policy,
  ledger format, authority model, merge and deploy policy, and the per-role file
  lane - is declared state in the registry (#699), consumed here and
  reimplemented nowhere; the role/address handshake is `/flow:register` (#638);
  dependency-graph fixes for `project:next` are #607; the shared behavioral
  contract for gate judging is #636. This command consumes all three and
  duplicates none.
- The planner is deterministic and network-free by design: feed it a fresh
  `gh issue list` snapshot each time; re-running it is the whole cost of the
  dynamic contention rule, which is why the rule is affordable.
- Naming: the unit of work is a wave (matching spec-kit's
  `spec-sync:v1:...:wave-N` markers). `flow:fleet` was the runner-up.

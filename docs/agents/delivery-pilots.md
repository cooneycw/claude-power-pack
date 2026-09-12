# Delivery pilots: what the balanced-delivery wave actually observed

Maintained report for issue #861, the last task of the #855 balanced-delivery
programme. It records what was measured, by what kind of instrument, and what each
instrument does not establish. It is also the wave's candid ledger: the approval
interruptions, duplicated documentation and lost requirements that actually
happened, including the ones caused by the worker writing this and by the
orchestrator reviewing it.

It is deliberately not a scorecard. Two pilots and three completion cases against
one model are a handful of observations, and nothing here supports a claim about
how agents behave in general.

## Evidence classes, and what each one cannot tell you

The #860 acceptance report failed by labelling a table "structural and executable,
not prose-matching" when several cited tests were `assert "<phrase>" in text`, and
by citing a named test for a requirement `grep -c` shows no test asserts. The
correction is to give every class a column for what it does NOT establish, because
that column is where an overstated report breaks.

| Class | Used for | Establishes | Does NOT establish |
|---|---|---|---|
| Executed shipped artifact | criterion 1, criterion 7 | the shipped script, run as a subprocess, produced these bytes | nothing about real `gh`, which is mocked; nothing about an agent's judgment |
| Helper isolation, with a positive control | criterion 1 packaging | the packaged converter used its OWN bundled helper - because removing it makes the run fail | NOTHING about document routing: it is a script dependency, not a link |
| Doc-link isolation, read not stat'd | criterion 7 | every `](docs/...)` link in an installed skill resolves AND opens with content | that the content is correct or current - only that it is reachable |
| Mutation of production code | criterion 1 | the test fails when the behaviour it names breaks | that the test would catch a defect nobody thought to inject |
| Observed model decision | criteria 2, 3, 4, 5 | what this model, at this config, decided on these inputs, once or twice | any rate, any other model, any other prompt shape |
| Behavioural check on agent output | criteria 4, 5 | the outcome survived whatever the agent chose to write | that the agent replaced the proposed approach - that is read from the diff |
| Phrase presence | nothing load-bearing | a string occurs in a document | that anything understood or acted on it |

Phrase presence appears in this work only as a `mentions` column in
`results.json`, to help a reader find the relevant paragraph. No conclusion rests
on it, and it is labelled in the runner as presence only.

## What was delivered, and how it is evidenced

| # | Acceptance item | Evidence | Class |
|---|---|---|---|
| 1 | Overlapping task IDs keep distinct acceptance context | `tests/test_speckit_handoff_integration.py` | executed artifact + mutation |
| 2 | A deliberately unmet item stays visibly unresolved | case `c1`, `~/Downloads/cpp-861-completion-cases/` | observed decision |
| 3 | A changed requirement reaches the report with its revision and evidence | cases `c1`, `c3` | observed decision |
| 4 | An agent replaces a flawed approach, preserving the outcome | pilot A, three cells, 10 runs | observed decision + behavioural check |
| 5 | A small fix proceeds without ceremony | pilot B, `open`/`guided` cells | observed decision + behavioural check |
| 6 | The report records approvals, duplication, lost requirements, judgment | this document | narrative over recorded events |
| 7 | Findings improve the existing workflow before expanding machinery | `scripts/codex-skill-sync.py`, commit `99c2d67` | executed artifact + isolation control |
| 8 | Setup, versions, actions and outcomes are reproducible | `scripts/run-delivery-pilots.py`, `tests/fixtures/delivery_pilots/` | checked-in runner |

### Criterion 1 - the handoff carries each feature's own promise

Every stage of the generated-issue path already had isolated coverage. Nothing
exercised the join, and a chain of green isolated tests does not establish that the
chain carries anything: each stage runs against inputs a test author wrote, and the
thing that actually travels is a generated issue body nobody reads back.

The tests run the shipped converter and the shipped context helper as subprocesses
and forward the bytes each stage produces into the next. Two features declare `T001`
with IDENTICAL task wording while their specs promise different things - so the
shared task line makes `task-digest` identical across both features, which is exactly
the condition under which identity has to come from the feature and its source.

Verified by mutation rather than by a green run:

| Mutation to production code | Result |
|---|---|
| spec lookup leaks across features | 7 failures in 3 classes |
| packaged converter falls back to the source checkout | the isolation control fails on all 4 bundles |
| a re-run refreshes the block as a side effect | the rerun class fails |
| a re-run appends ONE line, identity marker intact | byte-identity alone fails |

The production tree was restored from `cp` snapshots and confirmed byte-identical to
HEAD afterwards.

### Criteria 2 and 3 - the completion decision

Deterministic data tests cannot establish an agent's completion judgment, so these
are observed decisions. The issue handed to the model is not written by hand: it is
generated by the shipped converter from the fixture spec, then carries a recorded
`Acceptance-revision` naming the revised spec version, and the shipped checker reports
that record as naming the current source version before the model sees it. The
guidance comes from a reviewed commit via `git show`, never the working tree.

Three cases, one variable each, run three times AFTER the fixture was corrected -
identical dispositions every time, different wording every time. (The run before
that is the one described in the ledger below, where `c2` was mis-specified.)

| Case | Differs from the control by | Selected reference |
|---|---|---|
| `c1` revision preserved, item unmet | cancellation not implemented | `Refs #501` |
| `c2` control, every item met | (it is the control) | `Closes #501` |
| `c3` revision recorded, no evidence | nothing exercises the revised behaviour | `Refs #501` |

The control is what makes the other two mean anything. A model that answered `Refs`
to everything would score perfectly on `c1` and `c3` alone.

**These are decisions over SUPPLIED FACTS.** The model is told what the work did; it
does not read an implementation, run a test, or inspect a diff. So they establish how
the accounting rule is applied to an honest account - not that the model can tell a
true account from a false one, and not anything about a real export implementation.
The `work` text is fixture prose, written by the implementer.

**The selected reference is checked by the guard that actually runs.** A regex for
`Closes #` is phrase detection: it says which reference the model chose, not what the
merge step would do with it. Each produced body is therefore passed through the real
`gh-pr-merge.sh` incidental-close guard, extracted from the pinned commit, and that
harness proves its own positive control first - a body it must refuse with exit 7 -
before any clean result is reported. Latest run: control exit 7 with a diagnostic, all
three bodies exit 0.

On `c1` the report preserved the revision WITH evidence for the revised behaviour,
and separately named cancellation as owed - so preserving one item's revision did not
hide the other unmet item, which is the specific hazard this case exists to probe. The
selected reference is a real observation rather than a proxy: it is the value the
closing step publishes.

### Criteria 4 and 5 - the implementation pilots

Both pilots make real edits to a real file and are judged by a behavioural check
copied in AFTER the agent finishes. A check the implementer can read measures whether
it can satisfy a test it has seen, which is a different and much easier question.
**Both checks were confirmed to fail on the untouched starting state before any agent
ran.**

Pilot A states an outcome - exponential backoff, and a suite that must not spend
real seconds waiting - and proposes an approach that contradicts it:
`time.sleep(2 ** attempt)` at the end of the except block.

It is run in THREE cells, because the first comparison I built was confounded and
would have supported a conclusion the evidence does not:

| Cell | Task | CPP guidance | Runs | What the agent did |
|---|---|---|---|---|
| `baseline` | forbids new files | no | 4 | lifted sleeping into an INJECTABLE parameter |
| `open` | no such prohibition | no | 3 | kept `time.sleep` inline, ADDED A TEST that mocks it |
| `guided` | no such prohibition | yes, pinned | 3 | kept `time.sleep` inline, ADDED A TEST that mocks it |

**`open` and `guided` were indistinguishable across those runs, while `baseline`
differed.** The plausible reading is that the file prohibition is what mattered: with
no route to a test file the only way to keep the suite fast was to change the API,
and given a test file the agent took the more idiomatic route. On three runs a cell
that is a claim about what was observed, not a demonstrated cause; a sample this size
cannot establish that the prohibition explains the whole difference.

**These are historical observations, not retained artifacts.** Each run replaced its
output directory, so the counts above are what was seen during development. The one
retained guided pilot A run adds NO file, unlike the earlier guided runs that added a
test - so even within a cell the behaviour varied, and the retained bundle does not
reproduce the table. Re-run a cell rather than reading the counts as evidence on disk.

Without the `open` cell I would have attributed a prohibition effect to this
series' guidance - two variables moved at once between `baseline` and `guided`, and
a difference between them says only that they differ. The third cell is what makes
either attribution possible.

**What every one of the ten runs did do** is depart from the proposal in one
specific way: all ten guard the wait with `if attempt < attempts - 1`, so nothing
sleeps after the final failure. The proposal as written would spend eight seconds
waiting and then give up.

So criterion 4 holds, in a narrower form than a single cell would have suggested:
the agent consistently improves on the proposed mechanism, and it redesigns the API
when that is the only way to meet the stated constraint. It is NOT established that
it redesigns an API whenever a proposal is poor.

**The guidance result is a null result, and it is reported as one.** On these two
bounded tasks, prepending the pinned execution fence and plan-revision block changed
nothing observable: same implementation, same added test, same passing check, in
three runs each. That is "no difference observed on this probe" - not "the guidance
has no effect". Two small tasks with an obvious correct answer are close to the
weakest possible probe of guidance that exists to help on hard judgment calls.

Pilot B is a one-line bug whose fix is nowhere in the prompt. In every cell the
agent changed one line and added nothing. Most of the check's cases are inputs the
task never mentions - a leading separator, both ends, a run of them - because a fix
special-cased to the reported example passes that example and nothing else. It
generalised.

**Ceremony, measured where it could actually appear.** In the `baseline` cell the
prompt forbade extra files, so "no spec, no plan document" was task-instructed and
establishes nothing about CPP policy. The `open` and `guided` cells remove that
prohibition, and the only file either pilot has ever added across those cells was a
unit test. That is an observation about ceremony; the baseline one was not.

**The retained small-fix trace.** One guided pilot B run is kept in full - prompt,
raw JSON event stream, final account, diff and check result - in
`~/Downloads/cpp-861-pilots-guided/`. The event stream is what makes this reviewable:
a final message is a summary the model wrote about itself, while the stream is what it
actually did. It reads: read `src/slugify.py`, make the one-line edit, then verify inline - three
assertions covering the reported example, a leading separator, and an all-separator
input - with a `python` invocation that was not present, retried as `python3`, and a
closing report. It recovered from the missing interpreter itself. No request for
approval, clarification or confirmation appears anywhere in the stream, and no
specification artifact was created.

That is an observation about THIS AGENT'S BEHAVIOUR on an authorized small fix, and it
is worth separating from the harness limitation. **Observed: zero requests from the
agent in this trace** - it had a way to ask, in its own response, and did not use it,
including when a tool it reached for was missing. **Unmeasured: native harness
permission prompts**, which `codex exec` cannot surface at all. The first is evidence;
the second is a gap, and neither substitutes for the other.

**The behavioural check establishes that the outcome was preserved. It does not
establish that the approach was replaced**; that is read from the diff and the agent's
own account.

### Criterion 7 - the installed-contract routing defect

The assignment asked whether guidance that routes to a checkout-relative document is
readable once the skill is installed elsewhere. It is not. Before the fix,
`~/.codex/skills/flow-auto/reference.md` plus `../../../docs/agents/issue-contract.md`
resolved to `/home/cooneycw/docs/agents/issue-contract.md`, which does not exist.

Enumeration corrected the worker's own first report: three skills were named, the
actual set is **six** - `evaluate-issue`, `flow-auto`, `flow-finish`, `flow-merge`,
`github-issue-create`, `project-init` - across two documents. `issue-contract.md` has
five callers; `knowledge-lifecycle.md` has two direct callers and reaches the other
four transitively because `issue-contract.md` links it.

The fix rides the existing packaging path rather than adding machinery: the bundler
already discovers `scripts/<name>` references, and documents now use the same
mechanism, bundled at their repo-relative path so the sibling link between the two
resolves without rewriting any document's contents. No crawler was built. Current
state: 6 skills, 11 files, 95,193 bytes, 2 distinct documents, and zero
source-relative doc links left in any generated body.

**Scope was narrowed after measuring.** The first pattern matched every `docs/`
reference and bundled 241 KB, including two 35 KB copies of the best-practices guide,
because it caught bare prose mentions. It is now restricted to source-relative
markdown links.

**A bare prose mention is not classified as a defect.** `docs/x.md` written in prose
was never resolvable from a skill directory and never claimed to be. Its actual
consequence is narrower: a reader in an installed skill sees a path that names a real
file in the CPP repository and has no copy of it to hand. That is a limitation worth
knowing, not a broken link, and inventing a new meaning for it is a policy call this
change did not make.

The isolation proof reads content rather than checking existence - a zero-byte copy
resolves exactly as well as a real one - and its positive control removes the bundled
helper and requires exit 7, because a passing run only establishes which helper was
used if the run fails when that helper is gone.

## The candid ledger

### Unnecessary approval interruptions

Two, both observed in this wave's own transcripts, one caused by each side.

1. **Orchestrator wording (#860, rev38).** The assignment ambiguously said to begin
   after release while itself delivering the assignment. The worker stopped to ask
   whether that message was the release. Corrected in rev39. The interruption was
   caused by the wording, not by the worker being over-cautious.
2. **Worker delivery (#861, Step 3).** The worker printed its gate report in its
   native session and described it as delivered, but never sent it through the
   mailbox. The orchestrator never saw it, and the USER had to surface the wait.
   Corrected: every gate report now goes through `flow-wave-mailbox.sh send` before
   being described as delivered.

### Duplicated documentation

1. **A sentence shipped twice.** The #860 accounting rule says "A revision record on
   its own is never delivery evidence, and a revision record on its own is not
   delivery evidence." Landed in `f57b15a` - the worker's own change - and reaches
   four files, because both canonical command bodies are mirrored into generated
   skills. This paragraph is prompt text read by agents deciding what counts as
   delivered, and it is the exact block extracted by the #860 and #861 runners.
   Recorded in the nit store (`cooneycw/claude-power-pack#864`,
   [comment](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5647308210)),
   not fixed here: `.claude/commands/` is outside this issue's lane.
2. **Deliberate duplication, with a named owner.** Bundling documents into skills
   copies them byte-for-byte into 11 files. That is duplication by design, and the
   thing that keeps it honest is that `docs/` remains the only writable source and
   the generated copies are regenerated by `make codex-skills`. The bundled bullet
   in each skill says so.

### Lost requirements

Four, three of them the worker's, and the most interesting one was caught by the
model being measured.

1. **Three skills reported, six affected** (#861 Step 3). The worker reported the
   routing defect against the skills it had found rather than enumerating the set.
   Caught by the worker before implementation, by enumerating instead of counting.
2. **Seven acceptance criteria reported as six** (#860 gate report). Caught by the
   orchestrator.
3. **A named test cited for a requirement no test asserts** (#860 acceptance report).
   The worker cited `TestCanonicalPolicy` as establishing that demonstrated items must
   cite behavioural evidence; `grep -c` over the file returns 0. Caught by the
   orchestrator (rev54), which correctly called it the issue's own failure reproduced
   inside its own report.
4. **The control omitted a requirement its own fixture declared** (#861, this work).
   The first `c2` run was meant to be "every item met" and the model refused to close
   it, observing that R1 - "export runs without holding a request thread", a
   requirement the generated context block carries - had no evidence, and that an
   interactivity test does not establish it. **That was a defect in the fixture, not
   the model.** Every case now carries R1 evidence so each differs from the control in
   exactly one way. A second defect surfaced in the same run: the prompt never named
   the issue number, so the model echoed the rule's own `#N` placeholder, which no
   closing guard would act on.

### Useful independent judgment

1. **The model corrected the measurement.** Item 4 above. The instrument being
   evaluated found the flaw in the evaluation.
2. **Both pilots departed from what they were handed.** Pilot A replaced a proposed
   approach that contradicted the stated outcome, three times out of three, and
   additionally removed a wait the proposal would have spent before giving up. Pilot B
   generalised a fix beyond the single example it was given.
3. **The orchestrator corrected itself.** It had generalised that all earlier commit
   closing text reaches the squash; `gh-pr-merge.sh` normally supplies an explicit
   subject and body from the PR (#655). Corrected in rev45. The worker did not
   independently challenge the earlier prescription, which is its own finding.
4. **The orchestrator reported its own monitoring gap.** In rev58 it noted its
   one-shot watch had expired after the worker's acknowledgement, and said plainly
   that this was an orchestrator gap rather than a worker stall.

### Other worker errors in this issue

- Claimed six helpers were missing after `/cpp:update` by diffing directory listings.
  Only `speckit-context.py` was genuinely owed, and `/cpp:update` installed exactly
  it. The other five are not referenced as `~/.claude/scripts/<name>` by any command
  document.
- The first doc-bundling pattern over-matched by 2.5x (241 KB against 95 KB).
- The doc-link rewrite initially ran after the description was derived, leaving the
  broken path advertised in the skill's own frontmatter. Caught by a test in the same
  change - a real ordering flaw, not a test bug.
- Bytecode from the runner's own check was counted as files the agent added, which
  reads exactly like the unasked-for ceremony pilot B is supposed to measure.
- **I built a confounded comparison and nearly reported it.** The first guided pilot
  changed two variables at once - it added CPP's guidance AND swapped to a task that
  does not forbid extra files. The guided runs behaved differently from baseline, three
  times out of three, and the obvious reading was that the guidance changed the agent's
  design choice. Running the third cell (no prohibition, no guidance) showed it is
  indistinguishable from guided: the file prohibition was doing all the work. A
  difference between two cells says they differ, never why.
- **The guided variant fed the agent contradictory inputs.** Its workspace received
  `task.md`, which forbids extra files, while its prompt used `task-open.md`, which does
  not. The workspace now carries the same task the prompt used. This was live for the
  first three guided runs, which is a second reason the first comparison could not have
  supported a conclusion.
- **A fixture the whole bundle depends on was never committed.** `.gitignore:54 *.json`
  matches `tests/fixtures/delivery_pilots/completion/cases.json`, so `git add -A` skipped
  it in silence and every local run worked because the file sat in my working tree.
  Criterion 8 was broken in a clean checkout while the local evidence looked complete.
  Force-added, then verified by exporting ONLY the tracked tree into an empty directory.
  Caught by the orchestrator, not by me or by any gate I had run.
- **`--commit` pinned less than the report claimed.** The guidance and the scripts came
  from a reviewed commit; the fixtures were read from the working tree the whole time.
  Both suites now materialise their inputs with `git archive` and record the input
  tree's hash.
- **The pinning fix was incomplete, and the metadata still claimed otherwise.** After
  moving the spec, tasks and scripts onto `git archive`, the case wording was still
  read from the working tree - so an uncommitted edit reached a prompt built from a
  named commit while `commit` and `fixtures_tree` in the results file went on naming
  that commit. Review proved it with a sentinel; I reproduced it before fixing it, and
  the sentinel is now kept as a regression test. A pin is only as strong as its weakest
  input, and "I pinned it" was true of four inputs out of five.
- **`git reset --hard` took a new file with it.** Undoing a mutation commit deleted the
  regression test I had written inside it, because the file was new to that commit. I
  had snapshotted the script I was mutating but not the file I had just created;
  recovered from the reflog. Snapshot what you are about to lose, not only what you are
  about to change.
- **My wait loops could never exit.** `pgrep -f "make verify"` matches its own command
  line, so three monitor shells matched each other and outlived the build they were
  waiting on. The harness task result is the authority; process text is not.
- **The full gate caught what targeted linting missed.** `make verify` went red on
  a dead variable in `tests/test_codex_skill_sync.py`, shipped in the criterion 7
  commit. The worker had run `ruff` only over the files edited in the most recent
  step, so an earlier commit's defect was never in scope. Reading the line to fix
  it surfaced a second, latent problem beside it: the bundled document's source was
  resolved by counting a fixed number of parent directories, which happens to be
  right for `docs/agents/x.md` and would silently resolve a top-level `docs/x.md`
  to the wrong file rather than failing. Both fixed; the byte-identity assertion was
  then mutation-checked to confirm it is not vacuous.
- The same run is a reminder that `make verify | tail` reports a RED pipeline as
  exit 0, because the pipe discards the verdict. The failure was visible only in the
  text.
- **Naming two fixtures the same thing broke the typecheck gate.** Each pilot carried
  a `check.py`, which mypy reads as two modules with one name; `make verify` exited 2
  on it after the whole 3040-test suite had passed. The repo already excludes
  `codex/skills` for exactly this collision, so excluding the fixture tree was the
  available precedent - but only the check scripts actually collided, so they were
  renamed instead and the gate kept its coverage. It immediately earned that: with the
  runner now in scope, mypy found a second binding of `results` shadowing the first.

### The criterion 7 fix collided with a governance gate

`make verify` reached `claude-md-behavior-check` and failed with 11 findings, all
caused by the doc bundling: six copies of the canonical lifecycle policy, and five
bundled contracts carrying its pointer. The check was right. It treats every markdown
file below `codex/skills` as authored policy, and the policy half has no allowlist at
all, because the rule is that the policy lives in `docs/` and nowhere else.

This was not a false positive to suppress. The available moves were to stop bundling
the policy and leave the installed contract's dependency unreadable, or to exclude the
generated tree and weaken the gate. Both were put to the orchestrator, since the
checker sits outside this issue's lane; the ruling took neither and approved a
VERIFIED generated-copy allowance instead.

A copy under `codex/skills/<skill>/docs/` is treated as DISTRIBUTION of a canonical
document only when three things hold: the enclosing skill CARRIES THE GENERATED MARKER,
decided by the bundler's own `is_managed` imported rather than restated; the canonical
source exists; and the bytes match. Nothing is exempt for looking generated.

**That first leg is a marker check, not proof of generation history.** `is_managed`
reads a marker, and a marker can be written by hand. The boundary is the composition:
byte identity is what carries the weight, since an edited copy is reported however it
is marked, and whether the generated output is actually present and current is owned
by the separate packaging checks - the `make codex-skills` drift gate and the
bundled-docs byte-identity test - not by the locality checker.

Proven from both sides, because an allowance that cannot reject is just an exclusion:

| Case | Result |
|---|---|
| the shipped copies, against the real tree | recognised as distribution |
| a copy with one line appended | still reported |
| a copy in a hand-curated skill | still reported |
| a copy whose canonical source is gone | still reported |
| the bundler unavailable, so nothing can be verified | fails closed, still reported |
| policy pasted into a generated command body | still reported |

And mutation-checked in both directions: an allowance that never allows fails the two
positive tests, and one that never rejects fails six negative tests plus a pre-existing
locality test - so the older guard is still load-bearing too.

## Observed zero versus unmeasured

This distinction is where a report like this usually overreaches.

- **Approval interruptions inside the pilots are UNMEASURED, not observed zero.**
  `codex exec` is non-interactive: the agent cannot ask for approval, so its not
  asking is a property of the harness. What IS observed is narrower and still worth
  something: neither pilot added a file it was not asked for, and neither account
  requested confirmation before acting.
- **Approval interruptions in the wave ARE observed** - the two in the ledger above,
  from the wave's own message log.
- **No claim is made about creativity.** Two pilots, three runs of one of them, one
  model at one reasoning effort, fixtures written by the implementer. Phrase-presence
  tests establish nothing about behaviour and are not used for any conclusion here.
- **Data-handoff tests are not model decisions.** Criterion 1 establishes that bytes
  survive the journey between processes. It says nothing about whether an agent reads
  what arrives, and the module docstring says so.
- **Bounded implementer fixtures are not a whole-host lifecycle evaluation.** The
  #859 baseline exercised the delegated Codex prompt payload only. It did not
  exercise the host lifecycle and proves nothing about the Qwen or Gemma drivers.
- **A stated procedure is not a repaired behaviour.** Several entries above are
  worker acknowledgements of error. None of them is evidence that the error will not
  recur; only the encoded checks are.

## Reproducing this

Everything needed is in the repository. The evidence bundles under `~/Downloads/`
hold bulky transcripts only; no claim here rests on a path that exists on one machine.

```bash
# Criterion 1 - deterministic, no model required
uv run --extra dev pytest tests/test_speckit_handoff_integration.py -q

# Criteria 2 and 3 - observed completion decisions
scripts/run-delivery-pilots.py --suite completion --out /tmp/completion
scripts/run-delivery-pilots.py --suite completion --out /tmp/completion --dry-run  # prompts only

# Criteria 4 and 5 - bounded implementation pilots
scripts/run-delivery-pilots.py --suite pilots --out /tmp/pilots
```

The runner reads its guidance and its input-building scripts from a reviewed commit
(`--commit`, default `HEAD`), records the effective model and reasoning effort beside
every result, and records process status and output size on every run - an empty
output scores as "no `Closes`", which reads exactly like a correct `Refs` result.

### The reused baselines, and their limits

| Bundle | What it is | Limit to preserve |
|---|---|---|
| `~/Downloads/cpp-859-decision-cases/` | 6 direct Codex prompt/execution samples | one model, one runtime, implementer-authored fixtures; prompt payload only, never the host lifecycle. Return codes ARE recorded |
| `~/Downloads/cpp-860-report-cases/` | 5 supplied-fact report decisions plus the real-guard harness | its runner did not capture process return codes; that gap stays explicit and is NOT the same limit as #859's |
| `~/Downloads/cpp-861-completion-cases/` | this issue's 3 completion decisions | supplied facts, one model; the bundle holds ONE run |
| `~/Downloads/cpp-861-pilots/` | pilot `baseline` cell | the bundle holds ONE run |
| `~/Downloads/cpp-861-pilots-guided/` | pilot `guided` cell | the bundle holds ONE run |

**Provenance of the retained small-fix trace.** It executed at commit
`d115bd8b66eaba9b3ecf8f8d88af0c718cb23bb3`, a working commit that was later squashed
and is NOT reachable from the published branch. That is the commit it ran at and the
record says so; it is not relabelled as having run somewhere else.

For reproduction, what matters is not a particular commit but whether the two inputs
a guided pilot actually reads are the same bytes. Verified by object hash rather
than asserted:

| Input | at `d115bd8` | at the published head |
|---|---|---|
| `tests/fixtures/delivery_pilots/pilots` (tree) | `0b478ec80661` | `0b478ec80661` |
| `.claude/commands/codex/auto.md` (blob) | `ae6c73a3b640` | `ae6c73a3b640` |

`067477e1fcb08d68da43a42e3b7c1d00696f1004` on this branch is a verified example, and
any commit carrying those two hashes reproduces the same prompt. Check with
`git rev-parse <commit>:<path>` rather than trusting this paragraph to stay current.

So the run is reproducible from a published commit, and the observed commit remains
recorded as what actually produced the trace. Those are two different statements and
the bundle keeps both.

**Retained evidence versus runs performed.** Each re-run replaces its output
directory, so a bundle always holds exactly one run - the last. The counts in this
report (4 baseline, 3 open, 3 guided, and the completion cases) are observations made
during development and recorded here; they are not four, three and three retained
transcripts. Anyone re-checking a count should re-run the cell rather than look for
directories that do not exist. The `open` cell has no retained bundle at all; it was
run to separate two variables and its result is the table above.

Both older runners were repaired under this issue: each read its prompt source from a
worktree that has since been deleted, so the bundle documented a run nobody could
repeat. They now read from a reviewed commit via `git show`, with `--repo` and
`--commit` overrides. The #859 `results.json` also pointed its `output` fields at a
deleted session scratchpad and now names the transcripts beside it.

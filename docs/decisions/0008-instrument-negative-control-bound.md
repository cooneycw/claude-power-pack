# ADR 0008: What an instrument is, and when it needs a negative control

- Status: Accepted
- Date: 2026-09-14
- Issue: #932
- Supersedes: nothing
- Related: #924 (the executable negative-control machinery; it scopes itself
  to "gates" and could not define the word until this landed), #933 (its first
  consumer), #934 (the counter-model stage; produces ADR 0007, which is
  reserved for it and lands after this one - the numbering gap is deliberate),
  #936 (ADR 0009, the oscillation rule), #834 / [the detector
  contracts](../agents/detector-contracts.md) (the two questions asked of any
  instrument in a diff), [the glossary](../agents/glossary.md) (the defined
  terms this ADR attaches the bound to). Provenance:
  `docs/research/harness-strategy-recommendation-2026-09-14.html` section 04
  and the adoption plan `instruments-and-counter-model-adoption-2026-09-14`
  sections 01-02.

## TL;DR

**An instrument needs a committed negative control when its verdict is
consumed by a decision that will not independently re-derive the fact.** A
unit test the surrounding suite would catch does not; a gate that lets work
through does; a check whose green is read by another session or another repo
always does.

Enumerated against this tree on 2026-09-14, the bound captures
**61 distinct verdict contracts** - order tens, not thousands - which is
below the rejection threshold the issue set ("if the count lands in the
hundreds rather than the tens, the bound is wrong"). The count measures table
membership, not the effort of writing and maintaining the controls; that cost
is not measured here. The 2,408 test functions are excluded individually and
the suite is counted once. This narrows an existing directive; it adds no
tier, no process document and no checker.

## Context

The Negative Control directive in the host's global `~/.claude/CLAUDE.md`
(added 2026-09-13, the same day #924 was filed) defines an instrument as
"anything whose output is read as evidence" and requires that every one ship
with a committed input that makes it report the other verdict. The rule is
correct. Its scope is unbounded: taken literally it covers every one of 2,408
test functions in 102 files, 62 scripts, the nine `make verify` sub-gates,
seven CI steps, and every probe in every wave helper.

Nobody has that much time. What happens to an unaffordable rule is not that it
gets debated - it gets applied to whatever is in front of you and skipped
everywhere else, which produces exactly the condition the rule exists to
prevent: a population of instruments where some have controls and some do not,
and no way to tell which from the outside.

#924 sensed this and scoped itself to "gates", undefined, with seven named
consumers that are the seven that happened to fail recently - a list that
narrows rather than a rule that generalises. Its machinery cannot bound itself
until the word is defined and the rule has a denominator.

Two constraints shaped this decision and are recorded so they survive it:

- **Narrow, do not layer.** The 2026-09-14 issue-quality assessment concluded
  "adopt the proportional issue contracts already delivered rather than
  building another governance layer." If this document ever grows a tier
  system or a review process, it has gone wrong.
- **The enumeration comes first.** The bound was proposed untested ("I have not
  enumerated the instruments it captures. If the real count comes out in the
  hundreds rather than the tens, the rule needs another narrowing"). An
  enumeration that returns a number in the hundreds is the result the issue
  named as falsifying the bound, so it is the first acceptance item and the
  body of this document.

## Decision

### The bound

> An instrument needs a committed negative control when its verdict is
> consumed by a decision that will not independently re-derive the fact.

"Committed negative control" means a case checked into the repository - an
input and the verdict it must produce - that fails when the instrument stops
discriminating. "Will not independently re-derive" is the whole test: if the
consumer of a verdict re-establishes the fact itself before acting, the
instrument's green is not load-bearing and a blind instrument there costs
nothing but time. Re-deriving means establishing the *same fact*; a later
step that catches a different consequence of the same error (a merge conflict
after a missed file-overlap warning) is a backstop, not a re-derivation, and
does not exclude the earlier instrument.

### Necessary, and not sufficient (#970)

> A committed negative control is **necessary and not sufficient**. A battery's
> soundness is established by **mutation** - break each protection in turn and
> require some control to fail - and never by inspection.

The bound above says WHICH instruments need a committed control. It does not say
that having one makes a battery sound, and the difference is not a nuance.

An instrument is not one decision. It is a STACK of protections, and a single
end-to-end case only travels whichever path its own input happens to take. Every
OTHER protection can be deleted with the battery still green.

Demonstrated in wave `cpp-completion` on 2026-09-15. A battery of nine controls
was committed with a reachability sweep in #955, including a RED that genuinely
failed on the unfixed code and a GREEN positive control. The orchestrator read the
battery at the plan gate, judged the set correct, and explicitly called the
positive control load-bearing. A second model then disabled comment rejection,
command-position matching, hook detection and transitive scanning, one protection
at a time. **All nine controls kept passing, exit 0 every time.**

**Inspection structurally cannot catch this, and that is a fact about gates rather
than a criticism of any ruling.** A battery that survives its own protections being
removed and one with full coverage produce identical output and look identical on
the page. Reading is the only method a review gate has. So a clearance that rested
on "it has a committed negative control" established that the control exists, never
that the battery covers the instrument - and every clearance given on that basis is
in the same position, including the ones given by whoever is reading this.

**What follows from that, and what does not.** The requirement is on the AUTHOR of
an instrument the bound captures, at the point the battery is written: name the
protections, break each one, and record which control failed. It is not a new
review gate, not a tier, and not a per-run cost - mutation is paid once per
instrument, not once per run, so #952's per-run rejection criterion does not bite.
What #970 measured about affordability is in
[the re-examination](../research/battery-mutation-re-examination-2026-09-20.md);
it is not assumed here.

`scripts/mutation-probe.py` makes this a command rather than an exhortation.
Declarations live in the battery's own `control.json`, and a protection whose
control genuinely cannot be written is recorded as `expect: "uncaught"` with a
written reason - a STATED gap rather than a hidden one - which reverts to a red
the moment a control does reach it. `make mutation-probe` and the CI step of the
same name run it; `docs/scripts.md` holds the contract.

**The re-examination this produced, and what it found.** Four merged batteries had
never been mutation-tested, which #955's own author raised against their own work:
*"my #957 control pair should be held to the same standard, and it has not been."*
Of the enumerated protections actually probed, **#960's shellcheck battery
exercised 2 of 12**, **#955's sweep 3 of 5 despite its own self-test reporting 5 of
5**, and **#953's prototype 4 of 7**. None of those numbers was obtainable by
reading, and none of the authors was wrong about anything they claimed.

### The carve-out

A unit test whose failure would be caught by the next test in the same file
does not need one. Its green is not individually load-bearing; the suite's is.
Whether the suite as a whole discriminates is a mutation-testing question, and
answering it per test would spend the entire budget on the population least
likely to be blind. The suite is counted as ONE instrument below, because its
exit code is what the finish gate consumes.

### The carve-out does not cover a derived population (issue #1492)

The carve-out does not cover a test that DERIVES its own input population
from the repository tree (globbing files, enumerating scripts or controls,
parsing a manifest it did not construct). Such a test must assert that its
population is non-empty, with an assertion message naming what it
enumerated, OR carry a committed negative control. The non-empty assertion
is the default: it costs one line and turns the vacuous pass into a failure.
A committed control is required only where non-empty is not enough, i.e.
where a populated but wrongly-extracted set would also pass.

The carve-out's premise is that the surrounding suite catches a unit test's
failure. A test over an empty derived population cannot fail at all, so
there is no failure for the suite to catch. The bound's own logic, not a new
principle, removes the carve-out for that case. (A sweep of the existing
suite for tests needing this is tracked separately, #1518 - this amendment
states the rule; it does not itself fix every instance.)

### The escalation

A check whose green is read by a **different session or a different repo**
always needs one, because the consumer cannot see the conditions that produced
it. A wave orchestrator reading a worker's `FLOW_WAVE: registered`, kyle
running CPP's finish gate, codex-power-pack inheriting a drift check through
the source bridge - none of them can tell a green produced by a working
instrument from one produced by a blind instrument, and none of them will
re-derive it. This is the case #924 already makes about blind CPP gates passing
bad work in the other two repositories.

### What this does not change

- **The regression-test rule is untouched.** "A regression test must FAIL on
  the code before the fix" costs one run on the pre-fix tree, not a committed
  case. The carve-out relaxes which instruments need a *committed* control; it
  does not relax the obligation to run a new test red once and say so.
- **"Outside the bound" does not mean "may be blind".** It means the proof
  that it is not blind belongs to the suite, not to a per-instrument case.
- **`spec` is not renamed and `harness` is not overloaded silently.** The
  glossary owns both points; the ledger's `harness` tag (#557) keeps its
  meaning.
- **The detector contracts still apply to every instrument**, captured or not.
  Membership floor and ownership boundary are review questions about a claim;
  the bound is about which claims get a committed case.

## The enumeration

The enumeration itself - the universe it was derived from, the captured rows,
the exclusions with their reasons, and the retired rows - lives in
[`controls/census.md`](../../controls/census.md), beside the registered controls
it is the denominator for (issue #1671). It was moved there verbatim, with every
row number unchanged, so that adding or changing an instrument edits data and
not this decision. A citation of "row N" in this document means row N of that
file, and "Universe and derivation", "Captured", "Excluded" and "Retired" name
its sections.

This document keeps what is decided: the bound above, and the two rules below
that say what a registered control must satisfy. `make instrument-census-check`
still derives the census's membership from `scripts/`, so a new instrument
cannot arrive unenumerated; it now reads the census file.

### A control must be valid WHERE THE HARNESS RUNS (#960, #964)

A control is not a file; it is a thing that executes. So its dependencies have to
be satisfied **in the environment the harness runs in**, not merely in the
environment its own subject runs in. `check-negative-controls.py` deliberately
refuses a SKIP concept - a registration it cannot exercise reports `UNRESOLVED`
or `UNSIGNALLED` and fails, rather than passing quietly - so an unsatisfiable
dependency is a red, and correctly so.

**Dependency means environment, not just image.** All of these are dependencies,
and each can be present on the author's machine and absent where the verdict is
consumed:

- a **binary** the gate shells out to (#960: the negative-controls step runs in
  the `uv` image, which has no `shellcheck`, so the control reported
  `UNSIGNALLED` while the author's box passed with the tool on `PATH` from a
  scratch directory);
- a **tracked file** the control reads (#964: a control was green locally and
  BLIND in a clean clone, because its nested manifests fell outside a
  one-level-deep `.gitignore` negation and were never committed);
- a **tool the gate itself needs to enumerate**, such as `git`, which is absent
  from the CI image by design.

Two independent derivations reached this within an hour, from different tickets
and different mechanisms, neither aware of the other. That is the reason it is a
clause here rather than a note in a CI file: the common factor is not the image
or the gitignore, it is that **the control was verified somewhere other than
where it gates.**

Practical consequences:

- Enumerate every registered control's dependencies against **each** image that
  runs the harness. In this repo that is more than one step: the dedicated
  negative-controls step AND `validate`, whose pytest suite drives the whole
  register.
- Where a tool must be shared across steps, stage **one pinned copy** rather than
  installing per-step. `apt` in the `uv` image supplies shellcheck 0.9.0 against
  the 0.10.0 pinned for the gate, and one gate running under two linters makes
  the control's verdict depend on which container reached it.
- A local green says the control works **here**. Only a run in the harness's own
  environment says it works where its verdict is read.

### Adopting a third-party linter as an instrument (#960, and the pattern #961/#962 inherit)

`shellcheck` was the first standard tool adopted under this ADR. The shape it
settled, stated here because `pip-audit` (#961) and `bandit` (#962) are the same
ticket with a different binary:

- **Derive the file population; never glob it.** `git ls-files '*.sh'` misses
  `scripts/cpp-memory`, a tracked bash script with no suffix, and a tracked-only
  list misses untracked files entirely. Filter on extension OR content, and
  report which derivation ran.
- **Print the denominator on every run, including the clean one.** `0 findings`
  is only meaningful beside `N examined`. A zero-file scan is `UNKNOWN`.
- **A missing binary is `UNKNOWN` and exits non-zero, never a pass.** The
  tempting `command -v <tool> || exit 0` goes green on every machine that lacks
  the tool, which is the dormant-instrument failure this ADR exists to prevent.
- **Suppressions are visible or they do not happen.** Adopt at a severity the
  tree can actually hold, and record the findings below that severity as a
  counted residual with a filed issue. A disabled check is invisible; an issue
  is not. `shellcheck` shipped with **zero** suppressions and no `.shellcheckrc`
  at all - the day one is needed, the file appears with the reason in the same
  commit.
- **The residual closes by raising the severity, not by annotating around it.**
  #972 did this for `shellcheck`: 139 source findings below `error` were each
  fixed or suppressed ON ITS OWN LINE with its reason (still no `.shellcheckrc`,
  still no file-wide disable), and the gate's default moved from `error` to
  `style`. The largest class was not what the ticket predicted - 65 of the 68
  "unreachable" findings were one function with no caller since #505, deleted
  rather than suppressed. A raised severity needs its own BAD case, because every
  pre-existing case offended at `error` and so could not tell the new default
  from the old one: `controls/shellcheck-gate/cases/bad-note-severity` reports
  BLIND when the default is reverted. *What would move this back (ADR 0009):*
  repeated churn from note-level findings that are suppressed rather than fixed.
  The step back is to `warning`, never to `error`, which re-opens an unreviewed
  residual.
- **An anchor for a BRAND NEW gate cannot be historical on main, and that is
  accepted rather than worked around.** A control for a pre-existing gate anchors
  to a real commit in main's history (row 1's `c6df826` does). A gate introduced
  by its own PR has no such ancestor: its anchor commit lives on the branch, and
  squash-merging orphans it, so `--verify-provenance` will read `unverified`
  permanently. This costs nothing operationally - the operative check is the
  sha256 of the vendored anchor, which is git-independent, and CI deliberately
  runs `--strict` WITHOUT `--verify-provenance` because git is not in the CI
  image. What it costs is the distinction: `unverified` then means "unresolvable
  anywhere, forever" rather than the ordinary "git is absent here", and nothing
  in the output separates those two causes. Record the terminal cause in the
  anchor entry so a reader chasing it does not hunt for an object that was never
  going to exist. **Integrity is established; historicity is not.**
  - *What would move this back (#936):* if provenance ever becomes CI-checked, or
    an audit needs to establish historicity rather than integrity, then landing
    the naive implementation as its own merged PR and anchoring to ITS squash
    commit becomes correct, and this ruling should be revisited. Named here so
    #961 and #962 inherit the decision rather than re-litigating it.
  - *Taken up by #962, and worth recording because the anchor stopped being a
    construction:* bandit's blind implementation is codex-power-pack's live
    one-liner, vendored verbatim, so the control's demonstration IS the issue's
    thesis rather than an illustration of it. `kind: constructed` still, because
    the artifact has no commit in THIS repository's history - but "constructed"
    should not be read as "invented".

#### What #962 settled that #960 and #961 did not: the SHAPE of a suppression

`shellcheck` adopted with **zero** suppressions and #961 with a per-finding
ledger, so neither had to answer what to do with an inherited one. #962 did, and
the answer generalises past bandit:

- **A `--skip` is not a short allowlist, it is a different instrument.** It
  turns a rule off across the whole population, forever, and has no direction in
  which it can go stale. Measured: codex-power-pack's `--skip
  B104,B108,B310,B602` removes **10 of CPP's 11** MEDIUM+ findings, because the
  two rules it suppresses most are the two this tree's design produces most.
- **So the residual is recorded per (file, rule, COUNT).** That makes three
  distinctions a blanket skip cannot draw into reds: a new site in a file that
  already has one, a new site in a fresh file, and a recorded site that gets
  FIXED and leaves its line behind.
- **Adopting a neighbour's configuration is inheriting their evidence.** The
  skip list was correct about codex-power-pack's tree, and nobody measured it
  against this one. The precedent the issue cited is CPP's own four disabled
  mypy error codes, load-bearing in two repositories because the same move was
  made once and never re-derived.
- **Enforce the decision, do not merely document it.** A skip reaching the tool
  by any route, and an inline `# nosec`, are both findings - read off
  `metrics._totals.skipped_tests` and `metrics.<file>.nosec`. A decision nothing
  checks lasts until the next person edits a Makefile.
- **Excluding a fixture DIRECTORY is not suppressing a check.** The gate skips
  `controls/*/cases/**` (deliberately-bad inputs, still linted by the control
  itself with `--root`) and `controls/*/anchors/**` (frozen byte-identical
  historical copies whose sha256 is the provenance - editing one to satisfy a
  linter destroys what the control rests on).

### What the count says

61 distinct verdict contracts against a universe of thousands. That is
"tens" by the issue's own threshold, so the bound is not falsified by this
tree and stands. What the number does NOT say, stated so it is not read as
more: it is a count of rows, not a measure of the effort to write, keep and
re-confirm 61 controls, and "affordable" in that sense is unmeasured. It is
at the upper end of tens, and three things about it are worth stating rather
than leaving to be inferred:

- **The lifecycle helpers are the bulk (rows 1-25).** Twenty-five of the 61
  are flow, wave and session helpers, and twelve of those are
  cross-session by construction. That is where the escalation clause bites
  hardest and where #924's seven consumers all sit.
- **Nine are library entry points other repos consume (rows 53-61).**
  They are captured by the escalation clause alone: CPP cannot see kyle's
  deploy verification run, so kyle cannot see whether CPP's verdict was blind.
- **Thirteen of 102 test files carry explicit control language today**
  (`negative control`, `positive control`, `can_fire`, `known-bad`, `red
  case`) - a fact about vocabulary, not about discrimination, and stated only
  so the register #924 builds has a starting point. Which of the 61 have a
  registered, reverted-and-reconfirmed control is #924's denominator to fill,
  not this document's.

The enumeration is a dated snapshot. It is not maintained here: #924's register
is the living list, and a new instrument is added there, next to its control,
not to the census table. The enumeration is also the falsifier the issue named for
this decision, not a committed negative control in the directive's sense: no
case demonstrates that it would detect an omitted instrument, and the Step-5
review found seven omissions and mis-attributions in its first version, and
three more on its second pass. The count above is the corrected one.

## The directive edit

The Negative Control section of the host's global `~/.claude/CLAUDE.md` is
host-managed and outside this repository, so the edit cannot travel in a pull
request. It is quoted here so it is auditable. The first paragraph (the
definition) and the last five bullets are unchanged; the following block is
inserted after the definition, and the first bullet's opening changes from
"Before you ship an instrument" to "Before you ship an instrument the bound
captures":

```
The committed-case requirement is BOUNDED (claude-power-pack ADR 0008): an
instrument needs a committed negative control when its verdict is consumed by
a decision that will not independently re-derive the fact.

- A unit test whose failure the surrounding suite would catch does not need
  one; its green is not individually load-bearing, the suite's is. The
  regression-test rule below is unchanged: its red run costs one execution on
  the pre-fix code, not a committed case.
- A gate that lets work THROUGH (a finish gate, a preflight, a drift check,
  `make verify` itself) does need one; nothing downstream re-derives it.
- A check whose green is read by a different session or a different repo
  ALWAYS needs one; the reader cannot see what produced it.
```

Two known limits of that edit, recorded rather than solved here: it reaches
only this host, and kyle session containers do not mount `~/.claude/CLAUDE.md`
at all (kyle#1176), so a containerised session builds instruments under a rule
it cannot read until that mount lands.

**#970's amendment to that block is PROPOSED here and NOT applied.** The same
host-managed file is outside this repository, and a change to it takes effect for
every project on the machine rather than for this one, so it is the owner's edit
to make. Quoted so it is auditable and so the decision is not lost if it is
declined - the block gains one bullet, after the three above:

```
- A committed control is NECESSARY and NOT SUFFICIENT. An instrument is a stack
  of protections and one end-to-end case travels only its own path, so the rest
  can be deleted with the battery still green. Establish a battery by MUTATION -
  break each protection in turn, require some control to fail - never by reading
  it. A protection whose control cannot be written is recorded as a stated gap,
  not left silent.
```

Until it is applied, the rule reaches instruments built in this repository -
where this ADR, `docs/scripts.md`, `make mutation-probe` and the CI step all
state it - and does not reach instruments built elsewhere on this host.

## Consequences

- `instrument`, `harness` and `counter-model` are defined terms
  ([glossary](../agents/glossary.md)); issues and ADRs use them rather than
  "gate", "check" or "the tooling" when the distinction matters.
- #924 can scope itself: "every instrument the bound captures" replaces "the
  seven that failed recently", and the register it builds has a denominator
  of 61 to start from.
- Adding an instrument the bound captures means adding its committed control
  in the same change. Adding a unit test does not.
- No new check enforces this document. A checker for "is this verdict
  consumed without re-derivation" would be an instance of the pattern the
  detector contracts describe - a mechanical answer to a question about the
  relationship between a message and its consumer. The decision is held to
  account by the enumeration's rejection criterion (hundreds) and by #924's
  register, which will show, instrument by instrument, whether the bound's
  members actually get controls.

## What this does not solve

- **It does not register any control.** 61 instruments are named; how many
  of them have a control today is not measured here. That is #924's job, one
  instrument at a time, starting with #933.
- **It does not make the suite discriminate.** The carve-out moves the
  question to mutation testing, and #970 answers it only for a battery that
  declares its protections - `mutation-probe` asks whether a DECLARED protection
  is exercised, never whether the declaration is complete, and it says so in its
  own summary line. Whether the 2,408-function suite discriminates remains
  unmeasured.
- **It does not reach the other repos' instruments.** kyle's fleet checks and
  health probes (kyle#1209) and codex-power-pack's adoption (CxPP#240) apply
  the same bound to their own trees; this enumeration is CPP's only.
- **It does not carry the directive into containers** (kyle#1176).

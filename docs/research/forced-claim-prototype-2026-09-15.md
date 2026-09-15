# The forced claim: what a run prints, and what checks it

Prototype for [issue #953](https://github.com/cooneycw/claude-power-pack/issues/953).
Part of the [#950](https://github.com/cooneycw/claude-power-pack/issues/950) wayfinder map.

Asset: [`forced-claim-prototype-2026-09-15/`](forced-claim-prototype-2026-09-15/)
- [`forced-claim-check.py`](forced-claim-prototype-2026-09-15/forced-claim-check.py) - the runnable checker
- [`control.json`](forced-claim-prototype-2026-09-15/control.json) - the seventeen registered cases
- [`cases/`](forced-claim-prototype-2026-09-15/cases/) - the committed fixtures

Written against `origin/main` at `0a980314aa96`, wave `cpp-completion`.

---

## LIMITS - read before citing anything below

This is a **design with a runnable demonstration**, not a shipped gate. Stating
the bound first, because everything after it is worth less if the bound is
discovered late:

1. **Nothing in the tree invokes this checker.** No `.woodpecker.yml` step, no
   `make` target, no command document. The pipeline anchor in
   [Marker to receipt](#marker-to-receipt-the-three-levels) is **specified here
   and deliberately not written** - that is implementation and belongs to its own
   issue with its own lane.
2. **Its registration is not discovered by the real harness.**
   `scripts/check-negative-controls.py` scans `controls/`; this manifest lives
   under `docs/research/`. It is written in `control.json`'s shape so adoption
   is a move rather than a rewrite, and it is executed by the prototype's own
   `--selftest`. It is **not** covered by the `negative-controls` CI step.
3. **Tiers 2 and 3 are demonstrated on fixtures, never measured on a live flow
   run.** Every verdict below was produced against the committed cases. No
   claim here rests on a real `/flow:auto_codex` run, because wiring one is
   out of lane.
4. **The anchor is JSONL - one record per line.** A pretty-printed multi-line
   claim will not match a record, and `_project_modules` scans the tree root
   plus `src/` and `lib/` by convention rather than reading the project's
   configured package roots. Both are known narrowings, not oversights.
5. **The design was wrong in thirteen places until a second model read it.** All
   All thirteen are fixed and fixtured, and they are listed in
   [What the cross-model review found](#what-the-cross-model-review-found).
   The relevant limit for a reader is that this prototype's correctness rests
   on two review passes by one model, not on use.
6. **One sub-claim is untested by construction**: that the "filed once"
   ordering rule holds inside a real driver. The prototype can count
   amendments given a record; it cannot enforce when the claim is written
   relative to when the check runs.

---

## The one idea

Every line of the end-of-run block is a **claim**, an **observation made by
something other than the claimant**, and a **verdict that is a comparison of
the two**.

That is one mechanism, not two, and collapsing them was the ticket's explicit
instruction:

- **#956** forces an *agent* to state a checkable claim ("I added 3 tests,
  named X, Y, Z") instead of grading itself.
- **#952** forces an *instrument* to state its denominator ("scanned 96 files")
  instead of printing a bare green.

A denominator **is** a forced claim - #956's principle pointed at a script
instead of at an agent. So there is one convention, applied to both, and the
prototype has one code path for both.

The distinction that makes it work is the ticket's own:

| | |
|---|---|
| "Rate your tests 1-10" | cannot fail. The thing producing the rating is the thing that wrote the tests. Not evidence. |
| "State how many tests you added and name them" | checkable against the diff by a machine. An inflated number is caught by counting, not by honesty. |

**No step anywhere in this design has an agent assessing the quality of its own
work.** Tier 3 records *who reviewed*, never *how good it was*.

---

## The verdict enumeration - four, and the rule that keeps it four

The gate raised this: the first submission listed four verdicts and then used a
fifth (`UNSIGNALLED`) in the controls. A state that is used but never
enumerated is how the next person silently drops one.

| Verdict | Meaning | Clean? |
|---|---|---|
| `VERIFIED` | claim present, observation agrees | **the only clean state** |
| `DISAGREE` | claim present, observation contradicts it | no |
| `ABSENT` | the checker ran and the claimant filed no claim | no |
| `UNKNOWN` | no interpretable observation could be made | no |

Every non-`VERIFIED` verdict carries a **mandatory reason**. The rule that
decides whether a new state is a verdict or a reason:

> **Different conclusion -> a new verdict. Same conclusion, different cause ->
> a reason on an existing verdict.**

So **`UNSIGNALLED` is a reason on `UNKNOWN`**, not a fifth verdict and not a
`DISAGREE`. It licenses the same conclusion as any other `UNKNOWN` - *you may
not conclude; go fix the instrument* - and it is not a contradiction between
two known values, so filing it under `DISAGREE` would send a reader off to
compare numbers when the actual problem is a broken test run.

`ABSENT` stays separate from `UNKNOWN` under the same rule, and this is the
load-bearing case: they license **different actions**. `ABSENT` means the agent
was silent (make it file; tier 2 is disabled). `UNKNOWN` means the check could
not conclude (fix the check). Merging them rebuilds exactly the ambiguity
#951 and #952 each exist to remove.

Reasons currently in use: `inflated`, `under`, `no-match`,
`no-discrimination`, `no-claim`, `no-denominator`, `unsignalled`,
`empty-population`, `match-not-lit`, `import-escape`, `no-runner`,
`unanchored`, `anchor-incomplete`, `claim-unreadable`.

### Exit codes - three, because two cannot say "not established"

```
0   VERIFIED             the only clean state
1   HARD FAIL            DISAGREE(inflated), DISAGREE(no-match),
                     DISAGREE(no-discrimination)
3   NOT ESTABLISHED      UNKNOWN, ABSENT, or DISAGREE(under)
```

Exit 3 rather than 2 because argparse owns 2. **A caller that treats 3 as a
pass has reintroduced the fail-open this prototype exists to close.**

---

## Marker to receipt: the three levels

[#951's constraint](https://github.com/cooneycw/claude-power-pack/issues/953)
is the sharpest thing said about this ticket, and it is the one that could have
made the whole design worthless. #934's "0 of 200 merged PRs" counted PR bodies
containing the string `Codex pre-PR review`, emitted per a written instruction
at `.claude/commands/flow/auto_codex.md:98`. Nothing enforces or observes it.
So the number measures **absence of a self-reported marker, not absence of
execution** - and "no claim present" is indistinguishable from "the step did
not happen".

A forced claim emitted because a document asked for it, and read back out of a
PR body, reproduces that defect exactly. The fix is not to stop asking for a
claim; it is to move where the *block* comes from.

| Level | Who produces it | Kind |
|---|---|---|
| 1. the claim | the agent, to a known path | **marker** |
| 2. the block | the **checker**, which runs whether or not the agent filed | **receipt** |
| 3. the checker's invocation | `.woodpecker.yml`, tree-visible and log-retained | **anchor** |

Level 2 is the whole move. The agent does not print the block; the checker
does, and a silent agent yields `claim: ABSENT` - an affirmative observation
that the checker ran and found nothing filed.

**That gives #934 the discriminator it lacked:**

- block **missing entirely** -> the step did not run
- block **present, saying ABSENT** -> the step ran and the agent was silent

Two states that used to be one.

Level 3 is where the regress terminates, and it terminates *pragmatically*
rather than absolutely. `.woodpecker.yml` can be edited - but that is a
reviewable diff, which is a different class of thing from an unobserved
instruction inside a command document. The relevant measurement is already on
record: #954 found that two trees differing only in whether `.woodpecker.yml`
carries a gate's step produce byte-identical coverage, which is what makes the
CI step, rather than the test suite, the thing worth anchoring to.

### The anchor, specified and not written

Per the gate's fifth condition this is a **specification**. `.woodpecker.yml`
is not edited by this issue.

```yaml
  forced-claim:
    image: *python_image
    commands:
      # Exit 3 is NOT a pass. A caller that collapses it into success has
      # reintroduced the fail-open; see the exit-code table above.
      - python3 scripts/forced-claim-check.py --repo . --base "$CI_COMMIT_BEFORE"
```

---

## The three tiers (#956), each carrying its denominator (#952)

### Tier 1 - the claim. Mechanical, free, no model required.

Stated: how many tests were added, and their node ids. Observed: the test
functions present in the head tree and absent from the base tree.

**The counting rule is published**, which is not decoration - a `DISAGREE` has
to be about facts rather than about guessing the parser, or it is unactionable
and people learn to route around it:

> A test is a module-level or class-level `def`/`async def` whose name begins
> `test_`, in a file named `test_*.py`.

Denominator printed on every run: `base=present, N changed file(s), M non-test`.

### Tier 2 - the match test. Scoped **by** the claim.

Each named test is re-run against the **pre-fix tree** (base code + head tests,
the fix deliberately not applied) and must fail there.

This is affordable only because tier 1 named the tests - #956's ruling, and the
reason the two tiers cannot be separated.

**A crash is not a match.** Lifted directly from `check-negative-controls.py`
and issue #963, which had this bug one level up: it decided a case from the
exit code alone, so a gate that *crashed* on the known-bad input scored
identically to one that *reported* it. pytest exits non-zero for an assertion
failure, a collection error, an ImportError and a usage mistake alike. A test
that fails pre-fix by `ImportError` has demonstrated **nothing** about the
defect.

So a match requires a **signal**, not merely a non-zero exit. The signal is the
*cause* in pytest's short summary line, `FAILED <nodeid> - <cause>`: an
assertion reads `assert 1 == 2` or `AssertionError: ...`; anything else names
the exception class that killed the test.

Reading only *"is `FAILED` present"* is **not enough**, and that was this
prototype's own first cut. pytest reports an exception raised **inside the test
body** as `FAILED`, not `ERROR` - only a *collection* failure is an `ERROR` - so
an import that blows up on the function's first line scored as a clean
assertion match. The committed fixture hid it by putting the bad import at
module scope. Found by Codex on review; there is now a fixture for each
position.

**And the tier is two-sided.** Failing before the fix proves nothing on its
own: a test that fails *everywhere* - `assert False` - also fails pre-fix, and a
one-sided check credited it the moment any non-test file changed. So a named
test must **also pass on the fixed tree**. This is the same argument #963 makes
for gates, where the known-good input is what separates a working gate from one
wedged at "fail" - an argument this document quoted while checking one side.
Also found by Codex.

### Proving the match lit, before believing any red-less result

The trap the ticket names: if the pre-fix tree does not actually behave
differently, the test stays green and the run records "verified" having run no
experiment. Three assertions, each producing `UNKNOWN` rather than `VERIFIED`:

| Check | Failure reason |
|---|---|
| the diff changes at least one **non-test** file | `match-not-lit` |
| the named test's imports resolve **inside the tree under test** | `import-escape` |
| an interpreter that can actually run pytest exists | `no-runner` |

`import-escape` is the "installed copy outlives the fix" hazard: a test that
imports from site-packages never exercises the pre-fix tree at all.

### Tier 3 - intent. Counter-model only.

Printed as a **fact**, never a warning and never a grade:

```
counter-model: codex (2 passes)      |      counter-model: absent (intent unreviewed)
```

This is the only thing that degrades for a single-model user, per #956. A
public user must be able to see which assurance they got.

---

## When the claim and the diff disagree

The ticket's hardest part, untouched by either ruling. **Approved as proposed.**

| Direction | Verdict | Action |
|---|---|---|
| claimed > observed | `DISAGREE(inflated)` | **hard fail** (exit 1) |
| claim names a test absent from the diff | `DISAGREE(inflated)` | **hard fail** (exit 1) |
| claimed < observed | `DISAGREE(under)` | record, emit owner item, do not block (exit 3) |

### Under-reporting is measured, not merely tolerated

The gate's second condition, and it sharpened the proposal: as first stated,
under-reporting was *invisible* rather than *non-blocking*. "Add three tests,
name only the strong one" would have passed clean with two unexamined.

So both numbers print on every run - `claimed 1, diff contains 3` - and the
difference becomes the owner item, naming the tests:

> 2 test(s) in this diff were never named and therefore never match-tested:
> `test_b.py::test_two`, `test_c.py::test_three`. Under-reporting is
> non-blocking but it is not invisible.

Under-reporting is **evasion of tier 2**, not imprecision: an unnamed test is
one the match test never sees.

### Two rules without which the asymmetry is defeatable

1. **The claim is filed once, and amendments are counted.** See below - this is
   the design's weakest point and it is not fully closed.
2. **The counting rule is published.** Stated in tier 1.

### What I would not defend

**Symmetric hard-fail on any disagreement.** It reads as the strictest option
and it is the worst one, for two reasons:

- It maximizes the pressure to make the claim *match the counter* rather than
  be accurate. Since the agent can read the checker's output, it can converge
  on a checker-shaped lie.
- It converts benign under-reporting - a refactor that moved tests, parametrize
  counted differently - into a blocked run. A gate that blocks on benign input
  is one people learn to route around, and a gate routed around is #934 again.

**Pure advisory - never block.** Rejected for the opposite reason: an unenforced
marker is precisely how #934 became "0 of 200".

---

## The amendment counter, and the part that is not closed

The gate's third condition asked the question this design must ask of itself:
**what makes the counter unfakeable?**

The honest answer is that **locally, nothing does.** Enumerating where prior
claims could be recorded:

| Location | Authored by the claimant? | Survives a reset? |
|---|---|---|
| the claim file itself | yes | no |
| a checker-owned log in the worktree | no, but **writable** by it | no |
| git history of the claim file | amendable, rebasable, squashed at merge | no |
| **the retained CI step log** | **no** | **yes** |

Anything inside the worktree is the claimant's to erase, and - this is the
part that matters - **erasure is indistinguishable from a genuine first
filing.** Both present as "no prior claims".

**Notice the shape.** "Zero, or unable to tell?" is #952's amended denominator
rule exactly. The counter *is* a denominator: it states how many prior claims
it examined. So no new rule is needed; the rule already on the books applies
unchanged, and that it applies without modification is the strongest evidence
available that this is one convention rather than two dressed alike.

**The resolution:**

- **Unanchored** (nothing outside the claimant's reach to read): the counter
  reads `UNKNOWN(unanchored)`, **never 0** - including on a genuine first
  filing, which is a real cost accepted deliberately. A clean run is downgraded
  to exit 3.
- **Anchored** (a record the claimant does not author - the retained CI step
  log): the count is a real number, `0 amendment(s)` / `2 amendment(s)`.

**A bare `0` is never emitted.** There is no input that should produce one.

This is a **partial** closure and is labelled as one: an unanchored run is
honest about its blindness but is still blind. The anchor that would close it
is level 3, which is out of lane.

---

## The committed controls

Seventeen cases in
[`control.json`](forced-claim-prototype-2026-09-15/control.json).
Every verdict the checker can emit has at least one case, and the verdicts that
matter have a case on **both** sides. Each case registers its expected **exit
code** as well as its verdict string - see
[the cross-model review](#what-the-cross-model-review-found) for why that is not
cosmetic.

```
$ python3 forced-claim-check.py --selftest
FORCED_CLAIM_SELFTEST_REGISTERED: 14
FORCED_CLAIM_CASE: inflated-claim              expected=DISAGREE(inflated)      observed=DISAGREE(inflated)      ok
FORCED_CLAIM_CASE: honest-claim                expected=VERIFIED                observed=VERIFIED                ok
FORCED_CLAIM_CASE: passes-on-unfixed           expected=DISAGREE(no-match)      observed=DISAGREE(no-match)      ok
FORCED_CLAIM_CASE: no-claim                    expected=ABSENT(no-claim)        observed=ABSENT(no-claim)        ok
FORCED_CLAIM_CASE: empty-diff                  expected=UNKNOWN(no-denominator) observed=UNKNOWN(no-denominator) ok
FORCED_CLAIM_CASE: unsignalled-importerror     expected=UNKNOWN(unsignalled)    observed=UNKNOWN(unsignalled)    ok
FORCED_CLAIM_CASE: absent-claim-tier2-disabled expected=ABSENT(no-claim)        observed=ABSENT(no-claim)        ok tier2_executed=0
FORCED_CLAIM_CASE: amendment-reset-unanchored  expected=UNKNOWN(unanchored)     observed=UNKNOWN(unanchored)     ok
FORCED_CLAIM_CASE: amendment-anchored          expected=VERIFIED                observed=VERIFIED                ok amendments=2
FORCED_CLAIM_CASE: runtime-importerror        expected=UNKNOWN(unsignalled)    observed=UNKNOWN(unsignalled)    ok exit=3
FORCED_CLAIM_CASE: empty-claim-population     expected=UNKNOWN(empty-population)  observed=UNKNOWN(empty-population)  ok exit=3
FORCED_CLAIM_CASE: fails-on-both-trees        expected=DISAGREE(no-discrimination) observed=DISAGREE(no-discrimination) ok exit=1
FORCED_CLAIM_CASE: empty-anchor               expected=UNKNOWN(anchor-incomplete) observed=UNKNOWN(anchor-incomplete) ok exit=3
FORCED_CLAIM_CASE: malformed-claim            expected=UNKNOWN(claim-unreadable)  observed=UNKNOWN(claim-unreadable)  ok exit=3
FORCED_CLAIM_SELFTEST: 14/14 cases behaved as registered
```

Two of them are **positive controls**, and both are load-bearing rather than
padding:

- `honest-claim` must report `VERIFIED`. Without an input that must come back
  clean, a checker wedged permanently at `DISAGREE` is indistinguishable from a
  working one.
- `amendment-anchored` must report a real count. Without it, "always UNKNOWN"
  and a working counter are the same instrument.

`absent-claim-tier2-disabled` is the cost regression, which is silent by
construction: the fixture holds 6 tests across 3 files and asserts tier 2
executes **zero** of them rather than falling back to the whole suite.

### The demonstrated red

Per ADR 0008, the harness itself needs a named input that makes it report the
other verdict. Four were observed, two of them unplanned:

| Input | Result |
|---|---|
| checker wedged at `VERIFIED` (deliberate, reverted) | **4/14** |
| checker returning exit 0 for every case (deliberate, reverted) | **4/14** |
| **CLI forced to `return 0`** (deliberate, reverted) | **3/17** |
| first cut: `sys.executable` had no pytest | **4/9** |
| first cut: signal matched the substring `"error"` anywhere | **5/9** |
| committed tree exported with `git archive`, fixture data untracked | **crashed / 5/14** |

The second row is the one worth reading twice. Codex's review found that the
selftest checked verdict *strings* and never the exit code, so a regression
returning 0 for everything would still have reported a clean 9/9 - the controls
did not protect the fail-closed behaviour this prototype is largely about. Each
case now registers its expected exit code, and the always-zero perturbation is
caught.

Under the `VERIFIED` wedge, note which cases still read `ok`: precisely those
whose expected verdict *is* the wedged value. That is the argument for
both-sided cases, observed rather than asserted.

### What the cross-model review found

`/codex:code_review` (gpt-5.5, read-only) returned **seven findings and all
seven were accepted**. They are recorded here rather than only in the PR
because three of them are this map's own failure classes occurring inside the
tool built to detect them - which is the most useful thing in this document.

| Severity | Finding | Why it mattered |
|---|---|---|
| HIGH | runtime exceptions accepted as assertion matches | pytest reports an in-body exception as `FAILED`, not `ERROR`. The guard I called the best judgment call in the design was half-built, and its fixture hid the gap by using module scope |
| HIGH | an empty test population produced a clean match verdict | a claim naming zero tests printed "all 0 failed by assertion" as `VERIFIED`. **`scanned 0, clean`** - #952's amended rule violated inside the tool written to enforce it |
| MEDIUM | pre-fix failure does not establish discrimination | one-sided. `assert False` was credited the moment any non-test file changed |
| MEDIUM | an empty anchor verified an unsupported zero | a record establishing nothing scored like one establishing a clean first filing. The zero-denominator rule again, one level further in |
| MEDIUM | the import guard mistook external dependencies for escaped project code | a test importing `yaml` returned `import-escape` and asserted the pre-fix tree "was never exercised" - a claim the evidence did not support, whose verdict would flip when an unrelated package was installed |
| MEDIUM | malformed claim schemas crashed before producing a receipt | valid JSON of the wrong shape raised out of the checker, so **no block was printed at all** - indistinguishable from a step that never ran, which is the exact ambiguity this design exists to remove |
| MEDIUM | the selftest did not verify the exit-code contract | see the demonstrated-red table above |

Five fixtures were added to cover them: `runtime-importerror`,
`empty-claim-population`, `fails-on-both-trees`, `empty-anchor`,
`malformed-claim`.

#### Pass 2 - six more, all accepted

The bounded re-review over the fixes found six further defects, one of which
would have shipped a prototype that does not run at all:

| Severity | Finding | Why it mattered |
|---|---|---|
| HIGH | **the manifest, every `claim.json` and every `anchor.log` were untracked** | `.gitignore:54 *.json` and `:120 *.log` swallowed them. `git add -A` reported success and silently skipped them, so the whole 14/14 rested on files not in the repo and a fresh checkout would crash with `FileNotFoundError` |
| HIGH | skipped tests accepted as passing | pytest exits 0 for `SKIPPED` and `XFAIL` as well as for a pass, so a conditional skip on the fixed tree completed a discrimination that never ran |
| MEDIUM | fixed-tree infrastructure failures became hard discrimination failures | every non-pass head outcome collapsed into `DISAGREE(no-discrimination)`, so an uninterpretable head run was reported as an affirmative contradiction - the same collapse this file refuses for pre-fix crashes, in the other direction |
| MEDIUM | unrelated anchor lines became verified amendments | the counter counted distinct non-empty *lines*, so `CI job started` was an amendment; and a pretty-printed claim could never match, so formatting decided identity |
| MEDIUM | the selftest still did not observe the CLI exit status | the new exit assertions read the tuple `render_block` returns and never touched `main()` or `sys.exit`, so forcing the CLI to `return 0` left every assertion green |
| MEDIUM | project discovery excluded source-layout packages | a project shipping `src/widget/` had `import widget` treated as an external dependency, bypassing the escape guard |

Three more fixtures: `head-skips`, `head-collection-error`,
`anchor-with-noise`. The untracked-files finding was verified by exporting the
committed tree with `git archive` and running the selftest from it.

`head-skips` was registered first as `UNKNOWN(unsignalled)` and corrected to
`UNKNOWN(head-unsignalled)` - the expectation was wrong, not the behaviour.
Recorded because adjusting a registration to match observed output is exactly
how a control gets laundered into agreement with the thing it is supposed to
check.

### Two halves, and the negation is the lesser one

The immediate fix is a `.gitignore` negation, mirroring `:87`'s
`!controls/*/control.json` - added for issue #924 when the blanket rule
swallowed that framework's only manifest and shipped it inert.

That precedent is worth reading closely, because its own comment says *"the `*`
glob covers the next consumer, not just the first"* - **and it did not cover
this one**, because this one is outside `controls/`. A negation list is a
hand-maintained enumeration of the places where a blanket rule is wrong, and
extending it by one entry leaves the next location exactly as exposed. This map
exists because hand-maintained coverage lists go stale silently.

One more thing the negation taught, in passing: the first cut of the
`anchor.log` entry was placed beside the `.json` one and was **silently inert**,
because gitignore takes the *last* matching rule and `*.log` appears further
down the file. It looked correct, it was in the right file, and it did nothing.
A two-sided `git check-ignore -v` probe - one file that must now be trackable,
one unrelated file that must still be ignored - caught it; reading the line did
not.

So the prototype also **detects this about itself**: `--selftest` refuses to
report a case result until every manifest, claim and anchor it depends on is
tracked by git, printing `UNTRACKED fixture input` and *"this is UNCHECKED, not
clean"* - the same move `check-negative-controls.py` makes when it refuses to go
green having scanned nothing. The guard earned itself on its first run: three
fixtures added minutes earlier were already silently ignored, and it named them.

**The untracked-files finding deserves its own sentence**, because it is the
purest instance of this ticket's subject to appear anywhere in the work: an
instrument reported `14/14 cases behaved as registered` while a third of its
inputs did not exist in the repository, `git add -A` reported success, and
nothing anywhere said otherwise. The selftest was not lying. It was reading
files that were really there, on one machine, and would have reported exactly
the same thing to a reviewer for whom they were not.

**The negation fixes today. The guard fixes the class.** The negation covers
three globs in one directory; the guard covers every input this checker will
ever depend on, including in locations nobody has enumerated yet. Both are
here, and the ordering of that sentence is the point.

The pattern across the two HIGHs and two of the MEDIUMs is worth stating
plainly, because it is the ticket's own subject: **this prototype had written
the rule down correctly in prose and then not applied it to itself.** The
zero-denominator rule has its own section in this document; the tier-2
population and the anchor record both violated it. The both-sides argument is
quoted here from #963; tier 2 checked one side. An instrument that documents a
principle is not thereby an instrument that implements it, and the distance
between the two was invisible from the inside - it took a model that had not
written the code.

### Two defects the cases caught in this prototype

Both are the map's own failure classes occurring inside the tool built for
them, and both were found by running the controls rather than by re-reading
the code:

1. **The signal was over-broad.** The first cut treated any output containing
   the substring `"error"` as unsignalled, which matched pytest's own chatter
   and made *every* pytest-invoking case `UNSIGNALLED`. This is the finding
   Codex raised on #963 - a pattern matching everything restores
   crash-as-detection - reproduced here by hand. The match is anchored to the
   node id now.
2. **A missing runner was reported as a crashing test.** With no pytest on
   `sys.executable`, the checker reported `UNKNOWN(unsignalled)`: *"your test
   failed without an attributable assertion"*, when the truth was *"I have no
   pytest"*. Same verdict class, completely different cause, completely
   different fix - which is exactly the distinction the verdict-vs-reason rule
   exists to preserve. `no-runner` is now its own reason.

---

## Room for #965

[#965](https://github.com/cooneycw/claude-power-pack/issues/965) wants the same
block: an ELI5 layer, and an explicit owner TO-DO slot. It is held behind this
ticket. This is a collide-on-convention hazard rather than a merge conflict -
two coherent designs for one block would both pass CI.

The block is **section-keyed and additive**, and this checker owns exactly one
section:

```
-- VERIFIED CLAIMS ---    owned here
-- IN PLAIN LANGUAGE --   reserved for #965; this checker does not write it
-- YOURS TO DECIDE ----   reserved for #965; this checker FEEDS it
```

The two are **complementary rather than merely non-conflicting**: every
`DISAGREE` and every `UNKNOWN` emits an item into `YOURS TO DECIDE`. #965's
slot has a producer on day one, and this design's verdicts have somewhere to
land. #965 is not solved here and is not painted into a corner.

---

## A finding about an existing instrument

`scripts/check-negative-controls.py` is the specimen #952's amendment names as
already implementing unknown-is-not-clean, and it is the right model. But its
honesty is **flag-gated**:

```python
593:        return 1 if args.strict else 0     # inside `if not registrations:`
619:    return 1 if (failing and args.strict) else 0
```

Invoked bare it prints *"nothing was checked. This is UNCHECKED, not clean."*
and **exits 0**. `.woodpecker.yml:113` does pass `--strict`, so it is honest as
invoked - but the honesty lives in the **invocation**, not in the instrument,
and a reader copying the model without the flag copies a fail-open.

Hence this prototype's rule: **UNKNOWN is the default verdict, not a
strict-mode upgrade.** The orchestrator is carrying the finding back to #952.

---

## A resemblance worth recording

While this ticket was being built, the wave's own roster showed the same shape
it describes. `flow-wave-registry.sh` has a role-level `driver=` field, it is
read by routing logic (#783), and **no worker had populated it** - so "are all
three workers actually running `auto_codex`?" fell back to each worker's own
sentence about itself. A worker quietly running plain `/flow:auto` would have
produced a byte-identical roster row.

A declared field that nothing populates, whose absence is indistinguishable
from a healthy value, answered by self-report. That is this ticket's subject
wearing the wave's clothes, found by accident in the hour it was being
designed - which is the ordinary way these are found.

---

## What this does not establish

- **That the block works in a real run.** Every verdict here came from a
  fixture. No live `/flow:auto_codex` run produced one.
- **That the pipeline anchor is sufficient.** It is specified, not written, and
  not measured.
- **That the amendment counter can be closed.** It is honest about being blind
  when unanchored; it is not unblind.
- **That the counting rule survives contact.** `parametrize`, fixtures
  generating tests, and tests moved between files are all cases the published
  rule handles badly, and none has a committed fixture yet.
- **Whether any of this is affordable per-run.** #952 made per-run cost a
  rejection criterion. Tier 1 is genuinely free; tier 2 is a checkout plus a
  targeted test run and has never been timed against a real suite.

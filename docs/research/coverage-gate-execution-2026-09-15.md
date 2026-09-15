# Can coverage instrumentation answer "did this gate execute?"

Research findings for [#954](https://github.com/cooneycw/claude-power-pack/issues/954),
ticket 4 of wayfinder map [#950](https://github.com/cooneycw/claude-power-pack/issues/950).

Established 2026-09-15 against `0a98031` (origin/main), coverage.py 7.16.1,
Python 3.12, on the host. No repo file was modified to produce any of it: coverage
was installed into a throwaway venv outside the tree, and every variant tree is a
scratch copy. `pyproject.toml`, `Makefile` and `.woodpecker.yml` are untouched.

> **Measurement subject changed mid-run, and every affected number was re-taken.**
> The first pass ran against `8a4dbdb`. While it was in progress, PR #963
> (`Closes #946`) landed on main and rewrote `scripts/check-negative-controls.py`
> and its tests, which is the specimen used throughout the real-instrument
> sections below. Every number here was re-measured against `0a98031` after
> rebasing. The conclusions did not change; the figures moved slightly and the
> pre-rebase values are noted where they differ, so a reader can see what moved.

---

## Answers, up front

| Bullet | Answer |
|---|---|
| Can coverage say "this gate executed during **this run**"? | **Not as `pytest --cov`.** Yes, as `coverage run` wrapped around the gate itself, which is a different instrument with a different cost. |
| What does it cost per run? | **18-40%** added wall-time across scoped runs, all under possible host contention, so no figure is certified clean. The whole-suite figure and the overhead of the configurations that actually answer the question are both **unmeasured**. Added per-run configuration is the durable cost, not the percentage. |
| Does it separate #952's (b) from (c)? | **(b) from (c): yes**, in every shape tested. **(c) from (c'): no, not reliably** - and that second pair is the one the ticket's own gloss describes. See the split below; these are two questions and the answers differ. |

The third answer is the one the ticket asked to be given plainly, so, stated
precisely: **coverage cannot be relied on to distinguish a gate that ran from a
gate that ran against nothing.** It sometimes can, which is worse than never being
able to, because the capability disappears under refactors that change no
behaviour and nothing reports its loss.

**The ticket asks one question in two incompatible ways, and they have different
answers.** Its bullet names "state (b) from state (c)", and then glosses that as
"a gate that ran from a gate that ran against nothing". Those are not the same
pair. A gate that *ran* against nothing is (c); a gate that *ran* against real
input is (c'). State (b) did not run at all. So:

- **(b) versus (c)** - separable in every shape tested, because a disabled gate
  short-circuits and leaves a large distinctive gap. This is the easy pair.
- **(c) versus (c')** - the pair the gloss actually describes, and the one that
  fails. This is where the negative lives.

The rest of this section reports both, separately, because answering only the
easier pair would have produced a "yes" that the gloss does not support.

---

## Bullet 1: "this run" versus "the test suite"

The ticket's own framing is the finding: *the suite is not the production path*.
The precise reason coverage goes blind here is **not** a language gap. It is that
**the suite is not the CI step**.

Two distinct instruments get conflated under the word "coverage". They have
different answers and must not be collapsed.

### Instrument 1: `pytest --cov` over the suite

**It cannot answer the question, and it fails in the dangerous direction.**

Measured: `pytest --cov=scripts tests/test_negative_controls.py` reports

```
scripts/check-negative-controls.py     253    253     0%
```

**0%**, for a gate that this very test file exercises heavily. The test invokes it
as a subprocess (`subprocess.run([sys.executable, str(HARNESS), ...])`), and
coverage does not follow subprocesses by default.

Read naively, `0%` says *dormant*. It actually says *coverage did not follow the
subprocess*. Those are opposite conclusions from an identical number, and the
naive reading is the one that flatters the map: it would report a well-tested gate
as dead code.

**A zero is a denominator, and it carries the denominator's ambiguity.** This
result amended #952's ruling while that ruling was hours old. The ruling required
instruments to print what they examined, and said no denominator may read as a
silent pass. A measured zero is exactly such a denominator: `scanned 0 files, 0
findings` means either that nothing was there, or that the scanner could not see
what was there, and the two are indistinguishable from the output. The amended
rule is that **a zero reads UNKNOWN unless the instrument can show it was looking
in the right place.** That is what the positive control below supplies, and it is
the only reason the `0%` here could be classified at all.

> **Positive control, which is the thing that separates those two readings.**
> `coverage run --source=scripts scripts/check-negative-controls.py --strict`,
> the same instrument and the same gate, wrapped directly, reports **253
> statements, 63% covered** (pre-rebase: 221 statements, 66%). So the instrument
> is *not* blind in general. The `0%` above is blindness to subprocess execution
> specifically. Without this control, that `0%` is indistinguishable from a real
> absence.

**The `.woodpecker.yml` point, measured rather than argued.** Two scratch copies of
the tree differing in exactly one path, one carrying the gate's CI step
(`python3 scripts/check-negative-controls.py --strict`) and one with that line
deleted. Identical command in each:

| tree | CI step present | coverage of the gate |
|---|---|---|
| `w2With` | yes | `253  253  0%` |
| `w2Without` | **no** | `253  253  0%` |

Byte-identical. Deleting the gate's entire CI invocation does not move the coverage
number by a single statement, because `.woodpecker.yml` is not an input to the
measurement. A gate could be removed from CI altogether and `pytest --cov` would
report exactly what it reported the day before.

### Instrument 2: `coverage` wrapped around the CI step itself

**This one works**, and it is a genuinely different proposition from adopting
`pytest-cov`. The positive control above is this instrument.

Subprocess-invoked gates can also be reached from inside a pytest run, but only
with configuration:

| | config | result |
|---|---|---|
| control A | none | `253 stmts, 253 miss, `**`0%`** |
| control B | `.coveragerc` (`parallel=True`) + `COVERAGE_PROCESS_START` + `coverage run --parallel-mode -m pytest` + `coverage combine` | `253 stmts, 41 miss, `**`84%`** |

Control B produced **38 separate coverage data files**, the parent plus each
subprocess invocation, which is direct evidence the subprocesses were measured
rather than an inference from the percentage moving.

**Why control B works, because the recipe alone does not explain it.** Setting
`COVERAGE_PROCESS_START` does not by itself start coverage in a child interpreter;
a startup hook calling `coverage.process_startup()` is required. No such hook was
written by hand here - an attempt to install one failed, and control B worked
anyway, which was treated as unexplained until it was run down. The mechanism is
that **coverage.py 7.16.1 ships its own `a1_coverage.pth`**, found on `sys.path`,
which performs exactly that call when the environment variable is set. So the
recipe reproduces *on this version* because installing coverage supplies the hook.

Two consequences worth stating rather than leaving implicit:

- The recipe is **version-dependent**. On a coverage that does not ship that
  `.pth`, the same four steps would produce `0%` and look like a real absence.
- The four steps are **not the only route**. Recent coverage exposes a
  `patch = subprocess` configuration that covers the same ground, so "four steps
  are required" overstates it; what is established is that *some* added per-run
  configuration is required, which is the point that bears on cost.

That is a real capability. It is also four added per-run steps and a new config
file, which is the subject of bullet 2.

---

## Bullet 2: cost

Per-run cost is a **rejection criterion** for this map, not a footnote, so the
number comes with its measurement conditions rather than as a bare figure.

Scoped measurement (`tests/test_negative_controls.py`), interleaved bare/cov so
host drift hits both arms:

| pair | bare | with `--cov` | overhead |
|---|---|---|---|
| 1 | 1.95s | 2.73s | +40% |
| 2 | 1.96s | 2.70s | +38% |
| 3 | 2.33s | 2.74s | +18% |

**The honest reading is the range 18-40%, not a point estimate.** Another worker
session was running a full suite on this host throughout, verified in the process
table as a `pytest` under `claude-power-pack-issue-957-*`, so contention was
*possible for every pair* and none is certified clean. Pair 3 is the visible
symptom: its *bare* arm spiked to 2.33s while the coverage arm stayed flat, which
is the signature of load landing on one arm. That is the most likely explanation
and it is not a proven one, so pair 3 is neither discarded nor treated as
representative. What the spike does establish is that contention here can produce a
**sign error** - a pair in which coverage appears to get *cheaper*. On a rejection
criterion, a wrong-signed measurement is worse than a missing one.

**Caveats that bound this number, stated rather than buried:**

- It is a **scoped** run and therefore startup-dominated. A whole-suite ratio may
  differ and is **not** established here. Two attempts were made; both ran under
  the contention above, and a number taken across changing contention is worse
  than no number.
- It measures `pytest --cov`, the instrument bullet 1 shows *cannot answer the
  question*. The overhead of the configurations that CAN answer it is
  **unmeasured**. What is known is structural and specific to **control B**: it
  wrote 38 data files and needed a `combine` pass and a changed invocation. That
  says subprocess *file generation* scales with the number of gate invocations; it
  does not establish total runtime cost, and it does not transfer to direct gate
  wrapping, which spawns no such files.

**The cost of the useful configuration is NOT measured here, and an earlier draft
asserted it was "strictly more" than 40%.** That was an inference dressed as a
bound. Instrument 2 has a different workload and a different baseline: wrapping a
single gate invocation is not the same shape as running pytest with subprocess
tracking, and neither was timed. What *is* established about instrument 2 is
structural, not numeric: it writes one coverage data file per subprocess (38 in the
measured run) and requires a `combine` pass, so its cost grows with the number of
gate invocations rather than with suite runtime. Whether that clears the
operator's bar is unmeasured.

The durable objection is therefore **ceremony, not percentage**: a config file, an
environment variable, a changed test command, and a post-step, added to every
build. That is the "administrivia on every build" the operator's constraint
rejects, and it stands whatever the percentage turns out to be.

One further honesty note on the timings above: the other worker's presence
establishes that contention was *possible throughout*, not that pair 3 alone was
affected. Pairs 1 and 2 may also be inflated. The range 18-40% is what was
observed; no pair is certified clean.

**Method note, because the next A/B timing will read the same two columns in the
same order.** A whole-suite pair was also run and is *not* reported: `bare
wall=311.2s exit=1`, `cov wall=330.3s exit=0`. Naively that is +6%, which would
have contradicted the scoped range and made coverage look nearly free. The
disqualifier is not the contention it was first refused for - it is **`exit=1`**.
The bare arm did not complete the work, so the two figures share no denominator and
+6% is not a slow measurement, it is not a measurement. Wall time was the salient
column; the exit code was the load-bearing one. An A/B timing that does not assert
both arms succeeded is comparing an unknown quantity to a known one.

---

## Bullet 3: does it separate (b) from (c)?

The decisive result, and a clean negative.

### First, on a real instrument

Per the map's preference for real specimens over fixtures, the pair was run on
`check-negative-controls.py --strict` against two trees: one where it has something
to evaluate, one where nothing registers a control.

| tree | exit | verdict | coverage |
|---|---|---|---|
| full | 0 | `ok - 1 control(s) discriminate, each reporting its declared detection signal...` | 64% |
| stripped | **1** | `no gate carries a registration - nothing was checked. This is UNCHECKED, not clean.` | 28% |

**This specimen cannot carry the general claim, and saying why matters more than
the numbers.** It does not go green when it scans nothing. It detects its own
state (c) and refuses to report clean, in its own verdict, with no coverage
instrumentation involved. The 64/28 split is real but **redundant**: the exit code
already said it, for free.

That is a gate deliberately hardened against exactly this failure (it is #924 /
ADR 0008 work, further sharpened by #963 while this ticket was in flight).
Generalising from it would be generalising from the best-case specimen. The
question only bites where a gate is **silent**.

The specimen is not even fully accounted for by the register that enumerates it:
#964 records that `check-negative-controls.py` is an ADR 0008 instrument appearing
in neither register, so the register cannot be read as a coverage map of its own
population. That is this map's failure class showing up inside the best-case
specimen, and it is a further reason the 64/28 split must not be promoted into a
general result.

### The silent case, where it actually bites

A gate that exits 0 in all three states, so the exit code discriminates nothing and
only coverage could:

| state | meaning | exit | missing lines |
|---|---|---|---|
| (b) | switched off, returns early | 0 | `5-9, 14-19` |
| (c) | enabled, scans an **empty** input set | 0 | `7-8, 13, 18` |
| (c') | enabled, scans a **real** input set, finds nothing | 0 | `8, 13, 18` |

This looks like a win, and read carefully it is a real one: the discriminator is
**line 7**, the loop body. `7` missing means nothing was scanned. `7` covered with
`8` missing means something was scanned and honestly found nothing. That is
interpretable **from a single run, with no baseline**, which is more than the
percentage alone can do, since 76% versus 82% means nothing without a
counterfactual you do not have in production.

### Why it still fails

The same gate, same semantics, scan written as a comprehension instead of a loop:

| state | missing (statement) | missing (**branch**) |
|---|---|---|
| (b) switched off | `6-10` | distinct from both rows below |
| (c) empty input | `5, 9` | `stmts=10 miss=2 branch=4 partial=2 missing=5,9` |
| (c') real input | `5, 9` | `stmts=10 miss=2 branch=4 partial=2 missing=5,9` |

**(b) stays separable; (c) and (c') become identical.** A comprehension is one
statement that executes whether or not it iterates, so the (c)/(c') distinction
vanishes while the (b) short-circuit gap survives. Branch coverage, the obvious
rescue, tested rather than assumed, does not recover the lost pair either.

This is precisely why the two questions are reported separately above. Under both
fixtures, and under both statement and branch coverage, **(b) was always
separable**. Only (c) versus (c') ever fails - and it fails on a change of style
alone.

So coverage's ability to separate "ran against nothing" from "ran and found
nothing" is **an artifact of how the gate happens to be written**, not a property
of coverage. A refactor from a loop to a comprehension changes no behaviour, passes
every test, and silently destroys the signal. Nothing reports the loss.

That failure mode, an instrument that quietly stops being able to answer while
continuing to return confident-looking numbers, is the exact class this map exists
to detect. Adopting it as the map's mechanism would place a member of the problem
set in charge of policing the problem set.

**An instrument whose reliability depends on an unrelated style choice is not a
foundation.** Loop versus comprehension is a matter of taste, settled by a linter
or a reviewer's preference, decided by people who have never heard of this map. It
is not a property anyone would think to protect, and there is no gate that would
notice it changing. Any mechanism built on top of this signal inherits that
dependency silently.

### Two further limits

- **Coverage supplies evidence, not a verdict.** `missing: 7-8, 13, 18` becomes a
  finding only once somebody has declared *which* line is the scan and which is the
  fire. That mapping is a hand-maintained artifact whose drift is already on #950's
  own "Not yet specified" list.
- **It cannot say the input was the *right* input.** Line 7 covered means something
  was scanned, never that the correct things were scanned. A gate pointed at the
  wrong directory with three files in it looks exactly like a gate pointed at the
  right one.

---

## Reach: how much of the instrument population could coverage speak to at all?

`coverage.py` measures Python. ADR 0008 enumerates 61 instruments:

| artifact named in the row | rows | share |
|---|---|---|
| `.sh` | 25 | 41% |
| `.py` | 23 | 38% |
| `.yml` | 1 | 2% |
| names no file | 12 | 20% |

**Denominator provenance, because a percentage over an unverified base reads as
measured.** The 61 parsed rows match the ADR's own "61 instruments" claim, which is
a consistency check and not an independent one: it is hand-maintained markdown
whose currency #950 explicitly lists as unowned. So a 12-row sample was drawn
(deterministic seed) and each named artifact checked against the tree:
**12/12 present, 0 missing**. The base is not stale on that sample. It is not
verified row by row, and this number should not be quoted as if it were.

**This table counts filename references. It is NOT a reach ceiling, and an earlier
draft wrongly presented it as one** ("at most 23 of 61"). Two things break that
reading, both checked in the tree:

- **Rows naming no `.py` file are not therefore unreachable.** Rows 53 and 54 name
  `lib.cicd check` and `lib.cicd validate`; row 48 names `bootstrap-check.sh
  (lib.cicd bootstrap)`. These are Python, implemented in `lib/cicd/cli.py` and
  `lib/security/cli.py`, both present. Coverage can see them.
- **Shell-named rows may delegate substantive work to Python.** Row 1 is
  `flow-finish-gate.sh` + `lib.cicd run`, a shell wrapper whose actual work is a
  Python runner. Coverage would see the delegated half and be blind to the
  wrapper, which is *partial* visibility, not absence.

So the honest statement is narrower: **23 of 61 rows name a `.py` file outright**,
an unknown further number are Python behind a non-`.py` name or behind a shell
wrapper, and the shell wrappers themselves are invisible whatever the
configuration. Classifying implementations rather than filenames would be needed
to state a real ceiling, and that work is not done here. The figure above should
not be quoted as a coverage reach.

**Two corrections, one of them to this document's own method, and it is the more
instructive of the two.**

The assignment asserted "CPP's gates are largely shell" as the reason coverage
would go blind. An earlier draft of this document refuted that flatly: *every step
in `.woodpecker.yml` is Python*. **That refutation was false, and the way it was
produced is the subject of this whole ticket.** It came from a grep whose pattern
was `^\s+-\s+(make|python|\./|bash|sh |uv )`. That alternation can only match
steps beginning with those tokens, so it could never have returned
`gitleaks detect --source . --config .gitleaks.toml` (the `secret-scan` step) or
`find . -path ./.git -prune -o -name Dockerfile -print0 | xargs -0 -r hadolint`
(the `dockerfile-lint` step). Both are non-Python CI gates and both were present
the whole time. The extractor was structurally incapable of finding a
counterexample, and its silence was reported as a fact.

That is exactly the failure this document argues coverage would commit: an
instrument that cannot produce the disconfirming answer, returning a clean result
that looks identical to a true one. It was caught by cross-model review, not by
care, which is itself the point - a blind instrument does not announce itself to
the person holding it.

**Corrected claim, from an unfiltered enumeration.** The fix for a pattern that
could not return a counterexample is not a better pattern: it is to stop filtering.
Extracting *every* command line in `.woodpecker.yml` with no pattern at all yields
11 lines - 7 Python gates (`pytest`, `mypy`, and five `python3 scripts/*.py`),
**3 non-Python gates**, and `uv sync` as infrastructure:

| gate | implementation | visible to coverage.py |
|---|---|---|
| `secret-scan` | Gitleaks (Go binary) | no |
| `dockerfile-lint` | shell pipeline driving Hadolint | no |
| `ruff` | **Rust binary** (`.venv/bin/ruff` is a 27MB stripped ELF, not an importable module) | no |

Ruff was in the "Python" column of an earlier draft purely because it is a Python
*ecosystem* tool installed from PyPI. It is not Python code, and coverage.py cannot
instrument its checking logic. Finding that required opening the binary rather than
reasoning from where it came from, which is the same lesson as the grep above one
layer down.

**The blindness was two layers deep.** The refutation was not accepted on trust:
it was independently verified by a second party, whose check used a different
pattern with the *identical* structural flaw - an alternation anchored on `.py`,
`.sh`, and the three tool names already expected. Two people, two greps, one blind
spot, and a confirmation that added no information because the confirming
instrument could not have disagreed. Agreement counts only when the parties can
fail independently.

As for the broader population, the 41%/38% figures are **filename-reference
shares**, not implementation shares, for the reasons set out in the reach section.
They cannot be used to claim a shell plurality of implementations, and this
paragraph does not.

So the original "largely shell" claim is wrong about CI steps as a *majority*
statement, right that non-Python gates exist there at all, and unresolved for the
enumerated population until implementations are classified. None of those three
substitutes for the others.

---

## What this does not establish

- **Whole-suite cost, declared residual rather than an open gap.** The 40% is
  scoped and startup-dominated. Both whole-suite attempts ran under a contended
  host and are deliberately not reported: the contention was large enough to
  produce a **sign error**, with one pair's bare arm spiking while the coverage arm
  held flat, which reads as coverage getting *cheaper*. Cost is a rejection
  criterion, and a wrong number there is worse than none. Judged not load-bearing
  for the verdict: the cost objection does not rest on any percentage. It rests on
  the fact that every configuration which answers the question adds per-run
  configuration to the build. Quieting the host to chase a cleaner figure for
  `pytest --cov` would sharpen a number belonging to the configuration that cannot
  answer the question.
- **That instrument 2 is unaffordable, or what it costs at all.** Its overhead was
  never timed. It adds per-run configuration, and via control B's route it also
  adds data files and a combine pass. Whether that clears the operator's bar is a
  decision, not a
  measurement, and it is #952's to make.
- **That the code-shape defeat generalises to every CPP gate.** It is demonstrated
  on a fixture with a real-instrument anchor. The claim is that coverage's
  discriminating power is *shape-dependent*, which is established, not that any
  particular CPP gate is currently shaped the losing way.
- **What the 12 rows naming no file actually are.** They are *not* simply written
  instructions: at least three of them (`lib.cicd check`, `lib.cicd validate`,
  `lib.cicd bootstrap`) are Python commands coverage could see. Others may be
  prose. They were never classified, and grouping them with the 95 markdown
  instruments - as an earlier draft did - would restore the reach assumption this
  document retracts.
- **Anything about the 95 markdown instruments.** Coverage has nothing to say about
  instruments that are written instructions to an agent.

## Bearing on #952

For the three states, on the evidence here:

- **(a)** invoked by nothing: coverage over the *suite* cannot see it, per the
  `.woodpecker.yml` result above, where removing the invocation changes nothing.
- **(b)** invoked but unable to fire: separable by coverage when the disable is a
  code branch, because the short-circuit leaves a large distinctive gap.
- **(c)** invoked against input that never exercises it: separable from (c') only
  when the scan is written as a statement that can go unexecuted. Not separable
  under a comprehension, under either statement or branch coverage.

The honest summary for the definitional ticket: coverage is a **shape-dependent
partial signal**, not a mechanism that can be relied on to answer "did this gate
execute?", and its failures are silent.

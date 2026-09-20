# Re-examining five control batteries by mutation

- Date: 2026-09-20
- Issue: #970
- Method: `scripts/mutation-probe.py` - break each declared protection in turn in
  a disposable sandbox, require the battery to go red
- Examined by: a session that authored none of the five batteries, which is the
  condition #970 set. The wave's own finding was that every one of six specimens
  was caught by two methods disagreeing and none by an author checking their own
  work, so a self-audit here would reproduce the configuration that failed.

## What was asked, and the one thing that is not claimed

#970's third outcome is **re-examine**, not repair. Where a repair was cheap and
directly produced by a finding it was made and is named below; everything else is
recorded and filed. And the enumerations are **samples, not censuses**: a person
reads a gate and writes its protections down, so a "3 of 12" below means three of
the twelve *someone enumerated*, never three of the twelve the gate has. The probe
says this on every run for the same reason.

## Summary

| Battery | Protections enumerated | Caught | Uncaught | Method |
|---|---|---|---|---|
| #960 `controls/shellcheck-gate` | 12 | **2** as merged, **4** after two cases were added | 8 | source mutation, register battery |
| #955 `class-enumeration` sweep | 5 | **3** | 2 | source mutation, committed `CONTROL_CASES` |
| #953 forced-claim prototype | 7 (sampled) | **4** | 3 | source mutation, `--selftest` battery |
| #954 coverage-gate research | - | - | - | **not mutation-testable**, see below |
| #957 woodpecker-retention research | - | - | - | **not mutation-testable**, see below |

Not one of these numbers is obtainable by reading, and not one of the authors was
wrong about anything they claimed. That is the whole of #970 in a table.

---

## #960 - `controls/shellcheck-gate`

Declarations are committed in `controls/shellcheck-gate/control.json`; reproduce
with

```
uv run --extra dev python scripts/mutation-probe.py \
    --manifest controls/shellcheck-gate/control.json --strict
```

**As merged, the battery exercised 2 of the 12 protections enumerated** -
`interpreter-allowlist` and `env-shebang-resolution`, both reached by the same
two committed cases through the same extensionless-file path.

**Measured rather than reasoned.** The `option-terminator` claim below is the one
that could most easily have been an assumption, so it was measured against the
battery as it stood: with `bad-optionlike` removed from the manifest and only
that mutation declared, the probe reports `MUTATION-UNCAUGHT`. Removing the `--`
from the linter invocation changed no registered verdict.

### Two repairs, because a control was available

Leaving an available control unwritten while marking the protection "accepted"
would launder the finding, so two case trees were added:

1. **`cases/bad-optionlike`** - a file literally named `--help`. Without the `--`
   option terminator the linter reads it as a flag, prints its usage summary,
   exits 0 having examined nothing, and the gate reports a confident
   `0 findings`. Measured directly: `shellcheck ... -- --help lib.sh` exits 1
   with SC1087; the same command without `--` exits 0 and prints usage.
2. **`cases/good-fixture-skip`** - a deliberately broken script at
   `controls/*/cases/*`, which the gate must skip because that population belongs
   to the control that owns it. The offender is **extensionless on purpose**: a
   `*.sh` name would also be caught by the vendored anchor, which globs `*.sh`
   and has no such exclusion, and an anchor that disagrees with the gate on a
   known-GOOD input is reported INERT rather than blind.

With those, **4 of 12 are caught**.

### The structural finding: the register cannot control an UNKNOWN verdict

Seven of the eight remaining protections are not uncovered through inattention.
They are **inexpressible in the register as it stands**, and the reason is one
shared property: each reports **UNKNOWN (exit 2)** with a
`shellcheck-gate: UNKNOWN - ...` message.

`check-negative-controls` registers a case as `GOOD` or `BAD` against
`good_exit: 0`, and the UNKNOWN message does not match this control's
`detect_signal`. So a case exercising any of them scores `UNSIGNALLED` and takes
the whole control down instead of exercising the branch. The protections in that
position are `zero-matched-is-unknown`, `newline-path-audit`,
`unreadable-is-unknown`, `linter-absent-is-unknown`, `linter-crash-is-unknown`,
`root-must-be-a-directory` and `git-enumeration-failure`. Three of them are
doubly inexpressible - a filename containing a newline, an unreadable file, and a
non-directory `--root` cannot be committed or passed at all.

**This is a finding about the register, not about #960.** Every gate in this
repository has an UNKNOWN branch - "0 examined is not 0 findings" is a house
convention - and none of them can carry a control for it today. It is adjacent to
#1117 (UNSIGNALLED needs splitting from UNAVAILABLE) and is filed rather than
fixed here.

The eighth, `sh-extension`, is inexpressible for a different reason and the
distinction matters: exercising the `*.sh` arm needs a BAD case whose offending
file is a `.sh` file with no shebang, and **the vendored anchor globs `*.sh`**, so
it would CATCH that input and the control would be reported INERT. The anchor's
own blindness forbids any committed BAD case on the entire `.sh` path. That is a
real property of the pair, found by mutation and invisible in either file.

All eight are recorded in the manifest as `expect: "uncaught"` with their reason -
a stated gap, and a self-invalidating one: if a register ever carries a third
expected verdict and a case lands, the probe reports `MUTATION-STALE` and the
acceptance must be dropped.

---

## #955 - the `class-enumeration` sweep

This is the battery #970 names as the working reference, and re-examining it
produced the sharpest result of the five.

### Its own self-test reports 5 of 5. Source mutation reports 3 of 5.

`sweep.py --self-test` disables `cmdpos`, `quote`, `interp`, `comment` and `ast`
and reports every one caught. Applying the same five protections **to the sweep's
real source** and running its committed `CONTROL_CASES` gives:

| Protection | `--self-test` | source mutation |
|---|---|---|
| `cmdpos` | caught | **CAUGHT** (`SWEEP_CONTROL_FAIL: flow-ci-status.sh`) |
| `quote` | caught | **CAUGHT** (`SWEEP_CONTROL_FAIL: mcp-drift.py`) |
| `comment` | caught | **CAUGHT** (`SWEEP_CONTROL_FAIL: flow-finish-gate.sh`) |
| `interp` | caught | **UNCAUGHT** |
| `ast` | caught | **UNCAUGHT** |

The cause is in `_probe`, the self-test's case evaluator. Only `cmdpos` is a real
mutation - `run_controls` rebinds the module-level `_CMDPOS`. For the others,
`_probe` **re-implements** what the sweep would do: it substitutes a looser regex
inline for `interp`, and for `ast` it substitutes a text scan instead of routing
through `closure`'s `if f.suffix == ".py"` dispatch. Replacing the real `_INTERP`
constant with a loose one, or disabling the real `ast` dispatch, changes no
committed control's verdict.

So the harness mutates a MODEL of the instrument for four of its five
protections, and the model agrees with the instrument in three of those four by
coincidence of the cases rather than by construction. Declarations are committed
at `docs/research/class-enumeration-2026-09-15/mutations.json` - **not** a
register manifest and not discovered by `check-negative-controls`, read only when
named:

```
uv run --extra dev python scripts/mutation-probe.py \
    --manifest docs/research/class-enumeration-2026-09-15/mutations.json
```

### A second finding, unrelated to mutation: the sweep is RED on main

`python3 docs/research/class-enumeration-2026-09-15/sweep.py` exits **1** on the
current tree. Its committed RED bucket control asserts that
`eli5-core-drift.sh` is NOT AUTOMATED - #591's claim - and that claim has been
falsified by later work: `tests/test_codex_skill_sync.py` invokes it through
`subprocess.run(["bash", str(shim), ...])` at two sites. The sweep is right and
the control is stale.

Nobody noticed because nothing runs it - a research artifact, in no Makefile
target and no CI step, which is the dormant-guard class the sweep itself was
built to enumerate. And `--self-test` still exits 0, because it runs neither the
scan nor the bucket controls: **the self-test the issue holds up as the reference
passes while the instrument's own battery fails.** That is why the probe drives
`run_controls()` directly here rather than the whole program - a battery that is
red before any mutation would score every mutation CAUGHT for free, and the probe
refuses it as `UNRESOLVED` instead.

---

## #953 - the forced-claim prototype

Seven protections sampled from a 872-line checker, chosen from the ones its own
docstrings mark as load-bearing. Declarations are committed in the prototype's
`control.json`; reproduce with

```
uv run --extra dev python scripts/mutation-probe.py \
    --manifest docs/research/forced-claim-prototype-2026-09-15/control.json
```

**4 caught, 3 uncaught.**

Caught: `assertion-not-crash` (a pre-fix test that FAILED by raising is not a
discrimination), `exit0-is-not-pass` (pytest exits 0 for SKIPPED and XFAIL too),
`claim-tests-must-be-strings`, and `test-file-naming`.

Uncaught:

- **`claim-must-be-an-object`** and **`tests-added-must-be-a-count`** - both in
  `_claim_shape_error`, the function whose docstring says it was *"added after
  review"* because valid JSON of the wrong shape raised out of the checker and
  produced no block at all. **A protection added in direct response to a review
  finding has no control.** The committed `malformed-claim` case supplies
  unreadable JSON, which is a different branch.
- **`collected-nothing`** - `pytest` exit 5, "no tests collected", which no case
  reaches.

All three are expressible as committed cases - a `claim.json` holding
`{"tests": [], "tests_added": true}` reaches the second directly. They are left
UNCAUGHT rather than accepted, because an available control that is merely
unwritten is not a gap to accept. The prototype is a research artifact outside
`controls/` and outside the CI population, so the red is recorded here and filed
rather than gating.

### An environment finding, found by the sandbox

The first probe run reported the prototype's battery **already red**: `5/17`,
every failing case reading `UNKNOWN(no-runner)`. The sandbox holds tracked files
only, so it has no `.venv`, and `_resolve_runner` resolves pytest by walking
parents for one. Two things follow:

1. The battery does not run in a clean checkout - a CI image or a fresh clone
   gives `5/17` and exit 1. This is the #978 shape one level out: not "the
   fixtures are untracked" but "the runner is".
2. More seriously, **"the environment has no pytest" is scored as "the battery
   failed"**. Each case reports `UNKNOWN(no-runner)` and is then counted as a
   MISMATCH - the UNRESOLVED-versus-BLIND collapse, inside the prototype built
   largely to preserve exactly that distinction, and reported by its own selftest
   line as though twelve controls had stopped discriminating.

The probe now substitutes `{python}` in a declared battery so the project
interpreter carries through, which is why `make mutation-probe` runs under `uv`.

---

## #954 and #957 - not mutation-testable, and why that is the finding

Both are documents. `docs/research/coverage-gate-execution-2026-09-15.md` and
`docs/research/woodpecker-retention-2026-09-15.md` have no committed executable
artifact beside them - verified against the directory listing, where #953 and
#955 each have a sibling directory and these two do not. There is no source to
mutate and no battery to run.

That is not a technicality, and it is a different disposition from "uncovered":

- **#954's "positive control" is a measurement procedure.** Control A (no
  configuration, `0%`) versus control B (`.coveragerc` with `parallel=True`,
  `COVERAGE_PROCESS_START`, `coverage combine`, `84%`) establishes that the
  instrument could see the subject at all. It is a control over a *measurement*,
  re-derivable by re-running the recipe, and nothing about it is a claim a future
  change could silently break. Mutation has no purchase because there is no
  committed instrument whose protections could be removed.
- **#957's positive control was LIVE and is now unrepeatable.** Pipeline 1721
  step 3 returned 315 bytes of real `gitleaks` output through the identical call
  path, which is what made an empty result interpretable. It cannot be re-run:
  the retention window that document exists to establish has since closed over
  it. Its evidence is a record of an observation, not an instrument.

**Neither is in the position #970 describes** - "a committed control battery
whose soundness was cleared by inspection" - because neither committed a battery.
The honest re-examination result is that the class does not apply, and saying so
is different from saying they passed. What would put them in scope is promotion:
if either recipe is ever committed as a runnable check, it acquires protections
and needs this treatment then.

---

## What this cost, since #970 left affordability explicitly unmeasured

Mutation is paid once per instrument at authoring time, not per run, which is why
#952's per-run rejection criterion does not obviously bite. Measured here:

- One battery run per declared mutation, plus one baseline. `controls/mutation-probe`
  and `controls/shellcheck-gate` together declare 14 mutations and the whole
  `--strict` run over all 24 registered manifests takes single-digit minutes on a
  dev box.
- The dominant cost is not machine time. It is **reading the gate and writing the
  protections down**, which took the largest share of this examination and is the
  part no tool removes.
- The probe is kept out of `make verify` for that wall-clock profile and because
  the batteries it drives need `gitleaks` and `jq` on PATH, exactly as
  `negative-controls` is.

## Filed from this examination

- The register cannot express a control for a gate's UNKNOWN verdict (#960's
  seven, and every gate in the tree has such a branch).
- An anchor's own blindness can forbid a whole class of committed BAD case
  (#960's `.sh` path).
- #955's sweep is red on main: its RED bucket control was falsified by
  `tests/test_codex_skill_sync.py`.
- #955's `--self-test` mutates a re-implementation for 4 of its 5 protections.
- #953 has three uncovered protections, two of them in a function added in
  response to a review finding.
- #953's battery scores a missing pytest as a failed battery.

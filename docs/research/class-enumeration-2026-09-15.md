# Which issues are instances of "a guard that exists, works, and nothing runs it"

**Established 2026-09-15 for [#955](https://github.com/cooneycw/claude-power-pack/issues/955), against `1ba44cb`. Part of map [#950](https://github.com/cooneycw/claude-power-pack/issues/950). This document classifies and fixes nothing.**

## What this document concluded, including about itself

The issue classification is in the table near the end and is the deliverable. It was produced by reading issues, not by tooling, and nothing below changes it.

The second result was not planned and is worth more to the map: **an attempt to detect dormancy automatically failed six times, in both directions, and each failure produced a clean plausible number.** That is direct evidence about the mechanism #950 is trying to choose, and it is reported here rather than buried, because the failures were only found by adversarial review and mutation testing rather than by care.

## The class, and the three axes it is not

INSTANCE has three conjuncts, and **all three must hold**:

1. the guard **exists**,
2. it **works**,
3. **no automated path invokes it**.

A fourth condition disqualifies rather than qualifies: a guard whose invariant is now checked by something else is **superseded**, not dormant, even when nothing runs the original. That exclusion is stated here, once, and applied consistently below.

[#591](https://github.com/cooneycw/claude-power-pack/issues/591) states clause 3 in checkable form, and this document uses it verbatim:

> no step in `.woodpecker.yml`, no Makefile target, no test in `tests/`, referenced only from docs. **Advisory-by-design is fine; advisory-and-never-run is decoration.**

Three neighbouring axes are repeatedly mistaken for this class. Every ADJACENT ruling names which one applies:

| Axis | Question it answers | Owner |
|---|---|---|
| **Dormancy** (this class) | Does anything invoke it? | #950 / #955 |
| **Falsifiability** | Can it fail when poked? | #924 / PR #948, ADR 0008 |
| **Blindness** | Can it see what it claims to see? | #946, #933, #892, #939 |
| **Scope mismatch** | Does it answer a narrower question than its reader supplies? | #834 |

A perfect negative control proves an instrument beeps when poked. It says nothing about whether anything pokes it. **#591 and #576 would both have passed #924 completely.**

## Where the universe came from, and what it cannot see

### Axis A: complete census of issues, and the actual deliverable

Not a search. **27 of 27 open issues read in full**, plus the 103 closed since 2026-08-16 and the five closed issues #955 names. The open set is small enough to enumerate exhaustively, so there are no search terms for the result to be a statement about.

**Axis A is structurally blind to an instance with no issue.**

### Axis B: a screening sweep over the tree, and a cautionary tale

`docs/research/class-enumeration-2026-09-15/sweep.py` applies clause 3 mechanically over the scripts in the tree. Its universe is **derived from `git ls-files`**: every tracked file under `scripts/` that is executable or carries a shebang, **63 files**. It is not filtered by extension, because an extension filter is itself a search term and would hide the one shape the sweep exists to find. `scripts/cpp-memory` is exactly that shape: tracked, executable, `#!/usr/bin/env bash`, no extension.

**Axis B is screening, not measurement.** Its error rate is not zero and is not estimated. Use it to find candidates, never to bound a population.

### What neither axis can see

1. **Instruments outside `scripts/`.** The 309 markdown instruction-instruments, ADR 0008's 61 verdict contracts, CI steps that inline their logic, checks embedded in `lib/`.
2. **Host-level wiring.** Hook invocation lives in `~/.claude/settings.json`, outside the repository, and is invisible to any repo sweep.
3. **Whether a script is a guard at all.** The universe is scripts; the class is guards. Not every unrun script is a dormant instrument.
4. **Sub-instrument dormancy.** A field, flag or branch inside a reachable script. See the `driver=` specimen below, which no file-level sweep can detect.
5. **Issues closed before 2026-08-16**, except the five #955 names, and anything in other repositories.

## The sweep was wrong six times, in both directions

This is the map-relevant result, so it is reported in full with the evidence for each failure. Every version produced a clean, plausible, confidently-wrong number.

| Version | Rule | Reported | Actually |
|---|---|---|---|
| v1 | a *mention* counts as reachability | 4 dormant | wrong, far too permissive |
| v2 | require execution context; drop comments | 12 | wrong, same hole via a bare path pattern |
| v3 | drop the bare `scripts/<name>` pattern | 26 | closer, still text-only |
| v5 | derived universe (63) | 8 unreferenced | wrong: matched `sh` inside a quoted FILENAME |
| v6 | anchored interpreter, command position | 7 unreferenced, **32 agent-doc-only** | wrong in BOTH directions |
| v7 | `ast` for Python, quote-awareness, alias resolution | 6 unreferenced, **4 agent-doc-only** | current; still screening only |

**Four false positives (claimed invoked, was not).** Each is a real line in this tree:

- `scripts/tool-risk-drift.py:23` a docstring sentence, *"Same discipline as scripts/eli5-core-drift.sh (the eli5-gate vendor guard)"*, read by v1 and v2 as evidence that the guard runs. Its subject is #591, one of the two cases this whole map rests on.
- `tests/test_cpp_command_wiring.py:65` a test data tuple, `("install-memory-harness.sh", "cpp-memory would be missing from PATH")`, where v5 matched `sh` inside the quoted filename as an interpreter.
- `tests/test_driver_capability.py:896` a docstring line *beginning* with a script name, which v6 read as a command.
- `scripts/drift-detect.sh:543` a printed advice string containing `python3 scripts/mcp-drift.py`, which v6 read as running it.

**Two false negatives (claimed dormant, was invoked), and these were the damaging ones.** v6 required the script name and the invocation syntax on the same line, so it missed the ordinary test idiom:

```python
REGISTRY = ROOT / "scripts" / "flow-wave-registry.sh"      # tests/test_driver_capability.py:45
subprocess.run(["bash", str(REGISTRY), *a], ...)           # :482
```

and `importlib.util.spec_from_file_location` loads, such as `tests/test_project_init.py` exercising `project-init.py`.

**This is the correction that matters.** v6 reported **32 scripts invoked only by agent documentation, "more than half the tree's tooling"**, and that finding was circulated as the most valuable thing in the enumeration. It was an artifact. Ground truth: `tests/test_flow_wave_lexicon.py`, `tests/test_friction_log.py`, `tests/test_c4_mermaid.py` and their siblings exist and invoke those helpers through path variables. The corrected count is **4**. The conceptual point that the root set defines the answer survives; the number that made it look important does not.

**And a seventh failure, found while fixing the sixth:** the first `ast` rule accepted a script name appearing in *any* call, including parametrize lists and assertion messages, and reported 57 of 63 scripts automated. Tightened to calls that actually run or load something. Loose and strict rules fail equally confidently.

### The control battery, and why the previous one was decoration

v6 shipped nine control cases and they all passed. Adversarial mutation then showed that **disabling comment rejection, command-position matching, hook detection, or transitive scanning left every control passing with exit 0**. The battery did not test the protections it was advertised as holding.

The sweep now runs `--self-test`, which **breaks each protection in turn and requires a control to fail**:

```
disable cmdpos   -> 1 control(s) fail  [caught]
disable quote    -> 2 control(s) fail  [caught]
disable interp   -> 3 control(s) fail  [caught]
disable comment  -> 1 control(s) fail  [caught]
disable ast      -> 2 control(s) fail  [caught]
```

Writing that self-test immediately found one more hole: the `cmdpos` protection had **no control depending on it**, because the case that needed it had moved to the `ast` path. A case was added that fails without it. **A battery that survives its own protections being removed is decoration**, and it takes mutation rather than inspection to tell the two apart.

Nine cases are committed, each a real line, each naming the protection it holds.

**The generalizable result, and it reaches well past this ticket.** A negative control proves an instrument *can* beep. **Mutation proves each protection is load-bearing.** These are different properties, and the gap between them is invisible to inspection: this battery was read at a review gate, judged correct, and called load-bearing, and it was decoration. Inspection is exactly what a gate does, so a gate cannot close this gap. The confirmation is that writing the mutation harness found one more uncovered protection on its first run.

### Coverage, because a zero must not read as clean

Per #952, the sweep prints a denominator per root set (discovered, scanned, missing, unreadable) and **refuses to report buckets if any root set could not be fully examined**. Without that, making test and document files unreadable produced `AGENT-DOC-ONLY = 0` with every control passing and exit 0: absence of invocation and failure to look were indistinguishable.

The bucket controls also require their specimens to **exist in the universe**, so a deleted or misspelled file cannot satisfy "not in AUTOMATED" vacuously.

## Current screening result

Screening counts, on `1ba44cb`. **Not a census, and no bucket bounds dormancy.**

| Class | Count | Meaning |
|---|---|---|
| AUTOMATED | 52 | a CI step, Makefile target, test, or `lib/` call appears to run it |
| HOOK-ONLY | 1 | named by `.claude/hooks.json` |
| AGENT-DOC-ONLY | 4 | `classify-tool-risk.py`, `eli5-core-drift.sh`, `prompt-context.sh`, `secrets-mask.sh` |
| UNREFERENCED | 6 | `bash-prep.sh`, `commands-mirror-sync.sh`, `cpp-memory`, `memories-db-setup.sh`, `playwright-desk.py`, `sandbox-phase1-trial.sh` |

**UNREFERENCED = 6 is a screening count, not a bound on dormancy**, in either direction:

- it **overcounts**, because host hook wiring is invisible and because superseded leftovers sit here (`eli5-core-drift.sh` is the worked example, and `cpp-memory` is not a guard at all);
- it **undercounts**, because AGENT-DOC-ONLY also admits guards that nothing automated runs, and because false-positive invocation matches remove genuinely dormant scripts from the bucket entirely.

Anyone quoting a dormancy count from this table alone would be wrong, which is why the tool prints the bounds itself.

**The surviving conceptual finding.** Four scripts are invoked only because a command document tells an agent to run them. That is small, but it is not zero, and the class is exactly #950's open question, *"whether an instruction that tells an agent to run a check can be verified as obeyed"*, currently filed as not sharp enough to ticket. It is sharp enough to have members; it is not large enough to be the headline it was briefly reported as.

## The state the class has no name for: SUPERSEDED

`scripts/eli5-core-drift.sh` is not automated, exactly as #591 found. It is **not an instance today**, because the job moved:

| | then | now |
|---|---|---|
| guard | `eli5-core-drift.sh` | `eli5-vendor.py` |
| CI | none | `eli5-vendor-check`, `eli5-upstream-drift` |
| Makefile | none | `eli5-check`, `eli5-drift`, `eli5-revendor` |

A **dormant** guard leaves an invariant unchecked. A **superseded** one does not. The remedy differs completely: wire the first, delete the second. **No automated sweep can distinguish them, including this one** - both present as present-but-unrun.

### The reframing that may sharpen the map's question

Raised here as an open question rather than a ruling, and it came out of reviewing this ticket rather than from the ticket itself:

> **"Is this script dormant" may be the wrong subject.** A dormant guard leaves an *invariant* unchecked; a superseded one does not, because something else checks it. So the question belongs to the **invariant**, not the file: *is invariant X checked by anything?*

That reframing explains the `eli5-core-drift.sh` case exactly - unrun, with its own issue, and still not an instance, because `eli5-vendor.py` holds the invariant. It also explains why every sweep in this document struggled: **a script-rooted sweep structurally cannot answer an invariant-rooted question**, however good its detection rule gets. No amount of fixing the extractor reaches it.

It is a much harder question, because it requires enumerating invariants rather than files, and nothing in this repository currently does. Recorded as a sharper *unsharp* question for #950 rather than an answer.

## Classification

| Issue | Class | Reason |
|---|---|---|
| **#934** counter-model review, 0 of 200 PRs | **INSTANCE (provisional)** | Clauses 1 and 2 hold. **Clause 3 is not established**: per #951 the "0 of 200" counts a self-reported marker, so the evidence supports "never reported running", not "no automated path invokes it". Provisional pending evidence about the invocation path itself. |
| **`driver=` specimen** (no issue; nit store #864 + map comment) | **INSTANCE** | Wired, rendered on every `list`, routed on by `/flow:wave` per #783, carried by 0 of 3 live workers. Found by a **third method** neither axis here provides: inspecting live worker registrations. Axis B cannot detect it, and saying otherwise would overstate the two-axis remedy - identical repository contents with zero or three populated registrations produce identical sweep output. |
| **#591** (closed) | **INSTANCE**, historical | True when filed. Today the script is still unrun but **superseded**, so it is not a live instance. |
| **#576** (closed) | **INSTANCE**, historical, fixed | Item 1 is live at `.woodpecker.yml:90`. The GREEN control. |
| **#871** evergreen harness re-check | **PROVISIONAL, clause 2 unestablished** | The guard is an issue, not a script: a standing re-check whose only invocation path is someone remembering. Clause 3 plainly holds. **Clause 2 does not**: an intention written in prose cannot be shown to work in the sense the other instances can. Recorded as the ruling most vulnerable to resemblance, not defended. |
| **#924 / PR #948**, ADR 0008 | **ADJACENT, not instance** | Falsifiability axis. Called out explicitly because the resemblance is close: #591 and #576 would both have passed #924 completely. |
| **#946** | ADJACENT | Blindness, in the checker built to cure blindness. |
| **#933** | ADJACENT | Scope mismatch: claims "every constructed absence", detects only PATH replacement. |
| **#935** | ADJACENT | Falsifiability: secret-scan runs, cannot be shown able to fail. |
| **#892** | ADJACENT | Blindness: a codex `item.type: "error"` is invisible, so a lane that never started reports success. |
| **#939** | ADJACENT | Blindness: reads one stream while documenting two. |
| **#958** | ADJACENT | Blindness in an instruction-instrument. |
| **#964** | ADJACENT | Scope mismatch: the register is read as a coverage map and omits its own instrument. |
| **#834** (closed) | ADJACENT | Scope mismatch, the origin case. |
| **#910** | ADJACENT, boundary | Blindness plus **shadowing**: it executes while nothing depends on its verdict. "Invoked but inert" is a state no axis here names. |
| **#926** | ADJACENT, boundary | The recorded-property test runs and passes; the protection is a decorator whose application nothing enforces. Unenforced coverage, not an unrun guard. |
| **#927** | ADJACENT, and a **cause** | False green whose effect creates dormancy downstream: the stale installer omits two helpers. |
| **#921** | ADJACENT | Validity decay: the check runs, its result expires. |
| **#936** ADR 0009 | ADJACENT | Instruction-instrument whose compliance nothing verifies. |
| #864, #922, #937, #938, #943, #950, #953, #954, #955, #959, #965 | UNRELATED | Tracker mechanism, dependency advisories, a sub-question, a release task, map tickets, a proposed fix, an enhancement. |

## NOT AN INSTANCE, and which clause each fails

A list that only ever adds is this map's failure wearing the map's own clothes. **Every rejection names the clause**, which is the discipline that keeps a taxonomy from recruiting on resemblance.

- **#960 shellcheck, #961 pip-audit, #962 bandit** fail **clause 1 (exists)**. They look exactly like the class and a collector takes all three. An unadopted tool is *absent*, not dormant: a shopping decision, not a wiring defect.
- **`scripts/cpp-memory`** fails **"is a guard"**. A user CLI installed onto PATH by `ln -sfn`. Not every unrun script is a dormant instrument.
- **Orphaned remote branches** fail **"is a guard"**. `--delete-branch` produces no verdict anyone reads. A silent-failure defect, blindness axis at most.
- **`eli5-core-drift.sh` as a live instance** fails the **supersession exclusion**. This was the hardest rejection: unreferenced, with its own issue, and that issue is one of the two the map rests on. Resemblance was maximal and it is still not an instance.

**The ruling most vulnerable to resemblance is an acceptance, not a rejection** - #871, above, where clause 2 is acknowledged as unestablished. A taxonomy's weakest member should be named by its author.

## What the two-method remedy does not reach

Every specimen this wave produced was caught by **two methods disagreeing**. None was caught by an author checking their own work. "Have two things that can fail independently" is the natural remedy and it covers them.

It does not cover the shape where **nobody consulted the artifact at all.** A session disputed a published comment by arguing from a bare number in terminal output without reading the comment; git agreed with it; it was still wrong. No instrument would have caught that, because independence between instruments says nothing about whether either is aimed at the right object.

A related trap, recorded because it nearly landed twice in one day: a wrong correction was nearly accepted *because it fit* - a miscount, inside a discussion of miscounts, from the session that had caught the previous four. The fit was doing work the evidence should have done.

## Specimen: two correct commands, two different questions

An orphaned-branch census used `git branch -r`; the check was `git ls-remote --heads origin`. **Neither command is wrong.** One answers "what have I cached from any remote", the other "what does origin have", and **nothing in either output says which question it answered**.

Measured in this worktree on `1ba44cb`: `git branch -r` = **72**, `git ls-remote --heads origin` = **66**. Two independent causes at once: 5 stale refs under `refs/remotes/pr/` from a remote `git remote -v` does not list, and 1 symbolic ref (`origin/HEAD -> origin/main`) printed in the same column as real branches. `git fetch --prune` runs correctly and is powerless against the first.

**The gap is a property of the local ref cache, so it differs between checkouts of the same repository at the same commit.** Another session measured 70 where this worktree gives 72. An overcount that is not reproducible across checkouts cannot be caught by comparing notes with a colleague, which is the remedy every other specimen recommends.

## Reproducing this

```bash
python3 docs/research/class-enumeration-2026-09-15/sweep.py            # screening result
python3 docs/research/class-enumeration-2026-09-15/sweep.py --self-test  # break each protection
```

It derives its own universe, resolves the repo root itself, prints coverage denominators, refuses to report when a root set could not be examined, and exits non-zero if any control or mutation check fails. Verified from a clean clone, not only in the session that wrote it.

**A caveat this document owes about itself.** Shipping that sweep as a file a human is told to run makes it AGENT-DOC-ONLY by its own taxonomy - a fifth member of the class counted above. Promoting it to AUTOMATED means a `scripts/` entry plus a test, which is outside the file lane this ticket was granted. Recorded as a question for the map, deliberately not smuggled in.

## What this document does not establish

- **That the instance list is complete.** Axis A cannot see an instance with no issue; Axis B cannot see outside `scripts/`, inside a script, or into host configuration. The `driver=` specimen is proof the first bound bites and that a third method was needed.
- **Any dormancy count.** The screening buckets over- and undercount, in ways named above.
- **That automated dormancy detection is feasible.** Seven rule versions were wrong in both directions, and the errors were found by adversarial review and mutation, not by care. That is this document's most transferable result, and it bears directly on whichever mechanism #950 chooses.
- **Any remediation.** #955 fixes nothing.

# ADR 0010: The bandit LOW band - what was read, what was accepted, and what an unread rule class now does

- Status: Accepted
- Date: 2026-09-20
- Issue: #1114
- Supersedes: nothing
- Related: #962 (the adoption that created this residual, and whose re-decided
  skip list this ADR must not quietly reintroduce), #1113 (the MEDIUM+ residual,
  pinned per finding in `.bandit-audit-allow`, dispositioned in
  [docs/security/bandit-finding-dispositions.md](../security/bandit-finding-dispositions.md)
  - the band above this one, and explicitly not in scope here),
  #972 (the identical shellcheck residual, still undispositioned),
  [ADR 0008](0008-instrument-negative-control-bound.md) (the adoption shape this
  gate inherited), [ADR 0009](0009-oscillation-control.md) (this decision carries
  two of its tells, so it names its reversal trigger below).

## TL;DR

`bandit` gates at severity >= MEDIUM. Below that threshold this tree reports
**138 findings across 41 files in 7 rule classes** (re-measured 2026-09-20 after
merging #1113 and #1041, bandit 1.9.4, 115 tracked `.py` under `lib/` and
`scripts/`, 31,438 loc, 0 scan errors, 0 inline `# nosec`). **All seven classes
were read. All seven are accepted, and no code changed as a result** - the
reading found no site worth altering, which is a result rather than an absence
of one.

The first reading of this band measured 135 findings in 40 files; two sibling
PRs landed mid-review and moved it to 138 in 41, WITHOUT adding a rule class.
That is the ordinary case this decision is built for, and it is recorded rather
than smoothed over: the counts move, the classes are what were read.

The threshold stays at MEDIUM. What changes is that the gate can now tell a rule
class somebody read from one nobody has: each accepted class carries a
`reviewed-low <test-id> <issue>` record in `.bandit-audit-allow`, and a LOW
finding whose class has no record reddens the gate. On the day this landed that
gated **zero** findings.

## Context

Issue #962 adopted bandit with an **empty** skip list, deliberately: the
inherited `--skip B104,B108,B310,B602` from codex-power-pack removes 10 of this
tree's 11 MEDIUM+ findings, so copying it would have silenced exactly the
findings most likely to be real here. The accepted MEDIUM+ residual is recorded
one line per (file, rule) instead, where it is counted and printed on every run.

That left the LOW band. It was counted and printed from the start, so "below the
gate" never read as "not examined" - but nobody had read it, and a total cannot
say so. Issue #1114 is the IOU: a disabled check is invisible and an issue is
not, so the 133 findings of the day were filed rather than skipped.

**Three hardcoded counts for this band already disagreed before anyone read
it**: 133 (issue #1114's body), 136 (`.bandit-audit-allow`'s header), 135 (the
tree that fixed them). None was wrong when written. That is why no count appears
in this ADR outside the dated measurement above, and why the ledger header now
carries a pointer rather than a number: the gate prints the live count and the
per-rule breakdown on every run.

## The dispositions

Every site of every class was read. The evidence is stated per class, because a
count with no reading behind it is a number nobody can act on - and so is a
disposition with no evidence behind it.

### B603 - `subprocess` call without `shell=True` (58 findings, 30 files)

**Accepted.** This is the *safe* form; bandit flags it to ask one question,
which issue #1114 stated precisely: *is argv[0] attacker-controlled?* That is a
much smaller question than 57, and it is answered here rather than asserted.

Answered by walking the AST of every flagged site and extracting the argv[0]
expression, not by reading the diff or grepping - a text search over these files
matches their own documentation, and several of them document `subprocess` at
length. Across all 91 B603+B607 rows, and the rows sum to 91 deliberately:

| argv[0] | n | what it is |
|---|---|---|
| a literal at the call site | 66 | `git`, `docker`, `gh`, `uv`, `aws`, `gitleaks`, `pip-audit`, `tar`, `npm`, `codex` |
| a literal via a list built in the same function, or a module constant | 8 | `_compose_base_cmd` -> `["docker", ...]`, `["aws", ...]`, `["gitleaks", ...]`, `["uv", ...]`, `["pip-audit", ...]`, `GIT_LOG_ARGS`, `PlannedCommand.argv` |
| a `shutil.which()` result | 13 | `curl_path`, `pgrep_path`, `ss_path`, `lsof_path`, `systemctl_path`, and the `git` / `docker` / `uv` / `pip-audit` / `bandit` prefixes resolved the same way |
| a helper's own parameter, every caller passing a literal | 2 | `mcp-drift._run_capture`, `run-delivery-pilots.run` |
| taken from data | 2 | the two below |

**The two that take argv from data, both read:**

- `scripts/check-negative-controls.py:384` - argv comes from each control's
  `control.json` `invocation` array. That file is **tracked in this
  repository**, and anyone who can add one can already add the Python gate it
  invokes; the trust boundary is the repository, not the array.
- `lib/creds/run.py:104` - argv is the user's own command, from
  `secrets run -- <cmd>`. Running the caller's command with secrets injected is
  the entire feature. There is no shell, so an argument containing `;` is an
  argument.

No site builds argv from network input, from an environment variable, or from
an untrusted file. **Nothing to fix.**

The bound, stated rather than left to be discovered: this is a reading of the
tree on 2026-09-20, not a standing property. A future site that builds argv[0]
from untrusted input is a B603 like any other and this ADR will not notice it.
What the ledger record buys is narrower and worth being exact about: it makes a
NEW rule class visible, not a new site of an old one.

### B607 - process started with a partial executable path (33 findings, 18 files)

**Accepted, permanently.** `git` rather than `/usr/bin/git`, 24 times; then
`gh` x2, `aws`, `npm`, `tar`, `codex`. This repository's gates resolve tools
through `PATH` on purpose - the `.ci-bin` staging in `.woodpecker.yml` is built
on exactly that - so absolute paths would break the design rather than harden
it. The `shutil.which()` sites in the B603 table above are the same decision
made explicitly where a resolution failure needs its own diagnostic.

### B404 - `import subprocess` (33 findings, 33 files)

**Accepted, permanently.** One per file that shells out. CPP's product is a
family of helper scripts and gate runners; `import subprocess` is not a finding
about this repository, it is a description of it.

### B105 - possible hard-coded password string (5 findings)

**Accepted. All five are false positives, and that is the finding.** Bandit is
pattern-matching identifier names:

- `scripts/check-negative-controls.py:205` and
  `scripts/pytest-parallel-differential.py:59` - both are `PASS = "PASS"`, a
  verdict vocabulary.
- `lib/creds/credentials.py:199` - `"password": "****"` inside a **masking**
  function.
- `lib/security/explain.py:143,163` - the dictionary keys `HARDCODED_PASSWORD`
  and `HARDCODED_SECRET`, in help text that literally explains what a hardcoded
  password is.

Renaming a verdict constant to satisfy a name matcher would damage the code to
flatter the tool. **Nothing to fix.**

### B107 - possible hard-coded password default argument (4 findings)

**Accepted, same shape as B105.** Every default names a **field**, not a
credential: `password_key: str = "password"` in
`lib/creds/credentials.py:68` and `lib/creds/providers/aws.py:295`, and
`secret_id: str = "DB"` in `lib/creds/__init__.py:123` and
`lib/creds/providers/env.py:171`. **Nothing to fix.**

### B101 - `assert` used (4 findings)

**Accepted - and this is the class the filing expected to yield fixes, so the
reading is given in full.**

`assert` compiles away under `python -O`, which makes an assert that performs
**validation** a real defect and an assert that states an **invariant** a
non-issue. Issue #1114 called the distinction "a real class, and four is a
readable number". It is, and the answer is that all four are invariants:

| site | what it narrows | why `-O` changes nothing |
|---|---|---|
| `lib/security/modules/pip_audit.py:112` | `temporary_requirement is not None` | the same module's `_export_uv_requirements` returns `(None, str)` on every failure path and `(Path, None)` on success; the line above already returned on a non-`None` error |
| `lib/vendor.py:480` | `self.derived_field is not None` | its only caller, `audit()`, returns early when that field is `None` |
| `scripts/mcp-drift.py:919` | `host is not None` | the enclosing `if unreadable:` is `host is not None and ...` |
| `scripts/counter-model-uniformity-check.py:68` | `spec is not None and spec.loader is not None` | `spec_from_file_location` on a literal `.py` path always resolves a loader; a missing file fails later, at `exec_module` |

None validates external input. None is a security boundary. **Nothing to fix**,
and manufacturing two changes in a security module to look thorough would be
worse than the finding.

One bound worth recording, because it is the one that could change: the
`pip_audit.py` invariant is held by a sibling function's return contract and by
mypy, not by the assert. A future `(None, None)` return path would make that
site a real `-O` defect. It is a code-review question about that function, not
a bandit question.

### B405 - `import xml.etree` (1 finding)

**Accepted.** `scripts/pytest-parallel-differential.py:56` - the same file whose
B314 `parse` call `.bandit-audit-allow` already accepts under #1113, for the
same recorded reason: the XML is a JUnit report this repository itself just
produced, so the untrusted-input premise does not hold.

## The decision

### 1. The threshold stays at MEDIUM

Raising it to LOW would fail 41 of 115 files, and 124 of the 138 findings are
B603 + B607 + B404 - the same observation stated three times,
that this repository shells out on purpose, everywhere. A gate that fails
everything on day one is switched off inside a week, which is the oscillation
[ADR 0009](0009-oscillation-control.md) exists to predict, arriving as the
remedy rather than as the problem.

### 2. Acceptance is recorded as a review record, never as a `--skip`

`--skip` is the mechanism #962 measured and rejected, and this issue's
acceptance names it explicitly. The distinction is not cosmetic, and it is worth
stating in the form a reader can check:

| | `--skip B603` | `reviewed-low B603 #1114` |
|---|---|---|
| what it does | removes a distinction bandit could draw | adds one this gate could not draw |
| what it suppresses | every B603 at every severity, tree-wide | nothing - LOW already gates nothing |
| visibility | a flag in a build file | a tracked record, printed every run |
| new rule class | invisible | reported, and reddens |

The seven records live in `.bandit-audit-allow` beside the #1113 `finding`
records. They carry no count, deliberately: a count is what makes a `finding`
line a baseline a new site breaks, whereas a rule class is read or it is not,
and a count here would redden on every ordinary edit that adds a `subprocess`
call while saying nothing about whether anybody read anything.

### 3. An unreviewed LOW rule class reddens the gate

This is the part that outlives the reading. Before it, the band was a single
integer, and an eighth rule class arriving next month and a fifty-eighth finding
of the first class moved it by the same amount. A disposition nobody can check
is the third state this issue's own framing warns about: not a disabled check
(invisible) and not an issue (visible), but a decision recorded where nothing
re-derives it.

It gated **zero** findings on the day it landed: all 138 fall in the seven
recorded classes. Merging #1041 mid-review is the first live test of that - it
added a whole new script that shells out, moving the band by three findings, and
the gate stayed green because those are reviewed classes rather than new ones. It fires when a genuinely new pattern appears - a weak hash,
a `try/except/pass`, an insecure deserializer - and the remedy is to read that
class and add one line, or fix the sites.

### 4. Asymmetry: a record that matches nothing is a NOTE, not a finding

A `finding` record that matches nothing is STALE and reddens, because a
suppression that has outlived its finding is a blindfold nobody re-reads. A
`reviewed-low` record that matches nothing hid nothing, so it prints a note and
exits 0. Reddening there would mean that deleting the last `import subprocess`
in a file turns the build red, which is how a ledger gets switched off.

The asymmetry is pinned by `tests/test_bandit_audit.py`, not by this paragraph.

## The reversal trigger (ADR 0009)

This change carries two of ADR 0009's tells - it adds a ledger mechanism, and it
touches a rationale comment that exists to explain why the threshold sits where
it does - so it names what would move it back, beside the setting rather than in
a PR description:

> **If the unreviewed-rule-class check reds twice on ordinary work and neither
> reading finds anything worth acting on, it drops from a finding to a NOTE** -
> the same treatment the stale record already gets. Two is the number because
> one red is the check doing its job on a genuinely new pattern; a second, with
> both readings empty, is evidence that new LOW classes in this tree are noise
> rather than signal.

What would move it the *other* way - from NOTE back to finding, or from the
MEDIUM threshold down to LOW - is a LOW-band finding that turns out to have been
a real vulnerability. That has not happened; if it does, the reading above is
what was wrong, and it is recorded here so the next person can see which claim
failed.

## What this ADR does not claim

- **Not a per-site review that stays true.** Seven rule classes were read on
  2026-09-20. A new site of an accepted class is accepted without a second
  reading - that is what accepting a class means, and the ledger record does not
  pretend otherwise.
- **Nothing about the MEDIUM+ band.** Those findings are #1113's, pinned per
  finding with their own reasons in
  [docs/security/bandit-finding-dispositions.md](../security/bandit-finding-dispositions.md);
  it closed three of its eleven while this was in review, which is why the
  gate's `accepted` count reads 8 rather than 11.
- **Nothing about `tests/`, `extras/`, or the generated `codex/skills/`
  copies.** The population is `lib/` and `scripts/`, which is #962's scope and
  is printed on every run. Measured 2026-09-20, bandit over `tests/` reports
  9,400 findings, 8,618 of them B101 - a description of a test suite, not a
  finding about one.
- **Nothing about `shellcheck`'s equivalent residual (#972).** Same shape, still
  open, deliberately not resolved by analogy here - the reading is the work, and
  it has not been done for that tool.

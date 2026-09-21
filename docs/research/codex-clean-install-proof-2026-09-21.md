# Clean-install proof: a Codex host reaches CPP's surface and runs a workflow end to end

Issue #1074 (Phase 3, rescoped). Measured 2026-09-21.
Commands and evidence: [`codex-clean-install-proof-2026-09-21/`](codex-clean-install-proof-2026-09-21/).

| Pin | Value |
|---|---|
| CPP source SHA | `71ff29779142a3939ccc08edf12e3d74ccf270d7` |
| codex CLI | `codex-cli 0.155.1` (package `0.155.1-x86_64-unknown-linux-musl`) |
| model | `gpt-6-astra`, reasoning effort `high` |
| bubblewrap | `0.9.0` |
| kernel | `Linux 6.8.0-139-generic` |

---

## What was demonstrated

**One demonstration**, as the rescope requires: a Codex host, from a clean install,
reaching CPP's surface and running a workflow end to end.

Codex, on a host where the CPP checkout is unreachable, read the bundled
`flow-doctor` skill, ran the bundled installer, installed helpers with canonical
digests, and verified them itself. It **invoked** the helper rather than describing
it - which was the outcome most in doubt going in.

The demonstration was run twice and the two runs differ in a way worth stating up
front. Run 1 stayed on the clean host and installed the 3 helpers the bundle carries,
correctly reporting the setup still incomplete at 3 of 26. Run 2 diagnosed the same
gap and then **cloned CPP from GitHub**, installing the full 26 and verifying green -
a more complete workflow, reached by stepping outside the clean-host premise. Both
are reported; neither is presented as the single result.

---

## Why the proof measures an EFFECT, not an artifact

The obvious proof - ask codex about CPP and check the answer - is confounded, and
measurably so. CPP is a public repository and the model knows it in detail.

An arm with **no CPP surface present** named `stash-worktree-guard.sh`. That is a
real script in `scripts/` (25,652 bytes) that is **not** in `flow-doctor`'s
bundle. It did not invent a plausible-sounding filename; it **recalled a real one
that does not belong in that answer**. Any proof resting on the model producing
correct CPP *content* is dead on that measurement alone.

So the proof measures a filesystem effect, and specifically **content digests**:

| Property | Recallable from training? |
|---|---|
| A helper's filename | **Yes** - measured above |
| The set of helpers | Plausibly |
| 79,496 bytes across 3 files, byte-exact | **No** |

### Why the negative arm is not read-only

A read-only negative arm proves only that a crippled arm writes nothing. Both arms
ran with **full write capability** (`--dangerously-bypass-approvals-and-sandbox`,
correct here because bwrap is the external sandbox). The negative arm was free to
write anything at all, including fabricated helpers. What it cannot do is produce
the bytes.

### Why containment comes from bwrap, not from codex

Codex's own `--sandbox workspace-write` restricts **writes**; reads stay broad. An
arm that can read `/home/cooneycw/Projects/claude-power-pack` can simply `cp` the
helpers, and then a filesystem effect proves nothing about whether CPP's surface
was present. Containment therefore has to come from outside codex.

Verified from **inside** the sandbox, by a child process, rather than assumed:

```
HOME                     = /home/clean
~ resolves to            = /home/clean
real checkout readable?  = ls: cannot access '/home/cooneycw/Projects': No such file or directory
real ~/.claude readable? = ls: cannot access '/home/cooneycw/.claude': No such file or directory
real ~/.codex/skills?    = ls: cannot access '/home/cooneycw/.codex/skills': No such file or directory
CPP file anywhere        = (none - searched every mount, not `-xdev`)
```

The first run of that check used `find -xdev`, which skips bind mounts - and the
codex package is a bind mount. It was re-run without it.

---

## The differential

Exactly **one** variable differs: whether `~/.codex/skills/flow-doctor` is present.
Identical sandbox, identical prompt, identical capability. Run **twice**.

> Run the flow-doctor workflow on this machine: diagnose the flow workflow setup and
> install the CPP flow helper scripts into ~/.claude/scripts. Then report exactly
> which files you installed.

### Summary

| | Run 1 | Run 2 |
|---|---|---|
| **positive** (surface present) | 4 files, copied | 29 symlinks, 0 broken, canonical digests |
| **negative** (surface absent) | nothing written | nothing written |
| positive left the clean host? | no | **yes - cloned CPP over the network** |
| IPC errors (harness health) | 0 / 0 | 0 / 0 |

### Positive arm, run 1 - stayed on the clean host

Codex read `SKILL.md`, then `reference.md`, then ran the installer's own `--check`
first (`FLOW_HELPERS: missing`, exit 1 - the correct diagnosis on a clean host), then
invoked the installer:

```
flow-helpers-install: source /home/clean/.codex/skills/flow-doctor/scripts (plugin),
                      target /home/clean/.claude/scripts
flow-helpers-install: 3 helper(s) installed to /home/clean/.claude/scripts
FLOW_HELPERS: installed
```

Effect, measured independently of anything the model said:

| File | Bytes | sha256 | Written by |
|---|---|---|---|
| `flow-helpers-install.sh` | 15,010 | `619666ec2c0b...adea69` | the helper |
| `flow-worktree-claim.sh` | 24,411 | `5b2e977afd79...1ae53a` | the helper |
| `worktree-remove.sh` | 40,075 | `d57ee08d00f1...9edc318` | the helper |
| `hook-mask-output.sh` | 4,537 | `a3af9a07cc69...d0dbb8` | **the model, by hand** |

All three helper digests match the checkout exactly. The fourth is recorded
separately on purpose: `hook-mask-output.sh` is in the bundle but **not** on the
installer's 26-name allowlist, so the helper ignored it and the model installed it
itself with `install -m 0755`. *What the helper produced* and *what appeared* are
not the same set, and a proof that conflated them would be crediting the helper with
a model's initiative.

**It invoked the helper rather than describing it** - the outcome most in doubt going
in.

### Positive arm, run 2 - left the clean host, and that is the finding

Run 2 diagnosed `missing` the same way, and then did something run 1 did not:

```
git clone --depth 1 https://github.com/cooneycw/claude-power-pack.git /home/clean/.claude-power-pack
flow-helpers-install: source /home/clean/.claude-power-pack/scripts (checkout), target /home/clean/.claude/scripts
flow-helpers-install: 26 helper(s) installed to /home/clean/.claude/scripts
FLOW_HELPERS: installed
...
FLOW_HELPERS: ok
```

It fetched CPP from GitHub and installed the **full** 26-helper set from the
checkout, then verified itself green. 29 entries appeared: the 26 allowlisted
helpers, plus `hook-mask-output.sh`, `prompt-context.sh` and `secrets-mask.sh`
installed by the model beyond the allowlist. All 29 resolve; none is broken; the
digests are canonical.

This is a *more* complete end-to-end run than run 1 - it resolved the incompleteness
run 1 only reported. It is also **outside the premise**: a clean host that fetches
the repository is no longer demonstrating that the bundled surface is sufficient.
Both readings are true, and the proof states both rather than picking the flattering
one.

Note the installer's two modes, because the difference misled this investigation
once (see Hazard 3): with a **plugin** source it COPIES, with a **checkout** source
it SYMLINKS.

### Negative arm - both runs

Nothing written. No `~/.claude` at all, either time.

> I couldn't run `flow-doctor`: its workflow and the CPP helper scripts aren't
> present on this machine. [...] **Files installed: none.** Please provide the
> repository URL or local source path [...]

**It did not fabricate, and it did not clone** - in either run, despite full write
capability, network access, and demonstrably good CPP knowledge. It reported absence
and asked for a source.

---

## The confound this proof did NOT eliminate

The digest criterion was chosen because a model cannot reproduce 79,496 bytes from
memory. Run 2 shows it does not have to: **it can fetch them.**

Measured directly, with no model involved, in a sandbox holding **zero** CPP skills:

```
CPP surface present? 0 skills
clone exit: 0
HEAD:       71ff29779142a3939ccc08edf12e3d74ccf270d7
canonical worktree-remove.sh sha from the CLONE: d57ee08d00f108ae
```

An environment with no CPP surface at all obtains the exact digest the proof relies
on. So, stated plainly:

- The containment blocks **filesystem** access to the checkout. It does not block
  **network** access to a public repository, and CPP is public.
- The property the orchestrating design asked for - *writes the model cannot produce
  without the helper* - is therefore **not model-proof**. It is bundle-proof only
  under network isolation.
- The negative arm's emptiness across two runs is an **observation**, not a guarantee
  by construction. Nothing stopped it from cloning; it chose not to, twice.

The honest status: the demonstration of the positive claim (a Codex host reaches
CPP's surface and runs a workflow end to end) **holds**, and run 2 strengthens it.
The *differential* isolation is **weaker than designed**, and closing it needs egress
restricted to the model API only - which this harness does not do, because codex
needs that network to run at all.

## Known-bad inputs, and which are rejected

A proof that only exercises the happy path demonstrates that the happy path exists.
Re-runnable: [`known-bad.sh`](codex-clean-install-proof-2026-09-21/known-bad.sh).

| Input | Verdict | Rejected? |
|---|---|---|
| bundle as shipped (baseline) | `installed`, `EXAMINED: 3` | n/a - good input |
| source directory empty | `unverifiable`, `REASON: empty-source`, `EXAMINED: 0` | **yes** |
| source directory missing | `error`, `REASON: source-dir-missing`, `EXAMINED: 0` | **yes** |
| **bundle TAMPERED** (injected line) | `installed`, `EXAMINED: 3` | **NO** |

The tampered case is the one that matters. Canonical `worktree-remove.sh` is
`d57ee08d00f108ae`; the tampered copy `3b9cf001dddec901`. The installer copied it,
reported `installed`, and the injected line reached `~/.claude/scripts`.

**There is no check that the bundle is AUTHENTIC**, which is not the same as
saying there is no comparison at all - and the difference matters, because a reader
grepping the installer will find one.

`flow-helpers-install.sh:244,321` runs `diff -q "$src" "$dest"`, and
`install-drift.sh:246` runs `cmp -s "$source_helper" "$installed"`. Both compare the
**source against the installed copy**: they answer "is what I installed current with
respect to my source", and they answer it correctly. Neither has any reference for
whether the SOURCE itself is what CPP published. A tampered bundle is therefore
propagated faithfully and then confirmed as up to date - the comparison passes
*because* the tampering was copied through.

No sha256/digest verification exists anywhere in the sync or install path (no
`sha256`, `hashlib`, `md5` in `flow-helpers-install.sh`, `codex-skill-sync.py` or
`install-drift.sh`). `codex-skill-sync.py --check` is a *generation-parity* check of
`codex/skills/` against `.claude/commands/`, both of which live in the checkout, so
it cannot run on a clean host by definition. And `install-drift.sh` is not bundled
in any Codex skill (below), so it is not a fallback either.

Bound on that finding: it says a tampered bundle **on the host** is not detected.
It says nothing about whether a tampered bundle can *arrive* - distribution is
outside this proof.

---

## Coverage: what a clean Codex host actually gets

The installer knows 26 helper names. `flow-doctor`'s bundle carries 3 of them.

```
FLOW_HELPERS_ALLOWLIST: 26
FLOW_HELPERS_EXAMINED:  3
```

Across the union of **all** Codex skill bundles (41 distinct scripts), 22 of the 26
are reachable. Four are in no Codex bundle at all:

- `cpp-commands-link.sh`
- `delegated-run-check.sh`
- `install-drift.sh`
- `lane-serveability-check.sh`

The arm reported this itself - "Bundle contains only 3 of the installer's 26
helpers" - matching the independent measurement.

**`install-drift.sh`'s exit code is NOT the signal here, and cannot be.** It is not
present on a clean Codex host. An absent instrument does not return a passing exit
code; it returns nothing, and nothing must not be read as clean.

---

## Bounds

State these at full width; each is a limit of the proof, not a caveat on it.

1. **This does not cover a user starting from nothing.** Both arms begin with codex
   installed and authenticated, and the positive arm begins with the skill bundle
   **already placed** at `~/.codex/skills/flow-doctor`. How the bundle gets there -
   `codex-skill-sync.py --install`, which requires a CPP checkout - is **NOT RUN**.
   The demonstration starts one step after a real clean install would.
2. **n=2 per arm.** The negative arm refused both times; the positive arm behaved
   *differently* the two times (copy-from-bundle vs clone-then-symlink). Two runs
   establish that the positive path is **not deterministic**; they do not establish
   that the negative arm will always refuse. Neither number is a property.
3. **Containment depends on bwrap, and covers the filesystem only.** A host without
   bwrap cannot reproduce the read isolation, and codex's own sandbox does not
   provide it. Network egress is **not** contained: measured above, any arm can clone
   CPP from GitHub. This is the proof's largest residual.
4. **3-of-26 is `flow-doctor`'s bundle**, not CPP's Codex surface as a whole; the
   union reaches 22 of 26. Neither number is a claim that the 22 are *installable*
   by this installer - it installs only from its own skill's `scripts/` directory.
5. **The tamper finding is about detection on the host**, not about distribution.
6. **A measurement this document was expected to cite could not be located.** The
   working record carried forward a commitment to state "the 401 measurement itself,
   not just its conclusion". All 89 occurrences of `401` in the session transcript
   are UUID fragments; no such measurement exists in it. Rather than reconstruct a
   number, it is recorded here as **NOT FOUND** and is not cited anywhere above.

### NOT RUN

Recorded explicitly, never inferred from a neighbour:

| Cell | Status |
|---|---|
| Codex-only, fresh install, from the bundle alone | **RUN** (run 1; bound 1 applies) |
| Codex-only, fresh install, bootstrapping via network clone | **RUN** (run 2; outside the clean-host premise) |
| Codex-only, update | **NOT RUN** |
| Codex-only, interrupted update -> recovery | **NOT RUN** |
| Codex-only, rollback | **NOT RUN** |
| Claude-only, all four lifecycles | **NOT RUN** |
| Co-installed, all four lifecycles | **NOT RUN** |

The nine-cell matrix these come from was retired with the distribution program
(`807ffa5`) and is annotated as retired in place in
`.specify/specs/codex-consolidation/spec.md`.

---

## Three hazards this proof walked into

Recorded because both produce evidence that looks correct.

### 1. The instrument that named its own bound

`flow-helpers-install.sh` emits `FLOW_HELPERS_ALLOWLIST: 26` beside
`FLOW_HELPERS_EXAMINED: 3`. The verdict line alone says `installed` - which on a
clean host is true of 3 files out of 26 names. The denominator is only in the
adjacent marker.

This is **not** filed as a defect: `.claude/commands/flow/doctor.md:198` and
`codex/skills/flow-doctor/reference.md:195` both instruct the reader to read the
allowlist line alongside any verdict, and `tests/test_flow_helpers_install.py`
asserts `EXAMINED`. The instrument names its own limit and the docs say to read it.
It is recorded because a consumer keying on the verdict alone would still be wrong,
and because the honest version of this hazard is rare enough to be worth pointing at.

### 2. A proof that greps for its expected output matches its own input

Hit twice in one session.

**Once as a false positive.** `grep -c "FLOW_HELPERS:" arm-positive.log` returned
**14**, which reads as heavy helper activity. Twelve of those fourteen were the
installer's own source and doc comment, which the arm had `cat`'d - including
`#   FLOW_HELPERS: ok | installed | unverifiable | missing | stale | error`. Only
two were real output. The count was not evidence; the enclosing lines were.

**Once as a false negative, from the harness.** The first differential run
bind-mounted an Aug-20 `codex-code-mode-host` over the 0.155.1 package's own copy.
The two binaries are version-locked; the IPC frame failed to decode. Both arms
aborted, **both exited 0**, and both reported *"Files installed: none."*

That is byte-for-byte what a real negative result looks like, and **both arms
agreed on it**. Agreement between arms is not evidence when the harness is what
they agree about - N failures where N is everything you ran indicts the runner.

The fix is committed as a control, not a lesson:
[`probe-write.sh`](codex-clean-install-proof-2026-09-21/probe-write.sh) asks codex to
write one file into the same sandbox shape and reports the IPC error count. Run it
before trusting any empty arm. Its expected output is `WROTE` and `0`. Every arm
above ran with `0` IPC errors.

---

### 3. A measurement taken outside the namespace its subject lives in

Run 2's 29 entries were measured from the host. Every one stat'd as broken and hashed
to nothing:

```
sha256sum: .../arm-positive/.claude/scripts/worktree-remove.sh: No such file or directory
  worktree-remove.sh                57  sha256=
```

Read at face value that is a model which fabricated 29 plausible helper filenames and
wrote no bytes - a dramatic finding, and it was reported as one for several minutes.

It was wrong. The installer had installed by **symlink**, with absolute targets into
`/home/clean` - a path that exists only inside bwrap. Resolved from inside, all 29
links are intact and carry canonical digests. The subject was correct; the observer
was standing in the wrong namespace, and got back a confident wrong answer rather
than an error.

Two tells were present and both were briefly ignored: the "sizes" were 53-65 bytes,
which is the length of a path rather than of a script, and the digest column was
**uniformly blank** - a whole column of nothing indicts the instrument, not the
subject.

`run-arms.sh` was fixed to perform its measurement inside the sandbox, to label each
entry `file` or `link`, to print an explicit `broken=` count, and to report any
network-acquired checkout it finds. The committed instrument no longer has the defect
that produced the wrong reading.

---

## Re-running

```bash
D=docs/research/codex-clean-install-proof-2026-09-21
$D/probe-write.sh                 # positive control - MUST print WROTE and 0
$D/known-bad.sh                   # rejection half - deterministic, no model
OUT_DIR=/tmp/proof $D/run-arms.sh positive
OUT_DIR=/tmp/proof $D/run-arms.sh negative
```

Requires `bwrap`, a codex install, and `~/.codex/auth.json`. The arms reach the
OpenAI API and cost real quota; `known-bad.sh` does not.

# ADR 0013: The generated Codex mirrors are build output, not a tracked tree

- Status: Accepted (owner approval of the #1670 plan, 2026-11-11)
- Date: 2026-11-11
- Issue: #1670
- Related: #555 and #556 (the generator and its CI check), #575 (install wired
  into `/cpp:init` and `/cpp:update`), #823 and #1029 (installed-copy drift),
  #1267 and #1408 (mirror attribution and fidelity), ADR 0008 (the
  negative-control bound), cooneycw/skillc#704 (the consumer this changes)
- Consulted: Codex, read-only, as the consumer of these skills
  (https://github.com/cooneycw/claude-power-pack/issues/1670#issuecomment-6802948404)

## The decision, in plain language

CPP's commands are written once, for Claude. A generator turns each one into a
"mirror": a self-contained copy Codex can load, carrying the helper scripts it
needs and a checksum list for them. Until now those generated copies were saved
in the repository beside the originals.

1. **The copies are no longer saved in git.** `codex/skills/` is ignored; only
   its README is tracked. Changing one script changes one file.
2. **They are built when something needs them.** `make codex-skills` builds the
   tree. CI builds it once and every step that reads it waits for that build.
   The test suite builds it once per session.
3. **Installing is where a copy is checked against its source.** `--install`
   builds the skills in a private directory, compares that build with what the
   sources generate, and only then publishes it. Handed a tree that differs, it
   refuses and leaves the host alone.
4. **The drift report builds its own expectation.** `install-drift.sh` compares
   installed skills against a fresh build, not against whatever tree is lying
   in the checkout. If it cannot build one, it says "not checked".

## Why

Measured on `origin/main` at 31fe6a69: 48 scripts had 125 committed copies (334
files across 75 skill directories); in 60 days the `flow-auto` checksum manifest
changed 76 times; 23 of 244 fix PR titles mentioned codex. A forgotten
regeneration cost a full gate cycle. The two PRs merged in the hour after the
issue was filed both rewrote mirrors.

Self-containment is a property Codex needs of the INSTALLED tree. Nothing about
Codex requires the repository to hold the copies, and `SHA256SUMS` is read by
CPP's own `flow-helpers-install.sh`, not by Codex.

## What was rejected

- **Keep the mirrors tracked and regenerate them in one designated commit.** A
  tracked mirror that is allowed to lag its source either fails the parity
  check on every PR in between, or needs that check loosened to compare against
  an older release. The second is the weakening the issue forbids.
- **Symlink the install to the checkout's build tree.** It ties what Codex
  loads to the lifetime and current branch of one checkout.

## Where fidelity is enforced now

| Boundary | Check | Negative control |
|---|---|---|
| `--install` of a named tree | compared against the sources, all families; a difference refuses, exit 1, nothing published | `controls/codex-skill-install-fidelity` |
| bare `--install` | never reads the checkout tree; publishes its own fresh build | `tests/test_codex_skill_sync.py` |
| installed copies on a host | `install-drift.sh` against a fresh generation; `unexamined` when it cannot generate | `tests/test_install_drift.py` |
| generator completeness and determinism | CI `codex-skills-check` on the built tree | the four #1408 controls |

The committed known-bad case alters a bundled script and RECOMPUTES its
manifest line. A tampered file under a stale manifest is caught by the checksum
reader and proves nothing about source parity; an internally consistent tree
that still differs from its source can only be seen by comparing against the
source. The gate at dca1ac6b, the commit before this change, is vendored as the
anchor and is measured publishing the altered bytes.

## Consequences

- **skillc.** `scripts/freeze_cpp_fixture.py` and `scripts/project_init_fixture.py`
  read `codex/skills/` from git at a pinned CPP commit. Pins before this change
  are unaffected. A pin at or after it holds no tree, so skillc must export the
  pin and run the generator (stdlib-only, git-free, and it resolves its root
  from its own location). Tracked as cooneycw/skillc#704. The issue's stated
  assumption that nothing reads the committed mirrors from git was false.
- **A plain `git pull` does not refresh a host.** `~/.codex/skills` is a copy.
  It moves when `/cpp:update` or `make codex-install` runs; the session-start
  notice from `install-drift.sh` remains the signal. No automatic install was
  added.
- **Review.** Generated output no longer appears in a diff. A reviewer who
  wants to read what ships builds it.
- **Left in place deliberately.** `codex-skill-resync.sh`, its control, and the
  mirror-attribution code in `flow-plan-record.py` and `flow-wave-registry.sh`
  still exist. They refresh or describe a tree that is no longer tracked and are
  harmless; retiring them is recorded in the Nit Store.

## Reversal trigger

Re-track the tree (remove the two `.gitignore` lines, `make codex-skills`,
`git add codex/skills`) if a consumer that cannot run the generator needs the
bytes from git and cannot be adapted, or if building at install time proves
unreliable on a supported host. The validated install and the generated drift
expectation are worth keeping either way.

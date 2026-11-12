<!-- flow-run n=1 id=0088c1f587ac4ce897942cc0572cba3d -->
## Run 1 - issue #1715 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1715
- Read at:      2026-11-12T01:50:53Z
- updatedAt:    2026-11-12T01:50:52Z   (context only - moves on comments and labels)
- Body digest:  e651e9d277daecacf472a03da2c1fefeb601d658c21b603be4277bbdf04d75fa   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4722 of 4722 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 4 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
`scripts/codex-skill-sync.py --install` validates a skill tree while ignoring `__pycache__`, then publishes the tree with those directories included, so unvalidated bytes are installed. It also writes only to the default skills directory, ignoring `CODEX_HOME`; its success line names the in-checkout output for a custom root; and since #1679 stopped tracking generated mirrors, machinery and tests written for tracked mirrors are now dead or pin the wrong thing.

## Findings (4)
- [seq 453](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6014950566), 2026-10-06, medium (estimated): Pins on a generated skill's source do not pin the shipped mirror; audit other mirror tests, maybe warn on truncation. Status at origin/main `f63dc946`: Only a flow-check-specific pin was added (#1382); #1390 is a different bug and only references this. No audit of other tests, and --check does not warn on truncation. Mirrors now untracked (#1679), audit still unresolved.
- [seq 564](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6365089958), 2026-10-23, low (estimated): codex-skill-sync.py --install writes only to ~/.codex/skills, ignoring CODEX_HOME and .agents/skills. Status at origin/main `f63dc946`: install_dest_root() at scripts/codex-skill-sync.py:2295 still returns Path.home()/.codex/skills unconditionally. PR #1546 only mentions it as a recorded finding.
- [seq 715](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6804484530), 2026-11-11, medium (stated): codex-skill-sync --install validates trees ignoring __pycache__ but copytree publishes them unfiltered, so injected .pyc passes. Status at origin/main `f63dc946`: codex-skill-sync.py:1938 filters __pycache__ in skill_files only; copytree calls at L2548-2582 have no ignore.
- [seq 717](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6804485160), 2026-11-11, low (stated): codex-skill-sync success line claims both IN-CHECKOUT and codex/skills for temp or custom output roots. Status at origin/main `f63dc946`: codex-skill-sync.py:2059 still prints 'both IN-CHECKOUT'.

## Acceptance
- What `--install` publishes is exactly what it validated; `CODEX_HOME` is honoured or its absence is stated (amended 2026-11-11: met by STATING it); tracked-mirror machinery with no remaining caller is removed (amended 2026-11-11: NOT REPRODUCED, see the note below).
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Amendment, 2026-11-11 (planning run, approved by the wave orchestrator)

Checked against origin/main `3eaf643d`.

- **seq 715: fixed, and narrower than stated.** A bare `--install` builds into a fresh temporary directory, where no `__pycache__` can exist. The hole is on the two paths that name a tree (`--write --install`, `--output-root DIR --install`). The publish step now omits what the check omits.
- **seq 717: fixed.** The success line names the real output root and says "IN-CHECKOUT" only when it is.
- **seq 564: the absence is stated; honouring it is declined here.** `--install` prints one line when `CODEX_HOME` points elsewhere. Actually installing into `$CODEX_HOME/skills` changes the script's declared host writes, which Kyle pins verbatim, so it is an interface change and a feature: recorded at https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6812014902. Installing into `.agents/skills` is declined for the same reason.
- **seq 453: one part fixed, one part declined.** Fixed: a test fails when any command description exceeds the cap without a recorded exemption, so a description can no longer be shortened silently (measured: 55 descriptions, one over the cap, and it is exempt). Declined: the audit of every test that reads command sources. That is 112 test files and a separate job; the other two transformations the comment names (path adaptations and the `SKILL.md`/`reference.md` split) move text without dropping it.
- **Dead tracked-mirror machinery: not reproduced.** Every `def` and module-level constant in `scripts/codex-skill-sync.py` was scanned for a name with no other reference in the script. The one hit, `stale_cpp_checkout_exceptions`, is live: a staleness check on an allowlist, called by `tests/test_codex_skill_sync.py`. Limit of the scan: it finds unreferenced names, not a branch that can no longer be reached.

Parent: #1690 (child of #1673)



<!-- end of body -->

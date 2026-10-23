<!-- flow-run n=1 id=02eea8a1722a456e851f513240c816a7 -->
## Run 1 - issue #1532 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1532
- Read at:      2026-10-23T15:23:47Z
- updatedAt:    2026-10-23T11:44:44Z   (context only - moves on comments and labels)
- Body digest:  78b16743d49cb480bfdf15905e335964121f2c199f1019b7af0a26e6642f1854   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2666 of 2666 (cap 16384)

### Body as read
**Type:** scope:task

## Why

`scripts/check-skill-coverage-map.py`'s axis 1 (content) compares flow-check's current closure against the EVALUATION-BOUND reference committed in skillc's `evals/subjects/cpp-codex-flow-check-ea6dbfa/evidence/inventory.json`. That reference is fixed at the `ea6dbfa` evaluation pin; re-running `scripts/skill-coverage-snapshot.py` against the current repo only refreshes axis 2's baseline (`diagnose.closure_digests`), never axis 1's reference - that needs a genuinely NEW skillc evaluation of flow-check's current content, declared as a new profile directory (skillc's own "re-declares a profile as a new directory when it needs a new pin" convention; `check-skill-coverage-map.py`'s module docstring names this pattern).

Measured on #1496 (2026-10-20), against current main (`c8d9ba94`, after #1497 merged lib/cicd's final state) and the existing `cpp-codex-flow-check-ea6dbfa` profile:
- **axis 1: still stale** - `body_digest differs`, plus ~29 `lib/cicd/*` files removed/changed, `PROVENANCE.md` added, `SKILL.md`/`reference.md` changed. This is unaffected by re-snapshotting; it needs the new evaluation pin.
- **axis 2: now genuinely `broken`**, not just stale/unknown - `skillc profile diagnose` reports `[unresolved-reference] unresolved reference: ~/.qwen/projects` against `codex/skills/flow-check/scripts/counter-model-receipt.py`. That reference is real (a home-relative read at `counter-model-receipt.py:1353`, reached only for a Qwen-Code-delegated receipt) but currently undeclared in the profile - filed separately as [skillc Nit Store #20 comment](https://github.com/cooneycw/skillc/issues/20#issuecomment-6297430101), since the declaration mechanism (`profile.json`'s `unsupported` map) lives entirely on skillc's side.

## Acceptance

- A new skillc evaluation profile exists for flow-check's current content (post-#1497 lib/cicd state), with the `~/.qwen/projects` reference resolved in its `unsupported` map (per the linked skillc nit) or otherwise satisfied.
- `scripts/skill-coverage-snapshot.py flow-check --profile-dir <new-profile>` is run against that profile and current main, and the committed `docs/measurements/skill-coverage/flow-check.json` reports `current` on both axes (or names the real remaining reason if not).
- The `pinned_for` reason on the interim snapshot (#1496) is removed once this lands.

Until this lands, `docs/measurements/skill-coverage/flow-check.json` carries `pinned_for` naming this issue (#1496, then this follow-up).

Related: #1496 (where this pin was applied), #1497 (the lib/cicd closure this profile needs to be taken against), skillc #20 (the unresolved-reference nit).

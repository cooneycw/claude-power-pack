<!-- flow-run n=1 id=23996a41302542b080bb46db5b41b385 -->
## Run 1 - issue #1670 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1670
- Read at:      2026-11-11T17:43:54Z
- updatedAt:    2026-11-11T17:40:23Z   (context only - moves on comments and labels)
- Body digest:  5b2439e1b55feefa956926439e78215c3709c1d2989fb3b63f611e97c24419c8   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1872 of 1872 (cap 16384)

### Body as read
Tier: 2

Source: owner-requested methodology review, 2026-11-11, measured on origin/main at 31fe6a69 against the last commit before 2026-09-12. Owner approved filing.

## Outcome
An ordinary pull request that edits one script should change one file. Today the generated Codex mirrors under `codex/skills/` are committed, so a script edit also rewrites its copies and their checksum manifests, and an installed host drifts whenever the mirrors move (the session-start notice currently reports 30 stale Codex skills on the owner's host).

Measured on origin/main:
- 48 distinct files under `scripts/` have same-named copies under `codex/skills/`, 125 copies in total (334 files across 75 skill directories).
- In 60 days the `SHA256SUMS` manifests changed 76 times (flow-auto), 50 (flow-merge), 43 (flow-finish), 36 (flow-wave), 30 (flow-check).
- 23 of 244 fix PR titles in the window mention codex, 10 mention sha.

## Acceptance
- A decision, recorded where the repo records decisions, on whether the mirrors must be committed at all. If Codex needs self-contained skill directories on disk, that is a constraint on the INSTALLED tree, not necessarily on the repository.
- Either the mirrors are generated at install or release time and no longer tracked, or they are regenerated in one designated step and ordinary PRs do not touch them.
- Mirror fidelity stays gated. Negative control: a mirror that differs from its source is refused, shown by a committed known-bad case.

## Constraint
`make codex-skills` and the mirror-parity half of `make skills-check` exist for reasons (#1408, #1267). Read those before changing the model; do not weaken the fidelity guarantee to get the smaller diff.

## Assumption
That nothing reads the committed mirrors straight from GitHub. cooneycw/skillc pins CPP fixtures containing `codex/skills/` paths, so check that consumer first.


<!-- end of body -->

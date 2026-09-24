# Issue #1236 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1236
- Read at:      2026-09-24T09:43:38Z
- updatedAt:    2026-09-24T09:43:23Z   (context only - moves on comments and labels)
- Body digest:  a829819a66ce89aa2a20fb2f525442645b5a417bd1e3b81923cc88163a1518ac   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2845 of 2845 (cap 16384)

## Body as read
Part of the Codex consolidation epic (Refs #1067, Refs #1076). This is the remaining paperwork before #1076 and the epic can close. The owner approved #1076 on 2026-09-24 (https://github.com/cooneycw/claude-power-pack/issues/1076#issuecomment-5811719107), and #1075 is closed.

## Background

CxPP went private and dormant on or around 2026-09-22. Every criterion in `.specify/specs/codex-consolidation/spec.md` "Dormancy exit criteria" has since been met, **except R6**, but only Q10 is ticked. A checklist nobody ticks cannot be told apart from criteria nobody met.

## 1. R6 - stale references that still describe CxPP as active

The spec criterion: "No documentation, install snippet or example still routes an active flow through CxPP." Two present-tense references remain:

- `codex/skills/README.md:6-8` - "codex-power-pack vendors this source (pull model ...) rather than receiving a push from CPP." CxPP no longer vendors anything. This file is hand-maintained; `scripts/codex-skill-sync.py` does not generate it.
- `docs/skills/common-memory.md:45` - "The machine write/read contract the codex-power-pack telemetry writer targets is ...". The writer is dormant.

Rewrite both as history (past tense, naming the dormancy). Keep the provenance links: the spec explicitly allows historical provenance references.

The other `codex-power-pack` mentions in tracked docs were checked on 2026-09-24 and are already historical (`docs/project-next-provenance.md`, `.claude/commands/project/next.md`, `README.md:142`, ADRs). The implementation should re-run the sweep rather than trust this list.

## 2. Tick the dormancy checklist, with evidence

In `spec.md` "Dormancy exit criteria", tick each met box and add its evidence pointer. A bare tick is not evidence.

| criterion | evidence (measured 2026-09-24) |
|---|---|
| #1069 landed | closed 2026-09-20; drift/re-vendor targets retired (`docs/project-next-provenance.md`) |
| PR cxpp#239 merged | merged 2026-09-22T11:43:21Z |
| closes cite the ruling | 41/41 CxPP closes since 2026-09-21 cite a ruling; 40 cite 2026-09-20, and cxpp#290 (filed after that ruling) cites 2026-09-23 |
| host artifacts uninstalled | `~/.codex/scripts` absent on the owner host |
| no active route (R6) | this issue's part 1 |
| deprecation notice before flip | CxPP README notice dated 2026-09-22 |
| final owner approval | #1076 comment above, 2026-09-24 |

## Acceptance

1. Neither reference above describes CxPP as active. A fresh sweep of tracked docs for `codex-power-pack` finds no present-tense active route. The PR states the sweep command and its result, and names any hit it judged historical.
2. Every dormancy criterion in `spec.md` is ticked, with an evidence pointer on the same bullet.
3. `make verify` passes.

This issue does not close #1076 or #1067; the owner closes those once this lands.


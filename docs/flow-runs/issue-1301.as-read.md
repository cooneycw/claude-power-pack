# Issue #1301 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1301
- Read at:      2026-09-28T13:36:38Z
- updatedAt:    2026-09-27T18:14:04Z   (context only - moves on comments and labels)
- Body digest:  cbaa6656cf3923758ae43e90ba2b7c206052eb02358dba22b617825e9494e120   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1091 of 1091 (cap 16384)

## Body as read
<!-- cpp-learning: 05cd3034ac8fc055f133f207a4598f9568e174f98164c1fb4320857bf0a3e46f -->

## Learning (auto-filed from the CPP friction retro)

flow:auto Step 3 loads the ELI5 gate spec from ~/.claude/skills/flow-eli5/SKILL.md first, then .claude/commands/flow/eli5.md inside the CPP repo. On this host the global skill does not exist, so every run outside the CPP repo falls back to reading ~/Projects/claude-power-pack by hand (skillc flow:auto #3, #78, #26 on 2026-09-26..27). /flow:repair does not install it. Nit-store entry: claude-power-pack#864 comment 5855696730.

**Proposed fix:** Have /flow:repair (or /cpp:update) install the flow-eli5 global skill, and add a flow:doctor check that reports it missing; or make Step 3 name a path that /flow:repair guarantees.

## Provenance
- class: infra_trap / scope: knowledge
- confidence: 0.5
- fingerprint: 05cd3034ac8fc055f133f207a4598f9568e174f98164c1fb4320857bf0a3e46f
- source repo: claude-power-pack

Filed by /self-improvement:retro via the learnings->issue bridge (claude-power-pack #463). See the common-memory ledger for context.

<!-- flow-run n=1 id=c6d7dc52fae24e5d9b2cbb1e72c11638 -->
## Run 1 - issue #1366 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1366
- Read at:      2026-10-04T15:24:52Z
- updatedAt:    2026-10-04T15:09:51Z   (context only - moves on comments and labels)
- Body digest:  9e14d9144c7788f9fcd1aa42293401372f503a5fad4398ab06ec5ed56d4befb4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3733 of 3733 (cap 16384)

### Body as read
Evaluation programme: [skillc #245](https://github.com/cooneycw/skillc/issues/245). Consumers: [skillc #249](https://github.com/cooneycw/skillc/issues/249) and [claude-power-pack #1367](https://github.com/cooneycw/claude-power-pack/issues/1367). Related #951 (historical evidence inventory), #953 (checkable claims), #1084 and #1365. This is a bounded pilot extending existing gate records, not a new telemetry platform or an all-skills rollout.

## Outcome

After `flow-check`, retain a small machine-readable record of what the helpers actually executed so an auditor or CI can inspect coverage and evidence without replaying the agent. Preserve existing human output, authority rules and standalone command behavior.

Existing building blocks at `1e69afb`: `lib/cicd/state.py` step records already carry attempts, exit/status, test counts and coverage; `scripts/flow-plan-record.py` has run identities; `scripts/counter-model-receipt.py` has schema/review/head evidence; security and deployment helpers already emit JSON. Extend these mechanisms, rather than asking the agent to write an authoritative success JSON.

## Acceptance

- [ ] Inventory the pilot's actual execution paths and retain evidence for success, failure, skipped/not-run, unavailable and interrupted completion. State storage and retention explicitly; a temporary resume file is not promised as durable audit history. Write atomically and preserve terminal records across normal cleanup.
- [ ] Bind records to repository identity, worktree, HEAD plus checked dirty-tree/content identity, run/invocation ID, optional parent invocation, skill source/version and helper version. Reuse existing identities when available; standalone flow-check must not need an artificial issue or plan approval.
- [ ] Capture per-check observed status, exit, attempted/completed timestamps, measured population/coverage, skip/error reason and bounded evidence references/digests. Do not convert an unmeasured population to zero or a skipped child to passed. A record emitted after all tool calls failed cannot say successful execution; #1365 owns its separate delegated-run fix.
- [ ] Distinguish helper-observed facts from agent-declared skill context and completion claims. A writable local receipt is inspectable evidence, not tamper-proof attestation; skillc independently observes it and ordinary CI reruns/checks relevant facts under its own authority.
- [ ] Add good/bad/unknown controls: stale HEAD with dirty changes, duplicate/replayed invocation, missing terminal event, stopped aggregate, zero population, unreadable evidence and clean completed run. Validate privacy/redaction with synthetic values; no raw credentials or full arbitrary command environment.
- [ ] Provide one real local pilot artifact and a concise reader example with the exact claim it supports. Cost is bounded file I/O; no model calls, new network telemetry or extra user approval gates. Existing formats have explicit compatibility behavior.
- [ ] Update the canonical `.claude/commands/flow/check.md` route and regenerate the Codex mirror with the existing generator; generated skills remain derived. Do not refactor unrelated skills or force every user to commit run logs.

Proposed approach: a durable summary/envelope over existing gate execution records with a minimal opt-in export path, then decide further emitters from the pilot. Detailed schema ownership must align with [skillc #249](https://github.com/cooneycw/skillc/issues/249); CPP's usage record must remain distinct from skillc's independently assembled evaluation verdict. If implementation grows into a new subsystem, first specify it under `.specify/specs/` per the issue contract rather than stretching this pilot's scope.


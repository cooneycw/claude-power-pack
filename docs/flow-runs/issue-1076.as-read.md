# Issue #1076 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1076
- Read at:      2026-09-24T10:58:40Z
- updatedAt:    2026-09-24T09:43:02Z   (context only - moves on comments and labels)
- Body digest:  4728259114d6a2e1dc07245b06f954733af3ef886d5f6e8775253db472d40dbb   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5643 of 5643 (cap 16384)

## Body as read
> **Realigned 2026-09-20 to the authoritative spec after #1068 landed (`807ffa5`, spec.md "Dormancy exit criteria", plan.md Phase 4).** The owner ruled on 2026-09-20: **CxPP is not deleted and not archived.** It stops being updated and installed, its local folders are uninstalled, and the repository goes **private and dormant**. History, issues, PRs and attribution stay readable at their source. Every reference to "archive" below is superseded by that. Original body preserved. Realigned by the `codex-conversion` wave orchestrator.

## Scope now (Phase 4, second half - the dormancy decision)

**Requires explicit final owner approval.** This is a decision gate, not an implementation: nothing in the wave, the roadmap or any orchestrator ruling gets past it.

Before the flip, in this order:
1. **#1069 must have landed.** `scripts/project-next-vendor.py:90-91` hardcodes the CxPP GitHub URL and `lib/vendor.py` carries no auth handling, so `make project-next-drift` and `project-next-revendor` break the moment the repository is private. This is the hard ordering constraint of the whole conversion, not tidying.
2. Phase 3's clean-install proof (#1074) recorded, with every not-run cell marked not-run.
3. Phase 4a's cutover and reconciliation (#1075) complete and reversible.
4. The dormancy exit criteria in `spec.md` met and checked by name.

## Dependencies now

Depends on: #1075

("Blocked on Q3 and Q7" below is discharged - both ruled 2026-09-20 (Q3: merge cxpp#239 then dormant; Q7: accept-break). The "7 ledger rows, three of them unknown consumer populations" were dispositioned under Q7's accept-break ruling.)

---

## Original body (superseded, preserved)

Fenced so its `Depends on:` and `Blocked on` lines are read as text rather than as live edges - the planner strips fenced blocks before parsing dependencies (#607), and unfenced this body re-blocked the issue on cancelled phases.

```markdown
## Governing specification

Authoritative contract: [`.specify/specs/codex-consolidation/spec.md`](https://github.com/cooneycw/claude-power-pack/blob/main/.specify/specs/codex-consolidation/spec.md) (established by #1068). Governing sections: **Archive exit criteria**.

**Execution phase:** [Phase 7](https://github.com/cooneycw/claude-power-pack/blob/main/.specify/specs/codex-consolidation/plan.md)

Companions: [inventory](https://github.com/cooneycw/claude-power-pack/blob/main/.specify/specs/codex-consolidation/inventory.md) - what exists, at CPP `5ceb966a` / CxPP `681ea26b`; [ledger](https://github.com/cooneycw/claude-power-pack/blob/main/.specify/specs/codex-consolidation/ledger.md) - the disposition of every open obligation; [plan](https://github.com/cooneycw/claude-power-pack/blob/main/.specify/specs/codex-consolidation/plan.md) - phases and serialization; [review](https://github.com/cooneycw/claude-power-pack/blob/main/.specify/specs/codex-consolidation/review.md) - independent review, reviewer identity recorded.

**Blocked on Q3 and Q7**, and by 7 ledger rows - three of them unknown consumer populations that cannot be resolved by reading either repository, only by enumeration on hosts. PR cxpp#239 is unmerged user work and spec B6 forbids losing it. No repository deletion; archival is not erasure.

The spec is referenced, not copied: where it and the text below disagree, the spec is the later and authoritative statement, and the difference is a defect to fix in the spec.

---

Parent migration plan: #1067.

Status: proposed work, not authorization to implement. Before implementation, follow the approved governing spec established by the contract child and link its relevant sections. Existing issue acceptance is not superseded by this ticket.

Depends on: #1075

## Outcome

Retire CxPP as a maintained repository only after the consolidated CPP release and actual migration have satisfied the agreed exit criteria. Retain history and a clear recovery path.

## Acceptance and authority gate

- Re-audit the approved capability/consumer ledger at current SHAs. Every shipped capability has demonstrated replacement or explicitly agreed retirement; every known active consumer has migrated or been explicitly retired.
- Confirm no active CPP/client/CI/install/update path requires CxPP. Historical attribution, immutable release references and archival evidence may remain; do not erase provenance merely to get zero text matches.
- Verify all open issues/PRs have recorded, authorized dispositions and unfinished work has durable owners/destinations. Do not silently close unsatisfied acceptance. Verify Nit Store findings remain accessible and actionable at their maintained destination.
- Verify release/rollback artifacts, documentation, licenses, source attribution, tags, user work and transition results are retained. The agreed observation period has completed without unresolved migration blockers.
- Present the exit evidence and request **explicit final owner approval to archive cooneycw/codex-power-pack**. Filing this issue, approving the plan, or approving a code PR is not that authority.
- Only after approval, publish/verify the final deprecation pointer and perform GitHub archival. Confirm repository read-only state and working destination links; document how to unarchive if rollback needs maintenance.
- Report precisely what changed and what remains. No repository deletion, broad filesystem cleanup or removal of user installation/state/credentials is part of retirement.

The archive operation is intentionally last. A pending future feature can be transferred with authority; a broken shipped consumer cannot be relabeled future work to clear this gate.
```


# Issue #1299 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1299
- Read at:      2026-09-28T10:56:58Z
- updatedAt:    2026-09-27T18:14:00Z   (context only - moves on comments and labels)
- Body digest:  c9d9abbedee70ed8f6a777e2e49f5f4b76f4892cff45e8962af3bb74f0c43142   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1373 of 1373 (cap 16384)

## Body as read
<!-- cpp-learning: ba4b604251d00765bad9e1270c18bba9a973242eb4085c81e4dfc9d96a9663dc -->

## Learning (auto-filed from the CPP friction retro)

In cooneycw/skillc, flow-finish-gate's security_scan blocks CRITICAL on four deliberately planted fake keys (.gitleaks.toml:12 canary, tests/test_leak.py:187/201, ci/secret-scan-control.sh:56). skillc's own gitleaks run with its .gitleaks.toml passes, and those fixtures are negative controls that must exist. The false positive fired 12 times across about 10 flow:auto runs on 2026-09-26..27 (skillc #9, #37, #122, #124, #127, #106, #12, #26 x2, #139, #141, #130). Every run overrode the gate by hand, and a gate everyone routes around protects nothing. Prior nit-store entries: claude-power-pack#864 comments 5847657964 and 5847991522.

**Proposed fix:** Have the security quick scan honour the target repo's .gitleaks.toml allowlist (or run gitleaks with it when present), or accept a per-repo seeded-fixture exclusion file; add a negative control that a real planted key outside the allowlist still blocks.

## Provenance
- class: infra_trap / scope: knowledge
- confidence: 0.5
- fingerprint: ba4b604251d00765bad9e1270c18bba9a973242eb4085c81e4dfc9d96a9663dc
- source repo: claude-power-pack

Filed by /self-improvement:retro via the learnings->issue bridge (claude-power-pack #463). See the common-memory ledger for context.

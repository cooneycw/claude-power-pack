# CPP Project Next Contract Pointer

CPP ships the authoritative codex-power-pack project-next v1.3 engine,
contract, entry point, and fixture corpus verbatim under
`vendor/project_next/`. The pinned upstream commit, upstream MIT license,
contract version, vendoring date, and per-file hashes live in
`.claude/project-next-vendor.json`.

Read `vendor/project_next/docs/project-next-contract.md` for the classification,
ranking, `RecommendationResult`, and JSON I/O contract. `make
project-next-check` verifies the local snapshot offline; `make
project-next-drift` checks upstream main as a fail-open advisory; and `make
project-next-revendor` refreshes the pinned snapshot after review.

CPP's `scripts/project-next.py` is a thin extension boundary around that
unchanged result. It normalizes GitHub-native relationship evidence before the
engine and adds four CPP annotations afterward:

- relationship provenance and confidence, including uncertain documented-text
  fallbacks when native fields do not confirm an edge;
- planning-only routes for the landed Wayfinder map and linked decision IDs;
- spec lifecycle decisions from spec frontmatter, current engine issue
  evidence, and `.specify/graduation-ledger.json`;
- premise-staleness flags for open spec-derived issues whose parent
  specification predates a live architecture decision in the same domain.

These annotations do not replace the engine's `spec_features` field. That field
continues to describe `spec-sync:v1` mapping completeness. Lifecycle is a
separate axis, classified once and shared by brief, compact, and full output.
Missing lifecycle frontmatter means `active`; an absent graduated spec is
expected when its human-approved ledger entry carries tracker or PR evidence.

Premise staleness is likewise a separate axis from ranking. Ranking inputs
describe the issue; a premise flag describes the document the issue was derived
from, and it is emitted as evidence only - it never changes a score, an order,
or a partition. `/flow:eli5` remains the necessity decision point.

This symmetric pull model has a proven inverse in codex-power-pack's
`vendor/claude-power-pack/{PIN,codex-skills.sha256}`: CxPP vendors CPP's Codex
skills, while CPP now vendors CxPP's project-next engine.

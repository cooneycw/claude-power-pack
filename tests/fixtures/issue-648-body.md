## The divergence (found during the #636 flow run)

Two dependency grammars now coexist across the harness pair, and they disagree on edge existence for the same body text:

- **flow-wave-plan.py** (CPP, #607): line-anchored, four keyword forms (`Depends on|Blocked by|Requires|After #N`), comma/`and` lists. No grading, no code stripping, no ranges, three-way classification (startable / blocked / cycle).
- **project-next contract v1.3** (codex-power-pack `docs/project-next-contract.md`, consumed by CPP's `/project:next` since #636): graded phrases (strong - `depends on`/`blocked by`/`Blockers:`/`Prerequisites:` - assert a blocker even with no resolvable ref, producing UNCERTAINTY; weak - `requires`/`needs`/`after`/`follows` - count only with a ref), punctuation/Markdown-emphasis tolerance (`**Depends on:** #12`), dash-ranges (`#369-#371`, >50-issue ranges collapse to the first endpoint), fenced/inline code stripped BEFORE parsing, a fourth `uncertain` class, spec-ledger-first task resolution with duplicate-claim resolves-to-neither.

Concrete disagreement examples: `**Blocked by:** #12` (emphasis) - contract sees an edge, planner does not; a `# runs after #30` line inside a fenced code block - planner sees an edge, contract does not; `Blockers: (none resolved yet)` - contract raises uncertainty, planner sees nothing.

## The decision to make (deliberately NOT presumed here)

This issue is DECIDE-THE-RELATIONSHIP, not adopt-everything. Two live resolutions, either of which its implementer may choose with reasons:

1. **Converge:** wave-lane edge grammar adopts contract v1.3 grammar (or the relevant subset - grading and code-stripping matter for correctness; ranges maybe less for lanes). Cost: planner complexity, cross-repo behavior change (more/different edges). Benefit: one grammar across both harnesses and both consumers; a wave and a next-pick can never disagree about the same body text.
2. **Deliberately distinct:** wave-lane planning (which issues can run CONCURRENTLY without collision) and next-pick classification (which single issue is safe to START) are different questions with different failure costs - a fabricated wave edge freezes an issue (bad), a missed next-pick edge starts a blocked issue (also bad, caught at the gate). If distinct is chosen, the scopes and the reason are documented in both the planner header and wave.md, so the divergence is a recorded decision instead of an accident.

Relevant precedent either way: #607's negative-space rule (prose must never fabricate edges) is non-negotiable in both resolutions; the contract's code-fence stripping directly serves that rule and is the strongest single candidate if partial convergence is chosen.

## Context

- #607 unified CPP's two INTERNAL parsers (planner + next.md DEPENDENCY_MAP) before the contract landed in the loop; #636 then delegated next.md's decision policy to the contract engine, leaving the planner as the wave-lane authority and the fallback path.
- Contract doc: codex-power-pack `docs/project-next-contract.md` (v1.3, CxPP#158/PR#167); planner grammar: `scripts/flow-wave-plan.py` header + `tests/test_flow_wave_plan.py` TestEdgeGrammar.

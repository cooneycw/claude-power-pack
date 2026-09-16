# Domain Docs

How the engineering skills should consume this repo's domain documentation when
exploring the codebase.

This file departs from the skill's default layout in two places, because CPP
already has both artifacts under different names. The existing locations win.

## Before exploring, read these

- **[docs/agents/glossary.md](glossary.md)**: this repo's defined-term glossary.
  It is where a root `CONTEXT.md` would otherwise live. Terms currently defined:
  `instrument` (carrying the ADR 0008 bound), `harness`, `counter-model`.
- **`docs/decisions/`**: this repo's ADRs, numbered `0001-` upward. This is the
  directory the skills' `docs/adr/` refers to. Read the decisions that touch the
  area you are about to work in.
- **[docs/agents/issue-contract.md](issue-contract.md)**,
  [docs/agents/detector-contracts.md](detector-contracts.md), and
  [docs/agents/closing-report-contract.md](closing-report-contract.md) are
  binding contracts rather than glossary entries. Load one when the task touches
  its surface.

Generated Codex mirrors carry their own copies under
`codex/skills/*/docs/decisions/`. Those are mirrors, not separate decisions;
regenerate with `make codex-skills` rather than editing them.

## There is no root CONTEXT.md, and that is deliberate

Do not create one. The glossary at `docs/agents/glossary.md` is the single
source for defined terms, it is already referenced from the CLAUDE.md project
map, and a second root-level glossary would split the vocabulary.

When `/domain-modeling` would add or sharpen a term, it edits
`docs/agents/glossary.md`. When it would record a decision, it writes a new
numbered file in `docs/decisions/`.

## Use the glossary's vocabulary

When your output names a domain concept (an issue title, a refactor proposal, a
hypothesis, a test name), use the term as defined in the glossary. Do not drift
to synonyms the glossary explicitly avoids. `instrument` in particular is bound:
read its ADR 0008 qualifier before asserting anything about negative controls.

If the concept you need is not in the glossary yet, that is a signal: either you
are inventing language the project does not use (reconsider), or there is a real
gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing decision, surface it explicitly rather
than silently overriding:

> Contradicts ADR 0008 (instrument negative-control bound), but worth reopening
> because...

Cite decisions as `ADR NNNN` matching the `docs/decisions/NNNN-*.md` filename.

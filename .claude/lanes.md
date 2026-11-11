# Lanes

Reviewed: 2026-11-11

The routes the same behaviour travels in this repository. A plan answers every
row; the format and the rule are in
[the lanes reference](../docs/agents/lanes.md).

| Lane | Values | How it is exercised |
|---|---|---|
| Checkout | main checkout / linked worktree | Tests build both layouts in a temporary repository. A flow run exercises the linked worktree; the main checkout is exercised by installs and by tests that say so |
| Harness | Claude install / Codex install | `make codex-skills` builds the Codex mirrors and tests check them. A live Codex-driven run is not exercised in CI |
| Driver | `/flow:auto` (Claude implements) / delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`) | The delegated drivers have their own tests against recorded streams. A live delegated run is not exercised in CI |
| Coordination | without Kyle / with Kyle | Without Kyle is what CI runs. The Kyle path is exercised by tests that stub the coordination authority; a live Kyle fleet is not exercised here |
| CI provider | Woodpecker / GitHub Actions / none recorded | Tests feed the helpers recorded output from each provider. This repository's own CI is Woodpecker, so a live GitHub Actions run is not exercised here |
| Project state | a repository that has adopted a feature's file or record / one that has not | Tests build a temporary repository with and without the file. Absence must read as "not adopted", never as an error |

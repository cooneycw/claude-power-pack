# Lanes

Reviewed: 2026-11-13

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
| Toolchain version | CI's pinned uv and Python / the host or container's installed versions | `.woodpecker.yml` pins CI's image; `test_owned_cpp_checkout.py` checks the installed uv's help and both working-directory spellings. CI has no version matrix ([#1788](https://github.com/cooneycw/claude-power-pack/issues/1788)) |
| Clone shape | a full clone with all refs / a fresh or shallow main-only clone | `test_negative_controls_provenance_run.py` exercises fixture-owned full and shallow histories plus a detached, restricted-ref checkout and CI's fetch in CI too. Its separate whole-repository anchor comparison skips shallow or partial checkouts ([#1797](https://github.com/cooneycw/claude-power-pack/issues/1797)) |
| Run location | invoked from the CPP root / from another directory | `test_lane_file.py` exercises repository root, subdirectory and non-checkout callers. Bootstrap's external-cwd path: see [#1803](https://github.com/cooneycw/claude-power-pack/issues/1803) |
| Gate target | CPP itself / a consumer with its own interpreter and PATH | `test_cpp_runner_runtime.py` exercises consumer-owned uv environments on developer hosts only; CI skips its six dual-runtime cases because its image has only Python 3.11. Bare-interpreter/PATH boundary: see [#1801](https://github.com/cooneycw/claude-power-pack/issues/1801). Unlike Coordination, this is whose toolchain runs the steps |
| Wave role state | a fresh role / a released role returning to work | `test_flow_wave_registry.py` exercises registration and release; `test_flow_wave_reregister_review_regressions.py` characterizes legacy released-role reuse. See [#1804](https://github.com/cooneycw/claude-power-pack/issues/1804) |

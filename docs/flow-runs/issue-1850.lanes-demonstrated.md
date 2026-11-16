# Lanes demonstrated - issue #1850

<!-- lanes-demonstrated run=24a6e5c8d5254560a53eeb7bf5977625 plan=a8b43876428d50912683a9530e9dd0165176e7baeaddb533b2192d2e3111c0f3 -->

| Lane | Result | Evidence |
|---|---|---|
| Harness | passed | Claude install: the source command documents and helpers, exercised by the test suite (the installed `~/.claude` links are not exercised before merge); Codex install: `make codex-skills` generated flow-auto with `CHARTER.md` and, after the counter-model fix, bundled `docs/scripts/speckit-context.md` and `docs/scripts/flow-ci-status.md` (links rewritten to `docs/...`, no upstream URL); a live Codex run is not covered |
| Driver | passed | `/flow:auto` and the delegated drivers: `make driver-parity-check` reports ok, 24 items, 72 canonical pairs, 0 missing, after re-anchoring docs/agents/driver-parity.json |
| Project state | passed | a repository that has adopted `update_docs` / one that has not: no command document or generated Codex skill reads the target any more (a grep of `.claude/commands` and `codex/skills` finds only the "no `update_docs` target is run/read" statements and the rationale's history row), so both behave the same; not run against a consumer repository |
| Reader: scripts/codex-skill-sync.py | passed | `make codex-skills` mirrored the charter; `make driver-parity-check` (which builds codex-skills first) passed |
| Reader: skillc contracts | passed | `skillc contracts .` (skillc from ~/Projects/skillc): `CONTRACT flow-auto: GOOD`; negative control: the same charter with one test path pointed at a missing file reports `clause-backed` BAD |
| Reader: CI receipt check (counter-model-receipt.py validate) | passed | tests/test_counter_model_review.py::test_the_TIER_1_DOCS_ONLY_skip_is_written_and_validates (fails on the pre-#1850 writer) and ::test_an_UNLISTED_skip_reason_is_still_refused |

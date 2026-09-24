# Flow run record - issue #1242

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1242
- Base SHA:          5ad99f586e946418086276f45e1b690881ca0f11
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the repository owner, in session, replying "approved" to the Section C report
- Recorded at:       2026-09-24T10:53:48Z

## Section B evidence

- commits since 2026-09-24T10:47:20Z: none globally, and none touching
  scripts/host-surface-observe.py or tests/test_host_surface_observe.py
- merged PRs in the window: #1240, #1237, #1234, #1231 - all merged BEFORE the
  issue was filed and none touching either file
- duplicate / superseding issues: none. Searched "OVERRIDES_CACHE
  host-surface-observe cache" across all states, no hits. #1241 is the sibling
  CI-redness issue with a DIFFERENT cause (the negative-control battery's 120s
  timeout) and is deliberately kept separate.

## Section C - the approved plan

1. `scripts/host-surface-observe.py` - key _OVERRIDES_CACHE on the inputs the cached value is DERIVED FROM rather than on the repo path alone: the repo path plus the contents of GIT_EXEC_CONFIG_NEUTRALISED. A patched table then gets its own entry and cannot collide with the real table's. Production is unchanged - one table means one key, so the same single cache fill as today. _GIT_EXEC_FILTER_RE is the only other derivation input and no test patches it (verified), so the key is complete against the current patching surface.
2. `tests/test_host_surface_observe.py` - the committed red case, self-contained in ONE test rather than relying on two node ids in an order: patch the table empty inside a monkeypatch.context(), call git_exec_config_overrides(REPO_ROOT), let the context restore the table, then assert the real overrides come back carrying core.fsmonitor=false. On the pre-fix code the second assertion fails. Needs @requires_git.
3. `docs/scripts.md` - one bullet in the host-surface-observe section recording the cache-key change and what it does not cover. Named in the plan this time, unlike PR #1238 where the same kind of ledger entry arrived at Step 5 and read as a divergence.

Scope: 3 files, ~40 lines.

Risks:
- THE CHOSEN FIX REMOVES THE CLASS; the two alternatives remove the instance.
  Clearing the cache in an autouse fixture, or inside the two patching tests,
  both leave the trap for the next test that patches the table. Named because it
  is the one real decision here.
- @requires_git MAKES THE CONTROL VACUOUS WHERE GIT IS ABSENT. It skips rather
  than passes, so it never reads as a false green - but its green is evidence
  only on a host with git. Measured: the CI validate container DOES have git
  (absent binaries in pipeline 2629 were curl and ps only, and no skip reason
  names git), so it runs there. The marker's own reason string claiming the CI
  image ships no git is STALE and goes to the nit store, not into this change.
- controls/host-surface-observe/anchors/constructed-blind-covered-by.py CARRIES A
  FROZEN COPY of this cache code with a pinned sha256. It must NOT be updated: an
  anchor is a deliberately blind historical artifact and editing it would break
  the control's demonstration. This change is about caching, not about what the
  gate detects, so the control's discrimination should be unaffected - to be
  CONFIRMED by running the host-surface-observe control, not assumed.
- No material concern about the fix undermining the issue's intent.

# Flow run record - issue #1913

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=990a9d5449ea476f882e97f0f1d7e140 -->
## Run 1

- Run-id:            990a9d5449ea476f882e97f0f1d7e140
- Run-start:         b1cd1f1635a920ba4839097ebfff8977a0bf7dda

- Issue: #1913
- Approval: granted by ch-orch mailbox41087, owner/master priority in41078
- Approver: ch-orch, three-line plan41086 approved as written

### Section A - narrow fix

A helper link install currently replaces a personal regular file and reports
success. Refuse/preserve every existing non-symlink leaf before mkdir/link IO;
retain existing symlinks and absent installs, with exclusive symlink creation
so a race cannot clobber a new personal leaf or follow a new destination directory.
All init/update host-write invocations use the trusted checkout seam, never the
preserved personal installed seam. Local-tier bootstrap must reject a collided
seam before setup. No B2a backend, native execution, release or tag work.

### Section B - evidence and validation

Actual current-main helper reproduced personal regular-file loss with exit0 in
a disposable Make recipe; source/caller lines recorded in issue1913. B2a parked
clean at25783187 on its branch. Priority branch starts currentmain b1cd1f16.
Read real link-into, init/update callers and existing local-tier/caller checks.
Positive reader search found all installed-seam invocations and their exit/status
handlers; tests will execute maintained fences with a hostile personal seam.
The current generator explicitly excludes cpp/init, cpp/status and cpp/update.
Actual make codex-skills produced80 skills and the complete generated member
inventory matched the original baseline exactly (zero deltas). Thus this
priority fix needs NO attributed input delta or parity-test change. Keep every
baseline/generator/parser byte unchanged. B2b must not claim a generated
cpp-update reader exists without separately enrolling that surface.

### Section C - files for priority fix

1. `scripts/cpp-host-write.sh` - refuse non-symlink collisions before mutation, exclusive portable symlink creation, clear PRESERVED failure1; retain deferral3 and existing-link0.
2. `.claude/commands/cpp/init.md` - trusted checkout seam at actual calls, collision summaries, local-tier collision stop before setup; no trust in an executable personal seam.
3. `.claude/commands/cpp/update.md` - same trusted seam route and preserved-collision summaries, no B2b shared-updater wiring or tier upgrade.
4. `tests/test_cpp_host_link_preservation.py` - real helper file/directory/FIFO collisions, absent/CPP/foreign links, no nested-directory write, actual maintained init/update fences and hostile seam never executed; real pre-fix red.
5. `tests/test_cpp_init_local_tiers.py` - extend actual local-tier fence with executable-personal seam negative before configuration.
6. `controls/cpp-host-link-preservation/control.json` - register preservation BADs and real positive matrix with explicit runtime.
7. `controls/cpp-host-link-preservation/run-case.py` - owned fixtures, asserted collision preconditions and actual whole-tree/bytes preservation oracle.
8. `controls/cpp-host-link-preservation/anchors/b1cd1f16-cpp-host-write.sh` - exact historical helper bytes with pinned full SHA, never edited after vendoring.
9. `controls/cpp-host-link-preservation/cases/bad-regular/case.json` - personal regular-file input that old helper destroys and fixed helper preserves/refuses.
10. `controls/cpp-host-link-preservation/cases/bad-directory/case.json` - personal directory input; old helper adds a nested link, fixed helper preserves/refuses.
11. `controls/cpp-host-link-preservation/cases/good-links/case.json` - actual absent, existing CPP-link/source-advance and preserved foreign-link positive matrix.
12. `Makefile` - focused real helper/caller/local tests and control targets; declared project runtime, normal full gate unchanged.
13. `controls/census.md` - add preservation control to existing helper row.
14. `docs/scripts/cpp-host-write.md` - documented preserved collision/refusal and trusted caller route.
15. `changelog.d/1913.md` - concrete data-loss correction and caller behavior.
16. `docs/measurements/1913-helper-preservation.md` - actual red/green, controls, readers/lanes and remaining native gaps, no pending result called passed.
17. `tests/test_helper_orphan_prune.py` - narrow amendment approved mailbox41239: real Step5b reader supplies CPP_DIR and actual checkout seam; assertion follows quoted trusted route, retained removal/absent/deferral/unconfirmed semantics, hostile installed seam not executed.

Scope: 17 paths, including six tiny control/metadata files and a passive511-line
historical anchor. Small helper/caller correction; no unrelated source changes.
Own plan/as-read/lanes and receipt evidence are additional run records.

Risks: check-then-ln-force races; ln following a destination directory; preserved
personal executable seam still being invoked; summaries mistaking a preserved
collision for a missing file; baseline re-pin hiding input changes. Test real
BAD inputs red on main, commit controls with actual old-helper anchor, validate
actual caller fences and generated Codex output, then ch-rev priority review,
receipt and direct supervised gate after df>=25GB and fleet<=2 heavy-lane check.
Fresh review count0, default2passes/thirdwithreason; no inherited B rounds.
PR Closes1913 only; owner/master decide release/tag after merge.

Amendment: mailbox41239 approves one real reader fixture after finish-35637329
failed2tests (13948passed,5skipped). Confirm unchanged product prune semantics
before test edits. Third formal pass has explicit gate-found uncovered-reader
reason, no raised cap. Failed gate remains failed evidence.

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | will test | main checkout / linked worktree: owned ordinary checkout and actual linked issue worktree helper/caller invocation |
| Harness | will test | Claude install canonical init/update fences; Codex install generated output is unchanged and parity rerun, cpp-update is intentionally excluded; no live-model claim |
| Driver | not applicable | /flow:auto (Claude implements) / delegated drivers unchanged; helper and maintained cpp callers only |
| Coordination | not applicable | without Kyle / with Kyle product semantics unchanged; gate uses existing supervisor |
| CI provider | not applicable | Woodpecker / GitHub Actions / none recorded unchanged |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not: absent/CPP-linked and personal regular/directory/foreign-link installs |
| Toolchain version | not covered | CI's pinned uv and Python / host or container's installed versions, no version matrix; portable Python3 symlink syscall rather than platform-specific ln flags |
| Clone shape | will test | a full clone with all refs / a fresh or shallow main-only clone: historical control vendored, attribution source committed; no runtime old-ref dependency in preservation probes |
| Run location | will test | invoked from the CPP root / from another directory using explicit trusted checkout helper |
| Gate target | not applicable | CPP itself / consumer interpreter/PATH routing unchanged |
| Wave role state | not applicable | fresh role / released role registry unchanged |
| Reader: real init/update caller fences | tested against real output | helper's actual preserve/refuse statuses and hostile installed seam, no handwritten successful report |
| Reader: local tier bootstrap/config | tested against real output | actual selected local seam/config fences, collision stops before configuration, no native setup command |
| Reader: independent Codex parity | reader unchanged | actual80-skill output inventory matches original baseline, both independent generators/parsers rerun; cpp-update excluded |
| Reader: existing host-write gates | tested against real output | real maintained documents through existing checker and current counts; no gate relaxation |
| Reader: B2a shared schema/Pi | reader unchanged | parked B2a not in this branch; no neutral updater/Pi changes |
| Reader: Step5b orphan-prune fences | tested against real output | actual checkout helper and CPP_DIR, unchanged removed/absent/deferred/unconfirmed outcomes; fixture cannot execute a personal installed seam |
| Reader: live Claude/Codex instruction following | not covered | executing deterministic fences establishes helper/caller behavior, no native/model run |

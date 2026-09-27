# Issue #1263 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1263
- Read at:      2026-09-27T11:51:21Z
- updatedAt:    2026-09-26T14:12:37Z   (context only - moves on comments and labels)
- Body digest:  7e238c1bc0511f8579cfcdeffe95b4ea201b378a441900239de4b9734b1ab76c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5653 of 5653 (cap 16384)

## Body as read
**Wave W2B**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S2**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S2** install-drift --quiet omits the skipped-package count the hook actually reads (live; related 1028; found during #1034 / PR #1115 (Codex finding))
  - evidence: scripts/install-drift.sh quiet clause list; author-deferred pending #1028 design call
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749511251
- [ ] **S2** ~/.claude/scripts symlinks an undeclared subset of scripts/, colliding with overloaded exit 127 (partially-delivered; related 1060; found during wave codex-conversion, diagnosing shared-checkout drift)
  - evidence: measured now 107 top-level scripts/ vs 93 symlinks (was 95/65 at nit time); of the 5 tools named missing, 4 (checkout-readers.sh, toolchain-provenance.sh, instrument-census-check.py, gate-lib.sh) are now linked, mutation-probe.py still NOT LINKED
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750414917
- [ ] **S2** /cpp:update reports 'model missing' when only the endpoint was unreachable (live; found during /cpp:update v8.0.0 run, 2026-09-22)
  - evidence: .claude/commands/cpp/update.md:963-980 (Tier 6/7 blocks) still run the api/tags model check unconditionally regardless of the preceding api/version reachability result
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5775175918
- [ ] **S2** flow:auto re-syncs Codex mirrors only when base moved, not when a bundled file is edited (live; found during PR #1216 / issue #1192)
  - evidence: .claude/commands/flow/auto.md:774,820-821 and :1361,1405-1406 still nest both codex-skill-resync.sh calls inside the `git rev-list --count HEAD..origin/main -gt 0` block only
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5796792965
- [ ] **S2** cpp:update reports the SHA it pulled, not the SHA it finished on, in a shared checkout (live; found during routine /cpp:update run)
  - evidence: .claude/commands/cpp/update.md:134,270 still capture CURRENT_COMMIT/NEW_COMMIT only around the pull; no later re-read of HEAD before the final report
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5805176605
- [ ] **S3** /cpp:update never prunes a script symlink whose target was deleted upstream (live; related 1198; found during /cpp:update v8.0.0 run, 2026-09-22)
  - evidence: .claude/commands/cpp/update.md Tier 2 refresh loop (~610-620) still only adds; no `find -L ~/.claude/scripts -maxdepth 1 -xtype l` sweep or equivalent prune step found
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5775175704
- [ ] **S3** cpp:update never prunes helper symlinks whose source script was removed upstream (live; found during routine /cpp:update run)
  - evidence: .claude/commands/cpp/update.md Step 5b (L655-690) confirmed add/refresh-only (`for script in "$CPP_DIR"/scripts/*`), no prune half
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5805178758
- [ ] **S3** cpp:update drops the [Conflicting scopes] diagnostic from claude mcp list, missing a split MCP registration (live; found during routine /cpp:update run)
  - evidence: No "Conflicting scopes" or "SCOPE CONFLICT" handling found anywhere in .claude/commands/cpp/update.md
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5805181045
- [ ] **S3** Correction: symlink gap is unreported install staleness, not an exclusion list (partially-delivered; found during codex-conversion wave; cross-wave coordination for cooneycw/kyle#1267)
  - evidence: scripts/install-drift.sh HELPERS_MISSING axis exists (manual check) but is excluded from make verify (Makefile:947) and nothing runs it automatically after /cpp:init or /cpp:update
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750623036
- [ ] **S3** A mirrored source file under scripts/ or docs/ gives no in-file sign that codex/skills/ carries a shadow needing regeneration (live; related 934; found during 934 / PR #1001)
  - evidence: Of 43 mirrored source files, only 1 mentions 'make codex-skills' in its own text (grep -l 'make codex-skills' across docs/decisions and scripts) - unchanged from the reported 1-of-43
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5685525565
- [ ] **S3** eli5-vendor --revendor pins an upstream commit it did not necessarily fetch (two reads of a moving ref) (live; related 1012; found during 1012 / PR #1021)
  - evidence: lib/vendor.py revendor(): revision() (queries commits_api) is called before remote() (fetches raw_url), but remote() still fetches from the moving /main/ URL rather than a SHA-templated immutable URL - the two-read hazard persists
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5697209819

## Negative control (ADR 0008)

An upstream-deleted script whose symlink is still installed must be named AND pruned. Note idx 297: the `-e`/`-f`/`-L` predicate is different on each side, and a committed contract constrains it.

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).

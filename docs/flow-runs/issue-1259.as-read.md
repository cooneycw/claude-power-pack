# Issue #1259 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1259
- Read at:      2026-09-26T16:01:07Z
- updatedAt:    2026-09-26T14:12:32Z   (context only - moves on comments and labels)
- Body digest:  cff8fb13ce1921c94d2f431a5f254ee57f0fa973f60f4f286f2727b2406bd2e2   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 6199 of 6199 (cap 16384)

## Body as read
**Wave W1B**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S1**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S1** check-negative-controls.py scores a crashed/non-executing anchor as a valid 'detected' PASS (live; found during cooneycw/kyle#1233 (promotion-backup enforcement, PR-B))
  - evidence: No good_exit requirement on the GOOD case gates the anchor's blind-miss credit in scripts/check-negative-controls.py's anchor-verification step; a non-zero exit from any cause (including a crash) still reads as 'missed the known-bad input (blind, as required)'
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5775501124
- [ ] **S1** __pycache__ can survive a size-preserving mutation restore, masking a blinded control (live; related 1034; found during #1034 / PR #1115)
  - evidence: tests/test_skills_check.py:12-21 still loads via spec_from_file_location/exec_module (SourceFileLoader, mtime+size cache)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749511941
- [ ] **S1** Red-run procedure vulnerable to a stale .pyc cache when a mutation preserves file size (live; found during issue #1235 / PR #1244)
  - evidence: No PYTHONDONTWRITEBYTECODE/dont_write_bytecode handling found anywhere in scripts/*.py or flow command docs; the described risk (mutant executed as if fixed, or vice versa) directly undermines negative-control evidence in either direction
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5812918841
- [ ] **S1** Shared multi-target recipe is erased when a later rule re-declares one target (live; found during #1162, by counter-model reviewer codex/gpt-6-astra)
  - evidence: lib/cicd/makefile_declaration.py:226 `self.shared[declared[0]] = declared` runs unconditionally for every declaration line, including a later single-target line, overwriting the multi-target group
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5758005186
- [ ] **S2** check-negative-controls.py still conflates "tool absent" and "gate crashed" under one UNSIGNALLED verdict (live; related 977; found during issue #977 / PR #1246)
  - evidence: No tool-absent vs crashed-without-signal DETAIL differentiation found in scripts/check-negative-controls.py; author's own text states #977/PR #1246 covers only lib/cicd test-outcome parsing, not this register
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5813010763
- [ ] **S1** ADR 0008 rows 8 & 14 (class X/G, destructive) have no committed negative control (live; found during owner-requested negative-control regime audit (no issue))
  - evidence: scripts/flow-worktree-sweep.sh and scripts/lane-serveability-check.sh: `grep -c 'NEGATIVE-CONTROL:'` = 0 for both on main (verified 2026-09-26)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741238742
- [ ] **S1** Counter-model parser can't tell a format mismatch from no review, so a real review can be recorded as skipped (live; related #1046, #1049; found during #1056)
  - evidence: scripts/counter-model-receipt.py FINDING_RE (~L99) and cmd_parse (~L604-617) still collapse any non-`### [SEVERITY] title` shape to `unparseable`; .claude/commands/flow/auto.md item 1b/1c still don't quote the findings-format block or distinguish the two cases
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741945325
- [ ] **S1** check-test-binary-guards.py's script-following hop only resolves .sh scripts, missing subprocess-invoked .py scripts that shell out (live; related #1037; found during claude-power-pack#1037)
  - evidence: scripts/check-test-binary-guards.py:289 SHELL_RUNNERS = {"bash", "sh"} only; no handling for `[sys.executable, str(SCRIPT)]` hops. Already caused 3 real tests to ship unguarded and reach CI's git-less image before being caught (claude-power-pack#1037, pipeline 2128)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5745088921
- [ ] **S1** skills-check.py YAML parser accepts frontmatter no real YAML parser can load (live; related 1034; found during #1034 / PR #1115)
  - evidence: scripts/skills-check.py:151 content.partition(":") still splits on first colon only
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749510723
- [ ] **S2** check-test-binary-guards.py misses a conditional guard inside a helper and an allow-annotation on the helper's call line (live; found during PR #1247 / issue #972)
  - evidence: No conditional-guard-inside-helper recognition or per-helper-call-line annotation handling found in scripts/check-test-binary-guards.py
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5813576235
- [ ] **S3** check-test-binary-guards.py misreads hyphenated filenames like git-*.sh as a git invocation (live; related #1056; found during #1056)
  - evidence: scripts/check-test-binary-guards.py:302-305 SHELL_BINARY_RE; reproduced directly (`SHELL_BINARY_RE.search('git-stash-worktree-guard.sh')` matches `git`) 2026-09-26
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5741944483

## Negative control (ADR 0008)

This lane changes the instrument that audits the other instruments, so each fix needs its own red case. An anchor that crashes must score as not detected. A mutation that preserves file size must still be seen, whether through `PYTHONDONTWRITEBYTECODE` or by invalidating the cache. A multi-target recipe that a later rule re-declares must survive. Frontmatter that `yaml.safe_load` rejects must fail `skills-check`. A test that reaches git through a `.py` hop must be flagged.

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).

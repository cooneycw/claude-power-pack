# Issue #1265 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1265
- Read at:      2026-09-28T14:25:27Z
- updatedAt:    2026-09-26T14:12:40Z   (context only - moves on comments and labels)
- Body digest:  0388e23cceb7fcc3c21d6492e3e0b2a1bf6cd771852eebd308be6dbc975a01c6   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3805 of 3805 (cap 16384)

## Body as read
**Wave W3A**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S3**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S3** delegated-run-check.sh errored_tool_calls stops at depth 6, silently reports 0 beyond it (live; related 836; found during 836)
  - evidence: scripts/delegated-run-check.sh:401 `if depth > 6 or not isinstance(...)` unchanged
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5649047297
- [ ] **S3** delegated-run-check.sh reports RECOGNIZED==EVENTS over a payload containing unparseable stderr lines (denominator drops what it couldn't read) (live; found during kyle#1224 (cross-repo, but script is shared in CPP); companion to claude-power-pack#1054)
  - evidence: scripts/delegated-run-check.sh:224-227 comment still states 'EVENTS is the JSON lines parsed' (i.e. only successfully-parsed lines), not total lines in the payload file - unparsed/stderr lines still don't count against the denominator
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5740994440
- [ ] **S3** delegated-run-check.sh --help truncates its header at a hardcoded line 90, hiding Signals/Exit-codes sections (live; found during #1054)
  - evidence: scripts/delegated-run-check.sh:169-171 usage() still `sed -n '2,90p'`; header comment block runs to line 151; "Signals:" at L113 and "Exit codes:" at L141 both past the cutoff (verified 2026-09-26)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743056303
- [ ] **S3** delegated-run-check.sh TOOL_TYPES omits Codex's collab_tool_call/collab_agent_tool_call item type (live; related #892, #836; found during #1054 counter-model review (Codex finding))
  - evidence: scripts/delegated-run-check.sh:294 TOOL_TYPES still lacks collab_tool_call / collab_agent_tool_call; deliberately deferred pending a real multi-agent capture to settle the spelling
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743102323
- [ ] **S3** delegated-run-check.sh (ADR 0008 class G, row 13) has no census-visible negative control despite having pytest-resident ones (live; related #1036; found during #1054)
  - evidence: `grep -n delegated scripts/check-negative-controls.py` returns nothing; census script has no concept of a pytest-resident control
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5743056927
- [ ] **S4** Six mirrored delegated-lane guidance blocks already diverge by one clause (live; related 836; found during 836)
  - evidence: codex/auto.md:464 says 'treating it as a failure'; codex/exec.md:128, gemma/exec.md:218, gemma/auto.md:633, qwen/auto.md:606, qwen/exec.md:202 all say 'making it fatal'
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5649047666
- [ ] **S4** delegated-run-check.sh inline comment misstates pre-fix exit code (says exit 0, measured exit 1) (live; related 892; found during PR #988 / #981)
  - evidence: scripts/delegated-run-check.sh:231 comment still reads 'died on TOOL_ERRORS: unbound variable PART WAY THROUGH the contract...and on main that exits 0' - code itself is correct, only the comment's account of pre-fix behaviour is wrong
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5679524656

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).

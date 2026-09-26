# Issue #1264 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1264
- Read at:      2026-09-26T15:21:43Z
- updatedAt:    2026-09-26T14:12:39Z   (context only - moves on comments and labels)
- Body digest:  7cf572fa6048a9465867939fc64c6b156b1d6e9dfc28cdf0a2830bc252ed85d5   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5016 of 5016 (cap 16384)

## Body as read
**Wave W2C**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S2**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S2** npm_audit.py and gitleaks.py still have the same dormant-instrument shape #1044 fixed in pip_audit.py (live; related 1044; found during 1044)
  - evidence: lib/security/modules/gitleaks.py:52 `result.skipped.append("gitleaks not found")` and npm_audit.py:45,65 `result.skipped.append("npm not installed"/"npm not found")` - both still route a missing binary to skipped rather than UNKNOWN in result.errors, unlike pip_audit.py which now returns 'UNKNOWN: ...' (lines 35,58,61,66,69,85,117-118)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5740654475
- [ ] **S2** Two counter-model receipts exist for one branch; corpus has no per-branch uniqueness (live; related 1028; found during #1028)
  - evidence: scripts/counter-model-receipt.py has no branch-collision refusal in its write path; receipt corpus now 107 files
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749736750
- [ ] **S2** discover() stays scoped to top-level scripts/, cannot widen without also changing the census denominator (live; related 1036; found during #1036 / PR #1124)
  - evidence: scripts/check-negative-controls.py:786 discover() still uses scripts_dir.iterdir(), DISCOVERY_SCOPE constant documents the limit at :735
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749940821
- [ ] **S2** sweep.py --self-test mutates a re-implementation model, overreporting coverage for 2 of 5 protections (live; related 970; found during #970 / PR #1128)
  - evidence: sweep.py's _probe evaluator substitutes inline regex/scan models rather than perturbing real _INTERP/ast dispatch, per author's table (interp/ast UNCAUGHT on real source)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750144884
- [ ] **S2** check-control-ci-deps.py misreads env -u VAR as needing a binary literally named -u (live; found during registering controls/flow-vantage, issue #959 / PR #1130)
  - evidence: scripts/check-control-ci-deps.py:543-564 invocation_command only skips env and VAR=VALUE tokens, not option flags like -u; returns Path("-u").name
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750218584
- [ ] **S2** flow-finish-gate controls' GOOD cases depend on the developer's ambient branch/receipt state (live; found during #1084 half A)
  - evidence: scripts/flow-finish-gate.sh:476 `git rev-parse --abbrev-ref HEAD` resolves the calling process's cwd repo; controls/flow-finish-gate*/cases/good-all-green has no isolated .git/receipt context, so the GOOD case still inherits the real branch
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5767810443
- [ ] **S2** Negative-control harness resolves the ADR at a hardcoded path; a repo filing it elsewhere gets UNIVERSE: unknown forever (live; found during auditing control registration in cooneycw/kyle, wave kyle-improvements)
  - evidence: scripts/check-negative-controls.py:561 `ADR_0008 = Path("docs/decisions/0008-instrument-negative-control-bound.md")` is a single hardcoded path with no candidate-list or content-based fallback
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5775478579
- [ ] **S2** Negative-control harness cannot register a gate that isn't a top-level scripts/ file (live; found during orchestrating wave kyle-improvements; kyle#1318 parked pending this)
  - evidence: scripts/check-negative-controls.py discover() (:783-793) only iterates `root/scripts` top-level files; evaluate()'s adjacency rule (:1090-1095) still requires the registration to live next to the gate file, so a Makefile-target gate is uncountable
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5776090109
- [ ] **S2** AGENTS.md's Codex-specific facts have no behavioural fixture, unlike CLAUDE.md (live; found during reviewing PR #1156 / #1071, codex-conversion wave)
  - evidence: tests/fixtures/claude-md-obligations.fixture has no AGENTS.md entries; no reference to AGENTS.md found in scripts/check-claude-md-behavior.py or any *fixture* file
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5751638070

## Negative control (ADR 0008)

Apply #1044's `pip_audit` fix shape and its control to `npm_audit` and `gitleaks`: with the binary absent, each must report unknown, not clean.

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).

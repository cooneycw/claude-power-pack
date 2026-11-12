<!-- flow-run n=1 id=c0042c9c274e4e90b299a0380b4fa6dc -->
## Run 1 - issue #1719 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1719
- Read at:      2026-11-12T01:07:57Z
- updatedAt:    2026-11-12T00:54:39Z   (context only - moves on comments and labels)
- Body digest:  f7f893b959671d692984fb157f013ea4d059c1475dbe426927459ac481b4c43b   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5406 of 5406 (cap 16384)

### Body as read
Tier: 3

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 11 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
Eleven small accuracy items with no shared component: prose and docstrings that still point at a retired location (the census inside ADR 0008, per-script prose in `docs/scripts.md`, a retired playwright server), two project-next items (ordered child prose is not turned into dependency edges; the contract version literal is repeated in about nine places), `stash-worktree-guard.sh` refusing a pack-refs transaction on git 2.56 with a misleading message, and three checker edge cases.

## Findings (11)
- [seq 565](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6368427096), 2026-10-23, low (estimated): check-skill-coverage-map.py without --advisory exits 1 whenever unmapped skills exist. Status at origin/main `f63dc946`: _say() still sets any_problem for every state != current, including 'not evaluated' (lines 430-446). CI passes --advisory so nothing gates.
- [seq 573](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6390310736), 2026-10-24, low (estimated): check-behavioral-eval.py module overview lists cross-trial receipts as unchecked though _validate_bundle checks them. Status at origin/main `f63dc946`: Docstring lines 28-37 still say cross-trial receipts are NOT checked; the INSTALLATION_RECEIPT cross-trial loop exists (~line 679-697). PR #1556 left it unchanged.
- [seq 627](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6473465515), 2026-10-28, low (estimated): .agents/CODEX_SETUP.md still tells users to register retired playwright-persistent server (8081). Status at origin/main `f63dc946`: CODEX_SETUP.md lines 39,47,56,64 still name playwright-persistent and port 8081 on current main.
- [seq 660](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6637162524), 2026-11-04, low (estimated): stash-worktree-guard.sh refuses pack-refs ref transaction on git 2.56 with misleading 'git stash push' message. Status at origin/main `f63dc946`: Hook lane (lines 432-460) keys on refs/stash creation only; no pack-refs discrimination; script unchanged since #1143.
- [seq 661](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6638290079), 2026-11-04, low (estimated): speckit-tasks-to-issues placeholder refusal checks task line only; stub spec.md placeholders reach issue body. Status at origin/main `f63dc946`: The placeholder refusal from #1623 was reverted by #1625; no 'placeholder' check exists in scripts/speckit-tasks-to-issues.sh. Underlying stub-spec leak remains unguarded but the named code is gone.
- [seq 662](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6706194135), 2026-11-07, low (estimated): project-next classify.py does not turn a tracking issue's ordered child prose into dependency edges. Status at origin/main `f63dc946`: classify.py:258-259 still only handles checklist lines in issues titled wave/phase/epic/parent; #1627 explicitly deferred it.
- [seq 675](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6725320176), 2026-11-08, low (estimated): host-surface-check.py:53-76 and host-surface-observe.py:5-8 docstrings say every declaration is authored, none observed. Status at origin/main `f63dc946`: Docstrings still say 'No declaration is observed yet' while cpp-host-write.sh:18 etc. carry certified=observed.
- [seq 687](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728785534), 2026-11-08, low (estimated): check-negative-controls.py --verify-provenance KeyError 'sha' on anchor with unknown kind and no sha/origin. Status at origin/main `f63dc946`: check-negative-controls.py:2644 only skips kind=synthetic or sha in (0000000,n/a,''); a missing sha (get->None) falls through to anchor['sha'] at L2663 -> KeyError.
- [seq 711](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6800522335), 2026-11-11, low (stated): project-next contract version literal repeated in ~9 places, so any engine fix costs a bump across 15 files and a missed site. Status at origin/main `f63dc946`: CONTRACT_VERSION '1.9' still restated in tests/project_next/test_output_contract.py:33 and tests/test_project_next_preflight.py:78 plus goldens.
- [seq 724](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6806174704), 2026-11-11, low (stated): Stale prose still places instrument census inside ADR 0008 (shared-stash-stack.md, Makefile, .woodpecker.yml, docstrings). Status at origin/main `f63dc946`: shared-stash-stack.md:209, Makefile:674,687, .woodpecker.yml:244,467 still say ADR 0008's census.
- [seq 729](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6807165176), 2026-11-11, low (stated): Script and test comments still cite docs/scripts.md as home of per-script prose after #1672. Status at origin/main `f63dc946`: mutation-probe.py:230, bandit-audit.py:128, flow-wave-registry.sh:1211 still cite docs/scripts.md.

## Acceptance
- Each item is fixed or declined here with a one-line reason.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

Parent: #1690 (child of #1673)


<!-- end of body -->

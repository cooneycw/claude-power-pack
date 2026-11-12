<!-- flow-run n=1 id=bad17c9042764f0f9420b54594fba851 -->
## Run 1 - issue #1712 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1712
- Read at:      2026-11-12T05:33:17Z
- updatedAt:    2026-11-11T23:07:39Z   (context only - moves on comments and labels)
- Body digest:  ccc7670cbc4d0ef974983f22c96f4e5e02bafe26332795528e5ba6ef4b1fd822   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 6601 of 6601 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 13 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
Findings about what CPP generates for other repositories. Generated GitHub Actions workflows pin old action majors and one moving ref; the generated gitleaks step loads the scanned repository's own config, so a pull request can allowlist its own leak; the enrolment pin is not checked reachable from CPP main; `ci-stage-jq.py` downloads jq on every run with no cache; and scaffolded deploy targets, and `/flow:deploy`'s own log line, report success having deployed nothing. Plus three small `lib/cicd/doctor.py` and pipeline-comment items.

## Findings (13)
- [seq 643](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6544759452), 2026-10-31, medium (estimated): Scaffold deploy targets (python-uv.mk, django, lib/cicd/makefile.py) echo TODO and exit 0, read as deployment success. Status at origin/main `f63dc946`: python-uv.mk:38-42 and lib/cicd/makefile.py:388-389 still emit echo-only deploy; flow/deploy.md still treats exit 0 as deployed.
- [seq 644](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6544759692), 2026-10-31, medium (estimated): flow/deploy.md Step 6 logs $? after mkdir, not the deployment status. Status at origin/main `f63dc946`: deploy.md lines 183-194: fallback make then Step 6 'mkdir -p .claude' then echo ... $? >> deploy.log; still present.
- [seq 684](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728376667), 2026-11-08, low (estimated): lib/cicd/doctor.py lane_row requested-is-not-True guard has no test; deleting it leaves tests green. Status at origin/main `f63dc946`: Guard at doctor.py:87 still present; test_malformed_lane_evidence_never_green has no case with explicit requested False. Did not mutation-run it.
- [seq 685](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728376860), 2026-11-08, low (estimated): doctor.py _posture_fact replaces derive failure reason with fixed string, so user cannot tell why derivation failed. Status at origin/main `f63dc946`: doctor.py:238 still returns fixed 'PR check population not derivable from inspected pipeline shapes' reason.
- [seq 686](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728623706), 2026-11-08, low (estimated): Infra CI generators (GHA, Woodpecker) lack PR-time enrolment check because workflows are path-filtered; infra-only repos unenrolled. Status at origin/main `f63dc946`: grep for enrol in lib/cicd/infrastructure.py finds nothing; scoping decision recorded, gap still present.
- [seq 688](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728957839), 2026-11-08, medium (estimated): Generated-CI enrolment pin not checked reachable from CPP main; cpp_revision can be unmerged/unpushed commit. Status at origin/main `f63dc946`: No ancestor/merge-base/origin-main check in lib/cicd/enrolment.py or scripts/cpp-install-receipt.py.
- [seq 694](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6729905240), 2026-11-09, low (estimated): generate_github_actions emits runs-on ubuntu-latest for every framework while PowerShell matrix advertises windows-latest. Status at origin/main `f63dc946`: pipeline.py:192 hardcodes runs-on ubuntu-latest; L48 PowerShell matrix still lists windows-latest.
- [seq 695](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6730203811), 2026-11-09, low (estimated): infrastructure.py emits actions/checkout@v4 (moving ref) for plan/apply jobs. Status at origin/main `f63dc946`: infrastructure.py:614 and :633 still emit actions/checkout@v4.
- [seq 697](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6730800818), 2026-11-09, medium (estimated): Generated GHA templates pin old node20 action majors, no version comments on SHA pins, uv 0.9.7 old. Status at origin/main `f63dc946`: lib/cicd/actions.py pins SHAs with no vX.Y.Z comments; docstring says v4/v5 majors; UV_VERSION still 0.9.7.
- [seq 698](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6730801015), 2026-11-09, low (estimated): Generated consumer gitleaks full-history scan required check has no documented adoption path (baseline, allowlist) for existing repos. Status at origin/main `f63dc946`: No baseline-path or .gitleaksignore guidance found in docs or cicd commands (grep).
- [seq 699](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6731305194), 2026-11-09, medium (estimated): Generated gitleaks scan auto-loads scanned repo's own config, so a PR can allowlist its own leak; undocumented. Status at origin/main `f63dc946`: Woodpecker step uses repo-local config if present (pipeline.py:453-457); no pinning or documentation found.
- [seq 704](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6733065203), 2026-11-09, medium (estimated): ci-stage-jq.py downloads jq from GitHub releases every CI run with no cache or mirror; 504s block all pipelines. Status at origin/main `f63dc946`: JQ_URL fetch still direct with sha256 check only; no cache or mirror in ci-stage-jq.py; last changed #1465.
- [seq 721](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6805519007), 2026-11-11, low (stated): Comment above claude-md-budget-check in .woodpecker.yml merges text from host-writes step. Status at origin/main `f63dc946`: That step's comment is now clean (L549), but the host-writes comment (L431) still sits above cpp-init-promises-check, with cpp-host-writes-check at L458: comments still misattached nearby.

## Acceptance
- A generated secret scan cannot be weakened by the change under scan; a scaffold deploy target that does nothing does not exit 0 silently; `/flow:deploy` logs the deployment's status; the remaining items are fixed or declined here.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Constraint
Freeze (#1673): fixes only, no new feature under `scripts/flow-*`, `.claude/commands/flow/`, `lib/cicd/` or `.claude/commands/cicd/`. Owner ruling 2026-11-11 (#1673): output that kyle or skillc read (verdict lines, markers, exit codes, helper arguments) stays as it is by default; a change to one needs a coordination issue in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate before the PR merges.

Parent: #1690 (child of #1673)


<!-- end of body -->

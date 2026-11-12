<!-- flow-run n=1 id=c7ffc866a0c04add95a7a5cadf1e9811 -->
## Run 1 - issue #1711 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1711
- Read at:      2026-11-12T05:49:38Z
- updatedAt:    2026-11-11T23:07:38Z   (context only - moves on comments and labels)
- Body digest:  da95d9aec6e476892b781e688435c513ab9df048559ba6b53ca18215295f3a31   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4690 of 4690 (cap 16384)

### Body as read
Tier: 3

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 8 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
Eight small defects in `scripts/flow-ci-status.sh` and `lib/cicd/flow.py`: a network failure inside a commands step is classified as a code failure; a stale stall check carries over between polls; an attribution check that cannot fail; a pre-set backend variable bypasses recorded-provider dispatch; a classic-protection 404 is read as no rule; an explicit fallback probe exits 0 on `unknown` against the header's contract; a multi-line step error splits into a bogus failed step; and two wait exit codes are undocumented. Also still open from #1687: a PR number passed as the ref is not refused by name.

## Findings (8)
- [seq 431](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5913666455), 2026-09-30, low (stated): flow-ci-status.sh FLOW_CI_FAILURE_ORIGIN reports code for apt-get network failure inside commands step. Status at origin/main `f63dc946`: failure_origin() in scripts/flow-ci-status.sh:317-335 only treats clone type or exit 75 as precode; an apt-get timeout in a commands step still reads code
- [seq 613](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6442730809), 2026-10-27, low (stated): flow-ci-status.sh --wait: stale FLOW_CI_STALL_CHECK carries over from an earlier poll. Status at origin/main `f63dc946`: STALL_CHECK initialized once (line 270) and set inside wp_stall_check only; the wait loop (line ~730) does not reset it per poll.
- [seq 679](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728028088), 2026-11-08, low (estimated): lib/cicd/flow.py:244 FLOW_CI_PROVIDER == [name] attribution check cannot fail; PROVIDER initialised from lane name. Status at origin/main `f63dc946`: flow-ci-status.sh:248 PROVIDER=${CPP_FLOW_CI_BACKEND:-none}; flow.py:256 compares against lane name, so check is tautological.
- [seq 680](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728028251), 2026-11-08, low (estimated): Pre-set CPP_FLOW_CI_BACKEND / CPP_FLOW_PR_WATCH_BACKEND bypasses recorded-provider dispatch. Status at origin/main `f63dc946`: flow-pr-watch.sh:213 dispatches only when backend var empty; flow-ci-status.sh uses the var directly (248, 774); not made internal.
- [seq 682](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728028621), 2026-11-08, low (estimated): flow-ci-status derive_event reads protection with 2>&1 and treats classic 404 as no rule. Status at origin/main `f63dc946`: flow-ci-status.sh:472 and 480 still use 2>&1 and line 474 matches (HTTP 404); flow.py:326-329 same assumption.
- [seq 683](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728028849), 2026-11-08, low (estimated): flow-ci-status.sh explicit --fallback-provider-probes exits 0 on unknown, contradicting header contract that unknown exits 2. Status at origin/main `f63dc946`: Header still says unknown exits 2; exit 0 at end of verdict path unless --wait (L393-406) or --exit-code; fallback mode not special-cased.
- [seq 727](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6807024791), 2026-11-11, low (stated): flow/auto.md and merge.md do not document flow-ci-status --wait exits 2 and 5. Status at origin/main `f63dc946`: No mention of exit 5 or expired wait exit in auto.md around wait recipes (L1046) or merge.md L144.
- [seq 736](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6808882069), 2026-11-11, low (stated): flow-ci-status.sh Woodpecker failed-step jq pipe-delimited read splits a multi-line step error into a bogus step, giving origin unknown. Status at origin/main `f63dc946`: flow-ci-status.sh:767 still emits name|type|exit|error per jq line read with IFS='|'; no newline escaping.

## Acceptance
- Each finding is fixed with a case in `controls/flow-ci-status*` or a unit test, or declined here with a reason.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Constraint
Freeze (#1673): fixes only, no new feature under `scripts/flow-*`, `.claude/commands/flow/`, `lib/cicd/` or `.claude/commands/cicd/`. Owner ruling 2026-11-11 (#1673): output that kyle or skillc read (verdict lines, markers, exit codes, helper arguments) stays as it is by default; a change to one needs a coordination issue in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate before the PR merges.

Parent: #1690 (child of #1673)


<!-- end of body -->

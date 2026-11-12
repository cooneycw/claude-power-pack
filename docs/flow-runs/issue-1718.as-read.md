<!-- flow-run n=1 id=1bc8b0b82a714fb7906ea5d1426e542d -->
## Run 1 - issue #1718 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1718
- Read at:      2026-11-12T05:13:48Z
- updatedAt:    2026-11-12T04:54:15Z   (context only - moves on comments and labels)
- Body digest:  078d618f0cc11d3e8255c4396b017a1ad2c17ad44717568e356361efac7708e8   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5810 of 5810 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 12 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
Tests that fail for reasons other than the code under test. Several flake under parallel or CI load (`test_coordination_signal_preserves_queue` twice, the `flow-ci-status-stalled` control twice, two negative-control tests, one shared-`/tmp` snapshot). Others depend on a fact nothing declares: CI runs as root, which voids every chmod-based negative fixture there; two tests need a Python 3.11 interpreter their skip guards do not mention. Two have a predicate too loose to fail.

## Findings (12)
- [seq 247](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750716618), 2026-09-20, medium (estimated): CI runs as root and nothing declares it; chmod-based negative fixtures are void in CI. Status at origin/main `f63dc946`: No CI_RUNS_AS_ROOT fact or euid conftest guard found (grep scripts/check-test-binary-guards.py, tests/conftest.py, .woodpecker.yml); check-negative-fixture-preconditions has no root handling.
- [seq 548](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6295829389), 2026-10-20, low (estimated): test_an_untracked_control_file_refuses_the_green flaked in CI; hold-budget message looks inconsistent. Status at origin/main `f63dc946`: tests/test_negative_controls.py:1251 message still prints 'own 30s bound' with 'killed after remaining' value; no fix in git log; flake cause unexamined.
- [seq 550](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6296001550), 2026-10-20, low (estimated): Follow-up: restarted pipeline passed on same commit, so flake is load-dependent. Status at origin/main `f63dc946`: Follow-up evidence to seq 548; same flake, no fix landed.
- [seq 620](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6468237499), 2026-10-28, low (estimated): test_step9_verify_executes.py needs a Python 3.11 interpreter but its guards and quickstart do not say so. Status at origin/main `f63dc946`: Skip predicate is still uv/bash only (lines 37-40) and the subprocess pins 3.11 with UV_PYTHON_DOWNLOADS=never; README mentions the requirement but observed after #1579.
- [seq 621](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6468834555), 2026-10-28, low (estimated): tests/test_silent_test_success.py:118 skipif guards only bash and uv but runs finish helper needing installed Python 3.11. Status at origin/main `f63dc946`: skipif at line 117-120 still checks only bash/uv; same for test_step9_verify_executes.py skipif. Cited #1632 only provisioned 3.11 in its own environment.
- [seq 624](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6470509740), 2026-10-28, low (estimated): test_delegated_lane_failure_detection.py:203 capture-tail predicate accepts previous line merely containing the CLI binary word. Status at origin/main `f63dc946`: _capture_tail still returns previous.endswith('2>&1') or binary.split()[0] in previous (line ~193); #1597 explicitly recorded it separately, not fixed.
- [seq 668](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6711969677), 2026-11-07, low (stated): test_no_heredoc_inside_a_command_substitution regex cannot cross newline, misses DERIVED="$(\n python3 <<'PYEOF'". Status at origin/main `f63dc946`: tests/test_hook_permission_census.py:414-421 regex still [^()\n]-based, single-line.
- [seq 677](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6726280210), 2026-11-08, low (stated): controls/flow-ci-status-stalled bad-past-timeout intermittently reported BLIND once in Woodpecker pipeline 3553. Status at origin/main `f63dc946`: Seen once, unreproduced; control still exists and cause not established. Not investigated further (could not reproduce here).
- [seq 693](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6729574217), 2026-11-09, medium (estimated): tests/test_gh_pr_merge.py coordination_signal_preserves_queue test flaky under CI load: no gh calls recorded. Status at origin/main `f63dc946`: Test still present at test_gh_pr_merge.py:4119 and unchanged in cause; no issue found tracking it.
- [seq 696](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6730242004), 2026-11-09, medium (estimated): Intermittent BLIND recurrence of controls/flow-ci-status-stalled bad-past-timeout case under CI load. Status at origin/main `f63dc946`: Control already injects FLOW_CI_NOW via run-case.sh, yet comment reports flake; run-case.sh unchanged since #1653. Cause not established; no tracking issue found.
- [seq 703](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6732902658), 2026-11-09, medium (stated): Recurrence of flaky test_coordination_signal_preserves_queue test ([unknown] param) on PR #1666. Status at origin/main `f63dc946`: Duplicate of seq 693; same test still present and unfixed.
- [seq 733](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6808628818), 2026-11-11, low (stated): test_a_refused_review_leaves_no_diff_file_behind snapshots shared /tmp so a neighbour's file reads as its leak (flaky under xdist). Status at origin/main `f63dc946`: Test still globs shared /tmp/codex-review-diff.*.patch before and after (L104-107).

## Acceptance
- Each flaky test has an identified cause and a fix, or is quarantined with its reason; the root-in-CI fact is declared and chmod-based fixtures assert their precondition.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

Parent: #1690 (child of #1673)


<!-- end of body -->

<!-- flow-run n=2 id=510dae0f52144152ab0e1e7ec3f29ac1 -->
## Run 2 - issue #1718 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1718
- Read at:      2026-11-12T07:43:32Z
- updatedAt:    2026-11-12T07:42:48Z   (context only - moves on comments and labels)
- Body digest:  078d618f0cc11d3e8255c4396b017a1ad2c17ad44717568e356361efac7708e8   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5810 of 5810 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 12 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
Tests that fail for reasons other than the code under test. Several flake under parallel or CI load (`test_coordination_signal_preserves_queue` twice, the `flow-ci-status-stalled` control twice, two negative-control tests, one shared-`/tmp` snapshot). Others depend on a fact nothing declares: CI runs as root, which voids every chmod-based negative fixture there; two tests need a Python 3.11 interpreter their skip guards do not mention. Two have a predicate too loose to fail.

## Findings (12)
- [seq 247](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750716618), 2026-09-20, medium (estimated): CI runs as root and nothing declares it; chmod-based negative fixtures are void in CI. Status at origin/main `f63dc946`: No CI_RUNS_AS_ROOT fact or euid conftest guard found (grep scripts/check-test-binary-guards.py, tests/conftest.py, .woodpecker.yml); check-negative-fixture-preconditions has no root handling.
- [seq 548](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6295829389), 2026-10-20, low (estimated): test_an_untracked_control_file_refuses_the_green flaked in CI; hold-budget message looks inconsistent. Status at origin/main `f63dc946`: tests/test_negative_controls.py:1251 message still prints 'own 30s bound' with 'killed after remaining' value; no fix in git log; flake cause unexamined.
- [seq 550](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6296001550), 2026-10-20, low (estimated): Follow-up: restarted pipeline passed on same commit, so flake is load-dependent. Status at origin/main `f63dc946`: Follow-up evidence to seq 548; same flake, no fix landed.
- [seq 620](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6468237499), 2026-10-28, low (estimated): test_step9_verify_executes.py needs a Python 3.11 interpreter but its guards and quickstart do not say so. Status at origin/main `f63dc946`: Skip predicate is still uv/bash only (lines 37-40) and the subprocess pins 3.11 with UV_PYTHON_DOWNLOADS=never; README mentions the requirement but observed after #1579.
- [seq 621](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6468834555), 2026-10-28, low (estimated): tests/test_silent_test_success.py:118 skipif guards only bash and uv but runs finish helper needing installed Python 3.11. Status at origin/main `f63dc946`: skipif at line 117-120 still checks only bash/uv; same for test_step9_verify_executes.py skipif. Cited #1632 only provisioned 3.11 in its own environment.
- [seq 624](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6470509740), 2026-10-28, low (estimated): test_delegated_lane_failure_detection.py:203 capture-tail predicate accepts previous line merely containing the CLI binary word. Status at origin/main `f63dc946`: _capture_tail still returns previous.endswith('2>&1') or binary.split()[0] in previous (line ~193); #1597 explicitly recorded it separately, not fixed.
- [seq 668](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6711969677), 2026-11-07, low (stated): test_no_heredoc_inside_a_command_substitution regex cannot cross newline, misses DERIVED="$(\n python3 <<'PYEOF'". Status at origin/main `f63dc946`: tests/test_hook_permission_census.py:414-421 regex still [^()\n]-based, single-line.
- [seq 677](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6726280210), 2026-11-08, low (stated): controls/flow-ci-status-stalled bad-past-timeout intermittently reported BLIND once in Woodpecker pipeline 3553. Status at origin/main `f63dc946`: Seen once, unreproduced; control still exists and cause not established. Not investigated further (could not reproduce here).
- [seq 693](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6729574217), 2026-11-09, medium (estimated): tests/test_gh_pr_merge.py coordination_signal_preserves_queue test flaky under CI load: no gh calls recorded. Status at origin/main `f63dc946`: Test still present at test_gh_pr_merge.py:4119 and unchanged in cause; no issue found tracking it.
- [seq 696](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6730242004), 2026-11-09, medium (estimated): Intermittent BLIND recurrence of controls/flow-ci-status-stalled bad-past-timeout case under CI load. Status at origin/main `f63dc946`: Control already injects FLOW_CI_NOW via run-case.sh, yet comment reports flake; run-case.sh unchanged since #1653. Cause not established; no tracking issue found.
- [seq 703](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6732902658), 2026-11-09, medium (stated): Recurrence of flaky test_coordination_signal_preserves_queue test ([unknown] param) on PR #1666. Status at origin/main `f63dc946`: Duplicate of seq 693; same test still present and unfixed.
- [seq 733](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6808628818), 2026-11-11, low (stated): test_a_refused_review_leaves_no_diff_file_behind snapshots shared /tmp so a neighbour's file reads as its leak (flaky under xdist). Status at origin/main `f63dc946`: Test still globs shared /tmp/codex-review-diff.*.patch before and after (L104-107).

## Acceptance
- Each flaky test has an identified cause and a fix, or is quarantined with its reason; the root-in-CI fact is declared and chmod-based fixtures assert their precondition.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

Parent: #1690 (child of #1673)


<!-- end of body -->

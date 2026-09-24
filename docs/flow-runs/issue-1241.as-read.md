# Issue #1241 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1241
- Read at:      2026-09-24T17:40:23Z
- updatedAt:    2026-09-24T13:02:08Z   (context only - moves on comments and labels)
- Body digest:  83b889be7bf77296ab301e809bbe71ac8f7c0b0f6907497e99a16c51064cda0e   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5419 of 5419 (cap 16384)

## Body as read
> **Corrected 2026-09-24 after measuring.** The original body said "the four
> tests" and proposed sharing one battery run across them. Both were wrong: the
> count came from `grep -c "run_harness(ROOT)"`, which matches only the
> no-argument form, and the sharing proposal would have broken a test that
> deliberately runs the battery three times against three different tree states.
> The population and the remedy below are measured. The symptom table is
> unchanged.

## Symptom

CI `validate` fails intermittently with a 120s pytest-timeout inside
`tests/test_negative_controls.py`. The test named differs from run to run:

| pipeline | branch | failing test |
|---|---|---|
| 2628 | `issue-1232-...` | `test_the_summary_states_the_universe_it_is_a_fraction_of` |
| 2626 | `issue-1236-...` | `test_the_real_unavailability_control_discriminates_and_its_anchor_is_blind` |
| 2614 | `issue-1228-...` | `test_two_registrations_on_one_gate_are_distinguishable_in_the_output` |

Each: `Failed: Timeout (>120.0s) from pytest-timeout.`, one failed of ~5820-5860,
in a `validate` step taking 504-556s.

## The population, measured

`run_harness(ROOT, *args)` runs the ENTIRE registered negative-control battery as
a subprocess (`scripts/check-negative-controls.py --root <repo>`, itself spawning
one or more processes per control). **One battery run costs 26.2s** on an
otherwise quiet box (`/usr/bin/time` on this tree, 2026-09-24).

There are **9 invocations across 6 tests**, in 4 argument shapes:

| shape | calls | where |
|---|---|---|
| `run_harness(ROOT)` | 4 | `test_the_real_control_discriminates_and_its_anchor...`, `test_the_summary_states_the_universe_it_is_a_fraction_of`, `test_two_registrations_on_one_gate_are_distinguishable...`, `test_the_real_unavailability_control_discriminates...` |
| `run_harness(ROOT, "--strict")` | **3, all inside ONE test** | `test_an_untracked_control_file_refuses_the_green` |
| `run_harness(ROOT, "--quiet")` | 1 | `test_discover_is_not_recursive_so_nested_case_trees...` |
| `run_harness(ROOT, "--verify-provenance")` | 1 | `test_the_real_synthetic_anchors_are_not_reported_as...` |

So the suite pays ~236s of battery cost, and the cost rises monotonically as the
repo does the thing ADR 0008 asks of it - register more controls - until the
margin against a fixed 120s cap is gone. That crossing is what is being observed.

**`test_an_untracked_control_file_refuses_the_green` is the most marginal test in
the file and was not among the three observed failures.** Three sequential
battery runs is 78s of baseline against a 120s cap, so it needs only ~1.5x load
to time out. Any fix that leaves it alone leaves the worst case in place.

It is also load-coupled: this host runs several `make verify` invocations
concurrently from parallel flow worktrees (7 worktrees, 2-4 concurrent suites
observed while diagnosing), each with `pytest -n 4` inside.

## Why it matters

`ci/woodpecker/pr/woodpecker` is a REQUIRED check and `gh-pr-merge.sh` correctly
refuses to merge past a red one (#577, ADR 0004). So this blocks PRs
intermittently, with a failure that names a different innocent test each time -
the shape most likely to be misattributed to whatever change is in flight. It was
nearly misattributed to #1232: that branch went GREEN at pipelines 2619/2620 and
red at 2627/2628 after an ordinary base merge, with no change to anything the
battery touches.

## Remedy - two changes, not one

1. **Share the no-argument result across its four tests** (session-scoped
   fixture). All four ask the identical question of a tree at rest, so one run
   answers all four: 9 invocations become 6, ~78s off the suite.
2. **Raise the timeout on `test_an_untracked_control_file_refuses_the_green`
   specifically.** Its three runs measure three DIFFERENT tree states - before a
   mutation, after it, and after restoring - so they are not shareable and 78s is
   its honest floor.

**THE TRAP, and the reason the original proposal was wrong:** a general
"memoize `run_harness`" keyed on arguments alone returns the cached `before`
result for the `after` call in that test, so the test passes while checking
nothing. The cache must cover the no-argument shape only, or be explicitly
bypassed there. `--quiet` and `--verify-provenance` are single-use and caching
them gains nothing.

Not proposed: raising the timeout file-wide. That converts a structural cost into
a number someone must keep increasing, and the next person to register a control
will not know the headroom is spent.

## Out of scope here

Making the battery itself faster - parallelising `check-negative-controls.py`, or
sharding it - is the larger win and wants its own issue. The 26.2s is the floor
everything above is working around.

## Sibling, now fixed

#1242 was the OTHER cause of intermittent redness in the same window (a
module-level cache poisoned by a monkeypatched table, rotating victim, passes when
run alone). It landed in #1245, so a rotating failure seen from now on is this
issue rather than that one. `flow-finish-gate.sh` also does not name the failing
test, which cost an 11-minute re-run to identify - recorded separately in the nit
store (#864).

## Provenance

Found during `/flow:auto #1232` when its post-merge CI went red on a test its
change does not touch. Pipeline evidence above is from the Woodpecker logs of the
three named pipelines; the population and timing are from this tree.


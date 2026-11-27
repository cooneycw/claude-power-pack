# Opt-in CI shape qualification (#1917 PR-A)

Status: implementation and qualification in progress. No root/image success
or full acceptance is claimed by this draft record.

| Witness | Committed input and expected distinction | Evidence required |
|---|---|---|
| #1909 / 4026 modes | Unchanged historical inventory sees copied 0666; current tracked-input normalizer yields 0644 | Physical fixture RED/GREEN and both shaped focused runs |
| #1910 / 4030 root | chmod 000 is still readable at actual uid 0; current control drops to uid/gid 65534 with no groups and gets real PermissionError | Image/root run; local skip is UNKNOWN |
| #1910 / 4030 PATH | Exact old test replaces staged Git with system-only PATH; fixed test preserves the selected executable | Pinned image with no system Git |
| #1916 history | Unchanged old source fixture checks out an absent pin; current fixture creates owned history | Actual shallow fixture RED/GREEN |
| #1916 PATH | Unchanged owner helper excludes staged Git/Make; focused fixed fixtures supply explicitly selected tools | Pinned-image failure witness and focused owner positives |
| #1922 / 4056 | Actual filtered clone has commit but not historical file contents; old test attempts the missing checkout; fixed helper names the partial-clone exclusion | Actual filtered witness and named skip; no lazy fetch |
| #1922 / 4058 | Unchanged 79f2edf byte assertion enters rich diff under CI=true; same input with explicit raise completes | Four-second child bound, one-second traceback, RED/GREEN |
| #1923 | Actual child prints INTERNALERROR and exits 0; incomplete or empty outcome evidence | Gate BAD despite zero child exit; blind verifier misses |
| UNKNOWN | Backend, tool or requested shape cannot be examined | Nonzero UNKNOWN, never GOOD |
| Cross-tier BAD | A local GOOD receipt labels the root column GOOD | Verifier BAD; blind anchor misses |

The exact predecessor excerpts and hashes live in
`controls/ci-shape-check/history/provenance.json`. These bounded fixtures pin
the relevant distinction; they do not claim the entire historical PR ran.
The #1909 file transport failure's root cause remains unproven.

Qualification order: committed controls, local smoke, exact pushed checkpoint
host/image run, counter-model review, direct finish gate, PR CI. #1922 merges
first; this branch incorporates current main by merge, never rebase. PR-B
starts only after PR-A merges, and supplies required pre-review and CI wiring.

Related: [#1923](https://github.com/cooneycw/claude-power-pack/issues/1923)
tracks pytest-xdist's possible zero INTERNALERROR status.
[#1924](https://github.com/cooneycw/claude-power-pack/issues/1924) is the held
test-only review proposal; no review-budget change is implemented here.

# Opt-in CI shape qualification (#1917 PR-A)

Status: image/root qualification is GOOD at `1c989eee`. Final-head local
qualification, review, the direct finish gate and PR CI remain pending.

| Witness | Committed input and expected distinction | Evidence required |
|---|---|---|
| #1909 / 4026 modes | Unchanged historical inventory sees copied 0666; current tracked-input normalizer yields 0644 | Physical fixture RED/GREEN and both shaped focused runs |
| #1910 / 4030 root | chmod 000 is still readable at actual uid 0; current control drops to uid/gid 65534 with no groups and gets real PermissionError | Image/root run; local skip is UNKNOWN |
| #1910 / 4030 PATH | Exact old test replaces staged Git with system-only PATH; fixed test preserves the selected executable | Pinned image with no system Git |
| #1916 history | Unchanged old source fixture checks out an absent pin; current fixture creates owned history | Actual shallow fixture RED/GREEN |
| #1916 PATH | Unchanged owner helper excludes staged Git/Make; focused fixed fixtures supply explicitly selected tools | Pinned-image failure witness and focused owner positives |
| #1922 / 4056 | Actual filtered clone has commit but not historical file contents; old test attempts the missing checkout; fixed helper names the partial-clone exclusion | Actual filtered witness and named skip; no lazy fetch |
| #1922 / 4058 | Unchanged 79f2edf byte assertion enters rich diff under CI=true; same input with explicit raise completes | Four-second child bound, one-second traceback, RED/GREEN |
| #1923 zero execution | `controls/ci-shape-check/cases/zero-executed/case.json`: actual child prints `no tests ran` and exits 0, no terminal outcomes and no INTERNALERROR marker | Gate BAD (`zero executed tests`); blind verifier misses |
| #1923 internal error | `controls/ci-shape-check/cases/internalerror/case.json`: actual child prints `INTERNALERROR>` and exits 0, with otherwise complete healthy collection/outcome evidence | Gate BAD from output marker alone; blind verifier misses. Unit cases also reject exit 1, 2, 5 and 7 |
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

## Initial local evidence

At `4f38eaf095cad996fb01b3d5625957f027dfd041`, the original broad first lane
completed with 535 passed, 2 failed, 9 named skips in 580 seconds. Its verdict
was BAD. The failures were the newly filed
[#1927](https://github.com/cooneycw/claude-power-pack/issues/1927) symlink-TMPDIR
control fixture and `test_identical_legacy_install_does_not_offer_migration`.
The second lane was deliberately interrupted after the first lane's complete
RED evidence; its partial 237 terminal outcomes are BAD/incomplete, not a
completed filtered-lane result. All owned run scratch and basetemps were removed.

The legacy-copy test was isolated through the maintained Make target: ordinary
pytest runtime umask passed; runtime umask 000 failed (Make exit 2). This was a
test-process mask difference, beyond the intended checkout-created-at-000
shape. Pipelines 4060 and 4056 passed that test (orchestrator report), which is
indirect evidence CI is not testing at 000; it does not establish 022. The
checked-in profile therefore remains UNKNOWN pending the actual pinned-image
shell `umask; id` probe and root receipt. No local GOOD is claimed yet.

The revised committed manifest selects focused named builder/parity and
host-shape cases, retains the pi observers and owner fixtures, and pins all
acceptance witnesses by node id. It has a floor of 200; collection before the
last bootstrap tests was 240. It omits unrelated jq/shellcheck command-audit
populations rather than declaring their missing-tool skips acceptable. The
#1927 unreadability test remains selected and must go GREEN after its separate
fixture fix. PR-A does not change that control or source policy.

The Nit Store record
[7216998783](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7216998783)
now explicitly points to #1927 as its superseding disposition, so it is not a
second finding.

## #1927 fixed witness

Main `f966fbf5052dca7c5eb6c005b1b7dd24ff8d42e9` (#1928) was merged without
rebasing. The same maintained pi-install Make smoke with an outer symlinked
TMPDIR now passes all four direct/symlink and umask-022/000 cases. The prior
unmodified control failed with `PolicyError: symlink path refused`, as recorded
above; source policy remains unchanged. This is local uid-1000 evidence, not a
real-root result.

The fixture's new parameterized names are pinned individually in the manifest.
Actual pytest collection finds 255 tests and every required named witness,
above the floor of 200. The full local-tier verdict remains UNKNOWN until the
frozen host checkpoint supplies the actual validate-image umask profile.

## #1923 guard scope

The [owner-shared adjustment](https://github.com/cooneycw/claude-power-pack/issues/1923#issuecomment-7220507104)
folds the ci-shape guard requirements into PR-A. The named `zero-executed` and
`internalerror` BAD inputs are independent: the first has no error marker;
the second retains healthy nonzero results. Both use an actual exit-zero child.
The latter guard rejects `INTERNALERROR>` regardless of exit status.

This check does not fix pytest-xdist's underlying exit-status path or add a
new guard to standalone Make invocations outside ci-shape. Keep `Refs #1923`
until the remaining caller/runner scope is explicitly disposed; any remaining
guard is a separate follow-up, as the adjusted issue requests.

## First host attempt: source ownership UNKNOWN

K753 ran frozen `9646c0e0` on 2026-11-27 at 14:37:01-14:37:10 UTC.
The exact pinned image's default shell reported umask 0022 and uid/gid 0.
Git 2.39.5 and Make 4.3 staged successfully. The donor fetch then returned 128:
file transport opened the uid-1000 read-only mount as `/source/.git`, which the
working-tree-only `/source` trust did not cover. The run exited 2 with UNKNOWN,
zero executed lanes and no published profile. This was a checkpoint defect,
not root acceptance.

Raw `image.json` SHA256:
`c16bdab708ef190dfe9a81e68a7b62449dc8043f41f5cd821d426ee1ed5ac354`.
All seven original delivery files were hashed before copying and verified under
`/workspace/.work/cpp-1917-evidence/host-9646c0e0/`; the inventory and failed
receipt remain there unchanged. The image default mask is now directly
observed, while full image/root qualification and profile publication remain
pending the authorized retry.

`test_donor_fetch_trusts_only_its_selected_different_owner_source` uses Git's
ownership-check hook and reproduces the unchanged predecessor's exact dubious
ownership failure. It passes with the correction, including pinned Git 2.39.5.
The source and a separate neighbor both remain refused by plain Git afterward;
no global configuration is written. The correction resolves the selected
source's Git directory and passes only its working-tree and Git-directory
spellings to this fetch's upload-pack command. That witness is pinned in the
required collection. The host command file is unchanged; executable code is
re-frozen at the retry checkpoint after verification.

## Successful image/root qualification

The single authorized retry ran `1c989eeefac0074290d326c0f43dc72fdbc7c0b7`
on 2026-11-27 at 15:01:43-15:09:35 UTC and exited 0. The committed host command
file matched SHA256 `605a37100e03a5a250c031134386ee719224972eb33c23fc8f0e356b95be173a`.
The pinned image's shell and Python entry process both observed umask 0022;
both lanes observed real uid/euid/gid/egid 0 and supplementary groups `[0]`.

Both depth-1 and depth-1/tree:0 lanes selected 256 tests, executed 254 and
skipped two named historical installer comparisons. The shallow lane reported
absent historical commits; the partial lane reported the explicit partial-clone
exclusion. Their independent historical-file witness and all required root,
PATH, mode, CI=true, INTERNALERROR and zero-execution cases executed. The root
permission child proved uid/gid 65534 with no supplementary groups before the
actual CLI returned its expected PermissionError result. No root-only skip was
accepted in this tier. Lane times were 245.23 and 195.53 seconds.

The [raw root receipt](ci-shape-check/root-receipt.json) is committed unchanged:
SHA256 `a836c2c1a1a63b53a5fb8f6b9cfceb55842b1e14de2d51202276b80980d5e2ad`,
119,798 bytes. Eleven original delivery files were hashed before copying and
verified under `/workspace/.work/cpp-1917-evidence/host-1c989eee/`. The image and
[default-shell observation](ci-shape-check/validate-default-shell.txt) are
published beside the receipt. The digest-bound profile copies the observed
mask, full identity and exact receipt hash; tests check their agreement.

Only the approved profile/docs/measurement paths change after the frozen root
checkpoint. The bootstrap checker must qualify the final pre-review profile
head, which must also receive its own local-tier GOOD. Root evidence stays
bound to the exact ancestor above; the later review receipt follows the
independently checked receipt-only path.

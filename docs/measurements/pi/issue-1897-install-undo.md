# #1897 installation and undo observations

## Local fixture replay - 2026-11-26

LOCAL evidence only, permitted by mailbox 40632. Source was a separate clean
detached worktree at `337f411a6bb2cf104040fd5407a1987842ea89bb`.
No CPP push, CI, owner action or pi execution occurred. Installed tools were
Python 3.12.3, Git 2.43.0 and GNU Make 4.3. No version matrix is claimed.

The replay used the existing production Make targets for the full fresh build,
install and verification. The scratch HOME, agent, histories, XDG roots and
working/evidence paths were fresh. Children received an environment allowlist
and selected tool directories, with no inherited provider credentials. Actual
canonical output contained 18 packages and 36 regular 0644 members. Its source
Git state remained clean after generating the ignored fresh build.

Four independent fixture agents each started with no canonical CPP topic,
management or primary-lock paths and one synthetic personal skill. Before each
install, the replay saved scoped CPP pre-state/backup, target list and inverse
recipe. Actual commands and real CLI JSON were retained outside the agents.
There were 21 install/verifier invocations in the completed replay.

| Fixture | Negative verifier | Repair | Undo / preservation |
|---|---|---|---|
| Positive install/undo | Not applicable | Initial full install and verify exit 0 | Scoped baseline restored; personal file unchanged |
| Exactly one reference byte changed | CLI exit 1; expected count remained 18 | Actual install with explicit fixture-only adoption, then complete verify exit 0 | Undo first refused the changed post-state without deletion; after repair, baseline restored |
| Expected package removed | CLI exit 1; expected count remained 18 | Ordinary actual install restored it, then complete verify exit 0 | Undo first refused the incomplete post-state without deletion; after repair, baseline restored |
| Source marker stripped | CLI exit 1; expected count remained 18 | Actual install with explicit fixture-only adoption, then complete verify exit 0 | Undo first refused the changed post-state without deletion; after repair, baseline restored |

The replay asserted each negative precondition before verification. Every
positive verified all 36 expected members against the actual fresh bytes/modes.
The captured nonempty installed state is the positive control before interpreting
absence after undo. In the three changed cases, the refusal left the entire
fixture-agent snapshot unchanged; it did not erase the intervening edit.

Final fixture undo removed only the recorded CPP-created topic directories,
management tree (including work and both derived locks) and new primary lock.
The pre-existing personal skill's bytes/mode, inode and mtime were unchanged.
The scoped pre/post file/directory-mode manifests matched. Parent directory
timestamps and a whole-owner-agent comparison are outside this observation.
This fixture-only deletion procedure is NOT an owner rollback implementation
and establishes no concurrent-writer cleanup guarantee.

After undo, each real verifier returned CLI exit 1, with 18 expected packages
and zero examined members. That is the expected missing-installed state, not
installed-parity green. The verifier created no residual scoped paths, and the
personal-neighbor baseline still matched. Make reports status 2 for a failed
recipe; the raw records separately preserve that status and the CLI's exit 1.

## Retained incomplete first attempt

The first replay was incomplete because it incorrectly requested adoption while
repairing a missing package. The real installer refused with CLI exit 1:
`adoption names paths outside this reviewed conflict set`. This is a replay
command correction, not a product fix. The corrected recipe uses ordinary
install for absence, explicit adoption only for the edited fixture conflict.
The failed command/output and pre-state backup remain retained; its disposable
fixture directories were cleaned separately. No clean result is claimed for it.

## Provenance and unexecuted lanes

The completed raw summary is 2390 bytes, SHA256
`bdc8828db9b1c3d279fb8b2978fba4be7ab46d2ddaaf0b1b9fd8ce7257ce5197`.
The local replay transcript source SHA256 is
`d213384bf0e3574d8d64bdcbfe4c5fbca661dd9b88a03c17863236666539124a`.
The failed-attempt record SHA256 is
`0e96d43eb969666ac6334b55ef05fb2e249231a529adbe628641c3f121eb9711`.
Digests identify retained bytes, not authenticity. Raw commands/JSON, per-install
backups/journals and before/after manifests remain outside the checkout. Both
completed and failed fixture directory sets were removed after preserving the
evidence. No live-session rollout was copied for this replay.

No pi executable was available locally. Actual pi discovery/reload is
UNEXECUTED, and owner install/reload/undo and owner sign-off are UNEXECUTED.
No fixture-only snapshot substitutes for these rows. No new syscall trace or
six-boundary execution is claimed here: carry #1896's separately attributed
results and limits. Its two remaining inventory/diagnostic measurements remain
UNKNOWN. Section-5 integrations remain deferred and this is not a Part-1 sign-off.


## Durable relocation and repeat fixture replay

Mailbox 40651 authorizes persistent workspace copies and a WIP branch backup,
with no PR, CI or owner action. The branch repository and clean source were
recreated under persistent workspace storage using independent Git metadata.
Both original evidence sets were copied byte-for-byte (137 completed-run files,
91 incomplete-run files), with every file hash compared. The original summary,
failed-attempt record and original driver digests above are unchanged. Historical
absolute paths inside the raw evidence were not rewritten; a separate relocation
map identifies their persistent copies.

A portable replay derivative changes only source/run location initialization;
its SHA256 is
`8c13f293006e4fd8218ea314ba30a57444a1a36736b51f0dd4dbd8f7676971e7`.
It completed a fresh fixture replay from persistent source at the same revision,
with the same 18/36 population, negative/repair/undo results, source cleanliness
and fixture cleanup. Its summary bytes match the original summary digest above;
its raw stdout SHA256 is
`ccac5bcb0930ec17cf32f337cd7543b75398b0e7773f4bf932ac10dd5700eb84`.
The original driver remains retained separately. No owner or pi-discovery
observation was added by this durability work.


## Approved fresh-base fixture replay - 2026-11-26

The public owner ruling and mailbox 40665 approve the plan and require a fresh
fixture run after merging main without rebasing. Merge `fbd5d25f` incorporated
`c434101e7ae580de3bb81ca1db9d325a0483c44c`; the separate clean detached source
used that full main revision. The portable replay changed only its pinned
revision for this run. Driver SHA256:
`29f6e780188c7f4fcda5ee6fe17e5301086bd2c54b95c9d58158650e3c61cf02`.

The four scenarios again observed 18 packages / 36 members and 21 actual
install/verifier calls. Full positive verification passed. Changed reference,
missing package and stripped marker each produced actual CLI parity exit 1;
each changed state refused fixture undo without deletion, and actual repair
returned complete positive verification. All final scoped baseline comparisons
and personal identity/mtime checks passed. Post-undo verification returned
missing-installed exit 1 with 18 expected packages and zero examined members.
Source cleanliness and fixture cleanup were confirmed.

Fresh summary SHA256:
`af639665ca1ecd4e2c26564cc72e501755adb023b5b5f570fee937e97b68122d`.
Raw stdout SHA256:
`113797968ba0b2ace1fbe1a4e1c41e8088ce60a416ba34703cd829e1263c95a4`.
These identify retained local bytes, not authenticity or owner evidence.
No pi executable was available; discovery remains UNEXECUTED. The raw summary's
historical authority-pending string describes an unexecuted owner lane; owner
authority is now granted subject to exact commands being shown first. No owner
installation, reload, undo or sign-off occurred in this fixture replay.

## Exact owner-probe preparation - mailbox 40671

The adjacent `issue-1897-owner-probe.py` and command protocol are prepared for
owner presentation, not executed against owner paths. Eleven committed fixture
cases exercise the same probe with the actual pinned delivered CLI: complete
install/verify/undo with and without a personal neighbor; three existing-state
refusals; edited post-state and unexpected management-member refusals; missing
reload confirmation; held-lock refusal; alias refusal; and Make-metacharacter
path refusal. Every refusal leaves the relevant agent state intact. Successful
runs restore the scoped baseline. Simulated fixture confirmations establish
sequencing only, never real pi discovery.

`make test-pi-skill-install PYTEST_ARGS='tests/test_pi_owner_probe.py'` reports
37 passed, 1 skipped. The existing unreadable-fixture privilege regression
requires real root and was skipped; no pass is claimed for it. The new probe
controls all ran. Lint, typecheck, Markdown checks and staged whitespace checks
also passed. No owner install, pi process, reload observation or sign-off is
claimed; those rows remain pending the exact committed commands being shown.

## Owner stop, presence relay and review-only recovery preparation

Mailbox 40896 reports the first actual owner install and delivered verifier
succeeded: 18 packages / 36 examined members, current. The probe then stopped
with `installed bytes/modes differ`, before a sealed post-state or undo. The
reported difference was 28 directories: fresh build 0775 under umask 0002 versus
installer policy 0755. All 36 file bytes/modes matched. This is a probe defect.
The original fixture runs used another umask and did not cover this input.

Master's later relay (mailbox 40900) reports the existing-session `/reload`
presence observation at 03:25:27Z: 18 user-scope entries, exactly the journal's
sorted 18 slugs, versus zero in the baseline. This is attributed host evidence,
not local pi execution. Owner cleanup and post-cleanup discovery remain pending.

Mailbox 40903 supplied a sanitized journal archive. Its decoded SHA256 matched
`c181e7f224ec0ad586d5bf4dcf163d282d508cf8b994e9b24629be485cba19ed`.
The record has 20 targets, 18 expected packages, all 28 expected directories at
0775, and `skills_existed=false`. Both captured actual commands report current
with 36/36 members. The original unsanitized host-file digests supplied by master
are embedded in recovery; they cannot be independently checked in this container.
The recovery has no hash override/skip flag and requires explicit home equality.
The sanitized bytes are a design input, never authority to act on owner paths.

The committed umask regression FAILED on the exact original `a3dc5d6e` probe
with the same post-install error. The fixed comparison normalizes expected
build directory modes to 0755 and file modes to 0644, while checking actual
installed modes strictly. The regression now completes through undo and asserts
that its fresh build really produced all 28 directories at 0775. Original probe
bytes are frozen as a fixture with their original submitted digest, so squash
merge cannot erase the failure input's implementation.

The combined production/probe/recovery fixture run passed 47 cases, with the
existing real-root privilege case skipped. After adding the original-journal
hash and explicit-home guards, all 11 recovery cases passed; a follow-up actual
install/dry-run/execute case also passed using the byte-identical frozen anchor.
Together these cover 49 distinct passing cases and one existing skip. Recovery
controls include exact successful removal, personal-neighbor preservation,
changed file/directory/management refusal, a CPP-marked canonical path missing
from the record, tampered plans, intervening edits, held/missing locks, bad
journal hashes and a mismatched explicit home. Every refused case preserves
agent state; matching recovery verifies expected missing-installed afterwards.
All test basetemps were removed after results; needed logs remain in persistent
workspace evidence. No owner recovery dry-run or execution occurred locally.

Recovery is deliberately limited to the 20 exact recorded target roots. Its
review protocol currently retains the skills root because that root is absent
from the target list, despite `skills_existed=false`. This limitation was sent
to the orchestrator in mailbox 40916 before freeze; a matching target comparison
must not be reported as whole-filesystem restoration if the empty root remains.
The helper must obtain review/owner clearance before any recovery action, then
capture the second reload separately. This is not owner sign-off or Section-5
clearance; both #1896 UNKNOWN measurements remain visible.

## Original root inverse restored - mailbox 40923

The orchestrator confirms that the original logged inverse authorizes FINAL
plain rmdir of a newly created skills root. The recovery now prints that exact
conditional step in dry-run when `skills_existed=false`, binds root identity and
mode in the reviewed plan, checks for a symlink, and relies on plain rmdir to
refuse nonempty roots. Pre-existing roots remain. This supersedes the conservative
root-retention limitation above without authorizing removal of unrelated data.

All 13 recovery cases passed after this change, including empty-created-root
removal and nonempty-created-root refusal. A further committed symlink-root case
also passed, bringing recovery coverage to 14 passing cases. An unrelated file
appearing after dry-run survives final rmdir refusal; CPP targets were already
removed in that case, the root remains, and no success receipt is emitted.
The symlink case refuses before deletion. A successful empty-root recovery
removes both the 20 recorded targets and the logged-new root, then the actual
verifier returns expected missing-installed. Basetemps were removed after each
result; logs remain in persistent evidence. No owner dry-run or execution was
performed here. The host sequence remains review, owner presentation and
clearance for dry-run, review of the exact printed plan, owner approval for
execute, recovery, and separate second existing-session reload observation.

The review-note follow-up (mailbox 40929) makes the final lstat directory and
identity/mode check explicit and records ENOTEMPTY as a narrower target-restore
result in `root-retained.json`. It does not call that whole-filesystem recovery.
All three affected root cases passed after the clarification; lint/type checks
passed and the test basetemp was removed. No owner action occurred.

## Owner recovery and baseline discovery completed - master's relay 40996

The owner-authorized recovery used ONLY reviewed commit
`d013ef498318efbfc60592999faf4ac9a808ec28`, recovery script SHA256
`fe2b3b8931760c7bf910cf9a752f02f523581d5dead99228e3c34c4b87a72085`,
with the fixed probe module. Optional later `64e9ef07` was not executed on the
owner installation. The host reports execution at 04:25:56Z, exit 0 at 04:25:57Z.
Both execution and reviewed dry-run plans have SHA256
`fc919532130f924320c032ba206e6398c20b642dcf4a01ca76a1d82b866fedc4`.
All 20 recorded CPP targets, the logged-new skills root and primary lock are
reported absent. The actual delivered verifier after recovery returned absent:
18 expected packages / 36 expected members / zero examined, CLI exit 1 and Make
exit 2. This is expected missing-installed, not installed-parity green.

Master reports `/reload` in the SAME existing pi session at 04:26:17Z followed
by zero `/skill:` completion entries, matching the zero-entry pre-install
baseline. The earlier 18/18 user-scope presence is the nonempty positive control
before that absence observation. This completes the observed owner
baseline/install/presence/undo/baseline sequence. It does not erase the original
probe stop or imply that the original probe completed its own undo.

The decoded host execution-report text SHA256 was independently verified here:
`26e051967acc1ef7483da9cb8a21f303b8ea809680d38ff2253db48c0c22cc34`.
Individual host journal/plan/receipt file hashes are host-reported, not locally
recomputed. The [sanitized record](issue-1897-owner-lane.json) preserves those
attributions and excludes private paths/session names and unrelated content.
Master reports retaining original journal, recovery evidence and journal backup,
while removing three temporary worktrees. No owner command ran in this worker.

The [owner-facing Part 1 summary](issue-1897-owner-signoff.md) was sent to the
orchestrator before further review/gates/PR. Owner Part-1 sign-off is PENDING;
Refs #1897 remains the closing disposition until explicitly changed. Both #1896
UNKNOWN measurements remain, and Section 5 is not automatically authorized.

The post-receipt preflight found one missing Git binary guard in the committed
umask regression. Both disposable-owner test modules now guard required Git and
Make availability. `make binary-guards-check` changed from one unguarded test to
ok; all 26 actual fixture cases passed again, with lint/type checks also green.
The actual owner scripts and executed d013ef49 recovery remain unchanged.
Basetemp cleanup completed after retaining the focused result.

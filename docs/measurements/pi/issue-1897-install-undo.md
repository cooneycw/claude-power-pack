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

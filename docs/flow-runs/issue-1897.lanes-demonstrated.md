# #1897 local preparation and demonstrated lanes

Run `273368568fab4e52b3c4bac50fc1154b`, base main `337f411a`.
Mailbox 40632 permits local records/protocol and fixture dry runs only.
Owner ruling, push/CI/PR and owner action remain pending.

| Lane / reader | Current result | Evidence / limit |
|---|---|---|
| Linked checkout | prepared | Local branch and separate clean detached source both at `337f411a` |
| Fixture full install/verify | OBSERVED locally | Full real fresh build and actual Make/CLI/core, 18 packages / 36 members; source pinned and clean |
| Fixture mutations/repair | OBSERVED locally | One reference byte, missing package and stripped marker each fail CLI parity with nonzero expected population; real repair returns complete positive |
| Fixture undo/preservation | OBSERVED locally | Changed post-state refuses undo without deletion; repaired state removes only CPP-created paths; scoped baseline and personal inode/mtime retained |
| Fixture pi discovery | unexecuted | No local pi execution or reader self-test substitutes for actual discovery |
| Owner pi install/reload/undo | unexecuted | Owner ruling and concrete reviewed batch required |
| Owner sign-off | pending | Two #1896 UNKNOWNs must remain visible |
| CI provider | unexecuted | No CI while the issue remains frozen |

No runtime/provider/container, owner credential isolation or workflow result is
claimed. This record is not an approval stamp or a Part-1 completion statement.

The [local measurement](../measurements/pi/issue-1897-install-undo.md) retains
the first incomplete replay, its command correction and the complete second
replay. After cleanup, the actual installed verifier correctly reports missing
expected content (exit 1), not current with zero examined members. Source
artifacts, raw outputs and per-install journals remain locally retained.
The fixture-only undo procedure does not supply the separately required owner
batch, coordination window or owner sign-off.


Mailbox 40651 adds only a WIP durability-push exception. The repository, clean
source and raw evidence now persist under workspace storage; original file
hashes were rechecked and a path-portable fixture replay completed with the
same summary. This does not change the owner/CI/discovery/sign-off rows above.


Mailbox 40665 and the public owner ruling now approve the plan and unpark #1897.
The earlier pending-authority descriptions above are historical. Main
`c434101e` was merged without rebasing, and a clean source at that revision
repeated all four fixture scenarios: full 18/36 parity positive, three parity
negatives, three undo refusals, repaired positives and final scoped baseline
restoration. The measurement record retains fresh digests. Owner/discovery/
sign-off rows remain unexecuted; an exact committed owner probe must be shown
before owner execution. PR creation still awaits orchestrator clearance.

Mailbox 40671's exact probe is now prepared with committed opposite controls.
Disposable-home runs of that same probe cover success, collisions, changed
post-state, held locks, aliases and unsafe path bindings. All eleven new cases
passed; combined focused production/probe tests report 37 passed and one
existing root-only skip. No simulated prompt response counts as pi discovery.
The host-helper command protocol still requires presentation before owner use.

## Owner run stopped; subsequent presence observed - 2026-11-26

Master's relay via orchestrator mailbox 40896 reports actual owner install and
verifier current at 18 packages / 36 examined members. The probe then stopped
before sealing or undo: build umask 0002 made 0775 directories, whereas the
installer creates 0755 directories. The file bytes/modes matched. This is a
probe defect; no cleanup success is claimed and owner CPP state remains present.

A later master's relay, mailbox 40900, reports actual existing-session `/reload`
and `/skill:` completion at 03:25:27Z: exactly 18 user-scope entries, with sorted
names identical to the original journal slugs. The pre-install list had zero.
This establishes the presence observation; it does not imply undo or restored
discovery. Recovery and the second reload are still pending independent review
and owner clearance. The host is retaining the journal durably. Both #1896
UNKNOWN measurements and separate owner sign-off remain outstanding.

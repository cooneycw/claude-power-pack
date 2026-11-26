# Flow run record - issue #1897

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=273368568fab4e52b3c4bac50fc1154b -->
## Run 1

- Run-id:            273368568fab4e52b3c4bac50fc1154b
- Run-start:         337f411a6bb2cf104040fd5407a1987842ea89bb

- Issue: #1897, Tier 1, parent #1876; P1-B live topic-installation validation.
- Issue-as-read: helper captured SHA256
  `e8fc3dc38dcc2a4c0d142612002a1829294badc69c2fd6d72d12771ffd27755b`
  (2691 bytes). The public as-read snapshot is pending formal approval.
- Authority: mailbox 40632 approves LOCAL plan/protocol preparation and fixture
  dry runs. The owner ruling on unparking/publication and one owner-session
  install/undo is pending. No helper approval stamp is claimed here.
- Branch: `issue-1897-pi-validation`, based on merged main `337f411a`.
- Frozen design: rev 6.1 Sections 3, 4 P1-B and 5; retain its bytes unchanged.

### Section A - Outcome and constraints

Demonstrate the delivered complete topic build/install/verify path, actual pi
reload discovery, and an executed exact undo. Retain expected/examined counts,
hashes/modes, real outputs and a scoped before/after comparison for owner review.
Owner sign-off gates any deeper integration. The two remaining #1896
measurements stay UNKNOWN and must be visible at that sign-off.

All corrupt/missing/marker negatives run only in disposable fixtures. Preserve
pre-existing user skills and collisions; no owner adoption is authorized. Owner
actions, once approved, are limited to skill install/verify and reload in the
existing authorized session. Do not launch a new pi process with owner HOME,
inspect credential paths, enumerate the whole agent, change trusted settings,
tools/extensions/MCP/rules, invoke workflows, or make a provider turn. Evidence
omits credential-file names/contents, tokens, private host/session names and
unrelated conversation/scrollback. No CPP push, CI or PR before clearance.

### Section B - Approach and ordered evidence

1. Prepare the [protocol](../measurements/pi/issue-1897-validation-protocol.md)
   and raw-evidence record. Use a separate clean detached source at `337f411a`
   for dry runs so local planning edits do not dirty source binding.
2. Use existing Make targets and the real CLI/core to install the entire fresh
   expected population into fixture roots. Derive counts and file manifests
   from the actual build. Keep a synthetic personal neighbor as a preservation
   control. Record each install's scoped pre-state and inverse before execution.
3. In fixtures, change one bundled-reference byte, remove an expected member
   or package, and strip a source marker. Assert each negative precondition;
   parity must fail with a nonzero expected population. Restore from the actual
   fresh build using the real installer; explicit adoption is fixture-only.
   Show positive verification again. Discovery is unexecuted without actual pi.
4. Prove fixture undo restores the scoped baseline and retains the personal
   neighbor. Exercise the refusal to erase an intervening edit. Establish
   presence before interpreting absence after undo. Empty post-undo output is
   an expected missing-installed state, not installed-parity green.
5. Carry #1896's six-boundary results with attribution and limits. Record real
   pi discovery separately from copier/verifier facts. The built-in inventory
   and skill-loader diagnostic measurements remain UNKNOWN.
6. After an owner ruling, finalize and review the concrete owner batch against
   its scoped pre-state before any write. The first supported batch requires
   canonical topic slots and CPP management state absent; unrelated personal
   skills may exist. A collision or pre-existing management state requires a
   preservation/restore amendment, never automatic adoption.
7. Log exact undo before owner install, including management ledger/work and
   all three coordination locks. Establish an operator-exclusive writer window
   for the whole install/undo, including cleanup of newly created lock paths.
   Existing locks are retained. Cleanup removes only logged, still-matching
   CPP-created paths; unexpected/intervening edits stop cleanup for review.
   Verify all members, observe reload presence, execute undo, reload again and
   compare the scoped filesystem/discovery baseline. Parent timestamps or a
   global unchanged-agent claim are not inferred from file/hash/mode equality.
8. Obtain explicit owner sign-off. Do not automatically unpark Section 5 work.

### Section C - Planned file set

1. `docs/flow-runs/issue-1897.md` - this append-only scope/authority record.
2. `docs/flow-runs/issue-1897.as-read.md` - helper's issue snapshot at approval.
3. `docs/flow-runs/issue-1897.lanes-demonstrated.md` - observations and unknowns.
4. `docs/measurements/pi/issue-1897-validation-protocol.md` - fixture and owner
   protocol, pinned command recipes, pre-state/undo requirements.
5. `docs/measurements/pi/issue-1897-install-undo.md` - attributed sanitized
   raw-result summary with digests; append actual fixture/owner runs separately.

Scope: documentation, existing-command fixture replay and host evidence only.
No new product installer/uninstaller, provider or runtime feature. A missing
rollback/report helper or executable owner relay needs a scoped amendment and
committed opposite controls before activation. Existing readers receive actual
outputs, not rewritten verdicts. No automatic new acceptance-grading helper.

Risks: missing pi or owner authority leaves discovery/owner lanes unexecuted;
collisions or existing CPP records may require a narrower reviewed recovery
plan. Undo must account for work/journal/derived locks, not just topic folders.
Removing a newly created primary lock requires the exclusive writer window;
advisory locks alone cannot prove absence of a racing writer. Owner validation
cannot waive #1896 UNKNOWNs. The cap-7 ruling for #1896 does not transfer here.

### Lanes for this change

| Lane | Answer | Values and evidence plan |
|---|---|---|
| Checkout | will test | Linked worktree pinned to main `337f411a`; main checkout execution is not newly covered |
| Harness | not applicable | Existing Claude/Codex installations unchanged; pi reader is recorded separately |
| Driver | not applicable | Manual managed validation, no delegated-driver behavior changes |
| Coordination | not covered | Managed task messages are not a runtime Kyle coordination test; fixture commands do not claim that lane |
| CI provider | not covered | No CI while frozen; Woodpecker only after clearance, no live GitHub Actions claim |
| Project state | will test | Absent CPP state with synthetic personal neighbor, owned installed state, edited/missing/marker fixture states; unsupported owner collisions refuse |
| Toolchain version | will test | Installed local interpreter/Make/Git, approved host pi version recorded exactly; no matrix claim |
| Clone shape | not covered | This validation uses full local history; prior A1 full/shallow coverage remains attributed, not rerun evidence |
| Run location | will test | CPP-root Make invocation; external invocation is not newly covered by this replay |
| Gate target | not applicable | No consumer interpreter/quality-runner change |
| Wave role state | not applicable | No registry release/re-registration behavior change |
| Reader: installed verifier | will test | Actual CLI/core compares actual full fresh output to actual installed packages, including failing mutations and repaired positive |
| Reader: fixture pi discovery | will test | Real fixture pi when available; missing binary means unexecuted, not a pass |
| Reader: owner pi reload | will test | Existing owner session only after ruling and concrete batch review; relevant discovery evidence only |
| Reader: owner evidence/sign-off | will test | Actual pre-state/install/undo/discovery records, with all remaining UNKNOWNs visible |

Reader identification follows the issue's explicit readers and existing
`pi-skill-sync`/`pi-host-fixture` references. This change alters no production
output schema and asserts no absence of other cross-repository readers.


### Durability checkpoint authority - mailbox 40651

The orchestrator permits a WIP branch push with NO PR for durable backup.
This exception does not unpark the issue or authorize CI or owner action.
The working repository and detached source now live under persistent workspace
storage, with independent Git objects and no active /tmp Git dependency. The
run identity and as-read helper state were copied byte-for-byte; there is still
no helper approval stamp for owner execution. A WIP commit records local
preparation, not Part-1 sign-off.

Both original evidence sets and the original replay source were copied without
changing their bytes, and all 228 files in the evidence sets were hash-compared.
A portable replay derivative changes only source/run location initialization.
It completed against the persistent source and reproduced the same summary
bytes, with fixture cleanup and source cleanliness observed. Raw evidence stays
outside the CPP checkout; historical /tmp strings inside it remain unchanged.


### Owner approval and fresh-base checkpoint - mailbox 40665

The [public owner ruling](https://github.com/cooneycw/claude-power-pack/issues/1897#issuecomment-7179886781)
unparks #1897 and permits fixture pushes/PR CI plus one narrowly scoped owner
install/verify/reload/undo/reload. Mailbox 40665 approves this plan, requires
merging main `c434101e7ae580de3bb81ca1db9d325a0483c44c` without rebasing,
and keeps PR creation pending orchestrator clearance. This supersedes earlier
pending-authority statements; it does not claim a helper approval stamp.

Merge `fbd5d25f` preserves the prior WIP history. A new replay against a clean
detached source at that exact main revision passed the four fixture scenarios.
The sanitized results and digests are appended to the measurement record.
Owner action remains unexecuted: exact commands must first be committed and
sent to the orchestrator for presentation to the owner. The supported owner
preflight now stops if any target slug or CPP state, including a primary lock,
already exists. The earlier retain-existing-lock option is not used here.
No new pi process may use owner HOME, including a version query. No provider
turn, trusted-config change or credential inspection is permitted. #1896's
review cap does not transfer; #1897 uses the default review cap.

### Exact probe amendment - mailbox 40671 (before implementation)

Mailbox 40671 assigns the exact owner probe now that the fixture lane passed.
Add `docs/measurements/pi/issue-1897-owner-probe.py` and its adjacent command
protocol `issue-1897-owner-probe.md`, plus committed opposite cases in
`tests/test_pi_owner_probe.py`. These are one-use validation artifacts, not a
product uninstaller or new acceptance gate. The probe will use the delivered
Make/CLI, record pre-state and inverse before install, require an exclusive
operator window, pause for manual existing-session reload evidence, and remove
only a sealed still-matching created manifest. It never starts pi. Any changed
state refuses deletion; fixture controls cover that refusal and a collision
before install as well as a complete positive. No owner activation occurs here;
commit SHA, path and digest go to the orchestrator for owner presentation first.

### Stopped owner run and recovery amendment - mailbox 40896

The orchestrator reports the owner install and real verifier succeeded at
18 packages / 36 examined members, current. The probe then stopped before
sealing, reload or undo because it compared fresh build directory modes with
installed modes. A helper umask of 0002 produced 0775 build directories; the
installer's directory policy is 0755. All 36 file bytes/modes reportedly match.
This is a probe defect. Owner topics and management state remain installed;
there is no sealed post-state and no claim of discovery or cleanup success.

Before implementation, scope is extended to a one-use recovery artifact
`docs/measurements/pi/issue-1897-owner-recovery.py`, its adjacent `.md` review
protocol, and `tests/test_pi_owner_recovery.py`. Fix the probe comparison to
normalize expected directory modes to installer policy, retaining actual-mode
checks. Add a committed umask-0002 regression that fails on the original probe.
Recovery validates the original absent baseline and exact recorded canonical
population, checks normalized bytes/modes and CPP ownership markers, takes all
three existing locks without creation, and removes only enumerated recorded
CPP-created files/directories by unlink/rmdir. Dry-run lists exact operations;
unknown/changed state refuses before any deletion. Personal neighbors survive.
Require actual delivered verification before recovery and expected
missing-installed verification afterwards. No owner execution is authorized by
this amendment; freeze commits and digests for independent review and owner
presentation before helper use. Fixture execution scope was queried separately.

The recovery fixture also freezes the exact original probe bytes in
`tests/fixtures/pi-owner-probe-a3dc5d6e.py.txt` (SHA256 matching the submitted
original). This lets the stopped-install control remain reproducible after
squash merge without relying on a WIP commit remaining reachable. These source
fixtures require full local history through the explicitly pinned c434101e;
shallow-checkout execution is outside this validation's declared clone lane.

### Original root inverse clarified - mailbox 40923

The orchestrator confirms the original logged inverse authorizes a FINAL plain
rmdir of the skills root when `skills_existed=false`, only if empty and not a
symlink. This supersedes the conservative root-retention limitation at 6c5d4ddd;
it is the existing inverse, not a general expansion of removal scope. The
reviewed dry-run must print that final conditional operation. Add committed
empty-created-root success and unrelated-root-file refusal/preservation cases.
A nonempty-root refusal occurs after the recorded topic/state removals and
must not be reported as whole-filesystem restoration. One new push then freeze;
independent review and owner presentation precede dry-run, and owner approval
of the exact dry-run plan precedes execute.

### Reviewer root-step notes - mailbox 40929

The interim review of 6c5d4ddd raised no findings and requested explicit root
step details. Recovery now lstat-checks directory type and the planned root
identity/mode immediately before plain rmdir. ENOTEMPTY emits a STOP message
and `root-retained.json` stating whether recorded targets were restored; it
never emits successful recovery. The protocol explicitly notes the lock paths
are themselves unlinked, so the operator's confirmed window remains essential.
Affected empty/nonempty/symlink root cases all passed again (3 cases); basetemp
removed. This is a narrow review clarification, not owner execution authority.

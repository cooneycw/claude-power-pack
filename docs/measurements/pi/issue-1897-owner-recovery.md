# #1897 unsealed-install recovery - review before execution

The first owner run installed and verified all 18 topics / 36 members, then
stopped because the probe compared umask-dependent build directories (0775)
with installer directories (0755). It did not save `sealed-post.json` or undo.
Master's subsequent relay confirms all 18 user-scope topics were visible after
reload. This procedure recovers that specific completed, unsealed installation;
it is not a general uninstaller or permission to repeat the installation.

Master must show the owner this protocol, the adjacent recovery script, the
fixed probe module it imports, their exact reviewed commit/digests, and concrete
path bindings before the host helper runs anything. The existing-session
presence observation does not authorize recovery on its own. No owner action
was performed while preparing these artifacts.

Keep the original journal and relevant captures durably under workspace storage
on the host. A copied journal is supported: its recorded source/home/agent
bindings must still describe the actual installation. Never edit its recorded
targets, expected population, baseline or original command results. The source
must remain clean at `c434101e7ae580de3bb81ca1db9d325a0483c44c` and at the path
recorded in `before-and-undo.json`. Source, journal and new recovery evidence
must have physical absolute paths outside owner home/agent and disjoint from
each other. The same conservative ASCII path rules as the probe apply.
Before any owner IO, recovery requires the four ORIGINAL unsanitized journal
SHA256s supplied by master's relay (mailbox 40903), embedded in the script.
The sanitized design copy cannot pass this check. There is no hash override or
skip flag. The explicit `--home` binding must equal the original record.

Stop all other writers to the skill tree for the entire dry-run/review/execute
window, including lock removal. This is an explicit operator precondition;
advisory locks cannot prevent replacement-inode races. No new pi process,
version query, provider turn or trusted-config change is part of recovery.

After owner clearance, the host helper runs this exact dry-run argv, substituting
the reviewed paths. Both Python files must be from the same submitted commit:

```sh
python3 <reviewed-checkout>/docs/measurements/pi/issue-1897-owner-recovery.py \
  --source <original-clean-source-at-c434101e> \
  --journal <retained-original-journal-or-byte-identical-copy> \
  --home <approved-owner-home-matching-original-record> \
  --evidence <new-private-recovery-evidence-directory> \
  --dry-run --exclusive-window-confirmed
```

Dry-run checks the exact recorded canonical target population and absent
baseline; original install/verify success; current full delivered verification;
all topic bytes/membership, file modes 0644 and directory modes 0755; each exact
CPP source marker; and exact CPP management ledger, empty work directory and
three empty 0600 locks. Management identity is established by the exact producer,
pi namespace, revision, source and member records, not a SKILL marker. Unknown
management members, additional identities, changed bytes/modes, missing targets,
aliases or hard links refuse before deletion. The canonical population is read
from the approved source, never inferred from an empty owner scan.

The script prints the exact ordered unlink/rmdir operations and saves them in
`removal-plan.json`, including the current identities/hashes/modes and original
record digest. It acquires all three existing locks without creation. Dry-run
does not remove or write owner paths; its evidence files are private scratch.
It invokes only the delivered read-only verifier, not the build/install targets.
All removal candidates must be inside the exact recorded target roots. Personal
neighbors are never inventoried or added to that plan. If a canonical CPP-marked
topic is omitted from the original record, recovery refuses the whole plan.

Review the printed plan and preserve it. After approval to execute that exact
plan, use the SAME source, journal and evidence bindings:

```sh
python3 <reviewed-checkout>/docs/measurements/pi/issue-1897-owner-recovery.py \
  --source <original-clean-source-at-c434101e> \
  --journal <retained-original-journal-or-byte-identical-copy> \
  --home <same-approved-owner-home> \
  --evidence <same-private-recovery-evidence-directory> \
  --execute --exclusive-window-confirmed
```

Execution repeats verification, re-acquires every existing lock without
creation, and requires exact equality with the saved dry-run plan before any
deletion. It uses only unlink and rmdir; there is no recursive removal. It
retains the skills root because that root is not in the recorded target list,
even if empty. It verifies the recorded targets are absent and invokes the
actual delivered verifier afterwards: expected missing-installed exit 1 with
18 expected packages / 36 expected members / zero examined members, not current.
Private command JSON distinguishes Make's failure status from the CLI verdict.

Any refusal or OS error stops. Preserve all journal/evidence and surviving
state; no automatic retry, adoption or broad cleanup is authorized. A partial
deletion caused by an unexpected OS failure requires another reviewed recovery.
No unrecorded neighbor, even CPP-marked, is a deletion candidate. Only canonical
topics are examined; no whole-agent or whole-skills inventory is performed.

After successful recovery the helper types `/reload` in the SAME existing pi
session and captures the relevant list for comparison with the original zero
baseline. The script emits this step but never types it or starts pi. Record
that observation separately from the scoped filesystem result. Publish only
sanitized evidence; retain private paths, unrelated skill names and conversation
privately. Owner sign-off and both #1896 UNKNOWN measurements remain separate.

Committed disposable-home cases use the exact original `a3dc5d6e` probe under
umask 0002 to reproduce the stopped installation. They cover exact dry-run and
successful recovery, unrecorded personal neighbors, changed content/directory
mode/management, an omitted CPP-marked canonical target, tampered dry-run plans,
and edits between dry-run and execution. The separate probe regression fails
on the original probe and completes on the fixed policy comparison.

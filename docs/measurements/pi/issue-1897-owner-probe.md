# #1897 exact owner probe - review before execution

The original owner execution stopped after successful install/verify because
its directory-mode comparison used the build tree's umask. The fixed probe
compares expected directories with installer policy 0755 (files 0644), retaining
strict checks on actual installed modes. Recover the still-installed first run
using the separately reviewed [recovery protocol](issue-1897-owner-recovery.md).
Do not rerun this fresh-install probe against the existing installation.

Mailbox 40671 assigns preparation only. Master must show this file and the
adjacent [Python probe](issue-1897-owner-probe.py), at the submitted commit and
digest, to the owner before the host helper executes anything. This is one
authorized install/undo, not standing permission. No owner run is claimed here.

The helper must first identify the owner's EXISTING idle pi session and capture
its relevant baseline skill list. Keep all other writers to the selected skill
tree stopped until both reload observations and undo finish. The flag below is
the operator's assertion of that window; it is not a concurrency detector.
The probe never starts pi or sends a provider turn. The helper performs the two
literal `/reload` steps manually in that existing session when prompted.

Supply physical absolute paths for a clean detached CPP source at
`c434101e7ae580de3bb81ca1db9d325a0483c44c`, the approved owner home and agent,
and a NEW private journal directory. Source and journal must be outside owner
home/agent, and disjoint from one another. Existing personal skills are allowed.
This one-use batch accepts path components using ASCII letters, digits, dots,
underscores and hyphens only; spaces and Make/shell metacharacters refuse.
Existing target slugs, management state or primary lock stop this first batch.
Do not resolve a collision by adoption or deletion. Do not enumerate the agent.
No startup/version query of pi is part of this procedure.

After reviewing the concrete path substitutions with the owner, the host helper
runs this exact argv (angle-bracket values are mandatory reviewed bindings):

```sh
python3 <probe-checkout>/docs/measurements/pi/issue-1897-owner-probe.py \
  --source <clean-source-at-c434101e> \
  --home <approved-owner-home> \
  --agent <approved-existing-agent> \
  --journal <new-private-journal-outside-owner-home-and-source> \
  --exclusive-window-confirmed
```

The probe builds with `make pi-skills`, derives the actual 18 topics / 36
members, and reads only those fixed CPP slots/state. Before install it flushes
`before-and-undo.json` with target list, absent baseline, expected manifest and
exact inverse. It calls delivered `make pi-skills-install` and
`make pi-skills-verify` with explicit pinned source, home, agent and private
history, using a fresh environment. Its subprocess HOME and XDG directories
belong to the private journal. It seals actual installed files and management
state only after full positive verification and independent bytes/mode checks.

At the first prompt, the helper performs `/reload` in the existing session,
captures only the relevant skill list, and checks all 18 topics against the
logged slugs. Only after that observation enter `RELOAD-PRESENCE-CAPTURED`.
Otherwise stop; installed state remains for recovery review.

Undo first compares the entire recorded CPP post-state, acquires all three
existing locks exclusively without creation, and compares again. A changed,
missing, aliased or unexpected artifact refuses deletion. It removes only the
manifest's regular files and directories, using unlink/rmdir rather than a
recursive removal command. A newly created skills root is removed only if empty.
The actual post-undo verifier must return missing-installed, with 18 expected
packages and zero examined members; that is not a parity-positive result.

At the second prompt, perform `/reload` again in the SAME session and capture
the relevant list. Compare it with the pre-install baseline, then enter
`RELOAD-BASELINE-CAPTURED`. Keep private journals and relevant captures for owner
review; publish only sanitized evidence. Never publish unrelated skill names,
private paths/session names, unrelated conversation, tokens or sensitive files.
The probe does not inspect or name sensitive credential paths.

A failure leaves the journal and surviving state intact. No retry, automatic
adoption or broad cleanup is authorized. A partial install without sealed state
needs a separately reviewed recovery procedure. The comparison covers fixed CPP
paths and skills-root identity/mode; parent timestamps and all unrelated owner
files are outside its claim. Tests retain a synthetic personal neighbor.
The operator-exclusive window is required even with advisory locks, especially
while lock paths are removed. This probe is not safe for concurrent writers.

Committed controls in `tests/test_pi_owner_probe.py` run only disposable homes:
full actual CLI install/verify/undo, pre-existing slot/state refusal, edited
post-state refusal without deletion, unexpected management-member refusal,
missing reload confirmation and path alias refusal. Simulated fixture prompt
responses establish sequencing only; they are not pi discovery evidence.
Owner sign-off stays separate. #1896's built-in inventory and skill-loader
diagnostic measurements remain UNKNOWN; Section 5 stays deferred.

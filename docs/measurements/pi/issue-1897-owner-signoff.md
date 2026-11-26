# #1897 Part 1 evidence for owner sign-off

Owner decision: **PENDING**. The install/discovery/undo lane is observed; two
#1896 measurements remain UNKNOWN. This record requests a decision on Part 1,
not automatic approval of deeper integration or closure of #1896.

The disposable fixture lane passed against delivered source `c434101e`: all 18
CPP topic packages / 36 members installed and verified. A changed reference
byte, missing package and stripped source marker each made actual parity fail;
real repair restored the positive result. Undo refused changed state and later
restored its scoped baseline while preserving a synthetic personal neighbor.

Master's host observations now establish the owner sequence:

| Observation | Result |
|---|---|
| Existing-session baseline | Zero skill entries |
| Delivered install and verifier | 18 packages / 36 examined members, current |
| Existing-session reload and skill completion | 18 user-scope entries, exactly the journal's topic slugs |
| Reviewed, owner-approved recovery at `d013ef49` | Exit 0; execution plan identical to the reviewed dry-run plan; all 20 recorded CPP targets and the logged-new skills root absent |
| Actual verifier after recovery | Missing-installed: 18 expected packages / 36 expected members / zero examined, CLI exit 1 (Make 2) |
| Same-session reload at 04:26:17Z | Zero skill entries, matching baseline |

The first owner probe **stopped after successful installation** because its
comparison wrongly used fresh build directory modes: umask 0002 produced 0775,
while the installer creates 0755. All file bytes/modes matched. No sealed
post-state or undo was produced by that failed probe. The defect is fixed by
comparing against installer policy; the umask regression fails on the original
probe and passes fixed. Cleanup used the separately reviewed and approved
`d013ef49` recovery script, rather than retrying or bypassing the stopped probe.
Optional later clarifications in `64e9ef07` were not executed on owner paths.

Two measurements remain **UNKNOWN under #1896**:

- The built-in-tool inventory was not exposed by the measured RPC interface.
- The measured RPC stderr did not expose skill-loader diagnostics.

Equal stderr covers only the runtime/extension/provider/flag diagnostics that
were actually exposed. Discovery and undo do not resolve either UNKNOWN, prove
bearer isolation or contextual effectiveness, or establish a container boundary.
Parent timestamps and a whole-agent unchanged claim are outside this evidence.
The original journal and recovery artifacts remain retained on the host; private
paths/session names and unrelated conversation are omitted here.

The [sanitized owner record](issue-1897-owner-lane.json) attributes observations
to master's relays and separates the locally verified decoded-report digest
from host-reported artifact digests. The [full measurement](issue-1897-install-undo.md)
retains fixture results, the probe defect, its red/green correction and recovery.
Owner sign-off must be recorded explicitly before a closing reference is used.

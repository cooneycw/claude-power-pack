<!-- flow-run n=1 id=af8d279630304b5e879aa3dfcb349633 -->
## Run 1 - issue #1290 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1290
- Read at:      2026-09-28T17:19:21Z
- updatedAt:    2026-09-27T13:35:50Z   (context only - moves on comments and labels)
- Body digest:  f3fb29c6688bb546670829db2cfa2c098a4009e20721340c6905d0cebc4a164c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3405 of 3405 (cap 16384)

### Body as read
## Outcome

Before starting an enabled workflow, an operator can tell whether it is usable, what was actually checked, and the next repair action. Installed, current, consistently configured, reachable, and unexamined must not collapse into one READY label.

Source: owner-requested capability assessment and incremental improvement 4, 2026-09-27. Extend the existing `/cpp:status`, install-drift, toolchain provenance and host-surface machinery rather than creating another status subsystem.

## First increment

Cover only three existing capabilities: flow, second-opinion review, and browser QA. Preserve optionality: an absent optional model/browser service does not prevent an unrelated local flow task.

Depends on: #1256, #1282.

Those issues own effective MCP scope/endpoint conflict detection and checkout freshness respectively. Their behavior must be available before the integrated readiness result is accepted; consume their implementation rather than duplicating it. Report preparation can start earlier.

## Acceptance

- One status invocation gives a compact readiness table for the three capabilities, naming source revision, required local artifacts/dependencies, effective service configuration where relevant, and each observation's scope.
- Distinguish disabled/not installed, installed but unexamined, stale or unknown checkout, conflicting configuration, unreachable/unusable service, and ready for the explicitly tested operation. No response or unsupported probe is not ready.
- A bounded, harmless probe is available for each enabled capability. A metadata/list/capability probe establishes only that narrow fact; if an end-to-end probe needs authentication or a paid model request, leave that layer unexamined unless separately authorized. Never submit paid generation merely to print status.
- Fixtures discriminate missing helper, conflicting MCP scopes, unreachable service, old checkout, failed freshness lookup, and a healthy case. No test requires production credentials or a production service.
- A repeatable clean-home install/update smoke check demonstrates that installed helper/skill artifacts can execute the selected local probe after install and after update, using the same real installation entry points. Preserve unrelated host-owned files and namespace separation. At least one deliberately missing/stale artifact must change the verdict.
- Expose the same observations to human and machine consumers without independent reclassification. Keep secret values, authentication state and endpoint credentials out of output.
- Canonical command edits regenerate the Codex mirrors; verify the shipped generated surface, not only its source.

## Boundaries

No automatic repairs, MCP scope removal, dependency installation, service starts, credential rotation or production configuration writes as a side effect of status. No new daemon, fleet dashboard or parallel source of configuration truth.

#1074 already supplied a bounded clean-install demonstration after the old distribution matrix was retired. Reuse its evidence/fixtures where appropriate; this issue adds a repeatable narrow readiness/install-update contract, not a revival of that retired matrix. Implementation shape remains revisable if the observable outcome and these boundaries are preserved.

Value-first sequence and related work: #1292. The sequence does not replace this issue's acceptance.


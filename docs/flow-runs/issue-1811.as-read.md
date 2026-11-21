<!-- flow-run n=1 id=15008b78315749218f268bf83d96d4c1 -->
## Run 1 - issue #1811 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1811
- Read at:      2026-11-21T14:55:45Z
- updatedAt:    2026-11-14T06:06:59Z   (context only - moves on comments and labels)
- Body digest:  bcbcb3c6180eca866c4858a73289ccbd808635a404479a9a94f8cdfdb5522fa4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3072 of 3072 (cap 16384)

### Body as read
## What this tracks

`/flow:auto` runs gates that the delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`) neither run nor replace with an equivalent step. The driver parity test (#1810) exempts each of these pairs with a one-line reason and a link to this issue. The test reds on any gap not listed in `docs/agents/driver-parity.json`, so this list cannot grow without a recorded decision.

Each gap is the same for all three drivers. Inventory measured on main `bcd0f3ed`:

| `/flow:auto` gate | codex | qwen | gemma | Why it is not covered today |
|---|---|---|---|---|
| `check-ignored-additions.sh` | gap | gap | gap | The delegated pre-commit text has no ignored-additions check. A plain `git diff` does not do this job. |
| `flow-finish-gate.sh` | gap | gap | gap | The drivers call the runner directly, with a lint/test fallback. That does not give the audited wrapper's behaviour (counter-model enrolment, verdict line, resume, admission). |
| `flow-live-driver-guard.sh` | gap | gap | gap | It is reached only in the resolver's resume lane. It is not the check every lane runs before the first edit. |
| `flow-plan-record.py declare-salvage` / `drift` / `head-check` | gap | gap | gap | All three delegated drivers still omit these remaining plan-record operations. #1809 (PR #1815) added `reconcile`, `read-issue`, `begin-run`, `approve` and `compliance`; those five are now run, not exempt. |
| `flow-stale-check.sh` | gap | gap | gap | A fetch plus merge-base for the empty-diff check gives no stale-base or collision advice. |
| `flow-worktree-claim.sh` | gap | gap | gap | The resolver stakes the first claim. There is no separately named check before edits and no release lifecycle. |
| `flow-worktree-guard.sh` | gap | gap | gap | The workspace-write sandbox and the empty-diff check do not detect edits leaking into the main checkout. |
| `friction-log.sh` | gap | gap | gap | There is no always-on, fail-open friction capture. |
| `nit-store-resolve.sh` | gap | gap | gap | There is no step that routes supplemental findings. General review findings are not the same thing. |
| `speckit-context.py` | gap | gap | gap | There is no spec-context check. A task's recorded context still matters. |

## Not in this list

- **Run by the drivers:** `flow-start-resolve.sh` and `counter-model-receipt.py`.
- **Covered by an equivalent cited step:** `flow-ci-status.sh`, `gh-pr-merge.sh` and `worktree-remove.sh`. When merging, each driver's Step 8 follows `/flow:auto` Step 7.
- **Exempt for a real reason:** `codex-skill-resync.sh`. It is needed only for edits to commands or skills, which the delegated drivers refuse and route to `/flow:auto`.
- **Run since #1809 (PR #1815):** `flow-plan-record.py reconcile`, `read-issue`, `begin-run`, `approve` and `compliance`.

## Done when

Each row is either closed by a driver change, which removes its exemption and makes the parity test require the gate, or kept with a reason the owner accepts as permanent. Work this one row at a time. A single row may become its own issue when someone picks it up.



<!-- end of body -->

<!-- flow-run n=2 id=bee480efb058429fb5ae2a452abdbbfe -->
## Run 2 - issue #1811 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1811
- Read at:      2026-11-21T15:33:36Z
- updatedAt:    2026-11-14T06:06:59Z   (context only - moves on comments and labels)
- Body digest:  bcbcb3c6180eca866c4858a73289ccbd808635a404479a9a94f8cdfdb5522fa4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3072 of 3072 (cap 16384)

### Body as read
## What this tracks

`/flow:auto` runs gates that the delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`) neither run nor replace with an equivalent step. The driver parity test (#1810) exempts each of these pairs with a one-line reason and a link to this issue. The test reds on any gap not listed in `docs/agents/driver-parity.json`, so this list cannot grow without a recorded decision.

Each gap is the same for all three drivers. Inventory measured on main `bcd0f3ed`:

| `/flow:auto` gate | codex | qwen | gemma | Why it is not covered today |
|---|---|---|---|---|
| `check-ignored-additions.sh` | gap | gap | gap | The delegated pre-commit text has no ignored-additions check. A plain `git diff` does not do this job. |
| `flow-finish-gate.sh` | gap | gap | gap | The drivers call the runner directly, with a lint/test fallback. That does not give the audited wrapper's behaviour (counter-model enrolment, verdict line, resume, admission). |
| `flow-live-driver-guard.sh` | gap | gap | gap | It is reached only in the resolver's resume lane. It is not the check every lane runs before the first edit. |
| `flow-plan-record.py declare-salvage` / `drift` / `head-check` | gap | gap | gap | All three delegated drivers still omit these remaining plan-record operations. #1809 (PR #1815) added `reconcile`, `read-issue`, `begin-run`, `approve` and `compliance`; those five are now run, not exempt. |
| `flow-stale-check.sh` | gap | gap | gap | A fetch plus merge-base for the empty-diff check gives no stale-base or collision advice. |
| `flow-worktree-claim.sh` | gap | gap | gap | The resolver stakes the first claim. There is no separately named check before edits and no release lifecycle. |
| `flow-worktree-guard.sh` | gap | gap | gap | The workspace-write sandbox and the empty-diff check do not detect edits leaking into the main checkout. |
| `friction-log.sh` | gap | gap | gap | There is no always-on, fail-open friction capture. |
| `nit-store-resolve.sh` | gap | gap | gap | There is no step that routes supplemental findings. General review findings are not the same thing. |
| `speckit-context.py` | gap | gap | gap | There is no spec-context check. A task's recorded context still matters. |

## Not in this list

- **Run by the drivers:** `flow-start-resolve.sh` and `counter-model-receipt.py`.
- **Covered by an equivalent cited step:** `flow-ci-status.sh`, `gh-pr-merge.sh` and `worktree-remove.sh`. When merging, each driver's Step 8 follows `/flow:auto` Step 7.
- **Exempt for a real reason:** `codex-skill-resync.sh`. It is needed only for edits to commands or skills, which the delegated drivers refuse and route to `/flow:auto`.
- **Run since #1809 (PR #1815):** `flow-plan-record.py reconcile`, `read-issue`, `begin-run`, `approve` and `compliance`.

## Done when

Each row is either closed by a driver change, which removes its exemption and makes the parity test require the gate, or kept with a reason the owner accepts as permanent. Work this one row at a time. A single row may become its own issue when someone picks it up.



<!-- end of body -->

<!-- flow-run n=3 id=239ea5cdda114e6d9e1ec9bbb4267b3f -->
## Run 3 - issue #1811 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1811
- Read at:      2026-11-21T18:00:17Z
- updatedAt:    2026-11-21T15:38:23Z   (context only - moves on comments and labels)
- Body digest:  bcbcb3c6180eca866c4858a73289ccbd808635a404479a9a94f8cdfdb5522fa4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3072 of 3072 (cap 16384)

### Body as read
## What this tracks

`/flow:auto` runs gates that the delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`) neither run nor replace with an equivalent step. The driver parity test (#1810) exempts each of these pairs with a one-line reason and a link to this issue. The test reds on any gap not listed in `docs/agents/driver-parity.json`, so this list cannot grow without a recorded decision.

Each gap is the same for all three drivers. Inventory measured on main `bcd0f3ed`:

| `/flow:auto` gate | codex | qwen | gemma | Why it is not covered today |
|---|---|---|---|---|
| `check-ignored-additions.sh` | gap | gap | gap | The delegated pre-commit text has no ignored-additions check. A plain `git diff` does not do this job. |
| `flow-finish-gate.sh` | gap | gap | gap | The drivers call the runner directly, with a lint/test fallback. That does not give the audited wrapper's behaviour (counter-model enrolment, verdict line, resume, admission). |
| `flow-live-driver-guard.sh` | gap | gap | gap | It is reached only in the resolver's resume lane. It is not the check every lane runs before the first edit. |
| `flow-plan-record.py declare-salvage` / `drift` / `head-check` | gap | gap | gap | All three delegated drivers still omit these remaining plan-record operations. #1809 (PR #1815) added `reconcile`, `read-issue`, `begin-run`, `approve` and `compliance`; those five are now run, not exempt. |
| `flow-stale-check.sh` | gap | gap | gap | A fetch plus merge-base for the empty-diff check gives no stale-base or collision advice. |
| `flow-worktree-claim.sh` | gap | gap | gap | The resolver stakes the first claim. There is no separately named check before edits and no release lifecycle. |
| `flow-worktree-guard.sh` | gap | gap | gap | The workspace-write sandbox and the empty-diff check do not detect edits leaking into the main checkout. |
| `friction-log.sh` | gap | gap | gap | There is no always-on, fail-open friction capture. |
| `nit-store-resolve.sh` | gap | gap | gap | There is no step that routes supplemental findings. General review findings are not the same thing. |
| `speckit-context.py` | gap | gap | gap | There is no spec-context check. A task's recorded context still matters. |

## Not in this list

- **Run by the drivers:** `flow-start-resolve.sh` and `counter-model-receipt.py`.
- **Covered by an equivalent cited step:** `flow-ci-status.sh`, `gh-pr-merge.sh` and `worktree-remove.sh`. When merging, each driver's Step 8 follows `/flow:auto` Step 7.
- **Exempt for a real reason:** `codex-skill-resync.sh`. It is needed only for edits to commands or skills, which the delegated drivers refuse and route to `/flow:auto`.
- **Run since #1809 (PR #1815):** `flow-plan-record.py reconcile`, `read-issue`, `begin-run`, `approve` and `compliance`.

## Done when

Each row is either closed by a driver change, which removes its exemption and makes the parity test require the gate, or kept with a reason the owner accepts as permanent. Work this one row at a time. A single row may become its own issue when someone picks it up.



<!-- end of body -->

<!-- flow-run n=4 id=03776eb0b3d5448a9ab2d99b0e00cb74 -->
## Run 4 - issue #1811 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1811
- Read at:      2026-11-21T18:49:42Z
- updatedAt:    2026-11-21T15:38:23Z   (context only - moves on comments and labels)
- Body digest:  bcbcb3c6180eca866c4858a73289ccbd808635a404479a9a94f8cdfdb5522fa4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3072 of 3072 (cap 16384)

### Body as read
## What this tracks

`/flow:auto` runs gates that the delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`) neither run nor replace with an equivalent step. The driver parity test (#1810) exempts each of these pairs with a one-line reason and a link to this issue. The test reds on any gap not listed in `docs/agents/driver-parity.json`, so this list cannot grow without a recorded decision.

Each gap is the same for all three drivers. Inventory measured on main `bcd0f3ed`:

| `/flow:auto` gate | codex | qwen | gemma | Why it is not covered today |
|---|---|---|---|---|
| `check-ignored-additions.sh` | gap | gap | gap | The delegated pre-commit text has no ignored-additions check. A plain `git diff` does not do this job. |
| `flow-finish-gate.sh` | gap | gap | gap | The drivers call the runner directly, with a lint/test fallback. That does not give the audited wrapper's behaviour (counter-model enrolment, verdict line, resume, admission). |
| `flow-live-driver-guard.sh` | gap | gap | gap | It is reached only in the resolver's resume lane. It is not the check every lane runs before the first edit. |
| `flow-plan-record.py declare-salvage` / `drift` / `head-check` | gap | gap | gap | All three delegated drivers still omit these remaining plan-record operations. #1809 (PR #1815) added `reconcile`, `read-issue`, `begin-run`, `approve` and `compliance`; those five are now run, not exempt. |
| `flow-stale-check.sh` | gap | gap | gap | A fetch plus merge-base for the empty-diff check gives no stale-base or collision advice. |
| `flow-worktree-claim.sh` | gap | gap | gap | The resolver stakes the first claim. There is no separately named check before edits and no release lifecycle. |
| `flow-worktree-guard.sh` | gap | gap | gap | The workspace-write sandbox and the empty-diff check do not detect edits leaking into the main checkout. |
| `friction-log.sh` | gap | gap | gap | There is no always-on, fail-open friction capture. |
| `nit-store-resolve.sh` | gap | gap | gap | There is no step that routes supplemental findings. General review findings are not the same thing. |
| `speckit-context.py` | gap | gap | gap | There is no spec-context check. A task's recorded context still matters. |

## Not in this list

- **Run by the drivers:** `flow-start-resolve.sh` and `counter-model-receipt.py`.
- **Covered by an equivalent cited step:** `flow-ci-status.sh`, `gh-pr-merge.sh` and `worktree-remove.sh`. When merging, each driver's Step 8 follows `/flow:auto` Step 7.
- **Exempt for a real reason:** `codex-skill-resync.sh`. It is needed only for edits to commands or skills, which the delegated drivers refuse and route to `/flow:auto`.
- **Run since #1809 (PR #1815):** `flow-plan-record.py reconcile`, `read-issue`, `begin-run`, `approve` and `compliance`.

## Done when

Each row is either closed by a driver change, which removes its exemption and makes the parity test require the gate, or kept with a reason the owner accepts as permanent. Work this one row at a time. A single row may become its own issue when someone picks it up.



<!-- end of body -->

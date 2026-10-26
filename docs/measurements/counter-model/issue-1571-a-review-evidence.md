# Issue 1571-A review provenance and post-review fix

Canonical receipt: [2026-10-26T035050Z-issue-1571.json](2026-10-26T035050Z-issue-1571.json).
Base: `ad3c37e0c989c29d093a77fab6d313061924832b`.
Final source checkpoint: `32623cd636a816d3deeb1a1aa0695d4518d714af`.

Two actual Codex / gpt-6-astra passes ran, each with process exit 0 and a
complete diff plus source context. Both were diff-only: the reviewer executed
no commands, tests, or remote requests. Network was unverified by a sandbox
probe proxy, not measured directly on the reviewer. No repository git-config
credentials were found; this does not establish absence of all host credentials.

| Pass | Exact reviewed head | Findings | Native reviewer thread |
|---|---|---|---|
| 1 | `14fb6b6b4991717fb911c0a07eec088ef724b354` | 5 MEDIUM; all accepted | `01a1763b-2f18-78d3-b77e-0e1aca4a41eb` |
| 2 | `9a532a894fe96e2bf01835114b39eeaf4a0d86c7` | 1 MEDIUM; accepted | `01a17648-ddc4-7152-b8fc-d5fbf9b76072` |

All six findings were accepted, none rejected or deferred. Pass one identified
unused managed inventory overriding usable PATH Python, engine/repository
resolution loops, a neighboring module accepted as the engine, a host-dependent
control, and contradictory doctor report requirements. The regression population
failed on the actually reviewed source (6 failed, 24 passed), then passed after
fixes (30 passed). Two committed forbidden-command fixtures subsequently made a
deliberately blind command allowlist fail (2 failed, 30 passed); restored checks
passed all 32 tests. These fixtures invoke fake providers, not real auth/install.

Pass two identified an unusable managed candidate overriding another usable
managed candidate. The final production fix catches per-candidate inspection
errors, retains uncertainty, and continues discovery. A verified 3.11 candidate
wins; uncertainty remains when none verifies. Both directory orders failed on
the actual reviewed source (2 failed, 33 passed), then all 35 passed after the
fix. The new managed-neighbor GOOD control failed the reviewed adapter (exit 2),
then all six registered cases passed with zero unavailable. Two additional
acceptance cases distinguish known 3.12 plus an empty inventory (missing) from
invalid-only discovery (unknown), producing 37 passing focused tests. Lint and
type checking (388 files) also passed at that checkpoint (`fc0e4ebb`).

The orchestrator directly assessed the complete post-review production/control
delta and then the final two acceptance tests (mailbox 9934 and 9937). No third
Astra pass ran. The final source is not claimed to have received a clean Astra
review; the canonical receipt names the actual last reviewed ancestor.

The first complete local gate ran on `4fd8c25a` under actual Python 3.12.3.
It exited 1, run `finish-e3a3dead`: 8498 passed, 3 failed, 3 skipped in 381.03s.
There was one pytest invocation and no automatic or manual retry. Security
passed with three advisories. `make verify` stopped at its test prerequisite;
later verification, including the registered-control stage, was not reached.
The three failures were genuine integration gaps: an undispositioned LOW B106
on the noncredential gh validator sentinel, coverage declarations whose actual
test driver paths were not in the recognized binding shape, and missing exit
markers/namespaces in the installed helper family.

The final source checkpoint fixes all three contracts. It records the B106
reading in the ledger, ADR 0010 and security register without suppressing scans;
uses canonical path bindings for the actual import/subprocess drivers; and
emits stderr exit markers from both helpers while preserving JSON stdout and
actual statuses. The Python wrapper retains exception diagnostics before the
marker and handles failed output flushes; the shell forwards the child status
without an `exec` that would bypass its exit trap. Ten controlled status,
usage and exception cases failed on the pre-fix helpers, then passed. Two
`/dev/full` cases failed with the original Python source, then passed restored.
All four focused integration modules passed (215 tests before adding those two
flush cases); the final preflight module passed all 49 tests. Lint, type checking
(388 files), generated mirror checks and all six preflight control cases passed,
with zero controls unavailable and the always-ready anchor still missing all
three adverse populations. One earlier focused invocation timed out after one
second and is not counted as a completed test result.

The orchestrator directly accepted the complete integration delta in mailbox
9968. No third Astra review ran, no new review identity is claimed, and the
canonical receipt remains unchanged. The failed gate's raw log and state remain
preserved; the state SHA256 is
`92436bfc2d9aa0ef2fd3770ea8faabcd2582751d150ae5b909b83556dcaed4ff`.
A fresh complete gate after the integration fix remains pending authorization.

The final review report proposed 13 grouped red-case populations: bootstrap,
gh capability, uv presence, Python availability, Git identity, optional reviewer,
harness/engine, aggregate readiness, filesystem detector, command allowlist,
installer/bundle integrity, permission parity, and doctor readiness. The receipt
conservatively records zero already-covered groups: no group-by-group proof of
every proposed boundary was completed. This lower bound does not assert the
existing tests covered nothing, nor that every static proposal was executed.

Runtime and effects evidence is bounded. Python 3.10 compatibility was checked
with AST grammar only; native 3.10 execution remains unmeasured. Controlled
3.11 version observations are not native 3.11 runtime evidence. Focused tests
ran under native 3.12.3. The complete local gate will use installed 3.12;
native 3.11 verification remains pending the required existing CI lane, which
must exercise the full suite and registered controls before merge. No runtime
download or installation is authorized for this slice. The
real gh 2.102.0 probe initially created a telemetry device-id. Final version,
issue and PR probes with telemetry/update settings disabled preserved seven
owned fixture roots and emitted no HTTP-debug traces. This is a bounded client
trace and owned-state comparison, not a syscall network fence or whole-host
no-effects guarantee. Deliberately blind filesystem and telemetry variants
failed their detector tests. The always-ready anchor missed all three adverse
registered populations, while the real observer distinguished them.

Earlier slice 1572 logs genuinely recorded Python 3.11.14, without an explicit
interpreter selector or recorded cache/runtime provenance. Its old venv now
resolves to a nonexistent 3.11.14 target under `/home/claude/.local/share/uv/python`;
the current venv resolves to observed `/usr/bin/python3.12`. A separate root-home
inventory was inaccessible and remains unknown. This is consistent with fleet
context that HOME-managed interpreters do not survive container respawn while
`/workspace` persists, but the gate metadata does not prove that cause or timing.

A local wrapper failed to parse before launching the second pass; it invoked
no Codex process and is not a third actual pass. Its original tool-call/error
events are preserved in private worker evidence. The corrected second-pass
context measured 193445 bytes. No unmeasured context-size claim is retained.

Actual native reviewer rollouts, relative to the native sessions root:

- `2026/10/26/rollout-2026-10-26T03-22-32-01a1763b-2f18-78d3-b77e-0e1aca4a41eb.jsonl`
- `2026/10/26/rollout-2026-10-26T03-37-29-01a17648-ddc4-7152-b8fc-d5fbf9b76072.jsonl`

The original implementing thread is `01a17448-f63f-7ef0-ae87-d75ec3e637d0`;
its actual model and original rollout are derived in the canonical receipt.
Rollouts were not copied from another worker or synthesized. Native review
streams, findings, contexts, regression logs, and the private wrapper-failure
artifact remain with this worker's evidence. This slice does not implement B/C,
resolve the original same-tree ok/warn discrepancy, or perform host operations.

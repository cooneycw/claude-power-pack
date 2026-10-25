# Transport-specific handoff walkthrough (#1560)

This corrects instructions, not mailbox/registry code or native runtime behavior.
A shell watcher, an available native tool and an intended worker reading an
assignment are different observations. There is no new automated acknowledgement
validator. The comparisons below are manual; the negative inputs are retained so
a reviewer can distinguish confirmation from plausible but insufficient evidence.

## Pins and reproduction

Old source: CPP dd988219e056ddf23fb7ef5ba55e93979c07b61a. Read that commit's
`.claude/commands/flow/register.md` step 4 and `flow/wave.md` setup/hazards with
`git show <commit>:<path>`. The old instructions turn missing Claude watcher
ancestry into nobody being able to wake a worker, and require another watcher.
Feed the native-confirmation input below to that reading: it still prescribes a
Claude watcher even though the intended native worker replied. The failure is
this instruction mismatch, not an executed timeout or a failing runtime test.

Fixed source identities (SHA-256, refreshed after accepted review fixes):

- `.claude/commands/flow/register.md`: `d0ebac609f043643060e410175899d9f004efd042978a579b66f38be747e9db6`
- `.claude/commands/flow/wave.md`: `36dd335de3fbc73e2c7914d5b409fa66882fc61eb3e39302acc669b325b3981d`

Read the fixed "Select the delivery transport first" procedure and wave setup,
assignment and hazard branches against every input below. A fixed pin for the
skillc coordination fixture is supplied in the delivery handoff after review;
these content digests identify the prose without a self-referential commit hash.
The historical evidence report is not a new bundled command dependency.

## Available native surface and measured limits

On 2026-10-25 the compatibility session exposed
`mcp__codex_tui__send_message_to_thread` (existing threadId and prompt, at most
1,000 UTF-8 bytes), `read_thread` (target/cursor/turn limit), and `wait_threads`
(target status wait). A send returns acceptance; it does not report that the
receiver read the assignment. Waiting for thread completion/input is not a
native inbox wake guarantee. The local executable reported codex-cli 0.164.0;
the native MCP/app-server version was not exposed and remains unmeasured.
These claims expire on a changed tool/schema/harness or failed handoff.

**Measured:** a native worker hello reached the orchestrator, which observed the
actual source and verified the registered address. The worker received the
orchestrator's preparation notice, read the matching durable revision and
explicitly acknowledged it. Raw native/message/mailbox records and the private
neutral-identity mapping are retained outside the repository. No machine name,
private path or actual thread address is needed in this public scenario.

**Bounded probe:** a separate durable input and one native notification to the
orchestrator were sent with a declared 60-second budget and exact assignment id.
Its matching-response observation is recorded in the delivery evidence below.
No new thread, live study, host installation or shell watcher was created.

## Concrete neutral inputs and manual dispositions

Use this assignment for every variation, comparing actual transport source as
well as reply contents. Identifiers below are synthetic, not real host addresses.

```text
assignment: wave=example-wave role=worker-A thread=thread-A box=outbox-worker-A rev=7 id=task-7
budget: one notification attempt; 60 seconds; then escalate without retry
```

| Input | Manual disposition under the fixed guidance |
| --- | --- |
| native tool present; accepted send; reply within 60 seconds; source=thread-A reply="wave=example-wave role=worker-A box=outbox-worker-A rev=7 id=task-7 read" | Synthetic positive: matching on-time exchange for this assignment, if its durable record was read; not general wake reliability. |
| native tool present; accepted send; no worker reply by budget | Pending/unconfirmed; retain record and escalate. Acceptance is insufficient. |
| source=thread-B reply="wave=example-wave role=worker-A box=outbox-worker-A rev=7 id=task-7 read" | Wrong transport source; not confirmed even though the body names worker-A. |
| source=thread-A reply="wave=old-wave role=worker-A box=outbox-worker-A rev=7 id=task-7 read" | Wrong wave; not this assignment. |
| source=thread-A reply="wave=example-wave role=worker-A box=outbox-worker-A rev=6 id=task-7 read" | Stale revision; not this assignment. |
| source=thread-A reply="wave=example-wave role=worker-A box=outbox-worker-A rev=7 id=task-6 read" | Wrong assignment; not confirmed. |
| supervisor consumes revision 7; aggregate route=confirmed; no worker-A native reply | Supervisor/aggregate acknowledgement does not establish intended-worker receipt. |
| capabilities=[]; durable assignment retained; no native send tool | Unavailable; report it and request an explicit orchestrator/user session relay. Do not create a Claude watcher as a native repair. |
| shell watch=NO-WAKE; native reply matches the first row | Shell classification unchanged; native exchange is separately observed. |
| shell watch=armed; native tool present; no matching reply | Armed shell state does not complete this native assignment. |

These are committed manual counterexamples, not executions of a new classifier.
The empty capability input is deliberately simulated: this measured session did
have native tools. No wrong-worker message was sent to a real unrelated thread.
The positive row is synthetic, not a rendering of the measured late probe.
The measured exchange is recorded separately below; all table variations are
manual synthetic inputs. Existing shell controls distinguish qualifying
Claude ancestry from detached/orphan processes using explicitly injected lineage
where appropriate; no genuine Claude-session wake measurement was made here.

## Applying the scenario

Store the exact assignment durably, record the returned revision, then notify the
registered intended thread through the tools actually available. The intended
worker reads that record and replies with its wave, role, revision and assignment
identity. Compare its actual source, then explicitly acknowledge only that
revision. Mailbox data share a user boundary and are not cryptographic identity
proof; the helper does not automatically enforce the semantic comparison.

At the declared limit, lack of a matching reply stays pending/unavailable. Report
the exact missing capability or confirmation and request an explicit relay.
Preserve Claude watcher/orphan guards and do not relabel watch=armed from native
evidence. This walkthrough establishes no timeout reduction, task-success uplift,
reliable idle wake, or permission to revive the retired native-wave engine.

## Original contribution evidence

The probe and two reviews below belong to AA's preserved original candidate
`fcff8bfc5a4172fc5ce392fb06bd3672fab2d7d1`. Fresh delivery reviews and checks
are recorded separately in that delivery's flow run and counter-model receipt.

Implementation/review/check results and the bounded probe disposition are appended
here after they are actually observed. The raw records remain private; a manual
comparison is not automated runtime enforcement.

The probe began at 2026-10-25T07:48:20.982422Z, with deadline
2026-10-25T07:49:20.982422Z. The one-attempt probe missed its 60-second budget. The matching reply
was recorded 74.414578 seconds after start (2026-10-25T07:49:35.397Z), with the
expected native source, wave, role, mailbox revision and assignment identity.
Its disposition is deadline missed/unconfirmed, followed by a separately observed
late matching acknowledgement; the later reply does not manufacture on-time
success. The raw event record is privately retained (SHA-256
`2624d475bac0b03573a3aac16af89a90ff76457611cdb7b0defcda89116c480c`).
This is one observed exchange, not a measured wake latency distribution or an
explanation of the delay. No retry or replacement watcher was started.

Two independent codex/gpt-6-astra review passes each found one MEDIUM
contradiction in active watcher instructions; both were accepted and corrected.
Their scope is unverified (the pre-run scope probe did not establish full reads),
network probe blocked, local repository credentials absent. No third model pass
was run. Ten proposed manual red-case entries across the reports receive zero
credit as already executed controls; the table is manual evidence. Root retains
independent inspection and exact-head merge judgment after the final fixes.

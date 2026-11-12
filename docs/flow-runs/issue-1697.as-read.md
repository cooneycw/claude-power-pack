<!-- flow-run n=1 id=22808977ef614e6fb293278fbb2a9382 -->
## Run 1 - issue #1697 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1697
- Read at:      2026-11-12T00:18:36Z
- updatedAt:    2026-11-12T00:18:35Z   (context only - moves on comments and labels)
- Body digest:  296d608a9fc1e684c3991f6d86e90c509b9604aa2e9e3f5fd1fd3cf1319f08de   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 10051 of 10051 (cap 16384)

### Body as read
Tier: 2

Source: owner-requested follow-up to the 2026-11-11 methodology review. Owner approved filing. The evidence is the Codex-authored report `kyle-quality-measures-2026-11-11.html` (built 2026-11-11T20:56Z from read-only GitHub queries on cooneycw/kyle; a purposive sample of 34 issues, not a prevalence estimate). Two of its claims were spot-checked against GitHub (kyle#2098 closed 2026-11-02 and reopened 2026-11-03; kyle#2309 open as described); the other 32 were not.

This issue carries two corrective processes from the same review. The owner asked on 2026-11-11 for them to be one issue; the second was first filed as #1698 and folded in here. They are separate deliverables with separate red cases and may land as separate PRs. The issue closes when both are delivered.

## Part 1 - Record which completion a defect broke, and why its test did not catch it

### Outcome
When something breaks, the record says which earlier completion delivered the behaviour that broke. Over time that gives the owner a list of completions that fell short of their test, which is the material needed to learn why.

Today that link is not recorded. The report could not compute a regression rate for this reason: "exact prior pass receipts and exposure denominators are missing". CPP's own 60-day scan (429 merged PRs, 244 titled fix) has the same hole: none of the 244 can be traced to the completion it repaired without reading each one.

Checked on main at 15521b1e: `.github/ISSUE_TEMPLATE/bug-report.yml` asks for component, specific item, description, steps to reproduce, error message, environment and additional context. It asks nothing about origin. cooneycw/kyle has no issue templates.

### Acceptance
- **Where defects are actually filed (amended 2026-11-11, see the note below).** The origin question is asked on the `gh` filing path: `/github:issue-create`'s bug path and the issue contract. Sessions file defects with `gh`, not through the web form, so this is the surface that records anything.
- **Bug template.** The bug-report template has an optional field: which issue or PR delivered the behaviour that broke, if known. "Unknown" and "never worked" are valid answers and are distinguishable from a blank.
- **Fix closing report.** The closing-report contract says that a report closing a defect states the origin in one line: the delivering issue or PR, "never worked", or "not traced" with what was tried. It also states in one line why the original completion's test did not catch it. Suggested answers, to be corrected at planning: lane not exercised (#1695), reader not tested against real output, fixture smaller than real use, test could not fail, behaviour changed later by another change, not a defect in earlier work (hardening).
- **Where the rule lives.** The wording goes in `docs/agents/issue-contract.md` or `docs/agents/closing-report-contract.md`. Command documents carry at most a pointer, with no word budget raised (#1669).
- **New projects (amended 2026-11-11).** `/project:init` gains a bug-form install: it copies a project-neutral bug form carrying the origin field into a new repository. This is a NEW capability - `/project:init` installed no issue templates before this issue.
- **Readable later without a new tool.** The origin and the why are written so that one `gh` search over closed issues returns them (a fixed phrase or label, chosen at planning). This issue adds no report generator.
- **Negative control** is needed only if a check is added. If the implementer adds one (for example a closing-report linter rule), it gets a committed case: a defect close with no origin line is flagged, and one that says "not traced" with a reason is not.

### Constraint
- Tracing is best-effort. A fix must not be held up because its origin cannot be found; "not traced" is an honest answer. What is not allowed is silence.
- One underlying defect is counted once. A duplicate observation points at the first record and does not get its own origin (the report's #2309 and #2310 case).
- A never-tested combination or newly required behaviour is not a regression and is recorded as "never worked", not attributed to an earlier completion.
- The closing-report contract is used by `flow` command documents, which #1673 freezes for new features. The template field and the contract wording do not touch `flow`. Any pointer added to a `flow` command waits on the owner's freeze ruling recorded on #1695.

### Assumption
That sessions will fill the line honestly when the answer reflects on earlier work, including their own. The counter-model review reading the fix is the independent check on that.

### Not checked
- Whether the 244 fix-titled PRs can be traced after the fact. That retrospective study is not part of this issue; this issue only makes future ones traceable.
- How Kyle adopts the template. The owner's 2026-09-20 hold on CPP-touching Kyle work stands, so Kyle's adoption needs its own go.

## Part 2 - Plans name what reads a changed output, and test the reader against the real output

### Outcome
When a change alters what one part of the system writes, the plan names what reads it, and a test feeds the reader the writer's real output.

The clear case in the report is kyle#2309. A server response gained a field (kyle PR #2255, merged 2026-11-10). The existing client accepts only the older shape, and the client's test stub still modelled that older shape. Both sides stayed green while the real pair was broken, and a real job hit it (kyle#2310). The report groups four issues in this family (kyle#1899, #2262, #2287, #2309) and recommends exercising real producer output against its consumer.

This is a different gap from lanes (#1695). A lane miss is a route nobody tested. Here every route was tested, each against a hand-written copy of the other side.

Checked on main at 15521b1e: neither `docs/agents/issue-contract.md` nor `.claude/commands/flow/eli5.md` mentions readers of changed output.

Examples of a writer and its readers in CPP itself: a script's status line or exit code read by a gate or a command document; a receipt or record file read by a later step; a helper's JSON read by another helper; a generated file read by an installer.

### Acceptance
- **Plan question.** For work that changes an output another part reads (a response shape, a file format, a status line, an exit code, a record's fields), the plan presented for approval names each known reader and says, per reader: tested against the real output (naming the test), reader unchanged and why that is safe, or not covered (a stated gap). Work that changes no such output says so in one line.
- **How readers are found.** The plan states how it looked for readers (the search it ran), so "no readers" is a result and not an assumption. A search that can find nothing is not evidence: the plan shows the search finding a known reader of some existing output first, or says it did not check that.
- **Issue contract.** `docs/agents/issue-contract.md` states the rule: a hand-written copy of the other side's output is not evidence that the pair works. Where a stub is unavoidable, the plan says what keeps the stub in step with the real output.
- **Independent read.** The counter-model review asks whether the diff changes an output with readers the plan did not name, and whether each "tested against the real output" claim is backed by a test that actually uses real output.
- **Closing report.** The same reader rows appear with results, and a difference from the approved plan is explained.
- **Negative control** (ADR 0008: the review question's verdict is read by an approval that does not re-derive it): a committed example in which a writer gains a field and the reader's test uses a stale hand-written stub gets the other verdict from the review question. The same example with the reader fed the writer's real output does not.

### Constraint
- No new gate script, for the same reasons as #1695. The checks are the owner at approval and the counter-model review.
- The rule lives in the issue contract. Command documents carry at most a pointer, with no word budget raised (#1669): `flow/eli5.md` is at its cap and `flow/auto.md` has 8 words of room.
- Share the plan and closing table with #1695 where both apply, so a plan gains one block, not two.
- The plan-step and closing-report pointers edit `flow` command documents, which #1673 freezes for new features. Those parts wait on the owner's freeze ruling recorded on #1695. The issue-contract rule and the review question do not.
- Applies to Tier 2 and Tier 3 work that changes behaviour.

### Assumption
That a text search finds most readers. It will not find a reader in another repository (Kyle reads CPP output, for example `core/cpp_adapt_pin.json` describes CPP behaviour). Cross-repository readers are named from knowledge, and a plan that changes an output Kyle is known to read says so.

### Not checked
Whether CPP's own fix history contains this family in the proportion the kyle sample shows.

## Amendment, 2026-11-11 (planning run, approved by the wave orchestrator)

Two premises in the original text did not match the tree. Both were found at the plan step of the `/flow:auto` run for this issue and are corrected in Part 1's acceptance above.

1. The original said `/project:init` "installs the bug template". It installed no issue templates at all: `templates/project-init` held only language scaffolds. The acceptance now says plainly that this is a new capability.
2. The original treated the web bug form as the place a defect's origin is recorded. Sessions file defects with `gh`, through `/github:issue-create` or directly, so a field on the form alone would record almost nothing. The acceptance now names the `gh` filing path as the primary surface and keeps the form as the lesser one.

Delivery: two PRs, Part 1 then Part 2. Kyle's adoption of the form and the rule is not in scope and needs the owner's own go.

Related: #1695 (lanes exercised; Part 2 shares its plan and closing table), #1696 (lane commands).



<!-- end of body -->

<!-- flow-run n=2 id=827a3f784963499198a57af44e7561b4 -->
## Run 2 - issue #1697 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1697
- Read at:      2026-11-12T02:43:01Z
- updatedAt:    2026-11-12T01:09:47Z   (context only - moves on comments and labels)
- Body digest:  296d608a9fc1e684c3991f6d86e90c509b9604aa2e9e3f5fd1fd3cf1319f08de   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 10051 of 10051 (cap 16384)

### Body as read
Tier: 2

Source: owner-requested follow-up to the 2026-11-11 methodology review. Owner approved filing. The evidence is the Codex-authored report `kyle-quality-measures-2026-11-11.html` (built 2026-11-11T20:56Z from read-only GitHub queries on cooneycw/kyle; a purposive sample of 34 issues, not a prevalence estimate). Two of its claims were spot-checked against GitHub (kyle#2098 closed 2026-11-02 and reopened 2026-11-03; kyle#2309 open as described); the other 32 were not.

This issue carries two corrective processes from the same review. The owner asked on 2026-11-11 for them to be one issue; the second was first filed as #1698 and folded in here. They are separate deliverables with separate red cases and may land as separate PRs. The issue closes when both are delivered.

## Part 1 - Record which completion a defect broke, and why its test did not catch it

### Outcome
When something breaks, the record says which earlier completion delivered the behaviour that broke. Over time that gives the owner a list of completions that fell short of their test, which is the material needed to learn why.

Today that link is not recorded. The report could not compute a regression rate for this reason: "exact prior pass receipts and exposure denominators are missing". CPP's own 60-day scan (429 merged PRs, 244 titled fix) has the same hole: none of the 244 can be traced to the completion it repaired without reading each one.

Checked on main at 15521b1e: `.github/ISSUE_TEMPLATE/bug-report.yml` asks for component, specific item, description, steps to reproduce, error message, environment and additional context. It asks nothing about origin. cooneycw/kyle has no issue templates.

### Acceptance
- **Where defects are actually filed (amended 2026-11-11, see the note below).** The origin question is asked on the `gh` filing path: `/github:issue-create`'s bug path and the issue contract. Sessions file defects with `gh`, not through the web form, so this is the surface that records anything.
- **Bug template.** The bug-report template has an optional field: which issue or PR delivered the behaviour that broke, if known. "Unknown" and "never worked" are valid answers and are distinguishable from a blank.
- **Fix closing report.** The closing-report contract says that a report closing a defect states the origin in one line: the delivering issue or PR, "never worked", or "not traced" with what was tried. It also states in one line why the original completion's test did not catch it. Suggested answers, to be corrected at planning: lane not exercised (#1695), reader not tested against real output, fixture smaller than real use, test could not fail, behaviour changed later by another change, not a defect in earlier work (hardening).
- **Where the rule lives.** The wording goes in `docs/agents/issue-contract.md` or `docs/agents/closing-report-contract.md`. Command documents carry at most a pointer, with no word budget raised (#1669).
- **New projects (amended 2026-11-11).** `/project:init` gains a bug-form install: it copies a project-neutral bug form carrying the origin field into a new repository. This is a NEW capability - `/project:init` installed no issue templates before this issue.
- **Readable later without a new tool.** The origin and the why are written so that one `gh` search over closed issues returns them (a fixed phrase or label, chosen at planning). This issue adds no report generator.
- **Negative control** is needed only if a check is added. If the implementer adds one (for example a closing-report linter rule), it gets a committed case: a defect close with no origin line is flagged, and one that says "not traced" with a reason is not.

### Constraint
- Tracing is best-effort. A fix must not be held up because its origin cannot be found; "not traced" is an honest answer. What is not allowed is silence.
- One underlying defect is counted once. A duplicate observation points at the first record and does not get its own origin (the report's #2309 and #2310 case).
- A never-tested combination or newly required behaviour is not a regression and is recorded as "never worked", not attributed to an earlier completion.
- The closing-report contract is used by `flow` command documents, which #1673 freezes for new features. The template field and the contract wording do not touch `flow`. Any pointer added to a `flow` command waits on the owner's freeze ruling recorded on #1695.

### Assumption
That sessions will fill the line honestly when the answer reflects on earlier work, including their own. The counter-model review reading the fix is the independent check on that.

### Not checked
- Whether the 244 fix-titled PRs can be traced after the fact. That retrospective study is not part of this issue; this issue only makes future ones traceable.
- How Kyle adopts the template. The owner's 2026-09-20 hold on CPP-touching Kyle work stands, so Kyle's adoption needs its own go.

## Part 2 - Plans name what reads a changed output, and test the reader against the real output

### Outcome
When a change alters what one part of the system writes, the plan names what reads it, and a test feeds the reader the writer's real output.

The clear case in the report is kyle#2309. A server response gained a field (kyle PR #2255, merged 2026-11-10). The existing client accepts only the older shape, and the client's test stub still modelled that older shape. Both sides stayed green while the real pair was broken, and a real job hit it (kyle#2310). The report groups four issues in this family (kyle#1899, #2262, #2287, #2309) and recommends exercising real producer output against its consumer.

This is a different gap from lanes (#1695). A lane miss is a route nobody tested. Here every route was tested, each against a hand-written copy of the other side.

Checked on main at 15521b1e: neither `docs/agents/issue-contract.md` nor `.claude/commands/flow/eli5.md` mentions readers of changed output.

Examples of a writer and its readers in CPP itself: a script's status line or exit code read by a gate or a command document; a receipt or record file read by a later step; a helper's JSON read by another helper; a generated file read by an installer.

### Acceptance
- **Plan question.** For work that changes an output another part reads (a response shape, a file format, a status line, an exit code, a record's fields), the plan presented for approval names each known reader and says, per reader: tested against the real output (naming the test), reader unchanged and why that is safe, or not covered (a stated gap). Work that changes no such output says so in one line.
- **How readers are found.** The plan states how it looked for readers (the search it ran), so "no readers" is a result and not an assumption. A search that can find nothing is not evidence: the plan shows the search finding a known reader of some existing output first, or says it did not check that.
- **Issue contract.** `docs/agents/issue-contract.md` states the rule: a hand-written copy of the other side's output is not evidence that the pair works. Where a stub is unavoidable, the plan says what keeps the stub in step with the real output.
- **Independent read.** The counter-model review asks whether the diff changes an output with readers the plan did not name, and whether each "tested against the real output" claim is backed by a test that actually uses real output.
- **Closing report.** The same reader rows appear with results, and a difference from the approved plan is explained.
- **Negative control** (ADR 0008: the review question's verdict is read by an approval that does not re-derive it): a committed example in which a writer gains a field and the reader's test uses a stale hand-written stub gets the other verdict from the review question. The same example with the reader fed the writer's real output does not.

### Constraint
- No new gate script, for the same reasons as #1695. The checks are the owner at approval and the counter-model review.
- The rule lives in the issue contract. Command documents carry at most a pointer, with no word budget raised (#1669): `flow/eli5.md` is at its cap and `flow/auto.md` has 8 words of room.
- Share the plan and closing table with #1695 where both apply, so a plan gains one block, not two.
- The plan-step and closing-report pointers edit `flow` command documents, which #1673 freezes for new features. Those parts wait on the owner's freeze ruling recorded on #1695. The issue-contract rule and the review question do not.
- Applies to Tier 2 and Tier 3 work that changes behaviour.

### Assumption
That a text search finds most readers. It will not find a reader in another repository (Kyle reads CPP output, for example `core/cpp_adapt_pin.json` describes CPP behaviour). Cross-repository readers are named from knowledge, and a plan that changes an output Kyle is known to read says so.

### Not checked
Whether CPP's own fix history contains this family in the proportion the kyle sample shows.

## Amendment, 2026-11-11 (planning run, approved by the wave orchestrator)

Two premises in the original text did not match the tree. Both were found at the plan step of the `/flow:auto` run for this issue and are corrected in Part 1's acceptance above.

1. The original said `/project:init` "installs the bug template". It installed no issue templates at all: `templates/project-init` held only language scaffolds. The acceptance now says plainly that this is a new capability.
2. The original treated the web bug form as the place a defect's origin is recorded. Sessions file defects with `gh`, through `/github:issue-create` or directly, so a field on the form alone would record almost nothing. The acceptance now names the `gh` filing path as the primary surface and keeps the form as the lesser one.

Delivery: two PRs, Part 1 then Part 2. Kyle's adoption of the form and the rule is not in scope and needs the owner's own go.

Related: #1695 (lanes exercised; Part 2 shares its plan and closing table), #1696 (lane commands).



<!-- end of body -->

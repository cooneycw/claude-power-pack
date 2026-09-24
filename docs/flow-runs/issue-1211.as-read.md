# Issue #1211 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1211
- Read at:      2026-09-24T17:53:15Z
- updatedAt:    2026-09-23T12:07:40Z   (context only - moves on comments and labels)
- Body digest:  13fd247624cee32b0f3bd81f6ca4df5431d99f4e19f8aad6990e78cd80c375d3   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 13830 of 13830 (cap 16384)

## Body as read
## Outcome

Reduce the amount of procedure an agent must read and repeatedly execute to complete an ordinary CPP issue, while preserving the existing approval, correctness, security, recovery, and evidence contracts.

The first delivery should be a bounded simplification of `/flow:auto`, with a reproducible before/after measurement. The other opportunities below identify where to look next or which existing issue owns the work; they are not a request to rewrite every component in one PR.

Requested by the owner after the September 23 assessment: file a simplification issue with specific, analysis-backed opportunities. This issue authorizes no removal of safeguards, new global hooks, or paid evaluation runs by itself.

## Measured baseline

Compared the September 20 assessment pin `0e6c140bc5669264957aa449c1eb3d3f986c041c` with current main at filing, `7d36a8f96acd2d9695255b34e1c158928d2f47e2` (September 23). The latter includes #1199, #1200, #1201, #1205, #1208, #1209, and #1210. Counts below are from committed blobs, not a moving shared worktree.

| Surface | September 20 pin | September 23 pin | What this establishes |
| --- | ---: | ---: | --- |
| `CLAUDE.md` | 1,556 words | 1,561 words | Persistent CPP guidance is essentially stable; shrinking this is not the primary opportunity. |
| `AGENTS.md` | Absent | 308 words | The Codex-specific pointer is compact. |
| `.claude/commands/flow/auto.md` | 15,132 words / 1,845 lines | 19,978 words / 2,488 lines | Required full-workflow source grew 32% by whitespace-delimited words. |
| `.claude/commands/flow/wave.md` | 9,131 words | 9,131 words | A substantial existing coordination procedure, but no growth in this interval. |
| `.claude/commands/cpp/init.md` | 9,828 words | 12,320 words | Installation procedure grew 25%. |
| `.claude/commands/cpp/update.md` | 10,396 words | 12,212 words | Update procedure grew 17%. |
| `scripts/flow-finish-gate.sh` | 673 lines | 1,436 lines | Maintenance surface more than doubled. At the later pin, 754 lines begin with a comment marker after whitespace; this is not a claim that executable logic doubled. |
| `scripts/check-negative-controls.py` | 1,865 lines | 2,293 lines | The control harness itself is becoming a larger maintenance surface. |
| `docs/agents/detector-contracts.md` | 3,813 words | 5,612 words | Review guidance grew 47%; this is on-demand material, not universally loaded context. |
| Direct `verify:` prerequisites | 25 | 31 | More direct obligations in the aggregate, not a measurement of total invocations or runtime. |

**Measurement method:** `len(text.split())` for words, `len(text.splitlines())` for lines, where `text` is the decoded output of `git show <pin>:<path>`. Join the continued `verify:` declaration before counting its prerequisite tokens. These are not model-token counts, semantic-complexity measurements, or evidence of a runtime regression.

Reproduction, from a CPP checkout with both commits available:

```python
import subprocess

refs = [
    "0e6c140bc5669264957aa449c1eb3d3f986c041c",
    "7d36a8f96acd2d9695255b34e1c158928d2f47e2",
]
paths = [
    "CLAUDE.md", "AGENTS.md",
    ".claude/commands/flow/auto.md", ".claude/commands/flow/wave.md",
    ".claude/commands/cpp/init.md", ".claude/commands/cpp/update.md",
    "scripts/flow-finish-gate.sh", "scripts/check-negative-controls.py",
    "docs/agents/detector-contracts.md",
]
for ref in refs:
    print(ref)
    for path in paths:
        p = subprocess.run(["git", "show", f"{ref}:{path}"],
                           capture_output=True, text=True)
        if p.returncode:
            print(path, "unreadable or absent", p.stderr.strip())
            continue
        print(path, len(p.stdout.split()), "words",
              len(p.stdout.splitlines()), "lines")
    lines = subprocess.check_output(["git", "show", f"{ref}:Makefile"],
                                    text=True).splitlines()
    i = next(i for i, line in enumerate(lines) if line.startswith("verify:"))
    parts = []
    while True:
        line = lines[i]
        parts.extend(line.removeprefix("verify:").removesuffix("\\").split())
        if not line.endswith("\\"):
            break
        i += 1
    print("verify direct prerequisites:", len(parts))
```

## Specific opportunities

### 1. Make progressive disclosure work inside the selected workflow

The generated [flow-auto entry point](https://github.com/cooneycw/claude-power-pack/blob/7d36a8f96acd2d9695255b34e1c158928d2f47e2/codex/skills/flow-auto/SKILL.md#L20) requires reading the complete `reference.md` before acting. Its small entry file therefore does not bound the required reading after selection: the canonical procedure is 19,978 words before following additional references. This is a required-reading contract, not a measurement of what a particular model actually read.

**Proposed first slice:** keep the lifecycle, authority boundaries, stop conditions, and required decisions readily available; separate phase-specific execution details and historical explanations so they are loaded when needed. Update the actual loading instructions as well as file placement. A tiny index that still mandates reading every linked page has not reduced the burden.

Candidate blocks in [canonical `flow/auto.md`](https://github.com/cooneycw/claude-power-pack/blob/7d36a8f96acd2d9695255b34e1c158928d2f47e2/.claude/commands/flow/auto.md):

- Line 280: reconcile the prior plan record.
- Line 661: write the approved plan record.
- Line 742: write the as-read issue snapshot.
- Line 805: stamp the approval baseline.
- Line 1535: compare the diff with the approved plan, including an embedded shell/Python program.
- Line 1705: confirm the plan record exists at the PR head.

These are candidates for tested helper ownership and shorter call/interpretation instructions, not a direction to delete their behavior. `tests/test_flow_plan_compliance.py` already extracts and executes the documented block; preserve behavioral coverage if the implementation moves. Its multi-untracked-file defect is already recorded in [Nit Store comment 5775731658](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5775731658). Carry that known case into any replacement rather than perpetuating it or disguising UNKNOWN as agreement.

### 2. Separate operational instructions from accumulated incident history

`flow-finish-gate.sh` contains 754 comment-only lines out of 1,436. Many explain important failure modes, so line deletion is not itself an improvement. Retain nearby invariants and the reason a non-obvious guard exists; move longer incident narratives to the existing owned references and link them from the relevant symbol.

The same approach is worth evaluating for `cpp/init.md` and `cpp/update.md`, which now exceed 12,000 words each. #1199 correctly fixed host-write result handling at 20 call sites; preserve that behavior. Look for an existing shared helper that can own repeated deterministic decisions before adding another prose recipe or another abstraction. This is an opportunity to investigate, not a claim that every repeated call site can safely be merged.

### 3. Remove measured repeated work through the existing owner, #1192

#1192 records that Makefile dedup refuses the intended consumer's `-include` configuration. The issue reports approximately 10-12 minutes of repeated verification per issue in an affected Kyle workflow; Kyle subsequently adopted a delta-only workaround. This assessment did not rerun that timing, and it is not a current fleet-wide average.

**Keep #1192 as the implementation owner.** Expose the refusal at its point of consequence, measure the actual invocation graph, and demonstrate any safe reduction on both a supported consumer and a hostile/unsupported Makefile. Do not gain speed by blindly permitting includes or skipping required checks. This simplification issue should consume that evidence, not duplicate its fix.

### 4. Retire or narrow low-value machinery rather than automatically completing it

- **#1206:** the [owner's recorded decision](https://github.com/cooneycw/claude-power-pack/issues/1206#issuecomment-5793131191) is to withdraw the unsupported masking claim and remove dead installer wiring, not install a global output-rewriting hook. That issue owns the cleanup. Preserve this as a concrete simplification precedent.
- **#1083 / PR #1205:** [the guard's own source](https://github.com/cooneycw/claude-power-pack/blob/7d36a8f96acd2d9695255b34e1c158928d2f47e2/scripts/step3-record-guard.sh#L13) states that it enforces artifact presence, not approval occurrence, and describes coverage in the Bash-oriented fleet as near zero. This does not make it useless for consumers using the matched editing tools. Before expanding it, identify the actual supported execution path and demonstrate its effect there. Removing or changing the approval requirement is outside this issue.
- **#1085:** now delivered via #1210, it measures finding-to-issue movement with explicit attribution gaps. That is useful maintenance evidence, but it does not measure delivery cost, task correctness, or whether CPP pays for its overhead. Do not substitute that metric for those outcomes.

### 5. Use #1084 and skillc to establish whether complexity earns its cost

For the independent behavioral-evaluation work, include small tasks where scaffolding overhead may dominate. Report correctness, elapsed time, model usage/cost when available, repeated gate invocations, retries, and human interventions for matched conditions. Preserve failed and unavailable attempts in the accounting.

This belongs to existing CPP #1084 and the [skillc delivery roadmap](https://github.com/cooneycw/skillc/issues/1); do not build a second evaluation facility in CPP. This issue can establish static and deterministic before/after evidence without waiting for paid trials. Any productivity or cost claim beyond those measurements remains explicitly unproven until that evaluation exists.

## Bounded first delivery and acceptance

- [ ] Choose a concrete common `/flow:auto` path and one failure/recovery path before editing. Record which instructions each path must read, including mandatory transitive references; distinguish this calculated reading requirement from observed model reads or billed tokens.
- [ ] Deliver a smaller mandatory reading set for the common path through phase-specific disclosure, extraction of deterministic recipes, or another justified approach. Report before/after paths and counts using the same measurement method. Moving the same full text behind a mandatory link is not acceptance.
- [ ] Keep approval and stop conditions available before consequential actions, and recovery instructions reachable at the step that needs them. Demonstrate this for the chosen normal and failure paths; a smaller word count alone does not establish usability.
- [ ] For every moved executable block, preserve a known-good and a relevant known-bad or unknowable case. Exercise the actual production entry point, not a copied implementation. Carry forward the known multi-file comparison case if that block is selected.
- [ ] Measure relevant gate invocations and elapsed time on a pinned deterministic fixture before and after. Report retained duplication and why it remains. Do not call ordinary host-load variation a speedup, or claim fewer checks ran when only the output was shortened.
- [ ] Regenerate and verify Codex mirrors from canonical sources, check installed/bundled reference reachability for the changed workflow, and run appropriate `make` checks plus `make verify`. Passing source parity alone does not prove bundled helper resolution.
- [ ] Provide a concise completion note stating what became simpler, which safeguards remained, and what was not measured. Keep the broader opportunities linked to their existing owners. A document-only inventory is not delivery of the first simplification.

## Constraints and non-goals

- Preserve the distinct success, failure, absent, skipped, and unknown meanings; never recover a shorter or faster workflow by making an unexamined state look clean.
- Preserve required approval, secret handling, worktree ownership, host-write refusal, rollback/recovery, and evidence provenance contracts. Do not weaken known-bad controls to make a refactor pass.
- No new framework, mandatory reporting layer, global hook, arbitrary repository-wide size cap, or parallel evaluation platform is required. Use existing helpers, references, and review records where they suffice.
- Generated mirrors and fixtures are distribution/verification artifacts, not independent runtime overhead. Do not justify deleting them from raw repository size.
- Do not implement all five opportunity areas under this one change. A larger architecture or authority change needs its own explicit scope; this issue's deliverable is the bounded workflow simplification above.

## Codex-consolidation implications

**Disposition: changed.** The affected command source now serves both Claude and generated Codex skills. Outward: this issue depends on that source ownership, not on retired CxPP native skills. Inward: the consolidation ledger's Q6 selects `.claude/commands/**` plus `scripts/codex-skill-sync.py`; it cannot name this not-yet-filed issue, but it explicitly owns these surfaces. Subject overlap: spec boundaries **B3** (integrity/invocation), **B4** (public behavior and installed compatibility), and **B7** (evidence), plus ledger Q6, apply directly.

Simplify the canonical source, regenerate mirrors, and preserve bundled reference/helper resolution. Do not independently edit `codex/skills/`, revive the retired skill system, or introduce hooks into the Codex namespace. #1151 remains the owner of mirror enumeration. No new blocker on #1075/#1076 is asserted by this issue.


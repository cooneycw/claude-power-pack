<!-- flow-run n=1 id=8446aad069b947329dec18ac238defd3 -->
## Run 1 - issue #1547 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1547
- Read at:      2026-10-23T13:19:42Z
- updatedAt:    2026-10-23T13:18:39Z   (context only - moves on comments and labels)
- Body digest:  9f5b4dca93c8df691573a017229953f55f03e256cc5568ab895ec4dadd51694a   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3072 of 3072 (cap 16384)

### Body as read
## Problem

After #1542 (PR #1546, merge `f857754d`), generated Codex skills call their bundled helpers as `"${CPP_SKILL_DIR:-/dev/null}"/scripts/<name>`. Nothing in the Codex runtime sets `CPP_SKILL_DIR`; the agent has to set it from the SKILL.md location. #1542's gate measured this on a live `codex exec`: no skill-dir variable is exported, and `CODEX_HOME` is not exported either. When the agent does not set it, the call exits **126 with no output marker** ("/dev/null/scripts/flow-finish-gate.sh: Not a directory").

The Step-6 gate text in `codex/skills/flow-auto/reference.md` (around line 1305 at `f857754d`) does not cover that case:
- The only failure-to-launch rule is "**Exit 127** - helper not installed: fall back to `${CLAUDE_PLUGIN_ROOT}/...`, else the CPP-checkout copy". It does not fire on 126.
- The verdict list handles `ok` / `warn` / `fail` / `skipped`. A run with **no `FLOW_FINISH_GATE:` marker at all** has no rule. The nearest rule an agent may pattern-match, `skipped` (exit 4), says "warn the user, then **proceed**".
- The SKILL.md bullet says to set the variable and re-run, and never to run the target project's own copy. It does not say STOP if no copy can be run.

So the fail-closed property #1542 built holds at the shell: no decoy ever runs. It does not hold at the instruction level: an agent can read "the gate did not launch" as "the gate was skipped" and commit. The same gap applies to every other bundled-helper call that has a 127-only fallback sentence. The merge block is not affected, because it ends in MERGE_RC 12.

## Evidence

- At `f857754d`, mirror text: `codex/skills/flow-auto/reference.md` Step 6, the "(Exit 127 - helper not installed ..." paragraph and the verdict list beneath it.
- `bash -c '/dev/null/scripts/x'` gives `Not a directory`, rc 126 (checked on kyle19, 2026-10-23).
- skillc-orch asked exactly this question on 2026-10-23 while designing the skillc#529 bundled-gate witness. skillc#279's campaign on `ca3030d` saw all 7 live flow:auto attempts run the gate through the installed `~/.claude/scripts` path. The mirrors at or after `f857754d` no longer name that path, so the variable is now the main route.

## Acceptance

- [ ] Step 6's gate block in the generated flow-auto skill, and the Claude source text it is generated from, cover a launch failure: exit 126 or 127 with no `FLOW_FINISH_GATE:` marker. The rule is: set `CPP_SKILL_DIR` and re-run; else the plugin copy; else the CPP checkout; **if no copy produces a marker, STOP: the gate did not run**. It is never treated as `skipped`, and the flow never proceeds to commit.
- [ ] The SKILL.md bundled-helpers bullet states the same STOP for any helper whose result gates a step.
- [ ] Every other generated 127-only fallback sentence for a bundled helper also covers 126, or states why it cannot block.
- [ ] A test fails on today's mirror (no 126 / no-marker STOP rule in Step 6) and passes once the rule is in place.

Found while coordinating with skillc-orch (wave skillc-finish) after #1542. Related: #1542, #1543, cooneycw/skillc#529.


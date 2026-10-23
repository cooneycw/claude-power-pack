<!-- flow-run n=1 id=97a9324581764707a5404eb2570784c6 -->
## Run 1 - issue #1542 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1542
- Read at:      2026-10-23T12:27:18Z
- updatedAt:    2026-10-23T11:20:06Z   (context only - moves on comments and labels)
- Body digest:  30d48ad592d213834bb031af09deb23831d0a2ed1c1eea72df1bf181180fa96b   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3893 of 3893 (cap 16384)

### Body as read
## Problem

The generated Codex `flow-auto` skill tells the agent to run the finish gate as a
bare, relative command:

```bash
scripts/flow-finish-gate.sh
```

(`codex/skills/flow-auto/reference.md`, Step 6, "Invoke it BARE (#581 discipline)",
unchanged from ca3030d to main `b318a14b`.)

The Claude source (`.claude/commands/flow/auto.md`) says `~/.claude/scripts/flow-finish-gate.sh`.
`codex-skill-sync.py` rewrites that to `scripts/<name>` (#1408, commit `50261ddd`,
`rewrite_absolute_script_refs`). The comment above that rewrite gives the reasoning:
in a generated skill, `scripts/<name>` is "skill-dir-relative, since the helper is
bundled at that same relative path".

The assumption does not hold. A shell command resolves relative paths against the
agent's **working directory**, which is the target worktree, not the skill directory.
In a target project, `scripts/flow-finish-gate.sh` is either:
- missing, so you get exit 127; or
- the **target project's own** file of that name (CPP itself, or any repo that vendors the gate).

The documented exit-127 fallback chain doesn't name the bundled copy either:
- `${CLAUDE_PLUGIN_ROOT}/...` is unset in a Codex session;
- "the CPP-checkout copy" may not exist on the host;
- the copy that does exist, `~/.codex/skills/flow-auto/scripts/flow-finish-gate.sh`, is never mentioned.

Step 1's speckit section adds "Running inside a generated Codex skill, use the copy
bundled in that skill's own `scripts/` directory", but that sentence is absent from
the Step 6 gate section, and it still gives no path to type.

## Evidence (observed, not inferred)

skillc measures CPP's flow:auto in containers (cooneycw/skillc#279). Two live
codex-cli 0.157.1 attempts (gpt-6-astra, high effort) of flow:auto ran through Step 6
on CPP `ca3030d` (sizing run 4, skillc#279 issuecomment-6359844357). In **both**, the
agent did not run the relative `scripts/flow-finish-gate.sh`. It ran the gate by the
absolute path of the Claude convenience install, `~/.claude/scripts/flow-finish-gate.sh`.
That path existed only because the test container also installs the Claude-side helpers.
skillc#525 records the reference.md counts at the two revisions: 36 → 3
`~/.claude/scripts/` references and 19 → 51 bare `scripts/` references.

## Why it matters

On a Codex host **without** the `~/.claude/scripts` install, Step 6's gate is either
not found or not the gate:
- the bare call fails with 127;
- `CLAUDE_PLUGIN_ROOT` is unset;
- the agent is left to guess, or to skip the gate;
- in a repo with its own `scripts/flow-finish-gate.sh`, the bare call runs **that
  repo's** script as the quality gate.

This is the instrument every other Step-6 verdict rests on. The same rewrite applies to
the other remapped helpers (e.g. `scripts/counter-model-receipt.py` in Step 6's 1a block),
so this likely affects every `scripts/<name>` call in the generated Codex skills.

## Acceptance

- [ ] In generated Codex skills, helper invocations resolve to the skill's bundled copy
  regardless of the working directory. For example, an absolute path derived from the
  skill location (`$CODEX_HOME`/`~/.codex/skills/<skill>/scripts/<name>`), or a
  documented variable the skill sets. The fallback chain names that copy explicitly.
- [ ] A target worktree's own `scripts/<name>` is never picked up in a generated skill,
  unless the target IS the CPP checkout and that is stated.
- [ ] A red: a generated skill's gate call run from a scratch target worktree (no
  `scripts/`) on a host with no `~/.claude/scripts` install reaches the bundled gate.
  On today's main it fails with 127.
- [ ] Revisit `rewrite_absolute_script_refs`'s "skill-dir-relative" comment and its
  negative control (`controls/codex-skill-sync-remap`) so the control tests resolution
  from a non-skill working directory.

Found while orchestrating skillc wave skillc-finish (#279 sizing-4 and #525).


<!-- flow-run n=1 id=8090ef6e5a5049b0a8f762c08afcec3a -->
## Run 1 - issue #1835 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1835
- Read at:      2026-11-15T10:57:09Z
- updatedAt:    2026-11-14T20:59:54Z   (context only - moves on comments and labels)
- Body digest:  87bcabe269a2a8ac513eea26684153264784ec97d203a8d3c681d21a49b474fa   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1700 of 1700 (cap 16384)

### Body as read
## What is wrong

Three delegated-driver docs tell a waiting worker to escalate with:

```
~/.claude/scripts/flow-wave-mailbox.sh send --to orchestrator --from <your-role> --wave <wave> --kind message --body "Still waiting on Step 3 approval for <issue/role>, sent at <time>."
```

- `.claude/commands/codex/auto.md:346`
- `.claude/commands/gemma/auto.md:384`
- `.claude/commands/qwen/auto.md:364`

(line numbers at main `93ae8540`; the same lines are at `d5ef0a66`)

`scripts/flow-wave-mailbox.sh` has no `--kind` option anywhere. Its option parser ends with `--*) usage_fail "unknown option: $1"` (around line 2189). So the command fails, and the "still waiting on Step 3 approval" escalation every delegated driver prescribes never sends.

## Why it matters

This is the escalation path a worker uses when its plan approval is stuck. A worker following the doc gets a usage error instead of reaching the orchestrator, and the wait it was trying to break continues. The three driver docs are vendored identically (`controls/delegated-core-vendor`), so one fix in the shared core fixes all three.

## Fix

Drop `--kind message` from the prescribed command, or add `--kind` to the helper if a message kind is intended. Add a check that compares every flag a command doc passes to a helper against the flags that helper's parser accepts. That's the class of check that would have caught this.

## How it was found

Found by skillc's new `dangling-reference` decay rule (`skillc inspect`, cooneycw/skillc#725). It checks each flag written after a resolved helper path against the helper's source. I confirmed it by reading the parser.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- end of body -->

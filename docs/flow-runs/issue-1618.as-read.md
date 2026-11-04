<!-- flow-run n=1 id=8d339735690b44f7bc53e3a8b12bcf7b -->
## Run 1 - issue #1618 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1618
- Read at:      2026-11-04T16:11:32Z
- updatedAt:    2026-11-04T15:19:43Z   (context only - moves on comments and labels)
- Body digest:  c4288d579d5b3be77da64501434883354c64d28b690e84cf8afa228ca04f6f93   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2164 of 2164 (cap 16384)

### Body as read
## Problem

`/project:init` and `/spec:adopt` both tell the user to sync plan tasks to GitHub issues with `./scripts/speckit-tasks-to-issues.sh`. That relative path resolves only inside the CPP checkout. In any other project the script does not exist there, so the documented step fails with "No such file or directory".

`/project:init` copies `.specify/templates/` into the new project but no scripts (`.claude/commands/project/init.md` Steps 4b/4d). Step 5 then offers "Sync tasks to GitHub issues now?" and runs the relative path. `/spec:adopt` Step 4 prints the same path.

The script is also not one of the 31 helpers from `scripts/flow-helpers-install.sh`, so hosts installed by that helper alone do not have it at `~/.claude/scripts/` either. `/cpp:init` Tier 2 links all scripts, so it is present at the stable path there, but the docs still name the relative path.

This step was the replacement for `/spec:sync` (retired in #420), so it is the only supported route from a plan to issues.

## Evidence

Tested at `cac8eba2` (v10.1.0) on an `ubuntu:22.04` container with a `--depth 1` clone, `cpp-commands-link.sh` and `flow-helpers-install.sh`, from a separate project directory:

```
ls ./scripts/speckit-tasks-to-issues.sh            -> No such file or directory
ls ~/.claude/scripts/speckit-tasks-to-issues.sh    -> No such file or directory
```

The commands were read, not run inside Claude Code.

## Acceptance

- Following `/project:init` or `/spec:adopt` from a non-CPP project reaches the converter on every supported install path.
- `scripts/speckit-context.py` resolves alongside it (the #858 dependency).
- The stated command is one the user can run as printed, including `--dry-run`.
- A test covers invocation from outside the CPP checkout.

## Proposed approach (revisable)

Add `speckit-tasks-to-issues.sh` to the helper family and change both commands to call `~/.claude/scripts/speckit-tasks-to-issues.sh`. Copying the scripts into each project would also work, but those copies would drift.

Found by the aws-learn Start Here audit. aws-learn provisions with `flow-helpers-install.sh` and cannot complete this step until it is fixed.


<!-- end of body -->

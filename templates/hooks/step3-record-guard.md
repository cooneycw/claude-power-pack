# `step3-record-guard` — an opt-in floor under the Step 3 approval gate

## What it does

In a flow worktree — a checkout whose branch is `issue-<N>-<slug>` — this
PreToolUse hook **refuses an edit** unless `docs/flow-runs/issue-<N>.md` exists
and records `Approval: granted`. The refusal names what is missing and how to
obtain it.

`/flow:auto` Step 3 is a plan-approval gate with no bypass: no flag, no trailer,
no environment variable, no governance tier (issue #775). Until this hook, that
rule was **asserted and not enforced** — nothing checked it. This is the
deterministic layer beneath the advisory one. The advisory layer is unchanged.

## What it does NOT do, and please read this before relying on it

**It enforces the presence of an ARTIFACT, not the occurrence of an APPROVAL,
and only on the tool paths you match it against.** It sees a tool call; "was the
plan approved" is a fact about a run. Anything able to write the record can write
itself an approval line.

**It does not enforce #775.** Do not describe it that way.

### How much it actually covers depends on how your agents edit

This matters more than anything else on this page, and the honest answer has two
halves:

- **If your agents use `Write`/`Edit`, coverage is real.** That is the ordinary
  case and the hook is worth installing.
- **If your agents are steered to edit through the shell** — `sed`, heredocs,
  `cat > file` — **the hook does not see those edits at all.** It is matched on
  tool names, and a shell redirection is a `Bash` call. In the fleet where this
  was written that steering is the instructed default, so coverage there is near
  zero. Measured: three plan records across three runs of one session, every one
  written with `cat > … <<EOF`, none via `Write`.

**So the hook's silence is not evidence that no edit happened.** If your setup
resembles the second case, install it knowing that, or do not install it.

`controls/step3-record-guard` commits that gap as a **case** rather than as a
sentence, so if the matcher grows or the steering changes, the case flips and
the change is the notification.

## Install (opt-in, on purpose)

CPP ships this template and installs nothing. A hook that blocks edits must not
arrive unannounced in someone else's repository.

1. Install the script where your hooks can reach it, e.g. `~/.claude/scripts/`.
2. Merge this block into your own `.claude/hooks.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": { "tool_name": "Write|Edit|NotebookEdit" },
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/scripts/step3-record-guard.sh",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

The block lives in this document rather than in a sibling `.json` for a reason
worth knowing if you are adding another template: `.gitignore` carries a blanket
`*.json`, and every template JSON in this repository survives only via an
individually-named `!` negation. A new one needs its own negation or `git add`
skips it silently — with no error, which is how a template ships as an empty
promise. One file also means the matcher and its documentation cannot drift
apart.

## Behaviour you should expect

| state | result |
|---|---|
| flow branch, no record | **refused**, exit 2, with a message naming the route |
| flow branch, record without an approval line | **refused** |
| flow branch, record recording `Approval: granted` | allowed |
| write to `docs/flow-runs/issue-<N>.md` or its `.as-read.md` | **always allowed** |
| branch is not `issue-<N>-…` | allowed — not this hook's subject |
| edit made through `Bash` | **not seen** — see above |

**The record's own path is the only exemption, and it has to be.** The record is
written *by* an edit, so a guard without that exemption blocks the write that
would unblock it and every run deadlocks on its first edit. It is also a hole:
anything that can write the record can write itself an approval. Given the shell
bound above, that hole is already subsumed by a wider one.

**Refusal is refusal, not a default.** A record that cannot be read is refused
and said so. There is no permissive fallback to keep runs moving — a hook that
fails open is worse than no hook, because the prose it replaces at least made no
claim to be deterministic.

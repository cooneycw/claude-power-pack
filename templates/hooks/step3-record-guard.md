# `step3-record-guard` - an opt-in floor under the Step 3 approval gate

## What it does

In a flow worktree - a checkout whose branch is `issue-<N>-<slug>` - this
PreToolUse hook **refuses an edit** unless `docs/flow-runs/issue-<N>.md` exists
and records `Approval: granted`. The refusal names what is missing and how to
obtain it.

`/flow:auto` Step 3 is a plan-approval gate with no bypass: no flag, no trailer,
no environment variable, no governance tier (issue #775). Until this hook, that
rule was **asserted and not enforced** - nothing checked it. This is the
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
- **If your agents are steered to edit through the shell** - `sed`, heredocs,
  `cat > file` - **the hook does not see those edits at all.** It is matched on
  tool names, and a shell redirection is a `Bash` call. In the fleet where this
  was written that steering is the instructed default, so coverage there is near
  zero. **Measured**, from a single session's own transcript across five
  delivered issues: **468 `Bash` tool calls against 0 `Write`, `Edit` or
  `NotebookEdit` calls** - so this hook would have fired zero times over every
  plan record and every source edit that session made. (An earlier count is
  recorded in the control's limits: three plan records across three runs, none
  via `Write`. Same direction; see the note on units below.)

  Stated plainly, because the parent issue promises *enforced rather than
  asserted*: **in the measured session** this hook was enforced for a tool path
  that session never used, and asserted for the one it used throughout. Whether
  that holds fleet-wide is an **inference, not a measurement** - it follows from
  the Bash-first steer being written into session instructions rather than
  chosen per run, and a second session independently reported the same steer in
  its own instructions. Two sessions on one host is corroboration; it is not a
  survey. Do not read the numbers above as a claim about every session or every
  host.

  The two measurements are kept with their **units distinct** and deliberately
  not combined into a ratio: three *plan-record writes* and 468 *Bash tool
  calls* count different things, and most Bash calls in a session are reads,
  searches and tests rather than edits. The zero supports "this hook would not
  have fired"; it does not support a hundredfold claim about comparable
  evidence, and counting write-like shell commands to manufacture one would be
  the path-set prediction this repository keeps declining.

  That is an argument about coverage, not about correctness - the hook does what
  it says on the paths it matches.

**So the hook's silence is not evidence that no edit happened.** If your setup
resembles the second case, install it knowing that, or do not install it.

`controls/step3-record-guard` commits that gap as a **case** rather than as a
sentence, so if the matcher grows or the steering changes, the case flips and
the change is the notification.

### Hook-delivery trust roots are unowned, and that is a STANDING CONDITION

Recorded here because it is a design consequence that gets discovered late, and
because **nothing is in flight that will change it**. Read the paragraphs below
as a description of how things now stand, not as a forward reference to work
coming.

CPP's hook delivery was going to be owned by a separate piece of work - issue
#1073, *"ship pinned Codex plugins from CPP with safe hook update and rollback"*.
That issue was closed **`NOT_PLANNED`**: cancelled, not delivered. The owner's
rulings removed its premise, so CPP ships no Codex plugins and installs no hooks
into `~/.codex/`.

**The dependency did not lapse; it inverted.** It existed so hook delivery would
not be built twice, with the second build forced to preserve the first one's
trust roots. There is no second builder - not "not yet", but *cancelled* - so
*this* hook is the sole hook-delivery surface in CPP, and **if** later Codex hook
work is ever undertaken it inherits **these** trust roots rather than the other
way round. No such work is planned or scheduled at the time of writing.

One boundary, checked: a `PreToolUse` entry in `.claude/hooks.json` is the
**Claude** namespace and does not reach `~/.codex/`, so the dormant
safe-hook-update capability stays dormant. If hook delivery here ever does reach
`~/.codex/`, that capability has to be **rebuilt rather than remembered** - the
script that once provided it was retired with CxPP.

### This page is the record

The parent issue asked for a deterministic layer so that #775 would be *enforced
rather than asserted*. A floor shipped, its coverage bound is the one described
above, and the owner has **decided to accept that bound** rather than pursue
fuller coverage - the reasoning being that the social mechanism has held in
practice and that PR review is a second layer already in place. That decision was
taken with the narrower, session-bounded claim in hand, not the fleet-wide one.

So no further enforcement is coming, and **this page and the control's `limits`
are the only durable record of what this hook does and does not cover.** Treat
them as the contract, not as a status report on work in progress.

## Install (opt-in, on purpose)

CPP ships this template and installs nothing. A hook that blocks edits must not
arrive unannounced in someone else's repository.

1. Install the script where your hooks can reach it, e.g. `~/.claude/scripts/`.
2. Merge this block into your own `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|NotebookEdit",
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
skips it silently - with no error, which is how a template ships as an empty
promise. One file also means the matcher and its documentation cannot drift
apart.

## Behaviour you should expect

| state | result |
|---|---|
| flow branch, no record | **refused**, exit 2, with a message naming the route |
| flow branch, record without an approval line | **refused** |
| flow branch, record recording `Approval: granted` | allowed |
| write to `docs/flow-runs/issue-<N>.md` or its `.as-read.md` | **always allowed** |
| branch is not `issue-<N>-…` | allowed - not this hook's subject |
| edit made through `Bash` | **not seen** - see above |

**The record's own path is the only exemption, and it has to be.** The record is
written *by* an edit, so a guard without that exemption blocks the write that
would unblock it and every run deadlocks on its first edit. It is also a hole:
anything that can write the record can write itself an approval. Given the shell
bound above, that hole is already subsumed by a wider one.

**Refusal is refusal, not a default.** A record that cannot be read is refused
and said so. There is no permissive fallback to keep runs moving - a hook that
fails open is worse than no hook, because the prose it replaces at least made no
claim to be deterministic.

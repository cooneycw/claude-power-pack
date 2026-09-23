# Issue #1182 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1182
- Read at:      2026-09-23T11:33:48Z
- updatedAt:    2026-09-21T17:51:10Z   (context only - moves on comments and labels)
- Body digest:  c576b452b67233ce58d10aab30c738ad90348b2c8e4175a5c0bdbcc70d11da39   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4708 of 4708 (cap 16384)

## Body as read
Split out of #1150 by the `claude-improvements` wave orchestrator, under a stopping rule that worker-A proposed **before** seeing the finding that triggered it. #1150 ships the instrument; this issue owns the boundary.

## The finding that triggered the split

Three counter-model passes over #1150 found **three HIGH-severity sandbox escapes, by three unrelated mechanisms**:

1. **A stdlib fallback.** `Path.home()` and `os.path.expanduser()` honour `$HOME` when set and fall back to `pwd.getpwuid(os.getuid())` when it is **absent** — so an unset `HOME` resolves to the real home. (`HOME=""` gives `/.claude`: broken, not an escape.)
2. **A helper's own destination override.** `cpp-commands-link.sh` reads `HOME_DIR="${CPP_COMMANDS_LINK_HOME:-$HOME}"`, so a caller with that variable set redirects the write target while every sandbox check passes. The override is documented in the helper's own `#: HOST-SURFACE:` note.
3. **The configuration of the checkout the gate runs in.** `core.fsmonitor` is a repository-configured command that git **executes**.

Measured for (3), in a scratch repo with `core.fsmonitor` set to `sh -c 'echo FSMONITOR-RAN >&2; exit 1'`:

```
git status                   FIRES
git diff                     FIRES
git ls-files --others        FIRES
git rev-parse (all forms)    does not fire
git branch --show-current    does not fire
git config --get             does not fire
git stash list               does not fire
```

`scripts/cpp-commands-link.sh` has executable `git diff` and `git ls-files`, so the route is live. **Note for whoever picks this up:** the original report cited `cpp-commands-link.sh:342` (`git rev-parse --is-inside-work-tree`), which is the one invocation in that file that does *not* fire. The conclusion was right, the cited line was not. An enumeration that reads comment prose gets the opposite error — `git status` appears in that file only at :92, inside a comment.

The anchor carries the same mechanism, since the battery executes it too.

## Why this is a design question and not a bug queue

worker-A's framing, which is the reason the split was invoked rather than a fourth patch applied:

> Three different routes to the same failure is the signal the rule was written for: the containment claim is bigger than what a snapshot-and-probe design can support, and each pass finds another route because there are **more routes**, not because the reviewer is thorough.

A snapshot-and-probe harness compares what appeared inside a sandboxed `$HOME` against what was declared. It cannot bound what a helper's **child processes** do, and each of the three routes reaches outside by a different door: the interpreter's own fallback, the helper's own configuration surface, and the environment the gate is invoked in. A route-specific guard closes one door and says nothing about the next.

## Scope

**This issue decides what containment `host-surface-observe` should promise, and how that promise is enforced.** It is not "fix fsmonitor", though that is its first acceptance item so it is not lost.

## What #1150 already closed, and what it did not

Closed, with committed cases: `HOME` is refused when unset **and** when empty (they fail differently — only one escapes); the child environment is a closed **allowlist** rather than a copy, so `CPP_COMMANDS_LINK_HOME` and `BASH_ENV` are stripped, with a positive control asserting `PATH` survives; and the check reads the **child's resolved home** rather than the harness's own export.

Not closed: acceptance item 5 of #1150 — *"The real `$HOME` is never a target"* — is **not met**, and #1150 ships saying so rather than implying otherwise. `certified=observed` there means "observed through the paths this sandbox can see", and that bound is stated where a reader meets the value.

## Acceptance

- [ ] The `core.fsmonitor` route is closed or refused, with a committed case.
- [ ] The containment promise is **stated as a bound** — what the harness can and cannot see — rather than as an unqualified claim, and the statement is enforced somewhere rather than only documented.
- [ ] A deliberate attempt to enumerate further routes, with the result recorded whether or not any are found. Three were found by three passes of a reviewer who was not looking for them specifically; an absence found by looking is worth more than an absence found by not looking, and needs its own positive control before it is believed.
- [ ] Whatever containment is decided, the `certified=observed` vocabulary in `scripts/host-surface-check.py` matches it. A certification that outlives its own containment claim is the defect this whole line of work exists to remove.

Refs #1150, #1139, ADR 0008.


# Issue #1220 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1220
- Read at:      2026-09-24T09:07:07Z
- updatedAt:    2026-09-23T16:34:45Z   (context only - moves on comments and labels)
- Body digest:  8b6c344972c67126ae09dfa51a0dffc65059f2af9b29d19d6acacfb0388e523e   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2575 of 2575 (cap 16384)

## Body as read
**Record issue.** Created so this work has a subject the verdict ledger can key on, per the owner's ruling of 2026-09-23: when the don't-file rule produces work with no ticket, open an issue expressly so the record stays intact. This is not new scope — the work is already assigned and in flight.

## The defect

`.claude/commands/flow/auto.md:1574` captures the untracked-file list through **command substitution**:

```
if ! UNTRACKED_RAW="$(git -C "$GIT_ROOT" ls-files --others --exclude-standard -z)"; then
```

Command substitution **strips NUL bytes** — bash says so: `warning: command substitution: ignored null byte in input`. So by the time `:1579`'s `mapfile -d ''` runs there is no separator left, and N untracked paths collapse into one glued pathspec.

Reproduced rather than read:

```
new-0.txt + new-1.txt  ->  1 path recovered: [new-0.txtnew-1.txt]
git add -N -- that     ->  fatal: pathspec did not match any files, exit 128
control, split correctly -> 2 paths, exit 0
```

## It fails safe, and that bounds the severity

The block reports `PLAN_COMPLIANCE: unknown`, never a false agreement. Its own comment already says *"this check would otherwise report agreement over an incomplete diff"* — the third state is present and catching this.

**The cost is that the plan comparison goes dark whenever a change touches more than one new file**, which is most real changes, including several this wave shipped.

## Why it survived

`tests/test_flow_plan_compliance.py` exercises the untracked case with **one** file. **At N=1 a separator bug, an iteration bug, and correct code are indistinguishable.**

General rule adopted from this: any case exercising a list must use at least two elements.

## Acceptance

1. The block no longer round-trips the NUL-delimited list through a variable.
2. A regression test with **two** untracked files: red on the current block (`unknown`), green after (`divergence`).
3. That test asserts **both** files are named — a verdict-only assertion would pass a fix that recovered one path and dropped the other.
4. **One filename contains a space.** `-z` exists because filenames can contain whitespace; two ordinary names prove the separator survives, but only a whitespace name proves it survives for the reason it was chosen.
5. The mirror in `codex/skills/flow-auto/reference.md` carries the same block and is re-synced.

Provenance: nit store #864 comment 5775731658. Owner ruled 2026-09-23 that this is fixed separately rather than folded into #1211, so #1211's before/after measurement is taken on a clean file.


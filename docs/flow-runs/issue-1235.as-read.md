# Issue #1235 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1235
- Read at:      2026-09-24T10:25:02Z
- updatedAt:    2026-09-24T09:42:09Z   (context only - moves on comments and labels)
- Body digest:  8a6b4f45b9e33666dcbd6db59dba896c0e5737310f90127d589d47beb260cd22   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2171 of 2171 (cap 16384)

## Body as read
## What

`run_install()` in `scripts/codex-skill-sync.py` copies every source skill into
`~/.codex/skills` and only then walks the destination removing managed orphans
(scripts/codex-skill-sync.py:1276-1300). Within one skill it also replaces rather
than merges: `shutil.rmtree(dest)` followed by `shutil.copytree(d, dest)`.

So for the duration of an install the tree is observably inconsistent to any
concurrent reader:

- a skill listed by a reader and then `rmtree`'d by the prune loop reads as
  `No such file or directory`;
- a skill mid-replace exists as a directory whose `SKILL.md` is briefly absent.

## Why it matters

This is what turned #1232 from a silent shrink into a warning wall. Codex
enumerates `~/.codex/skills` and then reads each `SKILL.md`; entries removed
between the listing and the read produce

```
⚠ /home/cooneycw/.codex/skills/<name>/SKILL.md: failed to read file: No such file or directory (os error 2)
```

one line per affected skill. #1232 fixes the cause of that particular install
(a test aimed at the host). It does not make the install itself safe to observe,
so an ordinary `make codex-install` run concurrent with a Codex session start can
still produce the same warnings with nothing wrong.

The failure is cosmetic - nothing is lost, the tree converges - but the symptom is
indistinguishable from real breakage, which is what cost the diagnosis time in
#1232.

## Proposed direction (not settled)

Build the new tree in a staging directory beside the destination and swap it, so a
reader sees either the old tree or the new one and never a half-tree. That is a
real change with its own failure modes - a partial swap, a cross-device rename,
permissions on the parent - so it wants its own committed control: an input under
which a reader observes an inconsistent tree, and the same input under which it
does not.

Pruning before copying instead of after is cheaper but does not close it: the
per-skill `rmtree`-then-`copytree` window remains.

## Provenance

Split out of #1232's "Also worth deciding" section by agreement during that
issue's `/flow:auto` run, rather than folded into a fix whose subject was test
isolation.


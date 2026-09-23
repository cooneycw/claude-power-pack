# Issue #1151 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. It does not graduate.

- Issue:        #1151
- Read at:      2026-09-23T14:41:06Z
- updatedAt:    2026-09-20T17:27:37Z   (context only)
- Body digest:  71b14fa9bc37b5ef864a3edefdc26d5bae346ec6409e98fa563faab8fe88881f   (sha256 of the FULL body)
- Stored bytes: 1755 of 1755 (cap 16384)

## Body as read
## The gap

`scripts/codex-skill-sync.py --check` answers "is the mirror set in sync". It is being read - by the wave lane rule adopted 2026-09-20 on `codex-conversion` - as "what IS the mirror set for this source". Those differ exactly when the tree is clean, which is when a lane is declared:

```
python3 scripts/codex-skill-sync.py --check     exit 0
codex-skill-sync: 74 skill(s) in sync (...)
lines naming a codex/skills path: 2   <- summary + caveat, zero specific paths
```

`--check` names mirrors only after they have drifted - after the source was edited and before regeneration - which is the window in which the author already knows what they touched. There is no non-mutating enumeration: `--help` offers `--check`, `--write`, `--install` and a families positional; `--write` would name the set by changing the tree.

Found by worker-E while applying the rule (an instrument read for a question it does not answer - the #1147 shape one layer up).

## Ask

`--list-mirrors [SOURCE ...]` (or `--explain SOURCE`): print, without touching the tree, every `codex/skills/**` path the generator would produce from the given source(s) - or from all bundled sources when none is given - one per line, so a lane can be declared as sources and the mirror set derived at declaration time. Negative control: a source that is NOT bundled must produce zero lines and say so by name, distinguishable from a bundled source with zero mirrors (which cannot exist - say that too).

Until this lands, the wave rule is: the grant is the RULE - a lane naming a bundled source carries its mirrors implicitly and non-exclusively, no enumeration required. Related: Nit Store #864 (register.md rule), #1136 (bundled docs and scripts invisible to the re-sync trigger).

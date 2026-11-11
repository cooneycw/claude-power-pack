# The `scripts/` reference directory

One file per script, each loadable alone. [The inventory](../scripts.md) is the
index: one line per script, gated by `make scripts-inventory-check`. Issue #1672
split the former single-file inventory into this directory; every section was
moved verbatim. The former file's preamble is kept below as history. Its
inventory marker now lives in the index, and the gate reads only the index.

## Former preamble of `docs/scripts.md` (history)

Its title was:

````
# `scripts/` inventory - per-script history
````

Relocated from `CLAUDE.md` by issue #711: the root memory file loads into every
session, so it keeps exactly one line per script (the #501 line-granularity
convention) and the accumulated per-script history lives here. Entries are
verbatim moves - nothing was reworded or dropped.

See also `docs/commands-reference.md` (the command-surface half of the same move).

The **population** of this file is derived and checked - `make scripts-inventory-check`
(`scripts/scripts-inventory-check.py`, issue #1013) fails when a file in `scripts/`
has no entry here, or when a section names no file in `scripts/`. The prose per
entry stays hand-written; only the set is mechanical. The set is read from the
DIRECTORY (`iterdir`), not from `git ls-files`, so an UNTRACKED file in `scripts/`
counts locally and does not exist in CI's clean clone: the same tree can be red
locally and green in CI until the file is committed or removed (#1273). A section that is
legitimately about something other than one script is declared on the marker
below, and an undeclared one turns the gate red rather than passing quietly.

`<!-- scripts-inventory: non-script-sections: hooks, tools-check -->`

`hooks` groups the harness hook scripts; `tools-check` is a Makefile target
(the declared external-tool set `make verify` needs), not a file in `scripts/`.

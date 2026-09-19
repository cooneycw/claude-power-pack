This case is DELIBERATELY EMPTY of a `registry.json`.

It is the defect #1017 found while running the procedure #934 committed. That
procedure guarded the unreadable-registry case as

    raw=$(flow-wave-registry.sh list --wave "$W" --json) || { echo unknown; }

and `list` exits 0 with an empty roster when the registry does not exist, so the
branch was unreachable and a host with no registry read `RETIREMENT: clear` -
"I could not look, therefore nobody is there", on the gate whose own prose
spends three paragraphs warning against exactly that.

A directory holding only this file is what a machine with no wave registry looks
like. The gate must report `unknown` (exit 3).

Git does not track empty directories, so this file is also what keeps the case
present in a clean clone - a control whose input vanishes on checkout is a green
that does not survive a clone.

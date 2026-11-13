# Current register cross product (#1762)

These 196 rows characterize current `flow-wave-registry.sh register`, measured
on main `b2da2133e3958caede2a94c942e4b4c6459ab838` and rerun after merging
`57de62ae`. The measured fields remain as the pre-fix baseline. `chosen` records the
owner ruling of 2026-11-13, "1762 yes yes yes". On that baseline the chosen
196 rows plus completeness yield 133 failures / 64 passes; the plain
withdrawal-note check separately fails.

Each identity has seven states: absent/omitted, absent/present,
present/omitted, present/same, present/different, absent/explicit-empty and
present/explicit-empty. Cross both identities with present/absent `--files`
and a complete PR observation. All paths are fixture-owned placeholders.

The seed is written through real registration calls, including a real overtake
from base-1 to base-2. Every row asserts files, full prior observation and count1
before calling the real helper. The expected JSON is measured output, not a
calculation using a copy of the move predicate. A separate completeness test
requires every input tuple and both sides of preservation/reset behavior.
The existing matrix runs its 29 scenarios from main, linked-worktree and
outside-repository directories; these extra cross-product calls use the owned
outside-repository directory.

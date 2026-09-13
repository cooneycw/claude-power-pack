"""One wave namespace per pytest invocation (issues #881, #882).

`tests/test_flow_wave_mailbox.py` and `tests/test_flow_wave_lexicon.py` both
used the literal wave name ``testwave``, identical in every checkout on the
host. The mailbox helper's `ps` fallback lane scans the WHOLE host process
table (`scripts/flow-wave-mailbox.sh`, `ps -eo pid,ppid,args`) and filters
candidates by the ``--wave`` value in their argv, so a watcher belonging to a
DIFFERENT worktree's test run matched the filter and was indistinguishable
from one under test.

**The code under test was right and the tests were wrong**, which is why the
fix is here and not in the lane. When the `ps` lane finds a watcher-shaped
process it cannot prove belongs to this mailbox, answering ``unknown`` is the
honest verdict #845/#849 deliberately built - `FLOW_WAVE_MAILBOX_DIR` travels
in the environment and `ps -eo args` cannot see it. Two assertions expected a
confident ``dead``/``0``, which is only reachable when NOTHING matches at all:

- `TestListWatchState::test_ps_fallback_lane_agrees_only_where_it_can_verify`
- `TestPsFallbackWatcherIdentityAcrossDirectories::test_no_match_at_all_still_reads_a_confident_dead`

Their intended property is "no watcher for THIS mailbox". Under a shared wave
name that is not the question the filter asks, which is "no watcher-shaped
process anywhere on this host". A per-invocation namespace makes the two
questions one again, and does it without touching the `ps` scan, relaxing an
assertion, or teaching the lane to claim a confidence it cannot support.

**Uniqueness is per PROCESS, deliberately.** A pid is unique among LIVE
processes, which is exactly the population a whole-host `ps` scan can see, so
two concurrent runs cannot collide however they are launched. The random
suffix covers the one case a pid alone does not: a watcher orphaned by an
earlier run, outliving the pytest process whose pid a later run is then
assigned.

**What this does NOT do.** It does not isolate tests from each OTHER within one
invocation - every test in a file still shares its file's namespace. That is
unchanged from before and is safe for the same reason it was safe before: the
`/proc` lane resolves a candidate's real wave directory from
`/proc/<pid>/environ` and excludes one whose root differs, and each test gets a
fresh `tmp_path` root. The `ps` lane cannot do that, which is precisely why it
answers ``unknown`` rather than guessing. If a same-invocation orphan ever does
form, the `ps` lane will still report ``unknown`` for it - correctly.

Keep it in one module so the next file needing a wave namespace imports this
rather than typing a third literal. That is how the second one happened.
"""

from __future__ import annotations

import os
import secrets

#: Computed once per pytest process, so every namespace derived from it carries
#: the same run id. Handy in a `ps` listing: a stray watcher names the run that
#: leaked it. Charset is deliberately conservative - the helper validates these
#: as path components (letters, digits, `_`, `.`, `-`; no leading dot).
RUN_ID = f"{os.getpid()}-{secrets.token_hex(4)}"


def unique_wave(prefix: str = "testwave") -> str:
    """Return a wave name unique to this pytest invocation.

    The ``testwave`` prefix is kept so the value is still recognisable as test
    traffic by a human reading `ps` output, which is how #882 was diagnosed in
    the first place.
    """
    return f"{prefix}-{RUN_ID}"

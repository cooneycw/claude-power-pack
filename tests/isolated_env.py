"""One definition of "an isolated PATH that still works" (issue #1171).

WHY THIS EXISTS. Many fixtures in this suite hand their subject a deliberately
minimal environment - `env={"HOME": ..., "PATH": "/usr/bin:/bin"}` - and the
isolation is the point: the subject must not inherit the developer's PATH. But
that literal also encodes an ASSUMPTION, that the binaries the subject needs live
in system directories. For git that assumption is false wherever git is STAGED
rather than installed, which is exactly CPP's CI image: it ships no git at all
(`check-test-binary-guards.py` has recorded that since #451), and `.woodpecker.yml`
stages a pinned one into `.ci-bin` reached through PATH.

The consequence was invisible for as long as the tests never ran. 268 test
functions across 23 files carry `@requires_git`, so with no git in the image every
one of them SKIPPED in every pipeline - and the suite said so on every run
("missing-binary skips: N test(s) did not run because a binary is absent"), which
nothing consumed. When staging made git findable they ran for the first time and
raised FileNotFoundError on a binary their own marker had just certified present.

WHY A SHARED DEFINITION RATHER THAN A FIX PER FILE. The first CI red named three
files; fixing those revealed four more, one of which had already been edited. The
population is the idiom, not the failure list, and a literal copied into every
fixture means the next test that isolates PATH inherits the bug rather than the
fix. Defining it once is what makes that stop.

WHAT THIS IS NOT FOR. A fixture that deliberately withholds a binary - to prove a
gate reports UNKNOWN rather than crashing when git is absent - must NOT use this.
Those build their own git-free PATH (`git_free_path`) and assert the absence they
depend on. Isolation and absence are different intents; this constant serves the
first only.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_GIT = shutil.which("git")

#: `/usr/bin:/bin` plus git's REAL directory when git is resolvable. The fallback
#: is the bare literal, so a host with no git anywhere behaves exactly as before
#: and the `@requires_git` markers still make the decision.
ISOLATED_PATH = f"/usr/bin:/bin:{Path(_GIT).parent}" if _GIT else "/usr/bin:/bin"

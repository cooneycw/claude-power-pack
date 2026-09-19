"""Strip a flow helper's `<NAMESPACE>_EXIT=<code>` status line (issue #1031).

Every helper in the flow family now prints its exit status on stderr as the last
thing it writes, so that `helper | tail -3; echo $?` - which reports TAIL's
status - can no longer delete it.

Several tests assert that a helper is SILENT when it has nothing to report. That
claim is about DIAGNOSTICS, and the status line is not a diagnostic: it is
emitted on every run by design, clean or not. So the line is removed before the
claim is made, rather than the claim being weakened to tolerate anything extra
on stderr - which would also have tolerated the warning the assertion exists to
catch.

The pattern is deliberately exact (`^[A-Z][A-Z0-9_]*_EXIT=\\d+$`, whole line). A
looser one - dropping anything containing `_EXIT`, or any line matching a helper
namespace - would swallow a real diagnostic that happened to mention it.
"""

from __future__ import annotations

import re

STATUS_LINE = re.compile(r"^[A-Z][A-Z0-9_]*_EXIT=\d+$")


def without_status(text: str) -> str:
    """`text` with any whole-line exit-status marker removed, then stripped."""
    kept = [line for line in text.splitlines() if not STATUS_LINE.fullmatch(line.strip())]
    return "\n".join(kept).strip()

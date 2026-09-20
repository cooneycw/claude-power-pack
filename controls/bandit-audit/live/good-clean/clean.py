"""The other half of the live positive control (issue #962).

A gate wedged at "fail" passes the known-bad fixture on its own, so this tree
is what separates a working scan from a stuck one. It must stay clean at every
severity - not merely at the gated band - because a LOW finding here would make
the selftest's own denominator ambiguous.

If a future bandit release starts reporting something in this file, that is not
a reason to add a suppression: rewrite the file. A selftest fixture carrying a
suppression proves nothing about the scan.
"""

from pathlib import Path


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())

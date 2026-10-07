"""Blind anchor for controls/lib-security-gate (issue #1394).

A minimal stand-in at the SAME relative depth under its own anchor root
(`lib/security/cli.py`) that the real module sits at under the repository
root - the invocation's `sys.path` trick (see control.json) resolves
`import lib.security.cli` to whichever copy sits that many directories above
the path it was given, so this file is what gets imported when `{gate}`
names the anchor instead of the real file. It claims PASS unconditionally,
never inspecting the case directory at all - the blind half of the pair that
proves the real gate's detection is not assumed.
"""

from __future__ import annotations

import sys


def run() -> None:
    print("SECURITY_GATE: flow_finish PASS (blind anchor; never looked)")
    sys.exit(0)

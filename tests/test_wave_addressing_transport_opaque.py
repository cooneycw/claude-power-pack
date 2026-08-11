"""Pin: the wave-addressing docs show more than one transport (issue #675).

`flow-wave-registry.sh verify` accepts any transport-stamped token - it is a
string comparison with no scheme validation. The DOCS said otherwise: every
example was a `uds:` socket and the addressing rule read "socket-only". On a
host whose live transport stamps `bridge:session_...`, a worker read that
literally and reported the wave as structurally broken. The tool was fine; the
description was the blocker.

The prose itself is not testable and this file does not try. What IS testable is
the specific regression that created the defect: collapsing the examples back to
a single transport, so the one shown form reads as the required form. One
instance always teaches itself as the rule.

Deliberately narrow, so an innocent rewording cannot fail it:
  - no line numbers, no section scoping, no required phrasing
  - only two facts per file - a uds example is present, and at least one non-uds
    example is present
  - adding a THIRD transport passes untouched; that is the point of the list

A doc test that breaks on rephrasing is worse than no doc test, so if this ever
fails, check first whether an example was REMOVED before rewording anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Files that document how an orchestrator addresses a worker.
ADDRESSING_DOCS = [
    ROOT / ".claude" / "commands" / "flow" / "register.md",
    ROOT / ".claude" / "commands" / "flow" / "wave.md",
]

UDS_SCHEME = "uds:"

# Every non-uds transport whose stamped form the docs may use as the contrasting
# example. ADD to this list when a new transport appears - never narrow it to
# whichever one the docs happen to use today, which would re-privilege a single
# transport in the very test that exists to prevent that.
NON_UDS_SCHEMES = ("bridge:",)


@pytest.mark.parametrize("doc", ADDRESSING_DOCS, ids=lambda p: p.name)
def test_doc_shows_a_uds_example(doc: Path) -> None:
    """The uds form must survive: it is real, and it is what most hosts stamp."""
    assert UDS_SCHEME in doc.read_text(encoding="utf-8"), (
        f"{doc.relative_to(ROOT)} shows no {UDS_SCHEME} example. The fix for "
        f"#675 was to show SEVERAL transports, not to swap which single one is "
        f"privileged - dropping uds mirrors the original bug."
    )


@pytest.mark.parametrize("doc", ADDRESSING_DOCS, ids=lambda p: p.name)
def test_doc_shows_a_non_uds_example(doc: Path) -> None:
    """The regression pin (#675): a second transport must be visible.

    With only `uds:` on the page, a reader on any other transport concludes the
    addressing scheme has nothing to point at - the reported field failure.
    """
    text = doc.read_text(encoding="utf-8")
    assert any(scheme in text for scheme in NON_UDS_SCHEMES), (
        f"{doc.relative_to(ROOT)} shows only {UDS_SCHEME} addresses. The "
        f"registry stores whatever the transport stamped and never parses it, "
        f"so a uds-only page misdescribes the contract (issue #675): a worker "
        f"on a {NON_UDS_SCHEMES[0]}... lane read exactly this and reported the "
        f"wave broken. Show at least one of {list(NON_UDS_SCHEMES)} alongside "
        f"the uds example - or add the new transport to NON_UDS_SCHEMES here."
    )


def test_addressing_rule_is_not_worded_socket_only() -> None:
    """The rule's INTENT (never address by mutable display labels) survives; its
    old wording claimed a transport (#675). Pinned because the phrase is what a
    reader obeys literally - it is the sentence the field report acted on."""
    text = (ROOT / ".claude" / "commands" / "flow" / "register.md").read_text(encoding="utf-8")
    assert "Addressing rule: socket-only" not in text, (
        "register.md restates the addressing rule as 'socket-only' (issue "
        "#675). The rule means 'by the registry address, never by a ListAgents "
        "display label' - it never required a socket. Word it transport-neutrally."
    )

"""Pin: register.md names two watch-robustness rules the Nit Store found
missing (issue #1402).

Neither is enforceable in code - one is "arm from a directory that will not
be removed", the other is "probe before claiming, in a free-text report" -
so the fix for both is this document saying so. This file pins that it does,
by anchored substring rather than by line number, so a rewording of the
surrounding prose cannot fail it while the rule itself survives.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER_MD = ROOT / ".claude" / "commands" / "flow" / "register.md"


def _text() -> str:
    return REGISTER_MD.read_text(encoding="utf-8")


def test_step_4_names_the_removed_worktree_hazard() -> None:
    text = _text()
    assert "never a flow worktree" in text, (
        "register.md's watch-arming step (#1228) does not tell a worker to "
        "arm from a directory that outlives its work - a worktree removed "
        "while the watch blocks breaks the harness's own trailing re-anchor "
        "in the same shell, after the watch already delivered and exited 0 "
        "(issue #1402)"
    )
    assert "the output does not" in text, (
        "the step does not name the discriminator (output present means "
        "delivered, regardless of a misleading non-zero exit code)"
    )


def test_release_section_requires_a_probe_not_a_memory() -> None:
    """Anchored on "PROBED, never stated from memory" specifically, not the
    word "stand-down" - that word alone is not unique to this guidance (the
    quoted incident text also says "stopped at stand-down"), so a later,
    unrelated mention anywhere in the document could silently defeat a
    split keyed on it (counter-model review, 2026-10-06)."""
    text = _text()
    assert text.count("PROBED, never stated from memory") == 1, (
        "register.md's Release section does not tell a worker to probe its "
        "own watch state and release status before claiming either in a "
        "stand-down report - a real incident had both claims false while "
        "stated from belief (issue #1402)"
    )
    rest = text.split("PROBED, never stated from memory", 1)[1]
    assert "FLOW_WAVE_REGISTRY: released" in rest, (
        "the probe guidance does not name the release command's own "
        "verdict line to quote"
    )
    assert "FLOW_MAILBOX_WATCH_STATE" in rest, (
        "the probe guidance does not name the watch-status line to quote"
    )

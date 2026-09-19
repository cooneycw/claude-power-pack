"""Every script a command document invokes at `~/.claude/scripts/` must be installable.

THE DEFECT THIS PINS (issue #1066). `/project:next` states that its engine at
`~/.claude/scripts/project-next.py` "is always present with this command" and
invokes it there. Both loops that create that symlink - `/cpp:init` Tier 2 and
`/cpp:update` Step 5b - skip non-executable files:

    [ -f "$script" ] && [ -x "$script" ] || continue

and `scripts/project-next.py` was committed `100644`. So on a FRESH host the
symlink is never created and the command fails at the path its own document
calls always-present.

WHY NOTHING CAUGHT IT. It is invisible on an established host: the symlink here
predates the current loop, so `make verify`, CI, and every existing box look
identical to a healthy install. The only observable difference is on a machine
nobody had run the test on.

THE POPULATION IS DERIVED FROM THE CONSUMERS, not hardcoded. The question is not
"are these five files executable" - it is "does every path a command document
promises actually install". A hardcoded list would have to be updated by the same
person who forgets the mode bit, which is the failure it is meant to catch.

Measured when this landed: of the five non-executable files in `scripts/`,
exactly ONE is referenced at the stable path, so this gate names one file rather
than a class. The other four are invoked by repo-relative path and are correctly
unaffected - which is also what keeps this from being a "chmod +x everything"
rule that would assert something the installers do not require.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / ".claude" / "commands"
SCRIPTS = ROOT / "scripts"

#: `~/.claude/scripts/<name>` - the stable path the #581 allowlist matches and
#: the two installer loops populate.
STABLE_REF = re.compile(r"~/\.claude/scripts/([A-Za-z0-9._-]+\.(?:sh|py))")

#: The mode comes from the INDEX, which needs git. The CI `validate` image
#: (uv:python3.11-bookworm-slim) ships bash but not git, so the assertion that
#: shells out carries the guard CLAUDE.md requires; the two checks that only
#: read files stay unguarded and always run.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="requires git on PATH (absent in the CI validate container)",
)


def _referenced_at_stable_path() -> dict[str, list[str]]:
    """{script basename: [documents invoking it there]} - derived, never listed."""
    found: dict[str, list[str]] = {}
    for doc in sorted(COMMANDS.rglob("*.md")):
        for name in set(STABLE_REF.findall(doc.read_text())):
            if (SCRIPTS / name).is_file():
                found.setdefault(name, []).append(str(doc.relative_to(ROOT)))
    return found


def _index_mode(rel: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-s", rel],
        capture_output=True, text=True, check=False,
    ).stdout.split()
    return out[0] if out else ""


def test_the_scan_finds_something() -> None:
    """Positive control: a broken extractor's empty result looks exactly like a pass.

    If the reference pattern or the docs tree ever stops matching, every
    assertion below becomes vacuously true and this file goes green while
    checking nothing.
    """
    referenced = _referenced_at_stable_path()
    assert referenced, (
        "no command document references ~/.claude/scripts/<script> - the extractor "
        "is broken, or the docs moved; either way the checks below prove nothing"
    )
    assert "project-next.py" in referenced, (
        "the known consumer disappeared from the scan - re-check the pattern before "
        "trusting a clean result"
    )


@requires_git
def test_every_stable_path_script_is_executable() -> None:
    """The regression assertion for #1066.

    Fails on the pre-fix tree: `scripts/project-next.py` was `100644`, so both
    installer loops skipped it and `/project:next` had no engine on a fresh host.
    """
    offenders = []
    for name, docs in sorted(_referenced_at_stable_path().items()):
        mode = _index_mode(f"scripts/{name}")
        if mode and mode != "100755":
            offenders.append(f"  scripts/{name} is {mode}, invoked at the stable path by {', '.join(docs)}")
    assert not offenders, (
        "these scripts are promised at ~/.claude/scripts/ but both installer loops\n"
        "skip non-executable files, so a FRESH install never creates the symlink\n"
        "(issue #1066):\n" + "\n".join(offenders)
    )


def test_the_installer_gate_is_still_executability() -> None:
    """The assumption the test above rests on, asserted rather than assumed.

    If either loop stopped gating on `-x`, this pin would be enforcing a
    condition nothing requires - still green, and no longer about anything.
    """
    for doc, label in (
        (COMMANDS / "cpp" / "init.md", "/cpp:init Tier 2"),
        (COMMANDS / "cpp" / "update.md", "/cpp:update Step 5b"),
    ):
        assert '[ -f "$script" ] && [ -x "$script" ] || continue' in doc.read_text(), (
            f"{label} no longer gates the symlink loop on executability - re-derive "
            f"what this test should be asserting (issue #1066)"
        )

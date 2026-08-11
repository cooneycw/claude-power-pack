"""Pin: every helper the permissions template pre-approves gets linked (issue #669).

`templates/claude-settings-permissions.json` ships allow rules matching the
stable `~/.claude/scripts/<name>` path, and the Tier 2 link step (`/cpp:init`
Tier 2, re-run by `/cpp:update` Step 5b) is what creates those symlinks. The
two drifted once: the link loop iterated `scripts/*.sh` only, so the rule for
`flow-wave-plan.py` (a Python helper, #637/#642) pointed at a path the loop
never created and the zero-prompt lane silently degraded - a CODE-EXEC prompt
on every wave re-plan.

Two pins close the gap from both sides:

1. Template-side: every `Bash(~/.claude/scripts/<name>:*)` rule names a file
   that exists in `scripts/` AND is executable, because the widened link loop
   gates on executability - a rule naming a non-executable (or missing) helper
   is a rule pointing at a path the loop will not create.
2. Doc-side: the link loops in `.claude/commands/cpp/update.md` (Step 5b) and
   `.claude/commands/cpp/init.md` (Tier 2) iterate `"$CPP_DIR"/scripts/*` with
   an `-x` gate - a future editor cannot quietly regress to the `.sh`-only
   glob that caused #669.

THE SECOND INSTALLER (issue #677). The two pins above cover `/cpp:init` Tier 2,
which is only ONE of the two things that populate `~/.claude/scripts/`. The
other is `scripts/flow-helpers-install.sh` (`/flow:repair`), which installs a
CURATED array rather than globbing - and it omitted `cpp-commands-link.sh` and
`install-drift.sh`. So on any host provisioned WITHOUT interactive `/cpp:init` -
scripted provisioning being the motivating case - those two rules matched paths
nothing ever created: inert rules, and `/cpp:update` Step 5c falling back to the
checkout copy, whose path the rule does not match, and prompting.

#669's fix and this file both landed 27 minutes BEFORE #677 was filed, and did
not catch it, because they pin template -> Tier-2-loop and #677 lives on
template -> curated-array. Pin 3 below adds that axis. The disease was never one
missing entry; it was three hand-maintained lists (template rules, the
installer's array, and a copy of that array inside
`tests/test_flow_helpers_install.py` that had itself drifted to 9 of 13 entries)
with no two of them checked against each other.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = ROOT / "templates" / "claude-settings-permissions.json"
SCRIPTS_DIR = ROOT / "scripts"
INSTALLER = ROOT / "scripts" / "flow-helpers-install.sh"

LINK_LOOP_DOCS = [
    ROOT / ".claude" / "commands" / "cpp" / "update.md",
    ROOT / ".claude" / "commands" / "cpp" / "init.md",
]

STABLE_PATH_RULE = re.compile(r"^Bash\(~/\.claude/scripts/([^:)]+):\*\)$")
HELPERS_ARRAY = re.compile(r"^HELPERS=\(\n(.*?)^\)$", re.DOTALL | re.MULTILINE)


def _template_helper_names() -> list[str]:
    data = json.loads(TEMPLATE.read_text())
    names = []
    for rule in data.get("permissions", {}).get("allow", []):
        m = STABLE_PATH_RULE.match(rule)
        if m:
            names.append(m.group(1))
    return names


def installer_helper_names() -> list[str]:
    """The HELPERS array from flow-helpers-install.sh, parsed from the script.

    Deliberately PARSED rather than duplicated (issue #677): a test that keeps
    its own copy of the list under test cannot detect an omission from that
    list - it only proves the copy matches itself, which is exactly how the
    9-entry copy in tests/test_flow_helpers_install.py sat green beside a
    13-entry array missing two required helpers. Shared with that module so one
    source of truth serves both.
    """
    m = HELPERS_ARRAY.search(INSTALLER.read_text())
    assert m, (
        f"could not find the HELPERS=( ... ) array in "
        f"{INSTALLER.relative_to(ROOT)} - if the array was reformatted, update "
        f"this parser; do NOT hardcode a copy of the list (issue #677)"
    )
    names = []
    for line in m.group(1).splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            names.append(entry)
    return names


def test_template_names_at_least_the_known_family() -> None:
    """Sanity: the parse actually finds the helper rules (guards the regex)."""
    names = _template_helper_names()
    assert "flow-start-resolve.sh" in names
    assert "flow-wave-plan.py" in names, (
        "flow-wave-plan.py rule missing from the template - the #669 repro case"
    )


@pytest.mark.parametrize("name", _template_helper_names())
def test_every_templated_helper_is_created_by_the_link_step(name: str) -> None:
    """Each stable-path allow rule must point at a file the Tier 2 loop links.

    The loop iterates `scripts/*` and links files passing `[ -f ] && [ -x ]`,
    so existence + executability in `scripts/` is exactly "the symlink will be
    created" (issue #669).
    """
    src = SCRIPTS_DIR / name
    assert src.is_file(), (
        f"{TEMPLATE.relative_to(ROOT)} allows ~/.claude/scripts/{name} but "
        f"scripts/{name} does not exist - the rule points at a path no link "
        f"step will ever create (issue #669)"
    )
    assert os.access(src, os.X_OK), (
        f"scripts/{name} is not executable, so the Tier 2 link loop skips it "
        f"and its allow rule points at a nonexistent path (issue #669) - "
        f"chmod +x scripts/{name}"
    )


def test_installer_array_parses_to_a_plausible_family() -> None:
    """Sanity: the array parse works (guards the regex, as #669 guards its own).

    Without this, a reformat that broke the parse would silently empty the list
    and make the parity test below vacuously true - a green test asserting
    nothing, the failure mode this whole file exists to prevent.
    """
    names = installer_helper_names()
    assert len(names) >= 10, f"suspiciously short HELPERS parse: {names}"
    assert "flow-start-resolve.sh" in names
    assert "flow-helpers-install.sh" in names, "the installer installs itself"


@pytest.mark.parametrize("name", _template_helper_names())
def test_every_templated_helper_is_installed_by_flow_helpers_install(name: str) -> None:
    """Each stable-path allow rule must also be in the curated installer array.

    The #669 pins above only prove `/cpp:init` Tier 2 creates the path. A host
    provisioned without interactive `/cpp:init` gets its stable paths from
    `flow-helpers-install.sh` instead, and that installer globs nothing - it
    installs exactly the names in HELPERS. A rule outside that array is inert on
    such a host: it matches a path no installer creates, so the command prompts
    with the matching rule already installed (issue #677).

    The array may legitimately be a SUPERSET (flow-helpers-install.sh installs
    itself and has no allow rule of its own). Only the other direction is a
    defect.
    """
    assert name in installer_helper_names(), (
        f"{TEMPLATE.relative_to(ROOT)} pre-approves ~/.claude/scripts/{name} but "
        f"{INSTALLER.relative_to(ROOT)}'s HELPERS array does not install it - the "
        f"rule is INERT on any host provisioned without interactive /cpp:init "
        f"(issue #677). Add {name} to HELPERS; the array is the stable-path "
        f"install set, not a flow-only list."
    )


@pytest.mark.parametrize("doc", LINK_LOOP_DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_link_loop_docs_use_the_widened_executable_gate(doc: Path) -> None:
    """The documented link loops must not regress to the `.sh`-only glob."""
    text = doc.read_text()
    assert '"$CPP_DIR"/scripts/*.sh' not in text, (
        f"{doc.relative_to(ROOT)}: the `.sh`-only link glob is the #669 "
        f"regression - iterate \"$CPP_DIR\"/scripts/* with an executability "
        f"gate instead"
    )
    assert 'for script in "$CPP_DIR"/scripts/*' in text, (
        f"{doc.relative_to(ROOT)}: expected the widened link loop over "
        f'"$CPP_DIR"/scripts/* (issue #669)'
    )
    assert '[ -f "$script" ] && [ -x "$script" ] || continue' in text, (
        f"{doc.relative_to(ROOT)}: the link loop must gate on executability "
        f"so directories, __pycache__, and non-executable library files are "
        f"skipped (issue #669)"
    )

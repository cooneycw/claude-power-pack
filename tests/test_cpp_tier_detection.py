"""The Tier 2 predicate is evidence in its own right (#1206 Decision 1).

The removal's own control proves no shipped surface CLAIMS active masking. It
says nothing about the second half of the same change: dropping the
`.claude/hooks.json` conjunct from the Tier 2 test.

That conjunct had to go, because CPP stopped shipping the file and a newly
initialised project could then never make `[ -f ".claude/hooks.json" ]` true -
every new project would cap at Tier 1 while `/cpp:update` kept offering three
rungs. But swapping a silent degradation for an UNVERIFIED predicate is the
same trade this issue exists to undo, so the new predicate is executed here
rather than read.

THE PREDICATE IS EXTRACTED FROM THE SHIPPED DOCUMENT, never restated. A copy
pasted into this file would pass while `/cpp:update` shipped something else
entirely - the test would be supplying the thing under test.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE_MD = ROOT / ".claude" / "commands" / "cpp" / "update.md"

TIER2_NAMED_SCRIPTS = ("prompt-context.sh", "worktree-remove.sh", "secrets-mask.sh")


def _extract_tier_block() -> str:
    """The Tier-1 through Tier-2 half of `/cpp:update` Step 8's detection block.

    Cut at `# Tier 3`, because Tier 3 shells out to `claude mcp list` and this
    test is about a predicate over the filesystem, not about a missing binary.
    """
    text = UPDATE_MD.read_text(encoding="utf-8")
    m = re.search(r"\n# Tier 1 checks\nTIER=0\n(.*?)\n# Tier 3", text, re.S)
    assert m, "the Step 8 tier-detection block moved; this test cannot find it"
    return "TIER=0\n" + m.group(1)


def _run_tier(tmp_path: Path, *, scripts: tuple[str, ...], hooks_json: bool) -> int:
    """Run the SHIPPED predicate against a synthetic project + fake HOME."""
    home = tmp_path / "home"
    (home / ".claude" / "scripts").mkdir(parents=True)
    for name in scripts:
        (home / ".claude" / "scripts" / name).write_text("#!/bin/sh\n")

    project = tmp_path / "project"
    (project / ".claude" / "commands").mkdir(parents=True)  # Tier 1
    if hooks_json:
        (project / ".claude" / "hooks.json").write_text('{"hooks": {}}')

    # ASSERT THE ABSENCE YOU BUILT (CLAUDE.md core directive, #697). This
    # replaces both HOME and PATH wholesale. A sandbox that silently still
    # resolved the real HOME would count the operator's own ~/.claude/scripts
    # and report TIER=2 for reasons that have nothing to do with the fixture -
    # identical output, vacuous test.
    sandbox_path = "/usr/bin:/bin"
    assert shutil.which("bash", path=sandbox_path) is not None, (
        "the sandbox PATH must carry the shell the predicate runs under"
    )
    assert not (Path.home() / ".claude" / "scripts").samefile(home / ".claude" / "scripts") \
        if (Path.home() / ".claude" / "scripts").exists() else True, (
        "the fixture HOME must not resolve to the operator's real one"
    )

    script = f'cd "{project}"\n' + _extract_tier_block() + "\necho \"TIER=$TIER\"\n"
    out = subprocess.run(
        ["bash", "-c", script],
        capture_output=True, text=True, check=False,
        env={"HOME": str(home), "PATH": sandbox_path},
    )
    assert out.returncode == 0, out.stderr
    m = re.search(r"TIER=(\d+)", out.stdout)
    assert m, f"no TIER line in output: {out.stdout!r} {out.stderr!r}"
    return int(m.group(1))


def test_a_fresh_project_reaches_tier_2_on_scripts_alone(tmp_path):
    """The condition the ruling attached to dropping the conjunct.

    No `.claude/hooks.json` anywhere - which is what every project initialised
    after #1206 looks like. Before the conjunct was dropped this returned 1.
    """
    assert _run_tier(tmp_path, scripts=TIER2_NAMED_SCRIPTS, hooks_json=False) == 2


def test_an_older_install_that_still_has_hooks_json_is_unaffected(tmp_path):
    """Existing installs keep their copy; the change must not demote them."""
    assert _run_tier(tmp_path, scripts=TIER2_NAMED_SCRIPTS, hooks_json=True) == 2


def test_two_scripts_is_NOT_tier_2(tmp_path):
    """The red case. Without it, `== 2` could be a predicate that is always true.

    The threshold is `>= 3`, so two named scripts must stay at Tier 1 - that is
    what makes the passing case above a measurement rather than a constant.
    """
    assert _run_tier(tmp_path, scripts=TIER2_NAMED_SCRIPTS[:2], hooks_json=False) == 1


def test_the_predicate_no_longer_mentions_hooks_json(tmp_path):
    """Pin the removal itself, so the conjunct cannot quietly return.

    The behavioural tests above would catch its return only while CPP also
    stopped shipping the file; this catches the edit directly.
    """
    block = _extract_tier_block()
    tier2 = block.split("# Tier 2")[1]
    # COMMENTS ARE STRIPPED FIRST, and the reason is not convenience: the
    # shipped block carries a comment EXPLAINING why the conjunct was dropped,
    # which necessarily names the file. Matching that would force the
    # explanation out of the document to keep a test green - the check would be
    # deleting the record of its own reason.
    code = "\n".join(
        line for line in tier2.splitlines() if not line.lstrip().startswith("#")
    )
    assert "hooks.json" not in code, (
        "the Tier 2 predicate references .claude/hooks.json again. CPP does not "
        "ship that file (#1206), so this conjunct can never become true for a "
        "new project and every one of them caps at Tier 1:\n" + code
    )

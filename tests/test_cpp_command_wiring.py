"""Wiring gate for /cpp:init and /cpp:update (issue #575).

Why this file exists: CPP shipped four installers/teardowns that no command
ever invoked. `codex-skill-sync.py --install`, the `~/.codex/prompts` teardown,
the `~/.claude/skills` teardown, and `install-memory-harness.sh` all worked,
were referenced from docs, and sat idle for months. Hosts silently ran stale or
missing surfaces the whole time.

Nothing could have caught that, because nothing checks that a shipped tool is
actually *reachable* from the command that is supposed to run it. This is the
same failure class as #591 (a drift script wired to nothing) and #576 (guards
never run in CI) - a capability exists, and the wiring to it does not.

So: assert that each host-facing tool is invoked from the command markdown that
owns it. These are deliberately SUBSTRING assertions against the source of
truth in `.claude/commands/`, not behavioral tests - the goal is to make
"shipped but unreachable" a red test, cheaply. No network, no git, no HOME
access, no external binaries, so it is safe in the slim validate container.

When a step is intentionally renamed or moved, update the expectation here in
the same commit - that edit is the record of the decision.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / ".claude" / "commands" / "cpp"
UPDATE_MD = COMMANDS / "update.md"
INIT_MD = COMMANDS / "init.md"


@pytest.fixture(scope="module")
def update_text() -> str:
    return UPDATE_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def init_text() -> str:
    return INIT_MD.read_text(encoding="utf-8")


# --- the four #575 gaps ------------------------------------------------------


@pytest.mark.parametrize(
    ("needle", "gap"),
    [
        ("codex-skill-sync.py --install", "gap 1: codex skills never installed to ~/.codex/skills"),
        ("retired-surface-prune.py", "gaps 2+3: retired host surfaces never torn down"),
        ("install-memory-harness.sh", "gap 4: common-memory harness never wired"),
    ],
)
def test_update_invokes_the_host_surface_tools(update_text: str, needle: str, gap: str):
    assert needle in update_text, f"/cpp:update no longer invokes {needle} - {gap}"


@pytest.mark.parametrize(
    ("needle", "gap"),
    [
        ("codex-skill-sync.py", "a fresh Codex tier install would have zero CPP skills"),
        ("install-memory-harness.sh", "cpp-memory would be missing from PATH"),
    ],
)
def test_init_invokes_the_installers(init_text: str, needle: str, gap: str):
    assert needle in init_text, f"/cpp:init no longer invokes {needle} - {gap}"


def test_init_does_not_tear_down_retired_surfaces(init_text: str):
    """Teardown belongs to /cpp:update alone. A first-time init has no history
    to reconcile, and init must never move files out of a user's HOME."""
    assert "retired-surface-prune.py --prune" not in init_text
    assert "--prune --all" not in init_text


# --- the step must exist and stay ordered ------------------------------------


def test_update_has_the_host_surface_step(update_text: str):
    assert "## Step 7.9: Generated Host-Surface Refresh" in update_text


def test_host_surface_step_runs_before_tier_detection(update_text: str):
    """Step 7.9 must precede Step 8, which computes the tier reported in the
    summary."""
    assert update_text.index("## Step 7.9:") < update_text.index("## Step 8:")


def test_update_summary_reports_host_surfaces(update_text: str):
    """A step whose result never reaches the summary is invisible to the user."""
    assert "HOST_SURFACE_STATUS" in update_text


def test_init_has_the_codex_skill_substep(init_text: str):
    assert "#### 5e." in init_text
    assert "#### 5f." in init_text


# --- teardown safety must stay stated ----------------------------------------


def test_update_states_the_teardown_is_user_confirmed_and_reversible(update_text: str):
    """The safety properties are the reason this teardown is acceptable at all;
    if the prose loses them, the next editor will not know they are load-bearing."""
    step = " ".join(update_text.split("## Step 7.9:", 1)[1].split("## Step 8:", 1)[0].split())
    assert "eversible" in step
    assert "[y/N]" in step, "the per-surface prune must be opt-in, not default-yes"
    assert "--plan" in step, "the user must be shown what would move before being asked"


def test_update_never_prunes_all_without_assent(update_text: str):
    # Normalize whitespace: these are prose assertions against hard-wrapped
    # markdown, so a re-wrap must not fail the test for the wrong reason.
    step = update_text.split("## Step 7.9:", 1)[1].split("## Step 8:", 1)[0]
    flat = " ".join(step.split())
    assert "Never pass `--all` without per-surface assent" in flat


# --- the tools the steps name must actually exist ----------------------------


@pytest.mark.parametrize(
    "rel",
    [
        "scripts/codex-skill-sync.py",
        "scripts/retired-surface-prune.py",
        "scripts/install-memory-harness.sh",
        ".claude/retired-surfaces.yaml",
    ],
)
def test_referenced_tool_exists(rel: str):
    """The inverse failure: a step that survives after its script is deleted
    (issue #545 hit exactly this when a pull removed skill-drift.py)."""
    assert (ROOT / rel).is_file(), f"{rel} is referenced by a /cpp: command but does not exist"


@pytest.mark.parametrize(
    "target",
    ["codex-install", "host-surfaces-check", "host-surfaces-prune", "memory-harness"],
)
def test_makefile_exposes_the_host_surface_targets(target: str):
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert f"\n{target}:" in makefile, f"Makefile target '{target}' is missing"
    assert target in makefile.split("\n\n", 1)[0], f"'{target}' is missing from .PHONY"

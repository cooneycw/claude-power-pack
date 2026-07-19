"""Regression tests for the plugin-marketplace scaffold + per-family plugins.

Phase B1 of the plugin-marketplace migration (ADR docs/decisions/
0001-plugin-marketplace-packaging.md, issue #477) stood up
`.claude-plugin/marketplace.json` and packaged the `flow` command family as an
installable plugin under `plugins/flow/`. Phase B2 (issue #478) extends that to
every surviving family; Phase B4 (issue #480) retired the legacy global-skill
mirror, so `.claude/commands/<family>/*.md` is the single permanent source of
truth and each plugin holds byte-identical copies kept honest by
`scripts/plugin-sync.sh`.

The hazards these pin:
  * the manifests must stay schema-valid (name/source/required fields), because
    `/plugin install <family>@cpp` resolves the marketplace by its `name` field
    and the plugin by its `source` path;
  * the packaged commands must stay byte-identical to their source, or the
    packaged copies silently diverge from the source of truth;
  * the `cpp` plugin must stay help/meta-only (ADR 0001): packaging the legacy
    /cpp:init|update|status symlink installer into the surface that replaces it
    would ship the legacy installer B4 retired;
  * the Phase B3 (#479) bundled artifacts must stay coherent: the secrets
    plugin's masking-hook script is a byte-identical copy resolved via
    ${CLAUDE_PLUGIN_ROOT} (never a host path), and the second-opinion plugin
    must NOT auto-register an MCP server on install (#569): the external
    mcp-second-opinion server is opt-in and not running on a fresh box, so a
    bundled/auto-registered pointer surfaces as "1 error during load".

Hermetic and git-free: reads the REAL repo manifests + command sources and shells
only to the git-free sync guard, so it runs in CI's git-less validate container
(see the cpp_validate_container_no_git learning).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = ROOT / "plugins"
SOURCE_COMMANDS = ROOT / ".claude" / "commands"
SYNC_SCRIPT = ROOT / "scripts" / "plugin-sync.sh"

# Every packaged family (ADR 0001 target design). `spec` is deliberately NOT
# packaged (spec-kit is the upstream product); the loose top-level commands
# were folded into the project/cpp families by #582 - see the ADR amendment.
FAMILIES = [
    "browser",
    "cicd",
    "claude-md",
    "codex",
    "cpp",
    "documentation",
    "evaluate",
    "flow",
    "github",
    "project",
    "qa",
    "second-opinion",
    "secrets",
    "security",
    "self-improvement",
]

# Per-family source basenames excluded from packaging (mirrors plugin-sync.sh).
EXCLUDED = {
    "cpp": {"init.md", "status.md", "update.md"},
}


def packaged_source_names(family: str) -> set[str]:
    src = {p.name for p in (SOURCE_COMMANDS / family).glob("*.md")}
    return src - EXCLUDED.get(family, set())


# --------------------------------------------------------------------------- #
# Marketplace manifest
# --------------------------------------------------------------------------- #
def test_marketplace_manifest_exists_and_is_json():
    assert MARKETPLACE.is_file(), f"missing {MARKETPLACE}"
    data = json.loads(MARKETPLACE.read_text())
    assert isinstance(data, dict)


def test_marketplace_name_is_cpp():
    # The install path is `/plugin install <family>@cpp`; `cpp` is this field.
    data = json.loads(MARKETPLACE.read_text())
    assert data["name"] == "cpp"


def test_marketplace_lists_every_family_exactly_once():
    data = json.loads(MARKETPLACE.read_text())
    plugins = data.get("plugins")
    assert isinstance(plugins, list) and plugins, "marketplace lists no plugins"
    names = [p.get("name") for p in plugins]
    assert names == sorted(names), "keep marketplace plugin entries sorted by name"
    assert len(names) == len(set(names)), f"duplicate plugin entries: {names}"
    assert set(names) == set(FAMILIES), (
        f"marketplace/family mismatch: missing={set(FAMILIES) - set(names)}, "
        f"unexpected={set(names) - set(FAMILIES)}"
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_marketplace_entry_shape(family: str):
    data = json.loads(MARKETPLACE.read_text())
    entry = next(p for p in data["plugins"] if p.get("name") == family)
    assert entry["source"] == f"./plugins/{family}"
    assert entry.get("description"), f"{family} plugin entry needs a description"


def test_marketplace_sources_resolve_to_plugin_manifests():
    # Every declared local source must point at a real plugin dir with a manifest.
    data = json.loads(MARKETPLACE.read_text())
    for entry in data["plugins"]:
        source = entry["source"]
        assert source.startswith("./"), f"expected relative source, got {source}"
        manifest = (ROOT / source / ".claude-plugin" / "plugin.json").resolve()
        assert manifest.is_file(), f"{entry['name']}: missing {manifest}"


# --------------------------------------------------------------------------- #
# Plugin manifests
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("family", FAMILIES)
def test_plugin_manifest_required_fields(family: str):
    manifest = PLUGINS_DIR / family / ".claude-plugin" / "plugin.json"
    assert manifest.is_file(), f"missing {manifest}"
    data = json.loads(manifest.read_text())
    # `name` derives the command namespace (/<family>:*); description required.
    assert data["name"] == family
    assert data.get("description")
    assert data.get("version"), "pin an explicit version so /plugin gates updates"


def test_no_unlisted_plugin_directories():
    # A plugin dir the marketplace does not list is uninstallable dead weight.
    on_disk = {p.name for p in PLUGINS_DIR.iterdir() if p.is_dir()}
    assert on_disk == set(FAMILIES), (
        f"plugins/ vs FAMILIES mismatch: unlisted={on_disk - set(FAMILIES)}, "
        f"missing={set(FAMILIES) - on_disk}"
    )


# --------------------------------------------------------------------------- #
# Command parity (byte-identical copies of the source of truth)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("family", FAMILIES)
def test_plugin_commands_are_byte_identical_to_source(family: str):
    expected = packaged_source_names(family)
    assert expected, f"no packageable source commands found for {family}"
    packaged_dir = PLUGINS_DIR / family / "commands"
    packaged = {p.name: p for p in packaged_dir.glob("*.md")}
    # No missing and no orphaned commands.
    assert expected == set(packaged), (
        f"{family} command set drift: missing={expected - set(packaged)}, "
        f"orphaned={set(packaged) - expected}"
    )
    for name in expected:
        src = SOURCE_COMMANDS / family / name
        assert src.read_bytes() == packaged[name].read_bytes(), (
            f"{family}/{name} differs between source and plugin (run "
            f"scripts/plugin-sync.sh --write)"
        )


def test_cpp_plugin_ships_utilities_but_never_the_installer():
    # ADR 0001 (amended for #582): the cpp plugin carries cross-cutting
    # help/meta plus the utilities folded in from the loose top-level commands.
    # The init/update/status installer is the legacy surface B4 retired; it
    # must not ship through the plugin marketplace.
    packaged = {p.name for p in (PLUGINS_DIR / "cpp" / "commands").glob("*.md")}
    assert packaged == {
        "help.md",
        "dockers.md",
        "happy-check.md",
        "load-best-practices.md",
        "load-mcp-docs.md",
    }, f"unexpected cpp plugin command set: {packaged}"
    assert not packaged & {"init.md", "status.md", "update.md"}


def test_project_plugin_ships_next_and_lite():
    # The field report on #582 hit this exact gap from a clean plugin-only
    # install: /project:next was "Unknown skill" and the plugin's own help.md
    # advertised it anyway.
    packaged = {p.name for p in (PLUGINS_DIR / "project" / "commands").glob("*.md")}
    assert {"next.md", "lite.md"} <= packaged, f"project plugin missing next/lite: {packaged}"


def test_no_top_level_source_commands():
    # #582: a *.md directly under .claude/commands/ is outside every family
    # glob, so BOTH generated surfaces silently exclude it and the parity
    # diffs cannot see it. Every command must live in a family dir.
    loose = sorted(p.name for p in SOURCE_COMMANDS.glob("*.md"))
    assert loose == [], f"top-level commands are unpackageable, move into a family: {loose}"


def test_cpp_plugin_bundles_best_practices_doc():
    # /cpp:load-best-practices reads this doc; a plugin-only install has no
    # CPP checkout, so the plugin must bundle it byte-identically (#582).
    rel = "docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md"
    bundled = PLUGINS_DIR / "cpp" / rel
    assert bundled.is_file(), f"missing {bundled} (run scripts/plugin-sync.sh --write)"
    assert bundled.read_bytes() == (ROOT / rel).read_bytes(), (
        f"plugins/cpp/{rel} differs from source (run scripts/plugin-sync.sh --write)"
    )


_HELP_REF = re.compile(r"/([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)")


def test_family_help_advertises_only_real_commands():
    # #582 field report: plugins/project/commands/help.md listed /project-next
    # while the plugin (and, post-fold, the repo) had no such command. Every
    # /<family>:<cmd> reference on an ADVERTISING line of a family help.md
    # (table row, list bullet, heading - the formats that present a command as
    # available) must resolve to a source command file for that family. Prose
    # is exempt: retirement notes legitimately name commands that no longer
    # exist (e.g. spec/help.md documenting the #420 /spec:* retirement).
    known = set(FAMILIES) | {"spec"}
    stale: list[str] = []
    for help_md in sorted(SOURCE_COMMANDS.glob("*/help.md")):
        for line in help_md.read_text().splitlines():
            if not line.startswith(("| ", "- ", "#")):
                continue
            for family, cmd in _HELP_REF.findall(line):
                if family not in known:
                    continue
                if not (SOURCE_COMMANDS / family / f"{cmd}.md").is_file():
                    rel = help_md.relative_to(ROOT)
                    stale.append(f"{rel}: /{family}:{cmd}")
    assert stale == [], f"help files advertise commands that do not exist: {stale}"


RETIRED_BARE_INVOCATIONS = [
    "/project-next",
    "/project-lite",
    "/dockers",
    "/happy-check",
    "/load-best-practices",
    "/load-mcp-docs",
]


def test_retired_bare_invocations_gone_from_sources():
    # After the #582 fold these exist only as /project:next, /project:lite,
    # /cpp:dockers, /cpp:happy-check, /cpp:load-best-practices and
    # /cpp:load-mcp-docs. A bare reference in a command source is stale
    # advertising for an invocation no surface delivers.
    offenders: list[str] = []
    for src in sorted(SOURCE_COMMANDS.rglob("*.md")):
        text = src.read_text()
        for bare in RETIRED_BARE_INVOCATIONS:
            if bare in text:
                offenders.append(f"{src.relative_to(ROOT)}: {bare}")
    assert offenders == [], f"stale bare invocations in command sources: {offenders}"


# --------------------------------------------------------------------------- #
# Phase B3 (#479): bundled hooks + MCP client pointers
# --------------------------------------------------------------------------- #
SECRETS_HOOKS = PLUGINS_DIR / "secrets" / "hooks" / "hooks.json"
SECRETS_HOOK_SCRIPT = PLUGINS_DIR / "secrets" / "scripts" / "hook-mask-output.sh"
HOOK_SCRIPT_SOURCE = ROOT / "scripts" / "hook-mask-output.sh"
SO_PLUGIN_DIR = PLUGINS_DIR / "second-opinion"
SO_PLUGIN_MANIFEST = SO_PLUGIN_DIR / ".claude-plugin" / "plugin.json"


def test_secrets_plugin_bundles_posttooluse_masking_hook():
    assert SECRETS_HOOKS.is_file(), f"missing {SECRETS_HOOKS}"
    data = json.loads(SECRETS_HOOKS.read_text())
    matchers = data["hooks"]["PostToolUse"]
    commands = [h["command"] for m in matchers for h in m["hooks"]]
    assert commands, "secrets hooks.json declares no PostToolUse commands"
    for cmd in commands:
        # A host path (~/.claude/scripts/...) would keep the plugin dependent
        # on the symlink installer B4 retires (ADR 0001 section 6).
        assert cmd.startswith("${CLAUDE_PLUGIN_ROOT}/"), (
            f"hook command must resolve inside the plugin, got: {cmd}"
        )
        rel = cmd.removeprefix("${CLAUDE_PLUGIN_ROOT}/")
        bundled = PLUGINS_DIR / "secrets" / rel
        assert bundled.is_file(), f"hook references {rel} but the plugin does not ship it"


def test_secrets_hook_script_is_byte_identical_to_source():
    assert SECRETS_HOOK_SCRIPT.is_file(), f"missing {SECRETS_HOOK_SCRIPT}"
    assert SECRETS_HOOK_SCRIPT.read_bytes() == HOOK_SCRIPT_SOURCE.read_bytes(), (
        "plugins/secrets/scripts/hook-mask-output.sh differs from "
        "scripts/hook-mask-output.sh (run scripts/plugin-sync.sh --write)"
    )


def test_secrets_hook_script_is_executable():
    assert SECRETS_HOOK_SCRIPT.stat().st_mode & 0o111, (
        "bundled hook script lost its executable bit (hooks silently no-op)"
    )


# --------------------------------------------------------------------------- #
# #590: the flow plugin bundles its helper family
# --------------------------------------------------------------------------- #
FLOW_PLUGIN_SCRIPTS = PLUGINS_DIR / "flow" / "scripts"

# The load-bearing helpers plus the installer that places them. Sourced from the
# same list plugin-sync.sh packages; a helper the commands call but the plugin
# does not ship is exit 127 for a marketplace-only user.
FLOW_BUNDLED_HELPERS = [
    "flow-start-resolve.sh",
    "flow-live-driver-guard.sh",
    "flow-stale-check.sh",
    "flow-worktree-guard.sh",
    "gh-pr-merge.sh",
    "worktree-remove.sh",
    "friction-log.sh",
    "check-ignored-additions.sh",
    "flow-helpers-install.sh",
]


@pytest.mark.parametrize("name", FLOW_BUNDLED_HELPERS)
def test_flow_plugin_bundles_helper(name: str):
    bundled = FLOW_PLUGIN_SCRIPTS / name
    assert bundled.is_file(), (
        f"plugins/flow/scripts/{name} missing - a marketplace-only install would "
        f"exit 127 when a flow command calls it (#590). Run scripts/plugin-sync.sh --write"
    )
    assert bundled.read_bytes() == (ROOT / "scripts" / name).read_bytes(), (
        f"plugins/flow/scripts/{name} differs from scripts/{name} "
        "(run scripts/plugin-sync.sh --write)"
    )
    assert bundled.stat().st_mode & 0o111, (
        f"bundled {name} lost its executable bit (invoking it fails with EACCES)"
    )


def test_flow_start_resolve_ships_with_its_sibling_guard():
    # flow-start-resolve.sh calls "$SELF_DIR/flow-live-driver-guard.sh" (#503).
    # Bundling the resolver without the guard silently drops the live-driver
    # hazard check for plugin-only users.
    resolver = (FLOW_PLUGIN_SCRIPTS / "flow-start-resolve.sh").read_text()
    assert "flow-live-driver-guard.sh" in resolver
    assert (FLOW_PLUGIN_SCRIPTS / "flow-live-driver-guard.sh").is_file(), (
        "flow-start-resolve.sh resolves its live-driver sibling via $SELF_DIR, so "
        "the guard must be bundled alongside it"
    )


def test_flow_commands_reference_repair_for_missing_helpers():
    # The exit-127 paths must name the remedy; without it the model is left with
    # a dead end (auto.md forbids inline-bash workarounds, #581).
    for cmd in ("auto.md", "start.md"):
        text = (ROOT / ".claude" / "commands" / "flow" / cmd).read_text()
        assert "/flow:repair" in text, f"{cmd} does not point at /flow:repair on exit 127"
        assert "CLAUDE_PLUGIN_ROOT" in text, (
            f"{cmd} does not offer the plugin-bundled helper as a fallback (#590)"
        )


def test_second_opinion_plugin_does_not_autoregister_mcp_server():
    # #569: the external mcp-second-opinion server is opt-in and not running on a
    # fresh box. A plugin that auto-registers an http MCP pointer on install makes
    # Claude Code try to connect on every fresh install, fail, and surface a scary
    # "1 error during load". The plugin must ship the review COMMANDS only and let
    # the user register the server (claude mcp add ...) when they opt in.
    manifest = json.loads(SO_PLUGIN_MANIFEST.read_text())
    assert "mcpServers" not in manifest, (
        "second-opinion plugin.json must NOT declare mcpServers - that auto-registers "
        "the external server on install and fails to connect on a fresh box (#569). "
        "The server is opt-in via `claude mcp add second-opinion ...`."
    )
    assert not (SO_PLUGIN_DIR / ".mcp.json").exists(), (
        "second-opinion plugin must not bundle a .mcp.json client pointer (#569); "
        "with mcpServers removed it is dead weight, and any bundled pointer risks "
        "reintroducing an active-on-install registration."
    )


# --------------------------------------------------------------------------- #
# Drift guard
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("script", [SYNC_SCRIPT], ids=["sync"])
def test_sync_script_check_passes(script: Path):
    if shutil.which("bash") is None:  # pragma: no cover - bash present in CI
        pytest.skip("bash unavailable")
    result = subprocess.run(
        ["bash", str(script), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"{script.name} --check reported drift:\n{result.stdout}\n{result.stderr}"
    )


def test_sync_script_rejects_unknown_family():
    if shutil.which("bash") is None:  # pragma: no cover - bash present in CI
        pytest.skip("bash unavailable")
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "--check", "no-such-family"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, "unknown family must be a usage error (exit 2)"


# --------------------------------------------------------------------------- #
# Completeness gate (#582): sources outside every family fail --check loudly
# --------------------------------------------------------------------------- #
def _tmp_tree_with_flow(tmp_path: Path) -> Path:
    """Minimal repo tree where the flow family is in perfect sync, so any
    --check failure comes from the completeness gate alone."""
    src = tmp_path / ".claude" / "commands" / "flow"
    src.mkdir(parents=True)
    (src / "auto.md").write_text("# auto\n")
    dest = tmp_path / "plugins" / "flow" / "commands"
    dest.mkdir(parents=True)
    (dest / "auto.md").write_text("# auto\n")
    # The flow family also packages its helper scripts (EXTRA_FILES, #590), and
    # a missing extra source is a hard error - so the stub tree must carry them
    # on both sides to stay "in perfect sync".
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "plugins" / "flow" / "scripts").mkdir(parents=True, exist_ok=True)
    for name in FLOW_BUNDLED_HELPERS:
        body = f"#!/usr/bin/env bash\n# stub {name}\n"
        (tmp_path / "scripts" / name).write_text(body)
        (tmp_path / "plugins" / "flow" / "scripts" / name).write_text(body)
    return tmp_path


def _run_sync(tree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SYNC_SCRIPT), *args],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "PLUGIN_SYNC_REPO_ROOT": str(tree)},
    )


def test_completeness_flags_top_level_command(tmp_path: Path):
    if shutil.which("bash") is None:  # pragma: no cover - bash present in CI
        pytest.skip("bash unavailable")
    tree = _tmp_tree_with_flow(tmp_path)
    (tree / ".claude" / "commands" / "stray.md").write_text("# stray\n")
    result = _run_sync(tree, "--check", "flow")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "UNPACKAGED top-level command: .claude/commands/stray.md" in result.stdout


def test_completeness_flags_unlisted_family(tmp_path: Path):
    if shutil.which("bash") is None:  # pragma: no cover - bash present in CI
        pytest.skip("bash unavailable")
    tree = _tmp_tree_with_flow(tmp_path)
    rogue = tree / ".claude" / "commands" / "rogue"
    rogue.mkdir()
    (rogue / "x.md").write_text("# x\n")
    result = _run_sync(tree, "--check", "flow")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "UNPACKAGED family: .claude/commands/rogue/" in result.stdout


def test_completeness_allows_documented_exclusions(tmp_path: Path):
    if shutil.which("bash") is None:  # pragma: no cover - bash present in CI
        pytest.skip("bash unavailable")
    tree = _tmp_tree_with_flow(tmp_path)
    spec = tree / ".claude" / "commands" / "spec"
    spec.mkdir()
    (spec / "adopt.md").write_text("# adopt\n")
    result = _run_sync(tree, "--check", "flow")
    assert result.returncode == 0, result.stdout + result.stderr


def test_completeness_only_gates_check_mode(tmp_path: Path):
    if shutil.which("bash") is None:  # pragma: no cover - bash present in CI
        pytest.skip("bash unavailable")
    tree = _tmp_tree_with_flow(tmp_path)
    (tree / ".claude" / "commands" / "stray.md").write_text("# stray\n")
    result = _run_sync(tree, "--write", "flow")
    assert result.returncode == 0, result.stdout + result.stderr


# --------------------------------------------------------------------------- #
# B4 retirement (#480): the dual surface + skill-drift + symlink installer gone
# --------------------------------------------------------------------------- #
RETIRED_ARTIFACTS = [
    "scripts/flow-skill-sync.py",       # global flow-* mirror generator
    "scripts/skill-drift.py",           # dual-surface drift reconciler
    "scripts/plugin-flow-sync.sh",      # B1 shim, superseded by plugin-sync.sh
    ".claude/deprecated-skills.yaml",   # skill deprecation list of record
]


@pytest.mark.parametrize("rel", RETIRED_ARTIFACTS)
def test_dual_surface_artifact_retired(rel: str):
    # ADR 0001 B4 exit: these files exist only to keep the retired global-skill
    # mirror in sync. Plugins are the single delivered surface now.
    assert not (ROOT / rel).exists(), (
        f"{rel} was retired by B4 (#480); it must not come back"
    )


@pytest.mark.parametrize("cmd", ["init", "update", "status"])
def test_installer_no_skills_mirror_symlink(cmd: str):
    # The /cpp installer must no longer install or reconcile the global-skill
    # mirror (~/.claude/skills). Commands stay symlinked; skills ship via /plugin.
    text = (SOURCE_COMMANDS / "cpp" / f"{cmd}.md").read_text(encoding="utf-8")
    assert ".claude/skills" not in text, (
        f"/cpp:{cmd} still references the retired global-skill mirror (.claude/skills)"
    )


# --------------------------------------------------------------------------- #
# Post-merge re-sync wiring (issue #506)
# --------------------------------------------------------------------------- #
# When a sibling PR that edits any `.claude/commands/<family>/*.md` merges to
# main, whoever merges main next inherits stale in-repo copies generated from
# that source and the parity gates fail. Two such surfaces exist: the packaged
# plugin copies (`plugin-sync.sh`) and the Codex skills (`codex-skill-sync.py`,
# #555). The /flow merge paths re-run BOTH in-repo generators (all 15 families,
# not just flow) - the out-of-repo flow-* skill mirror they once also re-synced
# was retired in B4 (#480), and the flat codex/prompts/ surface they targeted
# before was retired at the #556 cutover. These guard that the triggers are
# present and correctly shaped, so they are not silently dropped in a future
# edit - the gate that would have caught the original gap.
AUTO_CMD = SOURCE_COMMANDS / "flow" / "auto.md"
FINISH_CMD = SOURCE_COMMANDS / "flow" / "finish.md"

# The broad match must cover every family, NOT the flow-only pattern the retired
# skill mirror used - a flow-only grep would reproduce the exact #506 bug.
ALL_FAMILIES_PATTERN = r"grep -q '^\.claude/commands/.*\.md$'"

# Every in-repo generator that must be re-run in the post-merge re-sync path.
INREPO_GENERATORS = ["scripts/plugin-sync.sh --write", "scripts/codex-skill-sync.py --write"]


@pytest.mark.parametrize("cmd", [AUTO_CMD, FINISH_CMD], ids=["auto", "finish"])
def test_flow_merge_path_reruns_inrepo_generators(cmd: Path):
    text = cmd.read_text()
    for gen in INREPO_GENERATORS:
        assert gen in text, (
            f"{cmd.name} post-merge re-sync must re-run `{gen}` so the in-repo "
            f"generated copies do not drift (issue #506)"
        )
    # The re-sync must be gated on ALL families, not just flow.
    assert ALL_FAMILIES_PATTERN in text, (
        f"{cmd.name} re-sync must match all `.claude/commands/**/*.md`, not only "
        f"the flow-only pattern (that flow-only scope is the #506 bug)"
    )


def test_auto_step7_commits_generated_before_push():
    # Step 7 squashes straight after `git push` with no further commit step, so
    # the regenerated plugins/ + codex/skills/ MUST be committed there or the
    # squash carries stale copies onto main (the exact race #506 guards).
    text = AUTO_CMD.read_text()
    assert "git add plugins/ codex/skills/" in text, (
        "auto.md Step 7 must commit the re-synced plugins/ + codex/skills/ "
        "before `git push` - otherwise the squash lands stale copies (issue #506)"
    )
    push_idx = text.rfind('git push origin "$BRANCH"')
    add_idx = text.find("git add plugins/ codex/skills/")
    assert 0 <= add_idx < push_idx, (
        "the generated-surface commit must precede the Step-7 `git push`"
    )

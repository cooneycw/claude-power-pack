"""Regression tests for the plugin-marketplace scaffold + per-family plugins.

Phase B1 of the plugin-marketplace migration (ADR docs/decisions/
0001-plugin-marketplace-packaging.md, issue #477) stood up
`.claude-plugin/marketplace.json` and packaged the `flow` command family as an
installable plugin under `plugins/flow/`. Phase B2 (issue #478) extends that to
every surviving family. During the B1->B4 parallel window the source of truth
stays `.claude/commands/<family>/*.md` and each plugin holds byte-identical
copies kept honest by `scripts/plugin-sync.sh` (the B1 `plugin-flow-sync.sh` is
now a shim onto it).

The hazards these pin:
  * the manifests must stay schema-valid (name/source/required fields), because
    `/plugin install <family>@cpp` resolves the marketplace by its `name` field
    and the plugin by its `source` path;
  * the packaged commands must stay byte-identical to their source, or the two
    surfaces silently diverge before B4 collapses them;
  * the `cpp` plugin must stay help/meta-only (ADR 0001): packaging the legacy
    /cpp:init|update|status symlink installer into the surface that replaces it
    would ship the thing B4 retires.

Hermetic and git-free: reads the REAL repo manifests + command sources and shells
only to the git-free sync guard, so it runs in CI's git-less validate container
(see the cpp_validate_container_no_git learning).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = ROOT / "plugins"
SOURCE_COMMANDS = ROOT / ".claude" / "commands"
SYNC_SCRIPT = ROOT / "scripts" / "plugin-sync.sh"
SHIM_SCRIPT = ROOT / "scripts" / "plugin-flow-sync.sh"

# Every packaged family (ADR 0001 target design). `spec` and the loose
# top-level commands are deliberately NOT packaged - see the ADR B2 resolution.
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


def test_cpp_plugin_is_help_only():
    # ADR 0001: the cpp plugin carries cross-cutting help/meta only. The
    # init/update/status installer is the legacy surface B4 retires; it must
    # not ship through the plugin marketplace.
    packaged = {p.name for p in (PLUGINS_DIR / "cpp" / "commands").glob("*.md")}
    assert packaged == {"help.md"}, f"cpp plugin must ship help.md only, got {packaged}"


# --------------------------------------------------------------------------- #
# Drift guard
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("script", [SYNC_SCRIPT, SHIM_SCRIPT], ids=["sync", "flow-shim"])
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

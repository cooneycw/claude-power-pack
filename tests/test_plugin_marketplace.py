"""Regression tests for the plugin-marketplace scaffold + flow POC plugin (issue #477).

Phase B1 of the plugin-marketplace migration (ADR docs/decisions/
0001-plugin-marketplace-packaging.md) stands up `.claude-plugin/marketplace.json`
and packages the `flow` command family as an installable plugin under
`plugins/flow/`. During the B1->B4 parallel window the source of truth stays
`.claude/commands/flow/*.md` and the plugin holds byte-identical copies kept
honest by `scripts/plugin-flow-sync.sh`.

The hazards these pin:
  * the manifests must stay schema-valid (name/source/required fields), because
    `/plugin install flow@cpp` resolves the marketplace by its `name` field and
    the plugin by its `source` path;
  * the packaged commands must stay byte-identical to their source, or the two
    surfaces silently diverge before B4 collapses them.

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
PLUGIN_DIR = ROOT / "plugins" / "flow"
PLUGIN_MANIFEST = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
SOURCE_COMMANDS = ROOT / ".claude" / "commands" / "flow"
PLUGIN_COMMANDS = PLUGIN_DIR / "commands"
SYNC_SCRIPT = ROOT / "scripts" / "plugin-flow-sync.sh"


# --------------------------------------------------------------------------- #
# Marketplace manifest
# --------------------------------------------------------------------------- #
def test_marketplace_manifest_exists_and_is_json():
    assert MARKETPLACE.is_file(), f"missing {MARKETPLACE}"
    data = json.loads(MARKETPLACE.read_text())
    assert isinstance(data, dict)


def test_marketplace_name_is_cpp():
    # The install path is `/plugin install flow@cpp`; `cpp` is this field.
    data = json.loads(MARKETPLACE.read_text())
    assert data["name"] == "cpp"


def test_marketplace_lists_flow_plugin_by_relative_source():
    data = json.loads(MARKETPLACE.read_text())
    plugins = data.get("plugins")
    assert isinstance(plugins, list) and plugins, "marketplace lists no plugins"
    flow = next((p for p in plugins if p.get("name") == "flow"), None)
    assert flow is not None, "no `flow` plugin entry in marketplace.json"
    assert flow["source"] == "./plugins/flow"
    assert flow.get("description"), "flow plugin entry needs a description"


def test_marketplace_sources_resolve_to_plugin_manifests():
    # Every declared local source must point at a real plugin dir with a manifest.
    data = json.loads(MARKETPLACE.read_text())
    for entry in data["plugins"]:
        source = entry["source"]
        assert source.startswith("./"), f"expected relative source, got {source}"
        manifest = (ROOT / source / ".claude-plugin" / "plugin.json").resolve()
        assert manifest.is_file(), f"{entry['name']}: missing {manifest}"


# --------------------------------------------------------------------------- #
# Plugin manifest
# --------------------------------------------------------------------------- #
def test_plugin_manifest_required_fields():
    assert PLUGIN_MANIFEST.is_file(), f"missing {PLUGIN_MANIFEST}"
    data = json.loads(PLUGIN_MANIFEST.read_text())
    # `name` derives the command namespace (/flow:*); `description` is required.
    assert data["name"] == "flow"
    assert data.get("description")
    assert data.get("version"), "pin an explicit version so /plugin gates updates"


# --------------------------------------------------------------------------- #
# Command parity (byte-identical copies of the source of truth)
# --------------------------------------------------------------------------- #
def test_plugin_commands_are_byte_identical_to_source():
    source = {p.name: p for p in SOURCE_COMMANDS.glob("*.md")}
    packaged = {p.name: p for p in PLUGIN_COMMANDS.glob("*.md")}
    assert source, "no source flow commands found"
    # No missing and no orphaned commands.
    assert set(source) == set(packaged), (
        f"command set drift: missing={set(source) - set(packaged)}, "
        f"orphaned={set(packaged) - set(source)}"
    )
    for name, src in source.items():
        assert src.read_bytes() == packaged[name].read_bytes(), (
            f"{name} differs between source and plugin (run "
            f"scripts/plugin-flow-sync.sh --write)"
        )


# --------------------------------------------------------------------------- #
# Drift guard
# --------------------------------------------------------------------------- #
def test_sync_script_check_passes():
    if shutil.which("bash") is None:  # pragma: no cover - bash present in CI
        pytest.skip("bash unavailable")
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"plugin-flow-sync --check reported drift:\n{result.stdout}\n{result.stderr}"
    )

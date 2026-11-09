"""Independent installation choices preserve presets without inheriting tiers."""

import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lib.cicd.enrolment import installed_revision
from tests.test_cpp_install_receipt import run

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("capability_receipt", ROOT / "scripts/cpp-install-receipt.py")
assert SPEC and SPEC.loader
receipt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(receipt)

# Deliberately independent of the resolver's tables: this is the pre-R1 content
# contract, including the optional extras question offered after every preset.
PRESETS = [
    (1, ["commands", "extras"], ["commands", "stash-guard"]),
    (2, ["commands", "scripts", "extras"], ["commands", "stash-guard", "scripts", "permission-profile"]),
    (
        3,
        ["commands", "scripts", "mcp", "extras"],
        ["commands", "stash-guard", "scripts", "permission-profile", "uv", "second-opinion", "playwright", "tavily"],
    ),
    (
        4,
        ["commands", "scripts", "mcp", "cicd", "extras"],
        [
            "commands",
            "stash-guard",
            "scripts",
            "permission-profile",
            "uv",
            "second-opinion",
            "playwright",
            "tavily",
            "host-ci",
        ],
    ),
    (
        5,
        ["commands", "scripts", "mcp", "cicd", "codex", "extras"],
        [
            "commands",
            "stash-guard",
            "scripts",
            "permission-profile",
            "uv",
            "second-opinion",
            "playwright",
            "tavily",
            "host-ci",
            "codex-cli",
            "codex-doctor",
            "codex-auth",
            "codex-skills",
            "memory-harness",
        ],
    ),
    (6, ["commands", "qwen", "extras"], ["commands", "stash-guard", "qwen-cli", "qwen-model"]),
    (7, ["commands", "gemma", "extras"], ["commands", "stash-guard", "gemma-cli", "gemma-model", "gemma-provider"]),
]
OPTIONAL_CONTENTS = {
    "commands": {"project-commands"},
    "scripts": {
        "shell-prompt",
        "user-flow-allowlist",
        "permission-census",
        "session-reminders",
        "tmux-autostart",
        "happy-cli",
        "spec-kit-cli",
    },
    "mcp": {"browser-pool"},
    "cicd": set(),
    "codex": {"codex-second-opinion", "codex-playwright", "codex-tavily"},
    "qwen": {"qwen-endpoint", "qwen-smoke", "qwen-always-on"},
    "gemma": {"gemma-endpoint", "gemma-smoke"},
    "extras": {
        "sequential-thinking",
        "codex-second-opinion",
        "codex-playwright",
        "codex-tavily",
        "workstation-tuning",
        "memory-store",
        "memory-store-start",
        "memory-store-ping",
    },
}


@pytest.mark.parametrize("preset,capabilities,steps", PRESETS)
def test_presets_preserve_existing_contents(preset, capabilities, steps):
    plan = receipt.capability_plan(preset=preset)
    assert plan["capabilities"] == capabilities
    assert plan["required_steps"] == steps
    assert set(plan["allowed_steps"]) == set(steps).union(*(OPTIONAL_CONTENTS[cap] for cap in capabilities))


def test_codex_and_gemma_resolve_runtime_scripts_without_mcp_or_cicd():
    plan = receipt.capability_plan(["gemma", "codex"])
    assert plan["capabilities"] == ["commands", "scripts", "codex", "gemma"]
    assert plan["sections"] == ["commands", "scripts", "codex", "local-seam", "gemma"]
    assert "host-ci" not in plan["allowed_steps"]
    assert {"scripts", "permission-profile"} <= set(plan["required_steps"])
    assert "second-opinion" not in plan["allowed_steps"]


def test_two_local_models_share_one_seam_and_dependencies_are_idempotent():
    plan = receipt.capability_plan(["qwen", "gemma", "commands", "qwen"])
    assert plan["sections"] == ["commands", "local-seam", "qwen", "gemma"]


@pytest.mark.parametrize("requested", [[], ["tier-5"], ["codex", 7], "codex"])
def test_invalid_selection_fails_closed(requested):
    with pytest.raises(ValueError):
        receipt.capability_plan(requested)


def test_existing_schema_reader_does_not_tolerate_additive_selection():
    # A new schema is required: schema 1 binds capabilities to one integer tier
    # and rejects additional selection keys. Keep this compatibility fact tested.
    original = json.loads((ROOT / "tests/fixtures/cpp-install-receipt/legacy-generic-makefile.json").read_text())
    receipt.validate(original)
    original["selected"]["requested"] = ["codex", "gemma"]
    with pytest.raises(ValueError, match="selection"):
        receipt.validate(original)


def test_custom_receipt_records_selection_without_inheriting_host_ci(tmp_path):
    plan = receipt.capability_plan(["codex", "gemma"])
    outcomes = [{"step": step, "outcome": "already"} for step in plan["required_steps"]]
    result = run(tmp_path, "write", "--capabilities", '["codex","gemma"]', "--profile", "Standard", data=outcomes)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / ".claude/cpp-install.json").read_text())
    assert data["schema"] == 2
    assert data["selected"] == {
        "preset": None,
        "requested": ["codex", "gemma"],
        "capabilities": ["commands", "scripts", "codex", "gemma"],
        "profile": "Standard",
    }
    assert "host-ci" not in data["offered_steps"]
    assert run(tmp_path, "summary").returncode == 0
    data["selected"]["capabilities"].remove("commands")
    with pytest.raises(ValueError):
        receipt.validate(data)


@pytest.mark.parametrize("schema,expected", [(1, "a" * 40), (2, "a" * 40), (999, ""), (True, "")])
def test_revision_reader_accepts_known_receipt_versions_only(tmp_path, schema, expected):
    path = tmp_path / ".claude/cpp-install.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"schema": schema, "cpp_revision": "a" * 40}))
    assert installed_revision(tmp_path) == expected


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.parametrize(
    "section,code,written",
    [
        ("codex", 0, True),
        ("gemma", 0, True),
        ("cicd", 3, False),
        ("scripts", 0, True),
        ("local-seam", 0, True),
        ("typo", 1, False),
    ],
)
def test_actual_dispatch_does_not_execute_unselected_sections(tmp_path, section, code, written):
    target = tmp_path / "attempted"
    text = (ROOT / ".claude/commands/cpp/init.md").read_text()
    guard = re.search(r"# CPP_CAPABILITY_EXECUTION_GUARD_BEGIN\n(.*?)# CPP_CAPABILITY_EXECUTION_GUARD_END", text, re.S)[
        1
    ]
    guard = guard.replace("# CPP_CAPABILITY_BODY", f"printf attempted > '{target}'")
    result = subprocess.run(  # binary-guard: allow Python executable, bash guarded above
        ["bash", "-c", guard],
        env={**os.environ, "CPP_DIR": str(ROOT), "CPP_CAPABILITIES_JSON": '["codex","gemma"]', "CPP_SECTION": section},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == code, result.stdout + result.stderr
    assert target.exists() is written


def test_every_live_component_names_its_execution_guard():
    text = (ROOT / ".claude/commands/cpp/init.md").read_text()
    components = {
        "Commands": "commands",
        "Scripts": "scripts",
        "MCP": "mcp",
        "CI/CD": "cicd",
        "Codex": "codex",
        "Qwen": "qwen",
        "Gemma": "gemma",
    }
    for name, cap in components.items():
        section = text.split("### " + name + " Execution", 1)[1].split("```", 1)[0]
        assert f"Execution guard: `CPP_SECTION={cap}`." in section
    assert "Only IDs in the plan's `allowed_steps`" in text


COMPONENT_HEADINGS = {
    "### Commands Execution": "commands",
    "### Scripts Execution": "scripts",
    "### MCP Execution": "mcp",
    "### CI/CD Execution": "cicd",
    "### Codex Execution": "codex",
    "### Local-model host-write seam": "local-seam",
    "### Qwen Execution": "qwen",
    "### Gemma Execution": "gemma",
    "## Step 6: Optional Extras": "extras",
    "## Error Handling": None,
    "## Step 7:": None,
}


def assert_component_block_guards(text):
    selected = None
    examined = []
    for part in re.split(r"(^#{2,3} .*?$|```bash\n.*?```)", text, flags=re.M | re.S):
        if part.startswith("#"):
            for heading, capability in COMPONENT_HEADINGS.items():
                if part.startswith(heading):
                    selected = capability
                    break
        elif part.startswith("```bash\n") and selected:
            block = part.removeprefix("```bash\n").removesuffix("```")
            expected = (
                'python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \\\n'
                '  --capabilities "${CPP_CAPABILITIES_JSON-}" --section ' + selected + " || exit $?\n"
            )
            assert block.startswith(expected), f"{selected} block missing its first executable selection guard"
            examined.append(selected)
    assert examined, "must examine at least one component block"
    return examined


def test_every_component_bash_block_starts_with_its_own_guard():
    examined = assert_component_block_guards((ROOT / ".claude/commands/cpp/init.md").read_text())
    assert set(examined) == set(COMPONENT_HEADINGS.values()) - {None}


@pytest.mark.parametrize("name", ["missing-host-ci-guard.md", "missing-spec-kit-guard.md"])
def test_structural_scan_rejects_committed_guard_deletion(name):
    bad = (ROOT / "tests/fixtures/cpp-capability-guards" / name).read_text()
    with pytest.raises(AssertionError, match="missing its first executable selection guard"):
        assert_component_block_guards(bad)


def test_selection_errors_do_not_claim_revision_failure(tmp_path):
    result = run(tmp_path, "plan", "--capabilities", '["unknown"]')
    assert result.returncode == 1
    assert "CPP_INSTALL_SELECTION: invalid capability selection or section" in result.stdout
    assert "revision" not in result.stdout


def test_public_help_and_status_describe_selection_instead_of_a_level():
    for document in ("init.md", "help.md"):
        text = (ROOT / ".claude/commands/cpp" / document).read_text()
        rows = re.findall(r"^\| ([1-7]) \| [^|]+ \| ([a-z, ]+) \|$", text, re.M)
        assert len(rows) == 7, "every preset must have one visible capability row"
        assert {int(number): contents.split(", ") for number, contents in rows} == {
            number: capabilities for number, capabilities, _ in PRESETS
        }
    help_text = (ROOT / ".claude/commands/cpp/help.md").read_text()
    assert "Build system, health checks, pipelines, containers" not in help_text
    assert "commands and scripts" in help_text
    status = (ROOT / ".claude/commands/cpp/status.md").read_text()
    assert "Current tier level" not in status and "Current Level: Tier" not in status
    assert "Selected capabilities and preset" in status


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
def test_custom_codex_gemma_never_enters_actual_host_ci_procedure(tmp_path):
    text = (ROOT / ".claude/commands/cpp/init.md").read_text()
    # Execute the actual old procedure too, to demonstrate the pre-fix red.
    heading = "### CI/CD Execution" if "### CI/CD Execution" in text else "### Tier 4 Execution"
    end = "### Codex Execution" if "### Codex Execution" in text else "### Tier 5 Execution"
    region = text.split(heading, 1)[1].split(end, 1)[0]
    blocks = re.findall(r"```bash\n(.*?)```", region, re.S)
    assert blocks
    bins = tmp_path / "bin"
    bins.mkdir()
    marker = tmp_path / "uv-called"
    uv = bins / "uv"
    uv.write_text('#!/bin/sh\nprintf attempted > "$CPP_TEST_UV_MARKER"\nprintf "HOST_CI_RECORD: written\\n"\n')
    uv.chmod(0o755)
    result = subprocess.run(
        ["bash", "-c", "\n".join(blocks)],
        cwd=tmp_path,
        env={
            **os.environ,
            "CPP_DIR": str(ROOT),
            "CPP_CAPABILITIES_JSON": '["codex","gemma"]',
            "PATH": str(bins) + os.pathsep + os.environ["PATH"],
            "CPP_TEST_UV_MARKER": str(marker),
            "CPP_PROJECTS_ROOT": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert not marker.exists(), "unselected CI/CD must not even invoke uv preflight"
    assert result.returncode == 3, result.stdout + result.stderr

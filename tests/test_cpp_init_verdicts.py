"""Run the shipped wizard snippets with silent failures and successful steps."""

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_cpp_init_mcp_registration import initialize_mcp

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"
CASES = [
    ("**Project scope (optional, this project only):**", "✓ Commands symlinked"),
    ("**Permission Profile Configuration**", "✓ Permission profile configured"),
    # Retired Makefile writer: read-only handoff cases live in test_cpp_init_no_makefile.py.
    ("#### 5b. Run Codex Doctor", "[x] codex doctor: all checks passed"),
    ("#### 3c. Register MCP Servers", "✓ playwright MCP"),
    ("#### 3c. Register MCP Servers", "✓ tavily MCP"),
    ("#### 3d. Register the browser desk pool", "✓ playwright-desk-1 MCP registered"),
    ("#### 3d. Register the browser desk pool", "✓ Seeded .claude/playwright-pool.json"),
    ("#### 5d. Register MCP Servers with Codex", "✓ second-opinion MCP registered with Codex"),
    ("#### 5d. Register MCP Servers with Codex", "✓ playwright MCP registered with Codex"),
    ("### 8a. Sequential Thinking", "✓ sequential-thinking MCP registered"),
    ("### 8b. Codex MCP Registration", "✓ second-opinion MCP registered with Codex"),
    ("### 8b. Codex MCP Registration", "✓ playwright MCP registered with Codex"),
]


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.skipif(shutil.which("python3") is None, reason="requires python3")
@pytest.mark.skipif(any(shutil.which(name) is None for name in ("cp", "ln", "cat")), reason="requires cp, ln and cat")
@pytest.mark.parametrize(
    "heading,success,list_rc",
    [(h, s, 0) for h, s in CASES]
    + [(h, s, 19) for h, s in CASES if ("Register" in h or "### 8" in h or "3d." in h) and "Seeded" not in s],
)
@pytest.mark.parametrize("step_rc", [0, 19], ids=["success", "silent-failure"])
def test_step_verdict_follows_exit_status(tmp_path, heading, success, list_rc, step_rc):
    text = INIT.read_text()
    assert heading in text, f"missing wizard step: {heading}"
    block = re.search(r"```bash\n(.*?)```", text.split(heading, 1)[1], re.S)
    assert block, f"missing executable snippet: {heading}"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = """#!/bin/bash
case "$*" in
  'mcp list'*)
    if [ "$LIST_RC" = 0 ]; then printf '[]\\n'; fi
    exit "$LIST_RC" ;;
  'mcp add '*) printf 'called\n' >> "$CALL_LOG" ;;
esac
exit "$STEP_RC"
"""
    for name in ("codex", "claude", "uv", "cp", "ln", "cat"):
        target = bindir / name
        # Successful file operations create the artifacts the real snippet uses.
        operation = (
            f'if [ "$STEP_RC" = 0 ]; then exec {shlex.quote(shutil.which(name))} "$@"; fi\n'
            if name in ("cp", "ln", "cat")
            else ""
        )
        target.write_text(stub.replace('exit "$STEP_RC"', operation + 'exit "$STEP_RC"'))
        target.chmod(0o755)
    for name in ("npx", "curl"):
        target = bindir / name
        target.write_text("#!/bin/bash\nexit 0\n")
        target.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    (tmp_path / ".claude").mkdir()
    if "Seeded" not in success:
        (tmp_path / ".claude/playwright-pool.json").write_text('{"desks": ["playwright-desk-1"]}')
    # A stale output must not turn a failed generator into a successful verdict.
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text("# pre-existing workflow\n")
    env = dict(
        os.environ,
        HOME=str(home),
        CLAUDE_CONFIG_DIR=str(home),
        PATH=f"{bindir}:{os.environ['PATH']}",
        CPP_DIR=str(tmp_path / "empty-cpp") if success.endswith("with defaults") else str(ROOT),
        STEP_RC=str(step_rc),
        LIST_RC=str(list_rc),
        CALL_LOG=str(tmp_path / "add-calls"),
        TAVILY_API_KEY="fixture-only-placeholder",
    )
    # Pin the negative condition: the command itself fails without diagnostics.
    probe = subprocess.run([str(bindir / "codex"), "doctor"], env=env, capture_output=True, text=True, timeout=10)
    assert (probe.returncode, probe.stdout, probe.stderr) == (step_rc, "", "")
    env["CPP_MCP_RUN_DIR"] = initialize_mcp(tmp_path, env)
    result = subprocess.run(
        ["bash", "-c", block[1]], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=30,
    )
    output = result.stdout + result.stderr
    assert "syntax error" not in output, output
    assert (success in output) is (step_rc == 0 and list_rc == 0), output
    if list_rc:
        assert not (tmp_path / "add-calls").exists(), output
    if step_rc or list_rc:
        assert re.search(r"(?i)warning|failed|could not", output), output


def test_installation_summary_follows_extras_and_requires_observed_results():
    text = INIT.read_text()
    assert text.index("## Step 7: Installation Summary") > text.index("### 8d.")
    assert "{STEP_RESULTS}" in text
    assert "CPP Installation Complete!" not in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
def test_config_file_alone_does_not_prove_credentials(tmp_path):
    config = tmp_path / ".codex/config.toml"
    config.parent.mkdir()
    config.write_text("")
    assert config.exists() and not config.read_text(), "fixture has no credential configuration"
    text = INIT.read_text().split("#### 5c. Observe Codex Authentication Configuration", 1)[1]
    block = re.search(r"```bash\n(.*?)```", text, re.S)
    assert block
    result = subprocess.run(
        ["bash", "-c", "codex() { :; };\n" + block[1]],
        env=dict(os.environ, HOME=str(tmp_path), OPENAI_API_KEY=""),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert "API credentials unverified" in result.stdout
    assert "[x]" not in result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.skipif(shutil.which("env") is None, reason="requires env")
@pytest.mark.parametrize("step_rc,state", [(0, "written"), (1, "failed"), (127, "failed"),
                                          (3, "deferred"), (3, "unavailable"), (3, "unknown")])
def test_host_record_verdict_never_claims_persistence_without_a_receipt(tmp_path, step_rc, state):
    tier = INIT.read_text().split("### Tier 4 Execution", 1)[1].split("### Tier 5 Execution", 1)[0]
    blocks = [b for b in re.findall(r"```bash\n(.*?)```", tier, re.S) if "CPP_HOST_RUNTIME=" in b]
    assert len(blocks) == 1
    bindir = tmp_path / "bin"
    bindir.mkdir()
    uv = bindir / "uv"
    uv.write_text('#!/bin/bash\nprintf "HOST_CI_RECORD: %s\\n" "$RECORD_STATE"\nexit "$STEP_RC"\n')
    uv.chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", CPP_DIR=str(ROOT),
               CPP_PROJECTS_ROOT=str(tmp_path / "projects"), HOME=str(tmp_path / "home"),
               STEP_RC=str(step_rc), RECORD_STATE=state)
    probe = subprocess.run([str(uv)], env=env, capture_output=True, text=True, timeout=10)
    assert probe.returncode == step_rc and state in probe.stdout, "fixture must supply the exact write outcome"
    result = subprocess.run(["bash", "-c", blocks[0]], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    assert ("Host CI record persisted;" in output) is (step_rc == 0)
    assert ("previous record preserved" in output) is (step_rc in {1, 127})
    assert result.returncode == (1 if step_rc in {1, 127} else 0)
    if step_rc == 3:
        assert "unconfirmed" in output and "previous record preserved" not in output

"""Run the shipped wizard snippets with silent failures and successful steps."""

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"
CASES = [
    ("**Project scope (optional, this project only):**", "✓ Commands symlinked"),
    ("**Permission Profile Configuration**", "✓ Permission profile configured"),
    ("**Makefile Setup (Optional)**", "✓ Makefile created from template"),
    ("#### 5b. Run Codex Doctor", "[x] codex doctor: all checks passed"),
    ("#### 3c. Register MCP Servers", "✓ playwright MCP"),
    ("#### 3c. Register MCP Servers", "✓ tavily MCP"),
    ("#### 3d. Register the browser desk pool", "✓ playwright-desk-1 registered"),
    ("#### 3d. Register the browser desk pool", "✓ Seeded .claude/playwright-pool.json"),
    ("If no Makefile exists, offer to generate one:", "✓ Makefile generated"),
    ("#### 4b. Generate cicd.yml", "✓ .claude/cicd.yml created from template"),
    ("#### 4b. Generate cicd.yml", "✓ .claude/cicd.yml created with defaults"),
    ("#### 4d. CI Pipeline Generation", "✓ .github/workflows/ci.yml generated"),
    ("#### 4e. Container Generation", "✓ Container files generated"),
    ("#### 5d. Register MCP Servers with Codex", "Registered second-opinion with Codex"),
    ("#### 5d. Register MCP Servers with Codex", "Registered playwright (upstream"),
    ("### 8a. Sequential Thinking", "✓ Sequential Thinking MCP registered"),
    ("### 8b. Codex MCP Registration", "✓ second-opinion registered with Codex"),
    ("### 8b. Codex MCP Registration", "✓ playwright (upstream"),
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
  'mcp list') exit "$LIST_RC" ;;
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
    result = subprocess.run(["bash", "-c", block[1]], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
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
    text = INIT.read_text().split("#### 5c. Verify OpenAI API Key", 1)[1]
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

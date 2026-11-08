"""Exercise the canonical wizard registration definitions with owned fake CLIs."""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"
SHELL = pytest.mark.skipif(any(shutil.which(x) is None for x in ("bash", "python3")), reason="requires bash and python3")


def definitions(text=None):
    text = INIT.read_text() if text is None else text
    match = re.search(r"# CPP_MCP_ROUTINES_BEGIN\n(.*?)# CPP_MCP_ROUTINES_END", text, re.S)
    return match[1] if match else ""


def block(heading):
    return re.search(r"```bash\n(.*?)```", INIT.read_text().split(heading, 1)[1], re.S)[1]


def literal_adds(text):
    """Census literal client/add commands in executable Bash fences only."""
    active = False
    found = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            active = line.strip() in {"```bash", "```sh"}
            continue
        if not active:
            continue
        try:
            args = shlex.split(line, comments=True)
        except ValueError:
            continue  # continued commands are pinned separately below
        for i in range(len(args) - 2):
            if args[i] in {"claude", "codex"} and args[i + 1:i + 3] == ["mcp", "add"]:
                found.append(args[i])
    return found


def test_one_registration_definition_per_client():
    text = INIT.read_text()
    assert sorted(literal_adds(text)) == ["claude", "codex"]
    for client in ("claude", "codex"):
        assert text.count(f"cpp_register_{client}_mcp() {{") == 1
        assert literal_adds("```bash\n" + definitions(text) + "\n```").count(client) == 1


def fake_environment(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    log = tmp_path / "calls.jsonl"
    cli = "#!" + sys.executable + "\n" + r'''import json, os, pathlib, sys
client = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["MCP_CALL_LOG"], "a") as f:
    f.write(json.dumps([client, *args]) + "\n")
if args[:2] == ["mcp", "list"]:
    print(os.environ.get("CODEX_LIST_JSON", "[]") if client == "codex" and "--json" in args else "")
    sys.exit(int(os.environ.get("LIST_RC", "0")))
if args[:2] == ["mcp", "add"]:
    sys.exit(int(os.environ.get("ADD_RC", "0")))
sys.exit(0)
'''
    for name in ("claude", "codex"):
        path = bindir / name
        path.write_text(cli)
        path.chmod(0o755)
    for name in ("npx", "curl"):
        path = bindir / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    env = dict(os.environ, HOME=str(home), CLAUDE_CONFIG_DIR=str(home), CODEX_HOME=str(home / ".codex"),
               PATH=f"{bindir}:{os.environ['PATH']}", MCP_CALL_LOG=str(log), CPP_DIR=str(ROOT),
               SECOND_OPINION_URL="http://fixture-server.invalid:9123", TAVILY_API_KEY="fixture-only-placeholder")
    for key in ("LIST_RC", "ADD_RC", "CODEX_LIST_JSON"):
        env.pop(key, None)
    return env, log


def run(tmp_path, code, **changes):
    env, log = fake_environment(tmp_path)
    env.update(changes)
    result = subprocess.run(["bash", "-c", definitions() + "\n" + code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=20)
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


@SHELL
@pytest.mark.parametrize("heading", ["#### 5d. Register MCP Servers with Codex", "### 8b. Codex MCP Registration"])
def test_codex_entrypoint_honors_second_opinion_url(tmp_path, heading):
    result, calls = run(tmp_path, block(heading))
    assert result.returncode == 0, result.stdout + result.stderr
    adds = [c for c in calls if c[:3] == ["codex", "mcp", "add"] and "second-opinion" in c]
    assert adds == [["codex", "mcp", "add", "second-opinion", "--url", "http://fixture-server.invalid:9123/mcp"]]

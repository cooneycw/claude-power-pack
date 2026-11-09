"""Execute Tier 4's published procedure against bounded local tool stubs."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"
requires_tools = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("bash", "python3", "env", "cp", "mkdir")),
    reason="requires bash, python3, env, cp and mkdir",
)


def _tier4():
    text = INIT.read_text().split("### CI/CD Execution", 1)[1].split("### Codex Execution", 1)[0]
    blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
    assert blocks, "Tier 4 has no executable procedure"
    return "\n".join(blocks)


def _files(root):
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None for path in root.rglob("*")}


@requires_tools
def test_tier4_writes_only_the_approved_host_record(tmp_path):
    repo = tmp_path / "projects/project"
    repo.mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="0.0.0"\n')
    before = _files(repo)
    cpp = tmp_path / "cpp"
    (cpp / "scripts").mkdir(parents=True)
    (cpp / "scripts/cpp-install-receipt.py").write_bytes((ROOT / "scripts/cpp-install-receipt.py").read_bytes())
    (cpp / "templates").mkdir()
    (cpp / "templates/cicd.yml.example").write_text("build:\n  framework: python\n")
    (cpp / "scripts/flow-preflight.sh").write_text('#!/bin/bash\nprintf \'{}\\n\'\nexit 0\n')
    bindir = tmp_path / "bin"
    bindir.mkdir()
    uv = bindir / "uv"
    uv.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
cwd = pathlib.Path.cwd()
if 'host-ci' in args:
    for key in ('UV_PROJECT_ENVIRONMENT', 'UV_CACHE_DIR'):
        assert not pathlib.Path(os.environ[key]).resolve().is_relative_to(cwd)
    assert os.environ['PYTHONDONTWRITEBYTECODE'] == '1'
    assert os.environ['UV_LOCKED'] == '1'
    root = pathlib.Path(args[args.index('--projects-root') + 1])
    target = root / '.claude/cpp-host.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'schema': 1, 'providers': {}}))
    print('HOST_CI_RECORD: written')
elif 'detect' in args:
    if '--generate-makefile' in args:
        (cwd / 'Makefile').write_text('test:\\n\\t@true\\n')
    else:
        print(json.dumps({'framework': 'python', 'package_manager': 'uv'}))
elif 'pipeline' in args:
    target = cwd / '.github/workflows/ci.yml'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('name: CI\\n')
elif 'container' in args:
    (cwd / 'Dockerfile').write_text('FROM scratch\\n')
''')
    uv.chmod(0o755)
    result = subprocess.run(
        ["bash", "-c", _tier4()], cwd=repo,
        env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "CPP_DIR": str(cpp),
            "CPP_CAPABILITIES_JSON": '["cicd"]',
             "CPP_PROJECTS_ROOT": str(tmp_path / "projects"), "PYTHONPATH": ""},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert _files(repo) == before, f"Tier 4 changed its invoked project: {set(_files(repo)) - set(before)}"
    assert (tmp_path / "projects/.claude/cpp-host.json").is_file()

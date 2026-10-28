"""Install only the local tiers into scratch homes, without Tier 2."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"
BOOTSTRAP = "### Local-model host-write seam (Tiers 6/7 only)"


def snippets(text, start, end):
    section = text.split(start, 1)[1].split(end, 1)[0]
    return re.findall(r"```bash\n(.*?)```", section, re.S)


def local_script(kind):
    text = INIT.read_text()
    # On pre-fix main there is no local-tier bootstrap. Execute the actual
    # configuration snippets there too, so missing files make the regression red.
    bootstrap = snippets(text, BOOTSTRAP, "### Tier 6 Execution")[0] if BOOTSTRAP in text else ""
    if kind == "qwen":
        blocks = snippets(text, "#### 6c. Remote Access", "#### 6d.")[:2]
    elif kind == "gemma":
        blocks = snippets(text, "#### 7b.1 Persist", "#### 7c.")[:2]
    else:
        blocks = snippets(text, "#### 7c. Install", "#### 7d.")[:1]
    return bootstrap + "\n" + "\n".join(blocks)


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.skipif(shutil.which("python3") is None, reason="requires python3")
@pytest.mark.parametrize(
    "kind,shell", [("qwen", "bash"), ("qwen", "zsh"), ("gemma", "bash"), ("gemma", "zsh"), ("fence", "bash")]
)
def test_fresh_local_tier_writes_without_tier2(tmp_path, kind, shell):
    home = tmp_path / "home"
    home.mkdir()
    seam = home / ".claude/scripts/cpp-host-write.sh"
    assert not seam.exists() and not seam.is_symlink(), "fresh local tier has no Tier 2 helper"
    config = home / ".config/opencode/opencode.json"
    if kind == "fence":
        config.parent.mkdir(parents=True)
        config.write_text('{"provider":{"mine":{"keep":true}},"agent":{"mine":{"keep":true}}}')
    env = dict(
        os.environ,
        HOME=str(home),
        SHELL=f"/bin/{shell}",
        CPP_DIR=str(ROOT),
        CPP_DEFER_SURFACES="",
        QWEN_ENDPOINT="http://model.invalid:11434",
        GEMMA_ENDPOINT="http://model.invalid:11434",
    )
    script = local_script(kind)
    for _ in range(2):
        result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
        assert seam.is_symlink() and seam.resolve() == ROOT / "scripts/cpp-host-write.sh", result.stdout + result.stderr
        assert {p.name for p in seam.parent.iterdir()} == {"cpp-host-write.sh"}, "do not install all Tier 2 helpers"
        if kind == "fence":
            data = json.loads(config.read_text())
            assert data["provider"]["mine"] == {"keep": True}
            assert data["agent"]["mine"] == {"keep": True}
            permission = data["agent"]["gemma-implementer"]["permission"]
            assert permission["bash"]["gh *"] == "deny"
            assert permission["external_directory"] == "deny"
            assert "gemma-ollama" in data["provider"]
        else:
            rc = home / (".zshrc" if shell == "zsh" else ".bashrc")
            assert rc.read_text().count(f"export {kind.upper()}_OLLAMA_URL=http://model.invalid:11434") == 1


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.skipif(shutil.which("python3") is None, reason="requires python3")
@pytest.mark.parametrize(
    "population,expected", [("deferred", 3), ("broken", 1), ("non-executable", 1), ("parent-is-file", 1)]
)
def test_unavailable_local_seam_refuses_before_configuration(tmp_path, population, expected):
    home = tmp_path / "home"
    home.mkdir()
    seam = home / ".claude/scripts/cpp-host-write.sh"
    if population == "parent-is-file":
        (home / ".claude").write_text("owned parent\n")
        assert (home / ".claude").is_file(), "a parent file prevents helper installation even under root"
    elif population != "deferred":
        seam.parent.mkdir(parents=True)
        if population == "broken":
            seam.symlink_to(home / "absent-helper")
            assert seam.is_symlink() and not seam.exists()
        else:
            seam.write_text("owned content\n")
            seam.chmod(0o644)
            assert seam.is_file() and not os.access(seam, os.X_OK)
    else:
        assert not seam.exists() and not seam.is_symlink()
    env = dict(
        os.environ,
        HOME=str(home),
        CPP_DIR=str(ROOT),
        CPP_DEFER_SURFACES="~/.claude/scripts" if population == "deferred" else "",
    )
    result = subprocess.run(["bash", "-c", local_script("fence")], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == expected, result.stdout + result.stderr
    assert "local-model host-write seam" in result.stdout.lower()
    assert not (home / ".config/opencode/opencode.json").exists()
    if population == "deferred":
        assert not seam.exists() and not seam.is_symlink()
    elif population == "non-executable":
        assert seam.read_text() == "owned content\n"
    elif population == "parent-is-file":
        assert (home / ".claude").read_text() == "owned parent\n"

"""Real legacy helper and maintained fences preserve personal collisions."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/cpp-host-write.sh"
pytestmark = [pytest.mark.skipif(not shutil.which("bash"), reason="bash required"),
              pytest.mark.skipif(not shutil.which("python3"), reason="python3 required by host helper")]


def inventory(root):
    rows = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            info = path.lstat()
            rows[str(path.relative_to(root))] = (
                ("link", os.readlink(path)) if path.is_symlink() else
                ("dir",) if path.is_dir() else
                ("file", path.read_bytes()) if path.is_file() else ("special", info.st_mode))
    return rows


def run(gate, source, directory, name, home):
    env = dict(os.environ, HOME=str(home), CPP_DEFER_SURFACES="")
    return subprocess.run(["bash", str(gate), "link-into", str(source), str(directory), name],
                          env=env, capture_output=True, text=True, timeout=15)


@pytest.mark.parametrize("kind", ["regular", "directory", "fifo"])
def test_existing_non_symlink_preserved_and_refused(tmp_path, kind):
    source = tmp_path / "source.sh"
    source.write_bytes(b"CPP source")
    source.chmod(0o755)
    home = tmp_path / "home"
    directory = home / ".claude/scripts"
    directory.mkdir(parents=True)
    leaf = directory / "source.sh"
    if kind == "regular":
        leaf.write_bytes(b"personal irreplaceable bytes")
        leaf.chmod(0o755)
        assert leaf.is_file() and not leaf.is_symlink()
    elif kind == "directory":
        leaf.mkdir()
        (leaf / "personal").write_bytes(b"personal nested bytes")
        assert leaf.is_dir() and not leaf.is_symlink()
    else:
        import stat
        os.mkfifo(leaf)
        assert stat.S_ISFIFO(leaf.lstat().st_mode) and not leaf.is_symlink()
    before = inventory(home)
    result = run(GATE, source, directory, leaf.name, home)
    assert result.returncode == 1 and "PRESERVED" in result.stderr, result.stdout + result.stderr
    assert inventory(home) == before


@pytest.mark.parametrize("population", ["absent", "cpp-link", "foreign-link", "dangling-link"])
def test_absent_or_existing_link_behavior_is_retained(tmp_path, population):
    source = tmp_path / "source.sh"
    source.write_bytes(b"CPP A")
    home = tmp_path / "home"
    home.mkdir()
    directory = home / ".claude/scripts"
    leaf = directory / "source.sh"
    if population != "absent":
        directory.mkdir(parents=True)
        target = source if population == "cpp-link" else tmp_path / "personal"
        if population == "foreign-link":
            target.write_bytes(b"personal link content")
        leaf.symlink_to(target)
        assert leaf.is_symlink()
        if population == "dangling-link":
            assert not leaf.exists()
        before = inventory(home)
    else:
        assert not directory.exists()
    source.write_bytes(b"CPP B")
    result = run(GATE, source, directory, leaf.name, home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert leaf.is_symlink()
    if population == "absent":
        assert leaf.readlink() == source
    else:
        assert inventory(home) == before
    if population in ("absent", "cpp-link"):
        assert leaf.read_bytes() == b"CPP B"


def fences(command):
    text = (ROOT / f".claude/commands/cpp/{command}.md").read_text()
    blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
    if command == "init":
        return next(block for block in blocks if "# BOOTSTRAP THE SEAM" in block and "SEAM_OK=0" in block)
    bootstrap = next(block for block in blocks if 'SEAM_STATUS="not installed (Tier 0/1' in block)
    loop = next(block for block in blocks if "SEAM_OK=0" in block and 'for script in "$CPP_DIR"/scripts/*' in block)
    return bootstrap + "\n" + loop


@pytest.mark.parametrize("command", ["init", "update"])
def test_actual_callers_preserve_and_never_execute_personal_seam(tmp_path, command):
    home = tmp_path / "home"
    seam = home / ".claude/scripts/cpp-host-write.sh"
    seam.parent.mkdir(parents=True)
    sentinel = home / "PERSONAL_SEAM_EXECUTED"
    content = b'#!/bin/sh\nprintf EXECUTED > "$HOME/PERSONAL_SEAM_EXECUTED"\nexit 0\n'
    seam.write_bytes(content)
    seam.chmod(0o755)
    assert seam.is_file() and not seam.is_symlink() and os.access(seam, os.X_OK)
    assert not sentinel.exists()
    env = dict(os.environ, HOME=str(home), CPP_DIR=str(ROOT), CPP_DEFER_SURFACES="",
               CPP_CAPABILITIES_JSON='["commands","scripts"]')
    result = subprocess.run(["bash", "-c", fences(command)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=60)
    assert not sentinel.exists(), "preserved personal seam was executed as trusted CPP code"
    assert seam.is_file() and not seam.is_symlink() and seam.read_bytes() == content
    assert "PRESERVED" in result.stderr and "UNAVAILABLE" in result.stdout
    assert "failed" in result.stdout and "preserv" in result.stdout.lower()


@pytest.mark.parametrize("kind", ["regular", "directory"])
def test_racing_destination_is_preserved_exclusively(tmp_path, kind):
    import shlex

    source = tmp_path / "source.sh"
    source.write_bytes(b"CPP source")
    home = tmp_path / "home"
    directory = home / ".claude/scripts"
    leaf = directory / "source.sh"
    tools = tmp_path / "tools"
    tools.mkdir()
    real_python = shutil.which("python3")
    assert real_python is not None
    shim = tools / "python3"
    collision = ('mkdir "$3"; printf personal > "$3/personal"' if kind == "directory"
                 else 'printf personal > "$3"')
    shim.write_text("#!/bin/sh\n" + collision + "\nexec " + shlex.quote(real_python) + ' "$@"\n')
    shim.chmod(0o755)
    env = dict(os.environ, HOME=str(home), CPP_DEFER_SURFACES="", PATH=str(tools) + os.pathsep + os.environ["PATH"])
    assert shutil.which("python3", path=env["PATH"]) == str(shim)
    assert not leaf.exists() and not leaf.is_symlink()
    result = subprocess.run(["bash", str(GATE), "link-into", str(source), str(directory), leaf.name],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and "PRESERVED" in result.stderr
    assert not leaf.is_symlink()
    if kind == "regular":
        assert leaf.read_bytes() == b"personal"
    else:
        assert leaf.is_dir() and {p.name for p in leaf.iterdir()} == {"personal"}
        assert (leaf / "personal").read_bytes() == b"personal"

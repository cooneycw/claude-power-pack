"""R3: host setup hands off project Makefiles without creating or changing one."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lib.cicd.detector import detect_framework

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"
RECEIPT = ROOT / "scripts" / "cpp-install-receipt.py"
LEGACY = ROOT / "tests/fixtures/cpp-install-receipt/legacy-generic-makefile.json"


def makefile_block(text=None):
    text = INIT.read_text() if text is None else text
    # Read the real pre-fix writer until retirement; no invented replacement.
    heading = ("**Project Makefile Handoff**" if "**Project Makefile Handoff**" in text
               else "**Makefile Setup (Optional)**")
    section = text.split(heading, 1)[1].split("**Happy CLI Installation (Optional)**", 1)[0]
    block = re.search(r"```bash\n(.*?)```", section, re.S)
    assert block and block[1].strip(), "must exercise the actual writer/handoff"
    return block[1]


def snapshot(project):
    return {str(p.relative_to(project)): (p.lstat().st_mode,
            os.readlink(p) if p.is_symlink() else None if p.is_dir() else p.read_bytes())
            for p in project.rglob("*")}


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("cp") is None,
                    reason="requires bash/cp for pre-fix case")
@pytest.mark.parametrize("framework", ["django", "node"])
@pytest.mark.parametrize("entry", ["absent", "file", "symlink", "dangling", "directory"])
def test_host_setup_never_creates_or_changes_a_project_makefile(tmp_path, framework, entry):
    if framework == "django":
        (tmp_path / "manage.py").write_text("# owned Django marker\n")
        (tmp_path / "requirements.txt").write_text("Django>=5\n")
    else:
        (tmp_path / "package.json").write_text('{"name":"fixture","scripts":{"test":"node --test"}}')
        (tmp_path / "package-lock.json").write_text("{}")
    assert detect_framework(tmp_path).framework.value == framework, "fixture must represent the named framework"
    target = tmp_path / "Makefile"
    if entry == "file":
        target.write_bytes(b"# owner Makefile\ncustom:\n\t@echo preserve\n")
        target.chmod(0o640)
    elif entry == "directory":
        target.mkdir(mode=0o750)
        (target / "owner.txt").write_text("preserve directory content")
    elif entry in {"symlink", "dangling"}:
        owner = tmp_path / "owner.mk"
        if entry == "symlink":
            owner.write_bytes(b"# owner target\n")
        else:
            assert not owner.exists(), "fixture must have a dangling target"
        target.symlink_to(owner.name)
        assert target.is_symlink()
    else:
        assert not target.exists() and not target.is_symlink(), "fixture must start without Makefile"
    before = snapshot(tmp_path)
    result = subprocess.run(["bash", "-c", makefile_block()], cwd=tmp_path,
                            env=dict(os.environ, CPP_DIR=str(ROOT)), capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot(tmp_path) == before, "cpp:init must leave project files, modes and symlink entries untouched"


def test_handoff_names_both_project_commands():
    code = makefile_block()
    assert "/project:init" in code and "/cicd:init" in code


def test_no_generic_makefile_offer_or_new_run_step_remains():
    text = INIT.read_text()
    for retired in ("Makefile.example", "Create a starter Makefile?", "[Tier 2 - Makefile]", "generic-makefile"):
        assert retired not in text
    assert "**Project Makefile Handoff**" in text


def test_legacy_receipt_reads_unchanged(tmp_path):  # binary-guard: allow explicit --revision bypasses git
    legacy = json.loads(LEGACY.read_text())
    assert legacy["schema"] == 1
    assert any(row["step"] == "generic-makefile" and row["outcome"] == "installed" for row in legacy["steps"])
    path = tmp_path / ".claude/cpp-install.json"
    path.parent.mkdir()
    path.write_bytes(LEGACY.read_bytes())
    before = path.read_bytes()
    for command in ("status", "summary"):
        result = subprocess.run([sys.executable, str(RECEIPT), command, "--project-dir", str(tmp_path),
                                 "--revision", legacy["cpp_revision"]], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stdout + result.stderr
        if command == "summary":
            assert "generic-makefile: installed" in result.stdout
        else:
            assert "receipt complete" in result.stdout
        assert path.read_bytes() == before


def assert_only_handoff_mentions_makefile(text):
    blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
    relevant = [block for block in blocks if re.search(r"\bMakefile\b", block)]
    assert relevant == [makefile_block(text)], "another executable Makefile reference needs examination"


def test_executable_makefile_population_is_only_the_readonly_handoff():
    assert_only_handoff_mentions_makefile(INIT.read_text())


def test_the_makefile_population_check_rejects_a_restored_writer():
    good = INIT.read_text()
    restored = '\n```bash\ncp "$CPP_DIR/templates/Makefile.example" Makefile\n```\n'
    assert 'cp "$CPP_DIR/templates/Makefile.example" Makefile' in restored
    with pytest.raises(AssertionError, match="another executable Makefile"):
        assert_only_handoff_mentions_makefile(good + restored)
    assert_only_handoff_mentions_makefile(good)

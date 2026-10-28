"""scripts/codex-global-agents.py - Codex's global instructions built from Claude's (issue #1441).

Every case runs against a sandboxed HOME under tmp_path, never the real one.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "codex-global-agents.py"

SOURCE = "# Global directives\n\n## Nit Store\n\n- One finding per comment.\n"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("CODEX_HOME", None)
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False, env=env)


def verdict(proc: subprocess.CompletedProcess[str], key: str = "CODEX_GLOBAL_AGENTS") -> str:
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(f"{key}: ")]
    assert len(lines) == 1, proc.stdout
    return lines[0].split(": ", 1)[1]


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "CLAUDE.md").write_text(SOURCE, encoding="utf-8")
    (tmp_path / ".codex").mkdir()
    return tmp_path


def agents(home: Path) -> Path:
    return home / ".codex" / "AGENTS.md"


def test_a_freshly_built_file_is_current(home: Path) -> None:
    assert verdict(run("--write", "--home", str(home)), "CODEX_GLOBAL_AGENTS_WRITE") == "wrote"
    proc = run("--home", str(home))
    assert (verdict(proc), proc.returncode) == ("current", 0)
    assert SOURCE.rstrip("\n") in agents(home).read_text(encoding="utf-8")


def test_a_rule_added_to_claude_md_makes_it_stale(home: Path) -> None:
    run("--write", "--home", str(home))
    claude = home / ".claude" / "CLAUDE.md"
    claude.write_text(SOURCE + "\n## Negative Control\n\n- Name the red case.\n", encoding="utf-8")
    proc = run("--home", str(home))
    assert (verdict(proc), proc.returncode) == ("stale", 3)


def test_a_changed_additions_file_makes_it_stale(home: Path) -> None:
    run("--write", "--home", str(home))
    (home / ".codex" / "AGENTS.local.md").write_text("- Codex-only rule.\n", encoding="utf-8")
    assert verdict(run("--home", str(home))) == "stale"


def test_a_hand_edit_is_reported_even_when_the_source_also_moved(home: Path) -> None:
    run("--write", "--home", str(home))
    with agents(home).open("a", encoding="utf-8") as handle:
        handle.write("- sneaked in by hand\n")
    (home / ".claude" / "CLAUDE.md").write_text(SOURCE + "- more\n", encoding="utf-8")
    proc = run("--home", str(home))
    assert (verdict(proc), proc.returncode) == ("hand-edited", 3)


def test_a_hand_written_file_is_unmanaged_and_write_refuses_it(home: Path) -> None:
    original = "# Global working preferences\n\n- Group related findings.\n"
    agents(home).write_text(original, encoding="utf-8")
    assert verdict(run("--home", str(home))) == "unmanaged"
    proc = run("--write", "--home", str(home))
    assert (verdict(proc, "CODEX_GLOBAL_AGENTS_WRITE"), proc.returncode) == ("refused", 3)
    assert agents(home).read_text(encoding="utf-8") == original


def test_adopt_backs_up_the_hand_written_file_then_replaces_it(home: Path) -> None:
    original = "# Global working preferences\n"
    agents(home).write_text(original, encoding="utf-8")
    proc = run("--write", "--adopt", "--home", str(home))
    assert verdict(proc, "CODEX_GLOBAL_AGENTS_WRITE") == "wrote"
    backups = list((home / ".codex").glob("AGENTS.md.pre-cpp-*"))
    assert [b.read_text(encoding="utf-8") for b in backups] == [original]
    assert verdict(run("--home", str(home))) == "current"


def test_write_refuses_a_hand_edited_file_without_adopt(home: Path) -> None:
    run("--write", "--home", str(home))
    with agents(home).open("a", encoding="utf-8") as handle:
        handle.write("- edit\n")
    edited = agents(home).read_text(encoding="utf-8")
    assert verdict(run("--write", "--home", str(home)), "CODEX_GLOBAL_AGENTS_WRITE") == "refused"
    assert agents(home).read_text(encoding="utf-8") == edited


def test_additions_are_appended_under_their_own_heading(home: Path) -> None:
    (home / ".codex" / "AGENTS.local.md").write_text("- Post routine nits without asking.\n", encoding="utf-8")
    run("--write", "--home", str(home))
    text = agents(home).read_text(encoding="utf-8")
    assert text.index(SOURCE.rstrip("\n")) < text.index("## Codex-only additions") < text.index("Post routine nits")


def test_rebuilding_is_byte_identical(home: Path) -> None:
    run("--write", "--home", str(home))
    first = agents(home).read_bytes()
    assert verdict(run("--write", "--home", str(home)), "CODEX_GLOBAL_AGENTS_WRITE") == "unchanged"
    assert agents(home).read_bytes() == first


def test_absent_and_not_applicable_are_different_facts(home: Path, tmp_path: Path) -> None:
    proc = run("--home", str(home))
    assert (verdict(proc), proc.returncode) == ("absent", 3)
    (home / ".codex").rmdir()
    proc = run("--home", str(home))
    assert (verdict(proc), proc.returncode) == ("not-applicable", 5)
    assert verdict(run("--write", "--home", str(home)), "CODEX_GLOBAL_AGENTS_WRITE") == "not-applicable"
    assert not (home / ".codex").exists()


def test_an_unreadable_source_is_unknown_never_current(home: Path) -> None:
    run("--write", "--home", str(home))
    (home / ".claude" / "CLAUDE.md").unlink()
    proc = run("--home", str(home))
    assert (verdict(proc), proc.returncode) == ("unknown", 4)
    assert verdict(run("--write", "--home", str(home)), "CODEX_GLOBAL_AGENTS_WRITE") == "unknown"


def test_a_workspace_agents_md_is_listed_and_does_not_change_the_verdict(home: Path) -> None:
    run("--write", "--home", str(home))
    projects = home / "Projects"
    projects.mkdir()
    proc = run("--home", str(home))
    assert "WORKSPACE_AGENTS_MD" not in proc.stdout
    (projects / "AGENTS.md").write_text("- workspace rule\n", encoding="utf-8")
    proc = run("--home", str(home))
    assert f"WORKSPACE_AGENTS_MD: {projects / 'AGENTS.md'}" in proc.stdout
    assert verdict(proc) == "current"
    (projects / ".git").mkdir()
    assert "WORKSPACE_AGENTS_MD" not in run("--home", str(home)).stdout


def test_quiet_prints_only_the_verdict(home: Path) -> None:
    proc = run("--home", str(home), "--quiet")
    assert proc.stdout == "CODEX_GLOBAL_AGENTS: absent\n"


def test_an_unreadable_additions_file_is_unknown_and_never_dropped(home: Path) -> None:
    extras = home / ".codex" / "AGENTS.local.md"
    extras.write_text("- Codex-only rule.\n", encoding="utf-8")
    run("--write", "--home", str(home))
    built = agents(home).read_bytes()
    extras.write_bytes(b"\xff\xfe not utf-8\n")
    proc = run("--home", str(home))
    assert (verdict(proc), proc.returncode) == ("unknown", 4)
    proc = run("--write", "--home", str(home))
    assert (verdict(proc, "CODEX_GLOBAL_AGENTS_WRITE"), proc.returncode) == ("unknown", 4)
    assert agents(home).read_bytes() == built


@pytest.mark.parametrize(("adopt", "adopted"), [(None, False), ("0", False), ("1", True)])
def test_make_adopts_only_for_adopt_1(adopt: str | None, adopted: bool) -> None:
    args = ["make", "-n", "-C", str(ROOT), "codex-global-agents"] + ([f"ADOPT={adopt}"] if adopt else [])
    if shutil.which("make") is None:
        pytest.skip("make not installed")
    recipe = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    assert "codex-global-agents.py --write" in recipe
    assert ("--adopt" in recipe) is adopted


def test_status_relays_workspace_files_even_when_current(home: Path) -> None:
    if shutil.which("bash") is None:
        pytest.skip("bash not installed")
    status = (ROOT / ".claude" / "commands" / "cpp" / "status.md").read_text(encoding="utf-8")
    start = status.index("# Codex's global instructions vs Claude's")
    block = status[start : status.index("\nfi\n", start) + 4]
    run("--write", "--home", str(home))
    (home / "Projects").mkdir()
    (home / "Projects" / "AGENTS.md").write_text("- workspace rule\n", encoding="utf-8")
    out = subprocess.run(
        ["bash", "-c", block],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": os.environ["PATH"], "HOME": str(home), "CPP_DIR": str(ROOT)},
    ).stdout
    assert "[x] ~/.codex/AGENTS.md: current" in out
    assert "WORKSPACE_AGENTS_MD:" in out


def test_a_dangling_additions_symlink_is_unknown_and_never_dropped(home: Path) -> None:
    extras = home / ".codex" / "AGENTS.local.md"
    real = home / "dotfiles-AGENTS.local.md"
    real.write_text("- Codex-only rule.\n", encoding="utf-8")
    extras.symlink_to(real)
    run("--write", "--home", str(home))
    built = agents(home).read_bytes()
    real.unlink()
    assert verdict(run("--home", str(home))) == "unknown"
    assert verdict(run("--write", "--home", str(home)), "CODEX_GLOBAL_AGENTS_WRITE") == "unknown"
    assert agents(home).read_bytes() == built


def test_a_non_empty_override_makes_a_fresh_file_overridden(home: Path) -> None:
    run("--write", "--home", str(home))
    override = home / ".codex" / "AGENTS.override.md"
    override.write_text("", encoding="utf-8")
    assert verdict(run("--home", str(home))) == "current"
    override.write_text("- Group related findings.\n", encoding="utf-8")
    proc = run("--home", str(home))
    assert (verdict(proc), proc.returncode) == ("overridden", 3)
    assert "underlying AGENTS.md: current" in proc.stdout


def test_two_adoptions_in_one_second_keep_both_backups(home: Path) -> None:
    spec = importlib.util.spec_from_file_location("codex_global_agents", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = agents(home)
    first = module.write_backup(target, "first\n")
    second = module.write_backup(target, "second\n")
    assert first != second
    assert (first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8")) == ("first\n", "second\n")


def test_relocated_codex_home(home: Path):
    relocated = home / "relocated"
    relocated.mkdir()
    assert relocated != home / ".codex"
    (relocated / "AGENTS.local.md").write_text("- Relocated addition.\n")
    args = ("--home", str(home), "--codex-home", str(relocated))
    proc = run("--write", *args)
    assert proc.returncode == 0, proc.stderr
    assert "Relocated addition." in (relocated / "AGENTS.md").read_text()
    assert not agents(home).exists()
    proc = run("--check", *args)
    assert (verdict(proc), proc.returncode) == ("current", 0)


def test_codex_home_environment_and_cli_precedence(home: Path, monkeypatch):
    relocated = home / "environment-codex"
    relocated.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(relocated))
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--home", str(home)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (relocated / "AGENTS.md").is_file()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--home", str(home),
         "--codex-home", str(home / ".codex")],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert agents(home).is_file()


@pytest.mark.skipif(shutil.which("python3") is None, reason="control invokes python3")
def test_registered_control_isolates_an_inherited_foreign_codex_home():
    """Exercise the shipped invocation, including both bad cases and its anchor."""
    foreign = ROOT / "controls/codex-global-agents/cases/foreign-codex-home"
    before = (foreign / "AGENTS.md").read_bytes()
    assert b"Foreign Codex instructions" in before
    assert b"cpp-codex-global-agents:" not in before
    env = os.environ.copy()
    env["CODEX_HOME"] = str(foreign)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-negative-controls.py"),
         "--root", str(ROOT), "--control", "controls/codex-global-agents", "--strict"],
        env=env, capture_output=True, text=True, check=False, timeout=60,
    )
    assert (foreign / "AGENTS.md").read_bytes() == before
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "case good-fresh-pair: expected=GOOD observed=GOOD (exit 0)" in proc.stdout
    for case in ("bad-source-gained-a-rule", "bad-hand-edited"):
        assert f"case {case}: expected=BAD observed=BAD (exit 3)" in proc.stdout
        assert f"on case {case}: missed the known-bad input (blind, as required)" in proc.stdout
    assert "NEGATIVE_CONTROL_VERDICT: PASS" in proc.stdout


def test_no_flags_still_selects_codex_home_environment(home: Path, monkeypatch, capsys):
    """Default relocation is a supported real-use policy, separate from fixtures."""
    relocated = home / "relocated-default"
    relocated.mkdir()
    spec = importlib.util.spec_from_file_location("codex_global_agents_default", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.Path, "home", lambda: home)
    monkeypatch.setenv("CODEX_HOME", str(relocated))
    assert module.main(["--write"]) == 0
    assert (relocated / "AGENTS.md").is_file()
    assert not agents(home).exists()
    capsys.readouterr()
    assert module.main(["--check", "--quiet"]) == 0
    assert capsys.readouterr().out == "CODEX_GLOBAL_AGENTS: current\n"

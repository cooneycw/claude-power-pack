"""Real package bytes feed builders and fidelity readers; no host installation."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from lib.pi_skills import PolicyError, build, fidelity, write

ROOT = Path(__file__).resolve().parents[1]


def _assert_codex_baseline(output, baseline):
    actual = {p.relative_to(output).as_posix(): [hashlib.sha256(p.read_bytes()).hexdigest(),
                                               p.stat().st_mode & 0o777]
              for p in output.rglob("*") if p.is_file() and p.name != "README.md"}
    assert actual and actual == baseline["members"]


def test_pinned_codex_outputs_and_deliberately_changed_transform(tmp_path, monkeypatch):
    from tests.test_codex_skill_sync import codex_skill_sync as generator
    baseline = json.loads((ROOT / "controls/pi-skill-build/codex-baseline.json").read_text())
    assert baseline["commit"] == "40d25173c8c09987fac851cffa565efdc0f11c72"
    output = tmp_path / "codex-good"
    assert generator.main(["--write", "--output-root", str(output)]) == 0
    _assert_codex_baseline(output, baseline)
    original = generator.generate_skill

    def changed_transform(*args, **kwargs):
        files = original(*args, **kwargs)
        return {**files, "SKILL.md": files["SKILL.md"] + "\nSeeded transform difference.\n"}

    monkeypatch.setattr(generator, "generate_skill", changed_transform)
    bad = tmp_path / "codex-bad"
    assert generator.main(["--write", "--output-root", str(bad)]) == 0
    assert next(bad.glob("*/SKILL.md")).read_text().endswith("Seeded transform difference.\n")
    with pytest.raises(AssertionError):
        _assert_codex_baseline(bad, baseline)


def source(tmp_path):
    root = tmp_path / "source"
    skill = root / ".claude/skills/topic"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: topic\ndescription: Fixture topic\nmetadata:\n"
        "  provenance:\n    class: cpp-authored\n---\nRead `docs/skills/topic.md`\n"
    )
    guide = root / "docs/skills/topic.md"
    guide.parent.mkdir(parents=True)
    guide.write_text("# Fixture guide\n")
    return root


def test_real_canonical_packages_build_deterministically(tmp_path):
    packages = build(ROOT)
    assert len(packages) == len(list((ROOT / ".claude/skills").iterdir())) > 0
    assert packages == build(ROOT)
    output = tmp_path / "skills"
    write(packages, output)
    report = fidelity(packages, output)
    assert report["fidelity"] == "matches", report
    assert report["checked"] == report["expected"] == len(packages)
    assert report["effectiveness"] == "unknown"
    assert all(p.stat().st_mode & 0o777 == 0o644 for p in output.rglob("*.md"))


def test_bundled_bytes_marker_and_drift(tmp_path):
    packages = build(source(tmp_path))
    output = tmp_path / "skills"
    write(packages, output)
    skill = output / "topic/SKILL.md"
    assert "./references/topic.md" in skill.read_text()
    assert "source: claude-power-pack/.claude/skills/topic" in skill.read_text()
    reference = output / "topic/references/topic.md"
    reference.write_bytes(reference.read_bytes() + b"x")
    assert reference.read_bytes() != dict(packages[0].members)["references/topic.md"]
    assert fidelity(packages, output)["fidelity"] == "differs"


@pytest.mark.parametrize("change", ["missing", "marker", "mode", "symlink"])
def test_fidelity_never_skips_missing_or_unsafe_expected_package(tmp_path, change):
    packages = build(source(tmp_path))
    output = tmp_path / "skills"
    write(packages, output)
    skill = output / "topic/SKILL.md"
    if change == "missing":
        skill.unlink()
        assert not skill.exists()
    elif change == "marker":
        skill.write_text(skill.read_text().replace("  source:", "  removed:"))
        assert "  source:" not in skill.read_text()
    elif change == "mode":
        skill.chmod(0o755)
        assert skill.stat().st_mode & 0o111
    else:
        skill.unlink()
        skill.symlink_to(tmp_path / "never-open")
        assert skill.is_symlink()
    report = fidelity(packages, output)
    assert report["fidelity"] == "differs"
    assert report["checked"] == 0


def test_foreign_neighbor_not_adopted_or_judged(tmp_path):
    packages = build(source(tmp_path))
    output = tmp_path / "skills"
    write(packages, output)
    neighbor = output / "foreign"
    neighbor.mkdir()
    (neighbor / "custom").write_text("preserve")
    assert fidelity(packages, output)["fidelity"] == "matches"
    assert (neighbor / "custom").read_text() == "preserve"


def test_changed_build_output_is_not_pruned(tmp_path):
    packages = build(source(tmp_path))
    output = tmp_path / "skills"
    write(packages, output)
    file = output / "topic/SKILL.md"
    file.write_text("user content")
    with pytest.raises(PolicyError, match="new empty"):
        write(packages, output)
    assert file.read_text() == "user content"


def test_unreadable_installed_bytes_are_unknown(tmp_path, monkeypatch):
    import lib.pi_skills as module
    packages = build(source(tmp_path))
    output = tmp_path / "skills"
    write(packages, output)

    def denied(path):
        raise PermissionError("fixture denied read")

    monkeypatch.setattr(module, "markdown", denied)
    report = fidelity(packages, output)
    assert report["fidelity"] == "unknown"
    assert report["checked"] == 0
    assert report["unexamined"] == 1


def test_reference_portability_after_source_hidden(tmp_path):
    root = source(tmp_path)
    packages = build(root)
    output = tmp_path / "skills"
    write(packages, output)
    shutil.rmtree(root)
    assert not root.exists()
    assert (output / "topic/references/topic.md").read_text() == "# Fixture guide\n"
    assert fidelity(packages, output)["fidelity"] == "matches"


def test_actual_cli_with_external_cwd_and_explicit_home(tmp_path, monkeypatch, capsys):
    import importlib.util
    import json
    script = ROOT / "scripts/pi-skill-sync.py"
    spec = importlib.util.spec_from_file_location("pi_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = source(tmp_path)
    home, cwd = tmp_path / "home", tmp_path / "unrelated"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    output = tmp_path / "build/skills"
    common = ["--root", str(root), "--home", str(home), "--output-root", str(output), "--json"]
    assert module.main(["--write", *common]) == 0
    assert json.loads(capsys.readouterr().out)["checked"] == 1
    assert module.main(["--check", *common]) == 0
    assert json.loads(capsys.readouterr().out)["effectiveness"] == "unknown"


@pytest.mark.skipif(shutil.which("git") is None, reason="requires real git checkout layouts")
def test_source_inventory_in_main_linked_and_shallow_clone(tmp_path):
    root = source(tmp_path)

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
             "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
            check=True, capture_output=True, text=True,
        )

    git("init", "--initial-branch=main", str(root))
    git("-C", str(root), "add", ".")
    git("-C", str(root), "commit", "-m", "fixture")
    linked = tmp_path / "linked"
    git("-C", str(root), "worktree", "add", "--detach", str(linked))
    shallow = tmp_path / "shallow"
    git("clone", "--depth=1", "--single-branch", root.as_uri(), str(shallow))
    assert git("-C", str(shallow), "rev-parse", "--is-shallow-repository").stdout.strip() == "true"
    assert build(root) == build(linked) == build(shallow)


@pytest.mark.skipif(shutil.which("python3") is None, reason="requires Python consumer interpreter")
def test_consumer_own_interpreter_and_path(tmp_path):
    import venv
    root = source(tmp_path)
    environment = tmp_path / "consumer-env"
    venv.EnvBuilder(with_pip=False).create(environment)
    python = environment / "bin/python"
    assert python.is_file()
    caller, home = tmp_path / "consumer", tmp_path / "home"
    caller.mkdir()
    home.mkdir()
    result = subprocess.run(
        [str(python), str(ROOT / "scripts/pi-skill-sync.py"), "--write", "--json",
         "--root", str(root), "--home", str(home), "--output-root", str(tmp_path / "build/skills")],
        cwd=caller, env={"PATH": str(environment / "bin")}, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["fidelity"] == "matches"

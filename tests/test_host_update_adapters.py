"""Real production adapters, pinned builders and installed fidelity readers."""
import json
import shutil
import subprocess
import sys
import tarfile
from dataclasses import asdict
from pathlib import Path

import pytest

from lib.host_update.driver import refresh
from lib.host_update.host import INCLUDED, registry, run_host
from lib.host_update.models import Request, Revision

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/cpp-host-update.py"
pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for pinned adapters")


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result.stdout.strip()


@pytest.fixture(scope="session")
def source_template(tmp_path_factory):
    folder = tmp_path_factory.mktemp("host-adapter-source")
    archive = folder / "source.tar"
    git(ROOT, "archive", "HEAD", "--format=tar", f"--output={archive}")
    source = folder / "repo"
    source.mkdir()
    with tarfile.open(archive) as rows:
        for row in rows:
            path = source / row.name
            assert path.resolve().is_relative_to(source)
            if row.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif row.isfile():
                path.parent.mkdir(parents=True, exist_ok=True)
                stream = rows.extractfile(row)
                assert stream is not None
                path.write_bytes(stream.read())
                path.chmod(0o755 if row.mode & 0o111 else 0o644)
    # Test the actual implementation being authored, committed into owned
    # history; never label dirty working-tree code as a source revision.
    names = ["source", "host", "claude", "codex", "antigravity"]
    for name in [*(f"lib/host_update/{n}.py" for n in names), "scripts/cpp-host-update.py"]:
        (source / name).write_bytes((ROOT / name).read_bytes())
    git(source, "init", "-q")
    git(source, "config", "user.name", "Fixture")
    git(source, "config", "user.email", "fixture@example.invalid")
    git(source, "config", "commit.gpgsign", "false")
    git(source, "add", ".")
    git(source, "commit", "-qm", "adapter implementation and source A")
    return source


@pytest.fixture
def source(tmp_path, source_template):
    result = tmp_path / "source"
    git(tmp_path, "clone", "-q", "--no-hardlinks", str(source_template), str(result))
    git(result, "config", "user.name", "Fixture")
    git(result, "config", "user.email", "fixture@example.invalid")
    return result


def request(source, **kwargs):
    return Request(Revision(git(source, "rev-parse", "HEAD"), source), **kwargs)


def cli(source, home, operation="refresh", *extra, cwd=None):
    result = subprocess.run([sys.executable, str(CLI), operation, "--source-root", str(source),
                             "--home", str(home), "--json", *extra],
                            capture_output=True, text=True, cwd=cwd, timeout=120)
    assert result.stdout, result.stderr
    return result, json.loads(result.stdout)


def files(root):
    return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mode & 0o777)
            for p in root.rglob("*") if p.is_file()}


def test_real_adapters_and_claude_checker(source, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    answer = run_host(registry(home, INCLUDED), request(source))
    assert answer.exit_code == 0, answer
    assert {r.harness for r in answer.results} == set(INCLUDED)
    assert all(r.revision == answer.revision and r.after.expected_packages > 0 for r in answer.results)
    assert not (home / ".claude/commands").exists()
    checked = subprocess.run([sys.executable, str(source / "scripts/skills-check.py"), "--root", str(source),
                              "--managed-root", str(home / ".claude/skills")], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "18 CPP-marked managed install(s) validated" in checked.stdout


def test_cli_presence_and_foreign_directory_do_not_enroll(source, tmp_path):
    home = tmp_path / "home"
    neighbor = home / ".gemini/config/skills/personal/SKILL.md"
    neighbor.parent.mkdir(parents=True)
    neighbor.write_text("my skill")
    before = files(home)
    result = run_host(registry(home), request(source))
    assert result.exit_code == 5 and all(not r.selected for r in result.results)
    assert files(home) == before


@pytest.mark.parametrize("prefix", [".gemini", ".gemini/config"])
def test_prefix_alias_refused_before_source_git(source, tmp_path, monkeypatch, prefix):
    home, outside = tmp_path / "home", tmp_path / "outside"
    home.mkdir()
    outside.mkdir()
    sentinel = outside / "do-not-read"
    sentinel.write_bytes(b"preserve")
    link = home / prefix
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside, target_is_directory=True)
    adapter = registry(home)[2]
    req = request(source)

    def forbidden(*args, **kwargs):
        raise AssertionError("Git reached before prefix refusal")

    monkeypatch.setattr("lib.host_update.driver._source_git", forbidden)
    result = refresh(adapter, req)
    assert result.exit_code == 1 and result.after.state == "unmanaged"
    assert files(outside) == {"do-not-read": (b"preserve", 0o644)}


@pytest.mark.parametrize("changed", [False, True])
def test_legacy_exact_match_bootstrap_or_stale_unknown(source, tmp_path, changed):
    home = tmp_path / "home"
    home.mkdir()
    assert run_host(registry(home, ("antigravity",)), request(source)).exit_code == 0
    root = home / ".gemini/config/skills"
    ledger = root / ".cpp-managed/ownership.json"
    ledger.unlink()
    assert not ledger.exists()
    guide = root / "python-packaging/references/docs/skills/python-packaging.md"
    if changed:
        guide.write_bytes(b"old or edited; no prior proof")
        assert guide.read_bytes() != (source / "docs/skills/python-packaging.md").read_bytes()
    before = {p: (p.read_bytes(), p.stat().st_ino) for p in root.glob("*/**/*")
              if p.is_file() and ".cpp-managed" not in p.parts}
    result = run_host(registry(home), request(source))
    row = result.results[2]
    assert row.exit_code == (4 if changed else 0)
    assert ledger.exists() is not changed
    assert all((p.read_bytes(), p.stat().st_ino) == value for p, value in before.items())
    if not changed:
        assert row.metadata_refreshed


def test_codex_source_alias_refused_before_generator(source, tmp_path, monkeypatch):
    from lib.host_update.codex import CodexAdapter
    from lib.host_update.models import AdapterError

    outside = tmp_path / "outside.md"
    outside.write_bytes(b"forbidden source content")
    target = source / ".claude/commands/cpp/update.md"
    target.unlink()
    target.symlink_to(outside)
    git(source, "add", ".")
    git(source, "commit", "-qm", "canonical source alias")
    assert target.is_symlink()
    original = subprocess.run

    def guarded(args, *positional, **kwargs):
        assert str(args[0]) == "git", "generator reached before source alias refusal"
        return original(args, *positional, **kwargs)

    monkeypatch.setattr(subprocess, "run", guarded)
    adapter = CodexAdapter(tmp_path / "home")
    with pytest.raises(AdapterError, match="source symlink"):
        adapter.build(request(source).revision, adapter.preflight(request(source)))


def test_malformed_ownership_unknown_not_absent(source, tmp_path):
    home = tmp_path / "home"
    record = home / ".gemini/config/skills/.cpp-managed/ownership.json"
    record.parent.mkdir(parents=True)
    record.write_text('{"schema":1,"producer":"claude-power-pack","adapters":')
    assert record.read_text().endswith(":")
    before = files(home)
    result = run_host(registry(home), request(source))
    assert result.exit_code == 4 and result.results[2].after.state == "unknown"
    assert files(home) == before


def test_deferred_surface_is_not_modified(source, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    target = home / ".gemini/config"
    report = run_host(registry(home, ("antigravity",), (str(target),)), request(source))
    assert report.exit_code == 1 and report.results[2].action == "refused"
    assert not target.exists()


def test_invalid_adoption_never_mutates(source, tmp_path):
    home = tmp_path / "home"
    result = subprocess.run([sys.executable, str(CLI), "refresh", "--source-root", str(source),
                             "--home", str(home), "--adopt", "antigravity:../outside", "--json"],
                            capture_output=True, text=True)
    assert result.returncode == 2 and not home.exists()


def test_bootstrap_io_failure_reports_actual_remaining_state(source, tmp_path, monkeypatch):
    from lib.host_update.scope import Scope
    from lib.host_update.source import valid_report

    home = tmp_path / "home"
    home.mkdir()
    assert run_host(registry(home, ("antigravity",)), request(source)).exit_code == 0
    ledger = home / ".gemini/config/skills/.cpp-managed/ownership.json"
    ledger.unlink()
    assert not ledger.exists()
    original = Scope.write

    def fail_after_write(scope, path, content, mode=0o644):
        original(scope, path, content, mode)
        if path == ledger:
            raise OSError("controlled IO failure after metadata publication")

    with monkeypatch.context() as patch:
        patch.setattr(Scope, "write", fail_after_write)
        report = run_host(registry(home), request(source))
    row = report.results[2]
    assert report.exit_code == 1 and row.action == "failed"
    assert row.after.state == "current" and row.metadata_refreshed
    assert valid_report(json.loads(json.dumps(asdict(report))), 1, report.revision)
    assert run_host(registry(home), request(source), verify_only=True).exit_code == 0


def test_qualified_adoption_retains_backup_and_other_adapters_progress(source, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert run_host(registry(home, INCLUDED), request(source)).exit_code == 0
    root = home / ".gemini/config/skills"
    ledger = root / ".cpp-managed/ownership.json"
    document = json.loads(ledger.read_text())
    del document["adapters"]["antigravity"]["python-packaging"]
    ledger.write_text(json.dumps(document))
    guide = root / "python-packaging/references/docs/skills/python-packaging.md"
    guide.write_bytes(b"reviewed personal modification")
    assert "python-packaging" not in document["adapters"]["antigravity"]
    src = source / "docs/skills/python-packaging.md"
    src.write_bytes(src.read_bytes() + b"\nnew desired source B\n")
    git(source, "commit", "-am", "source B for reviewed adoption")
    process, report = cli(source, home, "refresh", "--adopt", "antigravity:python-packaging")
    assert process.returncode == 0, report
    assert all(r["after"]["state"] == "current" for r in report["results"])
    backups = list((root / ".cpp-managed/work").glob(
        "transaction-*/backup/python-packaging/references/docs/skills/python-packaging.md"))
    assert len(backups) == 1 and backups[0].read_bytes() == b"reviewed personal modification"
    assert guide.read_bytes() == src.read_bytes()

"""Owned Git transports plus actual umask-000 checkout inputs."""
import json
import os
import shutil

import pytest

from tests.test_host_update_adapters import cli, git
from tests.test_host_update_adapters import source_template as template_fixture

source_template = template_fixture
pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for CI source shapes")


@pytest.mark.parametrize("mask", [0o022, 0o000])
@pytest.mark.parametrize("shape", ["full", "shallow", "worktree"])
def test_actual_entry_source_shapes(source_template, tmp_path, mask, shape):
    source, home = tmp_path / "source", tmp_path / "home"
    home.mkdir()
    previous = os.umask(mask)
    try:
        if shape == "worktree":
            clone = tmp_path / "clone"
            git(tmp_path, "clone", "-q", str(source_template), str(clone))
            git(clone, "worktree", "add", "--detach", str(source), "HEAD")
        else:
            flags = ["--depth=1"] if shape == "shallow" else []
            git(tmp_path, "clone", "-q", *flags, source_template.as_uri(), str(source))
    finally:
        os.umask(previous)
    if mask == 0:
        assert (source / "docs/skills/python-packaging.md").stat().st_mode & 0o777 == 0o666
    if shape == "shallow":
        assert git(source, "rev-parse", "--is-shallow-repository") == "true"
    result, report = cli(source, home, "refresh", "--select", "codex", "--select", "antigravity",
                         "--select", "claude-topics", cwd=tmp_path)
    assert result.returncode == 0, result.stderr + str(report)
    for row in report["results"]:
        assert row["after"]["state"] == "current" and row["revision"] == report["revision"]
    for root in [home / ".codex/skills", home / ".claude/skills", home / ".gemini/config/skills"]:
        assert next(root.glob("*/SKILL.md")).stat().st_mode & 0o777 == 0o644
    assert git(source, "status", "--porcelain") == ""


def test_dirty_source_does_not_mutate_home(source_template, tmp_path):
    source, home = tmp_path / "source", tmp_path / "home"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    home.mkdir()
    with (source / "CLAUDE.md").open("a") as out:
        out.write("\ndirty input\n")
    assert git(source, "status", "--porcelain")
    result, report = cli(source, home, "refresh", "--select", "antigravity")
    assert result.returncode == 4 and all(r["action"] == "not-attempted" for r in report["results"])
    assert list(home.iterdir()) == []


def test_moved_source_is_unknown_and_preserves_installation(source_template, tmp_path):
    from tests.test_host_update_adapters import files

    source, home = tmp_path / "source", tmp_path / "home"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    home.mkdir()
    initial, seeded = cli(source, home, "refresh", "--select", "antigravity")
    assert initial.returncode == 0, seeded
    before = files(home)
    source.rename(tmp_path / "moved-source")
    assert not source.exists()
    result, report = cli(source, home, "refresh")
    assert result.returncode == 4 and report["results"][2]["selected"]
    assert report["results"][2]["action"] == "not-attempted"
    assert report["results"][2]["after"]["state"] == "unknown"
    assert files(home) == before


def test_private_snapshot_never_registers_in_source(source_template, tmp_path):
    from lib.host_update.source import pinned_source
    from tests.test_host_update_adapters import files

    source = tmp_path / "source"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    registrations = git(source, "worktree", "list", "--porcelain")
    metadata = files(source / ".git")
    with pinned_source(source) as revision:
        assert git(source, "worktree", "list", "--porcelain") == registrations
        assert files(source / ".git") == metadata
        assert git(revision.snapshot_root, "rev-parse", "HEAD") == revision.commit
    assert files(source / ".git") == metadata


def test_control_declared_runtime_works_without_global_yaml(tmp_path):
    import shlex
    import subprocess
    import sys
    from pathlib import Path

    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv required for the declared control runtime")
    root = Path(__file__).resolve().parents[1]
    tools = tmp_path / "tools"
    tools.mkdir()
    python = tools / "python3"
    python.write_text("#!/bin/sh\nexec " + shlex.quote(sys._base_executable) + ' -S "$@"\n')
    python.chmod(0o755)
    (tools / "uv").symlink_to(Path(uv).resolve())
    excluded = {Path(sys.prefix, "bin").resolve(), (root / ".venv/bin").resolve()}
    if os.environ.get("VIRTUAL_ENV"):
        excluded.add(Path(os.environ["VIRTUAL_ENV"], "bin").resolve())
    paths = [p for p in os.environ["PATH"].split(os.pathsep) if p and Path(p).resolve() not in excluded]
    env = dict(os.environ, PATH=os.pathsep.join([str(tools), *paths]))
    for name in ("VIRTUAL_ENV", "PYTHONPATH", "UV_PROJECT_ENVIRONMENT"):
        env.pop(name, None)
    assert shutil.which("python3", path=env["PATH"]) == str(python)
    assert shutil.which("uv", path=env["PATH"]) == str(tools / "uv")
    probe = subprocess.run(["python3", "-c", "import yaml"], env=env, capture_output=True, text=True)
    assert probe.returncode != 0 and "No module named 'yaml'" in probe.stderr
    control = root / "controls/antigravity-skill-install-fidelity"
    specification = json.loads((control / "control.json").read_text())
    argv = [part.format(gate=root / "scripts/cpp-host-update.py", case=control / "cases/good-current")
            for part in specification["invocation"]]
    result = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    row = next(r for r in report["results"] if r["harness"] == "antigravity")
    assert row["after"]["state"] == "current" and row["after"]["expected_packages"] == 18


@pytest.mark.parametrize("fault", ["empty", "zero-count", "wrong-revision", "bad-summary"])
def test_pinned_reader_rejects_bad_current_writer(source_template, tmp_path, fault):
    from lib.host_update.host import DEFERRED, INCLUDED
    from lib.host_update.source import ExecutionFailure, execute_snapshot
    from tests.test_host_update_adapters import request

    source = tmp_path / "source"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    entry = source / "scripts/cpp-host-update.py"
    stage = {"state": "current", "expected_packages": 1, "expected_members": 1, "examined_members": 1}
    payload = {"schema": 1, "coverage": "partial", "backend": "copies", "included": list(INCLUDED),
               "unimplemented": list(DEFERRED), "exit_code": 0,
               "results": [{"harness": n, "selected": True, "exit_code": 0, "before": stage, "after": stage,
                            "action": "unchanged", "reason": "", "remedy": ""} for n in INCLUDED]}
    if fault == "empty":
        payload["results"] = []
    elif fault == "zero-count":
        stage.update(expected_packages=0, expected_members=0, examined_members=0)
    elif fault == "bad-summary":
        payload["exit_code"] = 4
    bad_revision = "'f'*40" if fault == "wrong-revision" else "sys.argv[-1]"
    entry.write_text("#: PRODUCTION-COPY-ENTRY: 1\nimport json,sys\n"
                     + "r=json.loads(" + repr(json.dumps(payload)) + ")\n"
                     + f"r['revision']={bad_revision}\n"
                     + "for row in r['results']: row['revision']=r['revision']\n"
                     + "print(json.dumps(r))\n")
    git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-am", "known blind current producer")
    if fault == "empty":
        assert not payload["results"]
    elif fault == "zero-count":
        assert payload["results"][0]["after"]["expected_packages"] == 0
    elif fault == "wrong-revision":
        assert request(source).revision.commit != "f" * 40
    else:
        assert payload["exit_code"] == 4
    with pytest.raises(ExecutionFailure, match="incomplete or inconsistent"):
        execute_snapshot(request(source).revision, ["verify", "--json"])


def test_unavailable_old_entry_is_unknown_before_execution(source_template, tmp_path):
    source, home = tmp_path / "source", tmp_path / "home"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    entry = source / "scripts/cpp-host-update.py"
    entry.write_text("raise AssertionError('old entry must never execute')\n")
    git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-am", "unsupported old production entry")
    assert "PRODUCTION-COPY-ENTRY" not in entry.read_text()
    result, report = cli(source, home, "refresh", "--select", "antigravity")
    assert result.returncode == 4 and report["results"][2]["action"] == "not-attempted"
    assert not home.exists()


def test_executable_source_alias_never_runs(source_template, tmp_path):
    source, home = tmp_path / "source", tmp_path / "home"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    outside = tmp_path / "outside.py"
    outside.write_text("raise AssertionError('outside code must never execute')\n")
    entry = source / "lib/host_update/host.py"
    entry.unlink()
    entry.symlink_to(outside)
    git(source, "add", ".")
    git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "executable source alias")
    assert entry.is_symlink()
    result, report = cli(source, home, "refresh", "--select", "antigravity")
    assert result.returncode == 4 and report["results"][2]["action"] == "not-attempted"
    assert not home.exists()

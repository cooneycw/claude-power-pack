"""Actual executing-identity denial, then independent harness progress."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from lib.host_update.host import INCLUDED, registry, run_host
from lib.host_update.models import Request, Revision
from lib.host_update.scope import Scope
from lib.host_update.store import lock_paths
from tests.test_host_update_adapters import CLI, files, git, request
from tests.test_host_update_adapters import source_template as template_fixture

source_template = template_fixture
pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for adapter permission acceptance")


def test_unwritable_destination_other_real_adapters_refresh(source_template):
    with tempfile.TemporaryDirectory(prefix="cpp-host-permission-") as temporary:
        base = Path(temporary)
        base.chmod(0o755)
        source, home = base / "source", base / "home"
        git(base, "clone", "-q", "--no-hardlinks", str(source_template), str(source))
        home.mkdir()
        assert run_host(registry(home, INCLUDED), request(source)).exit_code == 0
        first_commit = request(source).revision.commit
        guide = source / "docs/skills/python-packaging.md"
        guide.write_bytes(guide.read_bytes() + b"\npermission acceptance B\n")
        git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "-am", "source B")
        target = home / ".gemini/config/skills"
        identity = os.geteuid()
        options = {"env": {k: v for k, v in os.environ.items() if k != "CPP_DEFER_SURFACES"}}
        if identity == 0:
            identity = 65534
            for path in [source, home, *source.rglob("*"), *home.rglob("*")]:
                if not path.is_symlink():
                    os.chown(path, identity, identity)
            for path in [target, *target.rglob("*")]:
                if not path.is_symlink():
                    os.chown(path, 0, 0)
            options.update(user=identity, group=identity, extra_groups=())
        target.chmod(0o555)
        probe = subprocess.run([sys.executable, "-c", (
            "import os,pathlib,sys; assert os.geteuid()==int(sys.argv[2]); "
            "p=pathlib.Path(sys.argv[1]);\n"
            "try: p.write_bytes(b'probe')\n"
            "except PermissionError: print('DENIED')\n"
            "else: raise AssertionError('destination was writable')\n"
        ), str(target / "negative-write-probe"), str(identity)], capture_output=True, text=True, **options)
        assert probe.returncode == 0 and probe.stdout.strip() == "DENIED", probe.stderr
        assert not (target / "negative-write-probe").exists()
        try:
            adapter = registry(home)[2]
            policy = adapter.preflight(Request(Revision(first_commit, source)))
            locks = lock_paths(Scope(policy, owner=adapter.harness))
            for lock in locks:
                lock.unlink()
            assert all(not lock.exists() for lock in locks)
            before = files(home)
            verification = subprocess.run([sys.executable, str(CLI), "verify", "--source-root", str(source),
                                            "--revision", first_commit, "--home", str(home), "--json"],
                                           capture_output=True, text=True, timeout=120, **options)
            assert verification.returncode == 0, verification.stdout + verification.stderr
            assert files(home) == before and all(not lock.exists() for lock in locks)
            answer = subprocess.run([sys.executable, str(CLI), "refresh", "--source-root", str(source),
                                     "--home", str(home), "--json"], capture_output=True, text=True,
                                    timeout=120, **options)
            report = json.loads(answer.stdout)
            assert answer.returncode == 1, report
            assert report["schema"] == 2 and report["backend"] == "mixed"
            rows = {r["harness"]: r for r in report["results"]}
            assert rows["claude-links"]["backend"] == "links" and not rows["claude-links"]["selected"]
            assert rows["antigravity"]["exit_code"] == 1
            assert rows["antigravity"]["after"]["state"] != "current"
            assert all(rows[n]["after"]["state"] == "current" for n in ("codex", "claude-topics"))
            assert "failure" in answer.stderr
        finally:
            target.chmod(0o755)

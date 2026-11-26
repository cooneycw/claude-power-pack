"""Owned histories and real copy adapters feed the production CLI subject."""
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.host_update.host import INCLUDED, registry, run_host  # noqa: E402
from lib.host_update.models import Request, Revision  # noqa: E402
from lib.host_update.scope import Scope  # noqa: E402
from lib.host_update.store import lock_paths  # noqa: E402


def inventory(root):
    return {p.relative_to(root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mode & 0o777)
            for p in root.rglob("*") if p.is_file()}


def main():
    gate, case = map(Path, sys.argv[1:3])
    if not shutil.which("git"):
        print("HOST_UPDATE: UNAVAILABLE - git missing")
        return 3
    scenario = json.loads((case / "case.json").read_text())["scenario"]
    with tempfile.TemporaryDirectory(prefix="cpp-real-adapter-control-") as temporary:
        base = Path(temporary)
        source, home = base / "source", base / "home"
        source.mkdir()
        home.mkdir()

        def git(root, *args):
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                                     "-C", str(root), *args], capture_output=True, env=env)
            assert result.returncode == 0, result.stderr
            return result.stdout.decode().strip()

        archive = base / "source.tar"
        git(ROOT, "archive", "HEAD", "--format=tar", f"--output={archive}")
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
        # During authoring this also commits untracked implementation inputs
        # into the fixture's own history; at a frozen head these bytes agree.
        for name in [*(f"lib/host_update/{n}.py" for n in ("links", "source", "host", "claude", "codex", "antigravity",
                                                        "models", "driver", "store")),
                     "scripts/cpp-host-update.py"]:
            (source / name).write_bytes((ROOT / name).read_bytes())
        git(source, "init", "-q")
        git(source, "config", "user.name", "Fixture")
        git(source, "config", "user.email", "fixture@example.invalid")
        git(source, "add", ".")
        git(source, "commit", "-qm", "source A")
        revision = Revision(git(source, "rev-parse", "HEAD"), source)
        all_three = scenario == "refresh"
        selected = INCLUDED if all_three else ("antigravity",)
        setup = run_host(registry(home, selected), Request(revision))
        assert setup.exit_code == 0, setup
        adapter = registry(home)[2]
        policy = adapter.preflight(Request(revision))
        guide = policy.install_root / "python-packaging/references/docs/skills/python-packaging.md"
        initial = guide.read_bytes()
        if scenario == "stale" or scenario == "refresh":
            src = source / "docs/skills/python-packaging.md"
            src.write_bytes(src.read_bytes() + b"\nsource B\n")
            git(source, "commit", "-am", "source B")
            assert guide.read_bytes() != src.read_bytes()
        elif scenario == "missing":
            guide.unlink()
            assert not guide.exists()
        elif scenario == "edited":
            guide.write_bytes(b"edited installed guide")
            assert guide.read_bytes() != initial
        elif scenario == "foreign":
            foreign = guide.parent / "personal-note.txt"
            foreign.write_bytes(b"preserve foreign content")
            assert foreign.exists()
        elif scenario == "no-lock":
            paths = lock_paths(Scope(policy, owner=adapter.harness))
            for path in paths:
                path.unlink()
            assert all(not p.exists() for p in paths)
        neighbor = policy.install_root / "personal/SKILL.md"
        neighbor.parent.mkdir()
        neighbor.write_bytes(b"foreign sibling")
        before = inventory(home)
        args = [sys.executable, str(gate), "refresh" if all_three else "verify", "--source-root", str(source),
                "--home", str(home), "--json", "--lock-timeout", "0"]
        if scenario == "revision":
            args += ["--pinned", "f" * 40]
        with policy.lock_path.open("a+b") if scenario == "lock" else tempfile.TemporaryFile() as held:
            if scenario == "lock":
                fcntl.flock(held, fcntl.LOCK_EX)
            result = subprocess.run(args, capture_output=True, text=True, timeout=90,
                                    env={k: v for k, v in os.environ.items() if k != "CPP_DEFER_SURFACES"})
        if not all_three and inventory(home) != before:
            print("CONTROL_ORACLE: verifier mutated installed state")
            return 9
        assert neighbor.read_bytes() == b"foreign sibling"
        if all_three and result.returncode == 0:
            report = json.loads(result.stdout)
            assert report["schema"] == 2 and len(report["results"]) == 4
            assert all(r["backend"] == "copies" and r["after"]["state"] == "current"
                       for r in report["results"] if r["selected"])
            assert {r["revision"] for r in report["results"]} == {git(source, "rev-parse", "HEAD")}
            assert guide.read_bytes() != initial
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

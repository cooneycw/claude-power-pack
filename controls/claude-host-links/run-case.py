"""Actual shared CLI with confined positive and three preserved bad entries."""
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def inventory(root):
    rows = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            rows[str(path.relative_to(root))] = (("link", os.readlink(path)) if path.is_symlink() else
                ("dir",) if path.is_dir() else ("file", hashlib.sha256(path.read_bytes()).hexdigest(),
                                               path.stat().st_mode & 0o777))
    return rows


def main():
    gate, case = map(Path, sys.argv[1:3])
    if not shutil.which("git"):
        print("HOST_UPDATE: UNAVAILABLE - git missing")
        return 3
    scenario = json.loads((case / "case.json").read_text())["scenario"]
    with tempfile.TemporaryDirectory(prefix="cpp-link-control-") as temporary:
        base = Path(temporary)
        source, home = base / "source", base / "home"
        source.mkdir()
        home.mkdir()
        # A small real source: production modules plus actual maintained CPP
        # command/helper bytes. No invented CPP ownership marker is needed.
        inputs = [p.relative_to(ROOT).as_posix() for p in (ROOT / "lib/host_update").glob("*.py")]
        inputs += [".gitignore", "lib/antigravity_skills.py", "scripts/cpp-host-update.py",
                   "scripts/cpp-host-write.sh", "scripts/cpp-commands-link.sh",
                   ".claude/commands/cpp/update.md", ".claude/commands/flow/auto.md"]
        for name in inputs:
            original, target = ROOT / name, source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
            target.chmod(0o755 if original.stat().st_mode & 0o111 else 0o644)

        def git(*args):
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            result = subprocess.run(["git", "-C", str(source), "-c", "core.hooksPath=/dev/null",
                                     "-c", "commit.gpgsign=false", *args], env=env, capture_output=True)
            assert result.returncode == 0, result.stderr
            return result.stdout.decode().strip()

        git("init", "-q")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        git("add", ".")
        git("commit", "-qm", "actual CPP link sources")
        for kind, names in (("commands", ("cpp", "flow")),
                            ("scripts", ("cpp-commands-link.sh", "cpp-host-write.sh"))):
            root = home / ".claude" / kind
            root.mkdir(parents=True)
            for name in names:
                (root / name).symlink_to(source / (".claude/commands" if kind == "commands" else "scripts") / name)
        path = home / ".claude/commands/cpp"
        outside = base / "private-neighbour"
        outside.write_bytes(b"foreign bytes must survive")
        if scenario != "good-confined" and scenario != "unknown-lock":
            path.unlink()
            if scenario == "bad-regular-replacement":
                path.write_bytes(b"personal replacement")
                assert path.is_file() and not path.is_symlink()
            elif scenario == "bad-outside":
                path.symlink_to(outside)
                assert path.readlink() == outside and not outside.is_relative_to(source)
            elif scenario == "bad-dangling":
                path.symlink_to(base / "missing")
                assert path.is_symlink() and not path.exists()
            else:
                raise AssertionError("unknown control scenario")
        lock = home / ".claude/.cpp-skill-install.lock"
        with lock.open("a+b") if scenario == "unknown-lock" else tempfile.TemporaryFile() as held:
            if scenario == "unknown-lock":
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                assert lock.is_file()
            before, target_before = inventory(home), inventory(source)
            result = subprocess.run([sys.executable, str(gate), "verify", "--source-root", str(source),
                                     "--home", str(home), "--json", "--lock-timeout", "0"],
                                    capture_output=True, text=True, timeout=90,
                                    env={k: v for k, v in os.environ.items() if k != "CPP_DEFER_SURFACES"})
            assert inventory(home) == before, "verify changed installed state"
            assert inventory(source) == target_before, "verify changed persistent source"
        assert outside.read_bytes() == b"foreign bytes must survive"
        if scenario == "good-confined" and gate.resolve() == (ROOT / "scripts/cpp-host-update.py").resolve():
            report = json.loads(result.stdout)
            row = next(r for r in report["results"] if r["harness"] == "claude-links")
            assert row["backend"] == "links" and row["after"]["state"] == "current", report
            assert row["after"]["expected_members"] == row["after"]["examined_members"] == 4, row
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the real maintained refresh/finish fences against owned Git and HOME."""
import base64
import hashlib
import json
import os
import re
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
            rows[str(path.relative_to(root))] = (("link", os.readlink(path)) if path.is_symlink()
                else ("dir",) if path.is_dir() else ("file", path.read_bytes()))
    return rows


def main():
    case = Path(sys.argv[1])
    masked = sys.argv[2:] == ["--mask-summary"]
    for binary in ("git", "bash", "python3"):
        if not shutil.which(binary):
            print(f"HOST_COMMAND: UNAVAILABLE - {binary} missing")
            return 3
    scenario = json.loads((case / "case.json").read_text())["scenario"]
    legacy_case = scenario == "unknown-stale-legacy"
    document = (ROOT / ".claude/commands/cpp/update.md").read_text()
    blocks = re.findall(r"```bash\n(.*?)```", document, re.S)
    refresh = [b for b in blocks if "# CPP_SHARED_REFRESH" in b]
    finish = [b for b in blocks if "# CPP_SHARED_FINISH_GUARD" in b]
    migration = [b for b in blocks if "# CPP_CODEX_MIGRATION" in b]
    assert len(refresh) == len(finish) == len(migration) == 1, "maintained reader missing or duplicated"
    # Root must test a genuinely unwritable executing identity too. Its owned
    # temporary root is directly under /tmp, so no private ancestor blocks it.
    with tempfile.TemporaryDirectory(prefix="cmd.", dir="/tmp" if os.geteuid() == 0 else None) as temporary:
        base = Path(temporary).resolve()
        source, home = base / "source", base / "home"
        source.mkdir()
        home.mkdir()
        if legacy_case:
            clone = subprocess.run(["git", "clone", "-q", "--shared", str(ROOT), str(source)],
                                   env=dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1"),
                                   capture_output=True, text=True)
            assert clone.returncode == 0, clone.stderr
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
                                     "-c", "commit.gpgsign=false", *args], env=env,
                                    capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()

        git("init", "-q")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        git("add", ".")
        git("commit", "--allow-empty", "-qm", "actual maintained command inputs")
        scripts = home / ".claude/scripts"
        if not legacy_case:
            scripts.mkdir(parents=True)
            (scripts / "cpp-host-write.sh").symlink_to(source / "scripts/cpp-host-write.sh")
            (home / ".claude/.cpp-skill-install.lock").touch()
        missing = scripts / "cpp-commands-link.sh"
        assert not missing.exists() and not missing.is_symlink(), "GOOD must start stale at current source"
        personal = home / "personal"
        personal.write_bytes(b"personal exact bytes")
        if legacy_case:
            data = json.loads((case / "case.json").read_text())
            assert data["historical_commit"] == "5204ea06fa15efa7fec3e1d86fd489c61b85c708"
            assert data["package"] == "cicd-verify" and set(data["members"]) == {"SKILL.md", "reference.md"}
            package = home / ".codex/skills" / data["package"]
            package.mkdir(parents=True)
            for name, member in data["members"].items():
                assert name in ("SKILL.md", "reference.md")
                content = base64.b64decode(member["base64"], validate=True)
                assert hashlib.sha256(content).hexdigest() == member["sha256"]
                (package / name).write_bytes(content)
                (package / name).chmod(member["mode"])
            generated = subprocess.run([sys.executable, "-B", str(source / "scripts/codex-skill-sync.py"),
                                        "--write", "--output-root", str(base / "current-build")],
                                       capture_output=True, text=True)
            assert generated.returncode == 0, generated.stderr
            assert (base / "current-build" / data["package"] / "reference.md").read_bytes() != (
                package / "reference.md").read_bytes(), "historical fixture must actually be stale"
            legacy_before = inventory(package)
            assert not (home / ".codex/skills/.cpp-managed/ownership.json").exists()
        elif scenario == "bad-summary":
            entry = source / "scripts/cpp-host-update.py"
            entry.write_text("#: PRODUCTION-HOST-ENTRY: 3\nprint('malformed producer report')\n")
            git("commit", "-am", "fixture malformed producer")
            assert entry.read_text().endswith("print('malformed producer report')\n")
        elif scenario == "unknown-unavailable":
            git("rm", "scripts/cpp-host-update.py")
            git("commit", "-qm", "fixture unavailable entry")
            assert not (source / "scripts/cpp-host-update.py").exists()
        elif scenario not in ("good-stale-refresh", "bad-unwritable"):
            raise AssertionError("unknown fixture scenario")
        assert git("status", "--porcelain") == ""
        revision = git("rev-parse", "HEAD")
        env = dict(os.environ, HOME=str(home), CPP_DIR=str(source), CPP_DEFER_SURFACES="",
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        demote = None
        if scenario == "bad-unwritable":
            if os.geteuid() == 0:
                base.chmod(0o755)
                for parent, dirs, files in os.walk(base, followlinks=False):
                    os.chown(parent, 65534, 65534)
                    for name in dirs + files:
                        os.chown(Path(parent) / name, 65534, 65534, follow_symlinks=False)

                def demote():
                    os.setgroups([])
                    os.setgid(65534)
                    os.setuid(65534)
            scripts.chmod(0o555)
            probe = subprocess.run(["python3", "-I", "-c",
                                    "import os,sys; assert os.geteuid()!=0; "
                                    "assert not os.access(sys.argv[1],os.W_OK); print(os.geteuid())", str(scripts)],
                                   env=env, cwd=base, preexec_fn=demote, capture_output=True, text=True)
            assert probe.returncode == 0, "fixture is not genuinely unwritable: " + probe.stderr
            print("Unwritable executing UID: " + probe.stdout.strip())
        before = inventory(home)
        script = "\n".join((refresh[0], migration[0], finish[0]))
        script += '\nprintf "\\nCPP_COMMAND_EXIT=%s\\n" "$HOST_REFRESH_EXIT"\n'
        try:
            result = subprocess.run(["bash", "-c", script], env=env, cwd=base, preexec_fn=demote,
                                    capture_output=True, text=True, timeout=180)
        finally:
            if not legacy_case:
                scripts.chmod(0o755)
        assert result.returncode == 0, result.stderr
        matches = re.findall(r"^CPP_COMMAND_EXIT=(0|1|4|5)$", result.stdout, re.M)
        assert len(matches) == 1, "shared reader did not return its actual verdict"
        code = int(matches[0])
        assert personal.read_bytes() == b"personal exact bytes"
        if legacy_case:
            assert inventory(package) == legacy_before
            assert not (home / ".codex/skills/.cpp-managed/ownership.json").exists()
            assert "Codex refresh frozen: migration declined" in result.stdout
            assert "Codex migration packages: " + data["package"] in result.stdout
            assert "--adopt codex:" + data["package"] in result.stdout
        elif scenario == "good-stale-refresh":
            assert missing.is_symlink() and missing.readlink() == source / "scripts/cpp-commands-link.sh", (
                "refresh was skipped despite current source and stale installation")
            assert git("rev-parse", "HEAD") == revision, "fixture unexpectedly pulled or moved source"
        else:
            assert inventory(home) == before, "negative fixture altered owned home"
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        # The committed blind anchor still executes the real refresh. Only its
        # final report/exit is forged, so GOOD continues proving actual writes.
        if masked:
            code = 0
        state = {0: "current", 1: "failure", 4: "unknown", 5: "not-applicable"}[code]
        print(f"HOST_COMMAND: {state}")
        return code


if __name__ == "__main__":
    raise SystemExit(main())

"""Independent fixture setup; actual production CLI/core supplies the verdict."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib.pi_skills import SOURCE_PREFIX, build  # noqa: E402

# Prove the permission failure in the subject's own process/identity, then
# replace this bootstrap with the real gate. No synthetic product verdict.
UNREADABLE_EXEC = """
import os, sys
try:
    fd = os.open(sys.argv[1], os.O_RDONLY)
except PermissionError:
    pass
else:
    os.close(fd)
    raise SystemExit('CONTROL_PRECONDITION_FAILED: ledger remains readable')
print('PI_INSTALL_CONTROL_PRECONDITION: unreadable uid=%s gid=%s groups=%s' %
      (os.geteuid(), os.getegid(), os.getgroups()), file=sys.stderr, flush=True)
os.execv(sys.argv[2], sys.argv[2:])
"""


def main():
    gate, case = map(Path, sys.argv[1:3])
    seed = json.loads((case / "case.json").read_text())
    scenario = seed["scenario"]
    if not shutil.which("git"):
        print("PI_INSTALL_CONTROL: unavailable - git missing")
        return 3
    with tempfile.TemporaryDirectory(prefix="pi-install-control-") as temporary:
        # Canonicalize our own root; scenario-created symlinks remain untrusted.
        root = Path(temporary).resolve()
        source, agent, home, cwd = (root / name for name in ("source", "agent", "home", "work"))
        for p in (source, agent, home, cwd):
            p.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PI_", "GIT_"))}
        env.update(HOME=str(home), PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

        def git(*args):
            return subprocess.run(["git", "-C", str(source), *args], env=env, capture_output=True,
                                  check=True, text=True, timeout=10).stdout.strip()

        topic = source / ".claude/skills/topic/SKILL.md"
        topic.parent.mkdir(parents=True)
        topic.write_text("---\nname: topic\ndescription: Fixture topic\n---\n"
                         "[guide](../../../docs/skills/guide.md)\n")
        guide = source / "docs/skills/guide.md"
        guide.parent.mkdir(parents=True)
        guide.write_text("Fixture guide\n")
        git("init", "-q", "-b", "main")
        git("config", "user.email", "fixture@example.invalid")
        git("config", "user.name", "fixture")
        git("config", "commit.gpgsign", "false")
        git("config", "core.hooksPath", "/dev/null")

        def commit():
            git("add", ".")
            git("commit", "-qm", "fixture source")
            return git("rev-parse", "HEAD")

        revision = commit()
        packages = build(source)
        assert len(packages) == 1 and len(packages[0].members) == 2
        skills = agent / "skills"
        ledger = skills / ".cpp-managed/ownership.json"
        if scenario != "fresh-install":
            for name, data in packages[0].members:
                dest = skills / "topic" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                dest.chmod(0o644)
            ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps({"schema": 1, "producer": "claude-power-pack", "adapters": {"pi": {
                "topic": {"source": SOURCE_PREFIX + "topic", "revision": revision,
                          "members": packages[0].manifest()}}}}))
        neighbor = skills / "personal/SKILL.md"
        neighbor.parent.mkdir(parents=True)
        neighbor.write_bytes(b"foreign neighbor\n")
        operation, extra, unreadable = "--verify-installed", [], None
        installed_topic = skills / "topic/SKILL.md"
        if scenario in ("fresh-install", "adopt-with-backup", "foreign-collision", "hand-edited-before-stale",
                        "record-only-reconciliation", "record-only-unmanaged-refused", "dual-identity-refused",
                        "user-prefix-alias-refused", "ignored-source-member-refused"):
            operation = "--install"
        if scenario == "hand-edited-before-stale":
            installed_topic.write_bytes(installed_topic.read_bytes() + b"hand edit\n")
            guide.write_text("new source revision\n")
            commit()
            assert installed_topic.read_bytes().endswith(b"hand edit\n")
        elif scenario in ("foreign-collision", "adopt-with-backup", "record-only-unmanaged-refused"):
            ledger.unlink()
            assert not ledger.exists() and installed_topic.exists()
            if scenario == "adopt-with-backup":
                extra = ["--adopt", "topic"]
        elif scenario == "missing-expected-skill":
            shutil.rmtree(skills / "topic")
            assert not (skills / "topic").exists()
        elif scenario == "stripped-source-marker":
            installed_topic.write_bytes(installed_topic.read_bytes().replace(b"  source:", b"  removed:"))
            assert b"  source:" not in installed_topic.read_bytes()
        elif scenario == "modified-reference":
            (skills / "topic/references/guide.md").write_text("one byte differs!\n")
            assert ((skills / "topic/references/guide.md").read_bytes()
                    != dict(packages[0].members)["references/guide.md"])
        elif scenario in ("auth-helper-rejected", "path-escape-rejected", "manifest-rejected", "executable-rejected"):
            operation = "--install"
            if scenario == "auth-helper-rejected":
                topic.write_text(topic.read_text() + "[auth](auth.json)\n")
                assert "[auth](auth.json)" in topic.read_text()
            elif scenario == "path-escape-rejected":
                guide.unlink()
                guide.symlink_to(root / "protected.md")
                assert guide.is_symlink()
            elif scenario == "manifest-rejected":
                (topic.parent / "package.json").write_text("{}")
                assert (topic.parent / "package.json").is_file()
            else:
                topic.chmod(0o755)
                assert topic.stat().st_mode & 0o111
            commit()
        elif scenario == "output-under-trusted-config":
            operation = "--write"
            extra = ["--output-root", str(agent / "extensions/skills")]
        elif scenario == "output-under-sessions":
            extra = ["--session-dir", str(skills)]
        elif scenario == "unreadable-install":
            unreadable = ledger
            unreadable.chmod(0)
        elif scenario == "zero-expected-population":
            operation = "--install"
            shutil.rmtree(topic.parent)
            assert list(topic.parent.parent.iterdir()) == []
            commit()
        elif scenario == "dual-identity-refused":
            value = json.loads(ledger.read_bytes())
            value["adapters"]["other"] = value["adapters"].pop("pi")
            ledger.write_text(json.dumps(value))
            extra = ["--adopt", "topic"]
            assert "topic" in value["adapters"]["other"]
        elif scenario == "record-only-reconciliation":
            (source / "unrelated.md").write_text("revision change, same topic bytes\n")
            commit()
        elif scenario == "user-prefix-alias-refused":
            actual = root / "actual-agent"
            agent.rename(actual)
            agent.symlink_to(actual, target_is_directory=True)
            assert agent.is_symlink()
        elif scenario == "ignored-source-member-refused":
            (source / ".gitignore").write_text(".claude/skills/topic/references/\n")
            commit()
            ignored = topic.parent / "references/ignored.md"
            ignored.parent.mkdir()
            ignored.write_text("ignored source must not be attributed\n")
            assert git("status", "--porcelain") == "" and git("check-ignore", str(ignored))
        if seed.get("context") == "home":
            canonical = home / ".pi/agent"
            canonical.parent.mkdir()
            agent.rename(canonical)
            agent, cwd = canonical, home
            skills = agent / "skills"
            ledger = skills / ".cpp-managed/ownership.json"
            installed_topic = skills / "topic/SKILL.md"
            neighbor = skills / "personal/SKILL.md"
            assert skills.is_relative_to(cwd / ".pi")
        before = installed_topic.read_bytes() if installed_topic.exists() else None
        command = [sys.executable, str(gate), operation, "--root", str(source),
                   "--home", str(home), "--agent-dir", str(agent), "--json", *extra]
        child_options = {}
        try:
            if unreadable:
                if os.geteuid() == 0:
                    # Numeric fixture identity only; never consult a real
                    # credential store or follow symlinks while changing owners.
                    for path in [root, *root.rglob("*")]:
                        os.chown(path, 65534, 65534, follow_symlinks=False)
                    child_options = {"user": 65534, "group": 65534, "extra_groups": []}
                command = [sys.executable, "-c", UNREADABLE_EXEC, str(unreadable), *command]
            answer = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True,
                                    timeout=30, **child_options)
        finally:
            if unreadable:
                unreadable.chmod(0o644)
        try:
            assert neighbor.read_bytes() == b"foreign neighbor\n"
            if scenario in ("hand-edited-before-stale", "dual-identity-refused", "foreign-collision"):
                assert installed_topic.read_bytes() == before
            if scenario == "fresh-install":
                assert installed_topic.read_bytes() == dict(packages[0].members)["SKILL.md"]
            if scenario == "adopt-with-backup":
                backups = list((skills / ".cpp-managed/work").glob("transaction-*/backup/topic/SKILL.md"))
                assert len(backups) == 1 and backups[0].read_bytes() == before
            if scenario == "record-only-reconciliation":
                assert installed_topic.read_bytes() == before
                observed_revision = json.loads(ledger.read_bytes())["adapters"]["pi"]["topic"]["revision"]
                assert observed_revision == git("rev-parse", "HEAD")
        except (AssertionError, OSError, KeyError):
            print("CONTROL_ORACLE_FAILED")
            return 9
        try:
            report = json.loads(answer.stdout)
            code = report.get("exit_code", answer.returncode)
            assert code == answer.returncode and code in (0, 1, 4, 5)
        except (ValueError, AssertionError):
            code = 9
    if unreadable:
        print(answer.stderr, end="", file=sys.stderr)
    if code == 9:
        print("CONTROL_PROTOCOL_FAILED", answer.stderr)
        return 9
    print("PI_SKILL_INSTALL:", "current" if code == 0 else "unknown" if code == 4 else "finding", answer.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

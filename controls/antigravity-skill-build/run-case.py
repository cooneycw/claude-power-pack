"""Independent source/installed fixture and real thin-CLI invocation."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def digest(content):
    return hashlib.sha256(content).hexdigest()


def main():
    gate, case = map(Path, sys.argv[1:3])
    if not shutil.which("git"):
        print("AGY_SKILLS: UNAVAILABLE - git missing")
        return 3
    folder = case.parents[1]
    config = json.loads((folder / "cases.json").read_text())
    scenario = json.loads((case / "case.json").read_text())["scenario"]
    with tempfile.TemporaryDirectory(prefix="agy-control-") as temporary:
        root = Path(temporary)
        source, output = root / "source", root / "output"
        source.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

        def git(*args):
            return subprocess.check_output(["git", "-C", str(source), *args], env=env).decode().strip()

        git("init", "-q")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        git("config", "commit.gpgsign", "false")
        git("config", "core.hooksPath", "/dev/null")
        for topic in config["topics"]:
            skill = source / f".claude/skills/{topic}/SKILL.md"
            guide = source / f"docs/skills/{topic}.md"
            skill.parent.mkdir(parents=True)
            guide.parent.mkdir(parents=True, exist_ok=True)
            skill.write_text(f"---\nname: {topic}\ndescription: Fixture topic\n---\nRead `docs/skills/{topic}.md`.\n")
            guide.write_bytes(config["guide"].encode())
        git("add", ".")
        git("commit", "-qm", "control source")
        revision = git("rev-parse", "HEAD")
        records = {}
        # Materialize known expected bytes without invoking the subject's
        # builder or publisher, so a blind anchor cannot fabricate its setup.
        for topic in config["topics"]:
            metadata = {"name": topic, "description": "Fixture topic", "metadata": {
                "source": f"claude-power-pack/.claude/skills/{topic}",
                "cpp": {"schema": 1, "revision": revision, "harness": "antigravity"}}}
            skill = ("---\n" + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True) + "---\n"
                     "\nResolve package-relative guide and script paths from the directory containing this "
                     "SKILL.md, including when the current project is elsewhere.\n\n"
                     f"Read `./references/docs/skills/{topic}.md`.\n").encode()
            members = {"SKILL.md": skill, f"references/docs/skills/{topic}.md": config["guide"].encode()}
            for name, content in members.items():
                path = output / topic / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                path.chmod(0o644)
            records[topic] = {"source": f"claude-power-pack/.claude/skills/{topic}", "revision": revision,
                              "members": {n: {"sha256": digest(c), "mode": 0o644} for n, c in members.items()}}
        ledger = output / ".cpp-managed/ownership.json"
        ledger.parent.mkdir()
        ledger.write_text(json.dumps({"schema": 1, "producer": "claude-power-pack",
                                      "adapters": {"antigravity-build": records}}))
        guide = output / "python-packaging/references/docs/skills/python-packaging.md"
        if scenario == "changed-output":
            guide.write_bytes(b"changed output")
            assert digest(guide.read_bytes()) != records["python-packaging"]["members"][
                "references/docs/skills/python-packaging.md"]["sha256"]
        elif scenario == "removed-package":
            shutil.rmtree(output / "python-packaging")
            assert not (output / "python-packaging").exists()
        elif scenario == "broken-reference":
            guide.unlink()
            assert not guide.exists()
        elif scenario == "unknown-source":
            shutil.rmtree(source / ".git")
            assert not (source / ".git").exists()
        before = {p.relative_to(output).as_posix(): (digest(p.read_bytes()), p.stat().st_mode & 0o777)
                  for p in output.rglob("*") if p.is_file()}
        args = [sys.executable, str(gate), "--check", "--source-root", str(source),
                "--revision", revision, "--output-root", str(output), "--json"]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        after = {p.relative_to(output).as_posix(): (digest(p.read_bytes()), p.stat().st_mode & 0o777)
                 for p in output.rglob("*") if p.is_file()}
        if before != after:
            print("CONTROL_ORACLE: read-only tree changed")
            return 9  # no detector signal: preservation failure is not detection
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

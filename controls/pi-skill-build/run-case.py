#!/usr/bin/env python3
"""Materialize committed opposite inputs; run the actual producer or reader."""
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
from lib.pi_skills import build, write  # noqa: E402


def main() -> int:
    gate, case, reader = Path(sys.argv[1]).absolute(), Path(sys.argv[2]), sys.argv[3]
    scenario = json.loads((case / "case.json").read_text())["scenario"]
    with tempfile.TemporaryDirectory(prefix="pi-control-") as temporary:
        work = Path(temporary)
        source, home = work / "source", work / "home"
        agent = home / ".pi/agent"
        agent.mkdir(parents=True)
        topic = source / ".claude/skills/topic"
        topic.mkdir(parents=True)
        (source / ".claude/commands").mkdir()
        (source / "CLAUDE.md").write_text("# Fixture CPP\n")
        (topic / "SKILL.md").write_text(
            "---\nname: topic\ndescription: Fixture topic\ntrigger: fixture\nmetadata:\n"
            "  provenance:\n    class: cpp-authored\n---\nRead `docs/skills/topic.md`\n"
        )
        guide = source / "docs/skills/topic.md"
        guide.parent.mkdir(parents=True)
        guide.write_text("# Fixture supporting bytes\n")
        expected = build(source)
        output = agent / "skills" if reader == "drift" else work / "build/skills"
        fresh = work / "fresh/skills"
        write(expected, output)
        write(expected, fresh)
        if scenario == "missing":
            member = output / "topic/SKILL.md"
            member.unlink()
            assert not member.exists()
        elif scenario == "marker":
            member = output / "topic/SKILL.md"
            member.write_text(member.read_text().replace("  source:", "  removed:"))
            assert "  source:" not in member.read_text()
        elif scenario == "byte":
            member = output / "topic/references/topic.md"
            member.write_bytes(member.read_bytes() + b"x")
            assert member.read_bytes() != dict(expected[0].members)["references/topic.md"]
        elif scenario == "manifest":
            (topic / "package.json").write_text("{}")
            assert (topic / "package.json").exists()
        elif scenario == "history":
            output = work / "history/skills"
            output.parent.mkdir()
            (agent / "settings.json").write_text(json.dumps({"sessionDir": str(output.parent)}))
            assert output.parent.is_dir()
        elif scenario == "history-under-output":
            history = output / "topic"
            assert history.is_dir() and output in history.parents
            (agent / "settings.json").write_text(json.dumps({"sessionDir": str(history)}))
        elif scenario == "agent-under-output":
            agent = output / "topic"
            assert agent.is_dir() and output in agent.parents
        elif scenario == "source-0664":
            for member in [topic / "SKILL.md", guide]:
                member.chmod(0o664)
                assert member.stat().st_mode & 0o777 == 0o664
        elif scenario == "source-executable":
            member = topic / "SKILL.md"
            member.chmod(0o755)
            assert member.stat().st_mode & 0o111
        elif scenario == "installed-0664":
            member = output / "topic/SKILL.md"
            member.chmod(0o664)
            assert member.stat().st_mode & 0o777 == 0o664
        elif scenario == "unrelated-settings":
            project = work / ".pi"
            project.mkdir()
            (project / "settings.json").write_text("{malformed fixture")
            assert (project / "settings.json").read_text() == "{malformed fixture"
        elif scenario == "unknown":
            shutil.rmtree(source / ".claude/skills")
            assert not (source / ".claude/skills").exists()
        elif scenario != "good":
            raise ValueError("unknown committed scenario")

        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home)}
        if reader == "build":
            argv = [sys.executable, str(gate), "--check", "--root", str(source),
                    "--output-root", str(output), "--agent-dir", str(agent)]
        elif reader == "bundled":
            argv = [sys.executable, str(gate), "--root", str(source),
                    "--bundled-topic-root", str(fresh), "--managed-root", str(output)]
        else:
            if not shutil.which("bash"):
                print("PI_CONTROL: unavailable - bash")
                return 2
            (source / "lib").mkdir()
            (source / "scripts").mkdir()
            shutil.copy2(ROOT / "lib/pi_skills.py", source / "lib/pi_skills.py")
            shutil.copy2(ROOT / "scripts/pi-skill-sync.py", source / "scripts/pi-skill-sync.py")
            env.update(CPP_INSTALL_DRIFT_HOME=str(home), CPP_INSTALL_DRIFT_CHECKOUT=str(source))
            argv = ["bash" if gate.suffix == ".sh" else sys.executable, str(gate), "--json"]
        result = subprocess.run(argv, env=env, cwd=work, capture_output=True, text=True, timeout=15)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    if reader == "drift":
        # This advisory subject exits 0 on drift: read its actual row.
        row = json.loads(result.stdout).get("pi_skills", {})
        state = row.get("fidelity", "unknown")
        print("PI_READER:", state)
        return 0 if state == "matches" and row.get("checked", 0) > 0 else 1
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

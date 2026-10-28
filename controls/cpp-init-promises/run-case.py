#!/usr/bin/env python3
"""Build tiny checkout-shaped cases; use the production population floor."""

import subprocess
import sys
import tempfile
from pathlib import Path


def populate(root: Path, scenario: str) -> None:
    document = root / ".claude/commands/cpp/init.md"
    document.parent.mkdir(parents=True)
    scripts = root / "scripts"
    scripts.mkdir()
    count = 1 if scenario == "bad-near-empty" else 43
    lines = []
    for index in range(count):
        name = f"supplied-{index}.sh"
        (scripts / name).write_text("#!/bin/sh\n")
        lines.append(f'cp "$CPP_DIR/scripts/{name}" /consumer/destination')
    assert len(list(scripts.iterdir())) == count
    missing = scripts / "missing-helper.sh"
    assert not missing.exists(), "known-bad target must actually be absent"
    if scenario == "bad-missing-helper":
        lines.append("Installs: scripts/missing-helper.sh")
    elif scenario == "bad-real-hooks-json":
        (scripts / "hook-mask-output.sh").write_text("# standalone helper, not a registered hook\n")
        assert (scripts / "hook-mask-output.sh").is_file()
        assert not (root / ".claude/hooks.json").exists()
        lines.extend(
            [
                "## Step 4: Disclose",
                "### Tier 2 Disclosure (~/.claude/scripts/)",
                "  - hook-mask-output.sh standalone helper",
                "  To undo:",
                "    rm .claude/hooks.json",
                "## Step 5: Execute",
            ]
        )
    elif scenario == "bad-unclassified":
        lines.append("Installs: chosen-at-runtime")
    elif scenario == "bad-empty":
        lines = []
    elif scenario == "bad-retirement-hides-promise":
        lines.append("Retired scripts/old.sh. Installs scripts/missing-helper.sh")
    elif scenario == "bad-braced-source":
        lines.append('cp "${CPP_DIR}/scripts/missing-helper.sh" /consumer/destination')
    elif scenario == "bad-generation-hides-source":
        lines.append("Installs: scripts/missing-helper.sh (creates a symlink)")
    elif scenario == "bad-source-retirement-comment":
        lines.append('cp "$CPP_DIR/scripts/missing-helper.sh" /consumer/destination # retired predecessor')
    elif scenario == "bad-negative-then-positive":
        lines.append("No longer installs scripts/old.sh now installs scripts/missing-helper.sh")
    elif scenario == "bad-placeholder":
        lines.append("Installs: $CPP_DIR/scripts/<runtime>.sh")
    elif scenario == "bad-escape":
        lines.append("Installs: $CPP_DIR/../outside.sh")
    elif scenario == "good-retirement":
        lines.append("Retired scripts/old.sh; no longer installs scripts/missing-helper.sh")
    elif scenario not in {"good-fixed", "bad-near-empty"}:
        raise ValueError(f"unknown scenario: {scenario}")
    document.write_text("\n".join(lines) + "\n")


def main() -> int:
    gate, case = map(Path, sys.argv[1:])
    scenario = (case / "scenario.txt").read_text().strip()
    with tempfile.TemporaryDirectory(prefix="cpp-init-promises-") as directory:
        root = Path(directory)
        populate(root, scenario)
        return subprocess.run([sys.executable, str(gate), "--root", str(root)], check=False).returncode


if __name__ == "__main__":
    sys.exit(main())

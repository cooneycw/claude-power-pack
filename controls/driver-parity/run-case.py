#!/usr/bin/env python3
"""Materialize owned source fixtures; never edit the checkout under test."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DRIVERS = ("codex", "qwen", "gemma")
EXTRA = "parity-invented-gate.sh"
CALL = f"~/.claude/scripts/{EXTRA} check"


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text() + "\n```bash\n" + text + "\n```\n")


def append_mirror(root: Path, call: str) -> None:
    mirror = root / "codex/skills/flow-auto/SKILL.md"
    append(mirror, call.replace("~/.claude/scripts/", "${CPP_SKILL_DIR:-/dev/null}/scripts/"))
    helper = call.split("scripts/", 1)[1].split()[0]
    (mirror.parent / "scripts" / helper).write_text("# Owned fixture, never executed.\n")


def materialize(root: Path, mode: str) -> None:
    shutil.copytree(Path(__file__).parent / "base-tree", root, dirs_exist_ok=True)
    flow = root / ".claude/commands/flow/auto.md"
    mirror = root / "codex/skills/flow-auto/SKILL.md"
    policy = root / "docs/agents/driver-parity.json"
    data = json.loads(policy.read_text())
    if mode.startswith("closed-"):
        path = root / ".claude/commands/codex/auto.md"
        old = "~/.claude/scripts/flow-plan-record.py approve 42"
        assert old in path.read_text()
        variants = {
            "closed-D-good": old + ' --root "$(git rev-parse --show-toplevel)"',
            "closed-E-bad": "# " + old,
            "closed-E-good": old + " # scripts/comment-only.sh is not code",
            "closed-F-bad": old + "\necho flow-plan-record.py >&2",
            "closed-F-good": old + '\necho "flow-plan-record.py unavailable" >&2',
            "closed-G-bad": "${X}/$(cmd)/scripts/flow-plan-record.py approve 42",
            "closed-G-good": "${X:-/d}/scripts/flow-plan-record.py approve 42",
        }
        path.write_text(path.read_text().replace(old, variants[mode]))
    elif mode == "echo-alias-substitution":
        assert EXTRA not in flow.read_text()
        append(flow, "RUN=~/.claude/scripts/" + EXTRA + '\necho "$("$RUN" check)"')
        append_mirror(root, CALL)
    elif mode in {"echo-substitution", "printf-substitution"}:
        assert EXTRA not in flow.read_text()
        output = 'echo "$(' + CALL + ')"' if mode == "echo-substitution" else "printf '%s' \"$(" + CALL + ')"'
        append(flow, output)
        append_mirror(root, CALL)
    elif mode == "conditional-alias":
        path = root / ".claude/commands/codex/auto.md"
        call = "~/.claude/scripts/flow-plan-record.py approve 42"
        assert call in path.read_text()
        path.write_text(
            path.read_text().replace(
                call, 'REC=~/.claude/scripts/flow-plan-record.py\n[ -f "$REC" ] || REC=echo\n"$REC" approve 42'
            )
        )
    elif mode in {"unsupported-if", "unsupported-env"}:
        assert EXTRA not in flow.read_text()
        call = f"if {CALL}; then\n    :\nfi" if mode == "unsupported-if" else f"env MODE=1 {CALL}"
        append(flow, call)
        append_mirror(root, CALL)
        assert all(CALL not in (root / f".claude/commands/{d}/auto.md").read_text() for d in DRIVERS)
    elif mode == "reassigned-alias":
        path = root / ".claude/commands/codex/auto.md"
        call = "~/.claude/scripts/flow-plan-record.py approve 42"
        assert call in path.read_text()
        path.write_text(
            path.read_text().replace(call, 'REC=~/.claude/scripts/flow-plan-record.py\nREC=echo\n"$REC" approve 42')
        )
        assert call not in path.read_text()
    elif mode == "mirror-entry-point":
        (mirror.parent / "reference.md").write_text(mirror.read_text())
        mirror.write_text("# An unrelated entry point.\n")
    elif mode == "mirror-installed-paths":
        prefix = "${CPP_SKILL_DIR:-/dev/null}/scripts/"
        assert prefix in mirror.read_text()
        mirror.write_text(mirror.read_text().replace(prefix, "~/.claude/scripts/"))
        assert prefix not in mirror.read_text()
    elif mode in {"main-gap", "wrong-verb"}:
        for driver in DRIVERS:
            path = root / f".claude/commands/{driver}/auto.md"
            text = path.read_text()
            assert "~/.claude/scripts/flow-plan-record.py approve 42" in text
            text = text.replace(
                "~/.claude/scripts/flow-plan-record.py approve 42",
                "~/.claude/scripts/flow-plan-record.py drift 42" if mode == "wrong-verb" else "",
            )
            if mode == "main-gap":
                for verb in ("compliance", "reconcile", "read-issue", "begin-run"):
                    call = "~/.claude/scripts/flow-plan-record.py " + verb + " 42"
                    assert call in text
                    text = text.replace(call, "")
            path.write_text(text)
            assert "~/.claude/scripts/flow-plan-record.py approve 42" not in path.read_text()
    elif mode in {"stale-citation", "stale-entry"}:
        if mode == "stale-citation":
            entry = next(e for e in data["entries"] if e["disposition"] == "equivalent")
            entry["citations"][0]["text"] = "This text is not on the cited line."
        else:
            data["entries"].append(
                {
                    "gate": "retired-gate.sh",
                    "driver": "codex",
                    "disposition": "exempt",
                    "reason": "Retired fixture",
                    "issue": "https://github.com/cooneycw/claude-power-pack/issues/1810",
                }
            )
    elif mode != "baseline":
        assert EXTRA not in flow.read_text()
        append(flow, CALL)
        if mode != "mirror-missing":
            append_mirror(root, CALL)
        for driver in DRIVERS:
            path = root / f".claude/commands/{driver}/auto.md"
            run = mode in {"invented-run", "mirror-missing"} or (mode == "one-missing" and driver != "qwen")
            if run:
                append(path, CALL)
            elif mode == "prose-only":
                path.write_text(path.read_text() + f"\n`{EXTRA}` is a prose mention, not a call.\n")
            elif mode == "assignment-only":
                append(path, f"UNUSED=~/.claude/scripts/{EXTRA}")
            else:
                assert CALL not in path.read_text()
            exempt = mode in {"invented-exempt", "missing-issue", "empty-reason"}
            if mode not in {"invented-missing", "invented-run", "one-missing"}:
                entry = {
                    "gate": EXTRA,
                    "driver": driver,
                    "disposition": "exempt" if exempt else "run",
                    "reason": "Owned synthetic gate explicitly covered or waived.",
                    "issue": "https://github.com/cooneycw/claude-power-pack/issues/1810",
                }
                if mode == "missing-issue":
                    entry.pop("issue")
                    assert "issue" not in entry
                if mode == "empty-reason":
                    entry["reason"] = ""
                    assert not entry["reason"]
                data["entries"].append(entry)
    policy.write_text(json.dumps(data, indent=2) + "\n")


def main() -> int:
    case, gate = map(Path, sys.argv[1:])
    mode = json.loads((case / "case.json").read_text())["mode"]
    with tempfile.TemporaryDirectory(prefix="cpp-driver-parity-") as temp:
        root = Path(temp)
        materialize(root, mode)
        result = subprocess.run(
            [sys.executable, str(gate), "--root", str(root)], capture_output=True, text=True, timeout=30
        )
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

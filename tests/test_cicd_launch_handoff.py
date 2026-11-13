"""Inventory every literal lib.cicd launch; target execution cannot lose PATH policy."""
from __future__ import annotations

import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (".claude/commands", "templates", "scripts", ".claude/skills", "codex/skills")
# A known command is classified even when a particular invocation has no work.
TARGET = {"run", "verify", "health", "smoke", "<command>", "dispatcher"}
# check currently parses Makefiles without spawning make. Capture at this target
# query boundary too, so adding a real query cannot quietly restore the leak.
TARGET.add("check")
OTHER = {"detect", "container", "infra-discover", "infra-init", "infra-pipeline", "provider", "pipeline",
         "checks", "host-ci", "doctor-ci", "flow-host", "status", "evidence"}
ASSIGNMENTS = {"CPP_RUNNER_TARGET_PATH=${PATH-}", "CPP_RUNNER_TARGET_PATH_PRESENT=${PATH+x}"}
MATCH = re.compile(r"-m\s+lib\.cicd\b(?P<module>\.[a-z_]+)?(?:[ \t]+(?P<command><command>|[a-z][a-z0-9-]*))?")


def inventory(root: Path) -> list[dict[str, object]]:
    rows = []
    populations = [path for folder in SCAN_ROOTS for path in sorted((root / folder).rglob("*"))]
    extra = root / "docs/reference/flow-auto-rationale.md"
    if extra.is_file():
        populations.append(extra)
    for path in populations:
        if not path.is_file() or path.suffix not in {".md", ".sh", ".py"} or "__pycache__" in path.parts:
            continue
        text = path.read_text()
        lines = text.splitlines()
        for index, line in enumerate(lines):
            found = MATCH.search(line)
            if not found:
                continue
            if len(list(MATCH.finditer(line))) > 1:
                rows.append({"path": str(path.relative_to(root)), "line": index + 1,
                             "command": "multiple", "category": "unknown", "handoff": False,
                             "reason": "separate launch statements before classifying",
                             "error": "multiple module launches on one line require explicit classification"})
                continue
            command = found.group("command")
            module = found.group("module")
            statement = line
            if command is None and "lib.cicd)" in line:
                start = text.rfind("CPP_RUN=(", 0, text.find(line))
                assert start >= 0, f"{path}:{index + 1}: unclassified dispatcher"
                statement = text[start:text.find(line) + len(line)]
                command = "dispatcher"
            else:
                first = index
                while first > 0 and lines[first - 1].rstrip().endswith(chr(92)):
                    first -= 1
                statement = "\n".join(lines[first:index + 1]).replace(chr(92) + "\n", " ")
            lexer = shlex.shlex(statement, posix=True, punctuation_chars=";&|")
            lexer.whitespace_split = True
            tokens = list(lexer) if "uv run" in statement else []
            uv = "uv" in tokens and "run" in tokens
            handed = False
            if uv:
                prefix = tokens[:tokens.index("uv")]
                environments = [i for i, token in enumerate(prefix) if token == "env" or token.endswith("(env")]
                if environments:
                    arguments = prefix[environments[-1] + 1:]
                    handed = ASSIGNMENTS.issubset(set(arguments)) and not any(
                        token and set(token) <= set(";&|") for token in arguments)
            reason = "record/generation or fixed CPP probes; no target-configured step"
            category = "ii"
            error = ""
            if module:
                if module == ".bootstrap" and command == "check":
                    category = "i"
                    reason = "standalone original-PATH wrapper, no CPP uv activation"
                    if uv:
                        error = "bootstrap activation needs explicit policy review"
                elif module == ".bootstrap" and command == "list":
                    reason = "lists configuration only"
                else:
                    error = "unknown lib.cicd submodule"
            elif command in TARGET:
                category = "i"
                reason = "PATH handoff before target execution/query boundary"
                if not handed:
                    # One existing inline direct invocation. Its generated
                    # copy is the same instruction; there is no uv prepend.
                    direct = (str(path.relative_to(root)) in {
                        ".claude/commands/cicd/init.md", "codex/skills/cicd-init/reference.md"}
                        and line.strip() == "1. Run `python3 -m lib.cicd check` to validate against CPP standards")
                    if direct:
                        reason = "inline direct interpreter retains caller PATH; no uv boundary"
                    else:
                        error = "target execution/query launcher lacks exact PATH handoff"
            elif command is None:
                reason = "reference to module/import root, no dispatched subcommand"
            elif command not in OTHER:
                error = "unknown subcommand needs execution/query classification"
            rows.append({"path": str(path.relative_to(root)), "line": index + 1,
                         "command": ((module or "") + " " + (command or "(reference)")).strip(),
                         "category": category, "handoff": handed, "reason": reason, "error": error})
    return rows


def test_all_target_launchers_have_captured_path_policy() -> None:
    rows = inventory(ROOT)
    assert len(rows) >= 40, "the inventory must not pass after scanning no source population"
    assert all(any(str(row["path"]).startswith(folder + "/") for row in rows) for folder in SCAN_ROOTS[:-1])
    failures = [row for row in rows if row["error"]]
    assert not failures, failures


def test_committed_missing_handoff_case_is_red_and_repaired_case_is_green(tmp_path: Path) -> None:
    fixture = ROOT / "tests/fixtures/cicd_launch_handoff"
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    source.write_text((fixture / "bad-missing.md").read_text())
    bad = inventory(tmp_path)
    assert len(bad) == 1 and "lacks exact PATH handoff" in str(bad[0]["error"])
    source.write_text((fixture / "good.md").read_text())
    good = inventory(tmp_path)
    assert len(good) == 1 and not good[0]["error"]
    source.write_text((fixture / "bad-unclassified.md").read_text())
    unknown = inventory(tmp_path)
    assert len(unknown) == 1 and "unknown subcommand" in str(unknown[0]["error"])


def test_metadata_mentions_and_multiple_commands_are_not_a_handoff(tmp_path: Path) -> None:
    fixture = ROOT / "tests/fixtures/cicd_launch_handoff"
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    for name in ("bad-metadata-echo.md", "bad-multiple.md"):
        source.write_text((fixture / name).read_text())
        rows = inventory(tmp_path)
        assert rows and any(row["error"] for row in rows), name


INVENTORY_BEGIN = "<!-- launch-inventory:begin -->"
INVENTORY_END = "<!-- launch-inventory:end -->"


def render_inventory(rows: list[dict[str, object]]) -> str:
    lines = ["| Source:line | Subcommand | Class | Policy | Basis |",
             "| --- | --- | --- | --- | --- |"]
    for row in rows:
        policy = "captured" if row["handoff"] else "direct/no prepend" if row["category"] == "i" else "not required"
        lines.append(f"| `{row['path']}:{row['line']}` | `{row['command']}` | "
                     f"{row['category']} | {policy} | {row['reason']} |")
    return "\n".join(lines)


def test_committed_inventory_matches_the_actual_source_and_generated_population() -> None:
    document = (ROOT / "docs/measurements/runner-target-path-1801.md").read_text()
    recorded = document.split(INVENTORY_BEGIN, 1)[1].split(INVENTORY_END, 1)[0].strip()
    assert recorded == render_inventory(inventory(ROOT)), (
        "regenerate Codex mirrors and update the explicit launch inventory after source changes")

"""Inventory Python module and direct lib/cicd file launches in the source roots."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shlex
from pathlib import Path

import pytest

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
PYTHON_INVOKER = (
    r'''(?:"(?:[^"\n]*/)?python[0-9.]*"|'(?:[^'\n]*/)?python[0-9.]*'|'''
    r"\bpython[0-9.]*|[\"']?\$(?:[A-Z_]*PYTHON[A-Z_]*|\{[A-Z_]*PYTHON[A-Z_]*\})[\"']?)")
FILE_ARGUMENT = r'''(?:"[^"]*lib/cicd/[^"]+\.py"|'[^']*lib/cicd/[^']+\.py'|[^\s"';&|]*lib/cicd/[^\s"';&|]+\.py)'''
FILE_END = r"(?=$|[ \t;|&)`])"
FILE_MATCH = re.compile(
    PYTHON_INVOKER + r"\s+(?:(?:-B|-E|-I|-O|-OO|-P|-s|-S|-u)\s+)*"
    + rf"(?P<file>{FILE_ARGUMENT})" + FILE_END
    + r"(?:[ \t]+(?P<command><command>|[a-z][a-z0-9-]*))?")
FILE_MODULE = re.compile(r"(?:^|/)lib/cicd/(?P<module>.+)\.py$")
OPAQUE_FILE_INVOKER = re.compile(
    r"[\"']?\$(?:\{[A-Za-z_]\w*\}|[A-Za-z_]\w*)[\"']?\s+" + FILE_ARGUMENT + FILE_END)
UNSUPPORTED_FILE_INVOKER = re.compile(PYTHON_INVOKER + r"\s+-[^\n;&|]*?\s+" + FILE_ARGUMENT + FILE_END)

# Opaque Python module expressions cannot be classified from text. Refuse them
# rather than silently omitting a potentially target-running lib.cicd launch.
DYNAMIC_MODULE = re.compile(
    r"(?:\bpython[0-9.]*|[\"']?\$(?:[A-Z_]*PYTHON[A-Z_]*|\{[A-Z_]*PYTHON[A-Z_]*\})[\"']?)"
    r"\s+(?:-[A-Z]\s+)*-m\s+[^\s;|&]*\$[^\s;|&]*")


def direct_uv_python(tokens: list[str], file_token: str | None = None) -> bool:
    """Only reviewed direct uv/Python forms may carry a credited handoff."""
    terminal = file_token if file_token is not None else "-m"
    if "uv" not in tokens or terminal not in tokens:
        return False
    command = tokens[tokens.index("uv"):tokens.index(terminal)]
    if command[:2] != ["uv", "run"] or command[-1:] not in (["python"], ["python3"]):
        return False
    options = command[2:-1]
    seen = set()
    while options:
        option, *options = options
        if option in seen:
            return False
        seen.add(option)
        if option == "--no-python-downloads":
            continue
        if option not in {"--project", "--python"} or not options:
            return False
        value, *options = options
        if not value or value.startswith("-"):
            return False
        if option == "--python" and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value):
            return False
    return True


def statements(text: str) -> list[tuple[int, str]]:
    """Join shell continuations before looking for a module invocation."""
    result = []
    pending = ""
    start = 1
    for number, line in enumerate(text.splitlines(), 1):
        if not pending:
            start = number
        if line.rstrip().endswith(chr(92)):
            pending += line.rstrip()[:-1] + " "
        else:
            result.append((start, pending + line))
            pending = ""
    if pending:
        result.append((start, pending))
    return result


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
        for number, line in statements(text):
            if DYNAMIC_MODULE.search(line):
                rows.append({"path": str(path.relative_to(root)), "line": number,
                             "command": "(constructed module)", "category": "unknown", "handoff": False,
                             "reason": "replace opaque module expressions with explicit module launches",
                             "error": "variable-built Python module needs explicit execution/query classification"})
                continue
            launches: list[tuple[re.Match[str], str | None, str | None]] = [
                (match, match.group("module"), None) for match in MATCH.finditer(line)]
            opaque_file = False
            recognized_file = False
            for match in FILE_MATCH.finditer(line):
                filename = match.group("file").strip("\"'")
                name = FILE_MODULE.search(filename)
                if name is None:
                    continue
                recognized_file = True
                if "$" in name.group("module"):
                    opaque_file = True
                    continue
                relative = name.group("module").replace("/", ".")
                module = None if relative == "__main__" else "." + relative
                launches.append((match, module, filename))
            unsupported_file = (not recognized_file
                                and (UNSUPPORTED_FILE_INVOKER.search(line) is not None
                                     or OPAQUE_FILE_INVOKER.search(line) is not None))
            if opaque_file or unsupported_file:
                rows.append({"path": str(path.relative_to(root)), "line": number,
                             "command": "(constructed file)", "category": "unknown", "handoff": False,
                             "reason": "replace opaque or unsupported checker file expressions with audited launches",
                             "error": "Python file invocation needs explicit execution/query classification"})
                continue
            if not launches:
                continue
            if len(launches) > 1:
                rows.append({"path": str(path.relative_to(root)), "line": number,
                             "command": "multiple", "category": "unknown", "handoff": False,
                             "reason": "separate launch statements before classifying",
                             "error": "multiple module launches on one line require explicit classification"})
                continue
            found, module, file_token = launches[0]
            command = found.group("command")
            statement = line
            if command is None and "lib.cicd)" in line:
                start = text.rfind("CPP_RUN=(", 0, text.find(line))
                assert start >= 0, f"{path}:{number}: unclassified dispatcher"
                statement = text[start:text.find(line) + len(line)]
                command = "dispatcher"
            lexer = shlex.shlex(statement, posix=True, punctuation_chars=";&|")
            lexer.whitespace_split = True
            tokens = list(lexer) if "uv run" in statement else []
            # A preceding command's env is unrelated to this module launch.
            # Bind the matched module to its own shell simple-command segment.
            module_tokens = [i for i, token in enumerate(tokens)
                             if token.startswith("lib.cicd") or (file_token is not None and token == file_token)]
            if module_tokens:
                launch = module_tokens[-1]
                boundaries = [i for i, token in enumerate(tokens[:launch])
                              if token and set(token) <= set(";&|")]
                if boundaries:
                    tokens = tokens[boundaries[-1] + 1:]
            uv = "uv" in tokens and "run" in tokens
            handed = False
            if uv:
                prefix = tokens[:tokens.index("uv")]
                environments = [i for i, token in enumerate(prefix) if token == "env" or token.endswith("(env")]
                if environments:
                    arguments = prefix[environments[-1] + 1:]
                    # The existing verify lane unsets only this uv selector.
                    if arguments[:2] == ["-u", "UV_PROJECT_ENVIRONMENT"]:
                        arguments = arguments[2:]
                    allowed = ASSIGNMENTS | {
                        "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT-}",
                        "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT_PRESENT=${UV_PROJECT_ENVIRONMENT+x}",
                    }
                    handed = (ASSIGNMENTS.issubset(set(arguments))
                              and len(arguments) == len(set(arguments))
                              and set(arguments) <= allowed and direct_uv_python(tokens, file_token))
            reason = "record/generation or fixed CPP probes; no target-configured step"
            category = "ii"
            error = ""
            if command is None and re.match(r"\s+[\"']?\$", line[found.end():]):
                error = "variable-built subcommand needs explicit execution/query classification"
            elif module:
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
            rows.append({"path": str(path.relative_to(root)), "line": number,
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
    lines = ["| Source | Subcommand | Class | Policy | Basis |",
             "| --- | --- | --- | --- | --- |"]
    for row in rows:
        policy = "captured" if row["handoff"] else "direct/no prepend" if row["category"] == "i" else "not required"
        lines.append(f"| `{row['path']}` | `{row['command']}` | "
                     f"{row['category']} | {policy} | {row['reason']} |")
    return "\n".join(lines)


def assert_committed_inventory_matches(root: Path, scan=inventory) -> None:
    document = (root / "docs/measurements/runner-target-path-1801.md").read_text()
    recorded = document.split(INVENTORY_BEGIN, 1)[1].split(INVENTORY_END, 1)[0].strip()
    assert recorded == render_inventory(scan(root)), (
        "regenerate Codex mirrors and update the explicit launch inventory after source changes")


def test_committed_inventory_matches_the_actual_source_and_generated_population() -> None:
    assert_committed_inventory_matches(ROOT)


def test_unrecorded_direct_file_launch_is_not_invisible() -> None:
    fixture = ROOT / "tests/fixtures/cicd_launch_handoff/direct-file-inventory"
    case = fixture / "bad-extra-direct-file"
    source = (case / ".claude/commands/owned.md").read_text()
    assert 'python3 "$CPP_ROOT/lib/cicd/bootstrap.py" check' in source, "construct an extra direct-file launch"
    rows = inventory(case)
    assert len(rows) == 2, "the direct-file launch must be visible alongside the original module launch"
    with pytest.raises(AssertionError):
        assert_committed_inventory_matches(case)


def test_unchanged_scanner_anchor_misses_extra_direct_file_and_agrees_on_good() -> None:
    fixture = ROOT / "tests/fixtures/cicd_launch_handoff/direct-file-inventory"
    path = fixture / "anchors/5609227b-module-only.py"
    provenance = json.loads((fixture / "anchors/provenance.txt").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance["sha256"]
    spec = importlib.util.spec_from_file_location("module_only_inventory", path)
    assert spec and spec.loader
    anchor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(anchor)
    for name in ["bad-extra-direct-file", "good-module-only"]:
        case = fixture / name
        assert_committed_inventory_matches(case, anchor.inventory)
    good = fixture / "good-module-only"
    assert_committed_inventory_matches(good)


def test_recording_the_extra_file_launch_repairs_the_inventory(tmp_path: Path) -> None:
    source = ROOT / "tests/fixtures/cicd_launch_handoff/direct-file-inventory/bad-extra-direct-file"
    import shutil
    shutil.copytree(source, tmp_path / "repo")
    case = tmp_path / "repo"
    with pytest.raises(AssertionError):
        assert_committed_inventory_matches(case)
    document = case / "docs/measurements/runner-target-path-1801.md"
    document.write_text(INVENTORY_BEGIN + "\n" + render_inventory(inventory(case)) + "\n" + INVENTORY_END)
    assert_committed_inventory_matches(case)


@pytest.mark.parametrize("line,command,category", [
    ('python3 "$CPP_ROOT/lib/cicd/bootstrap.py" list', ".bootstrap list", "ii"),
    ('python3 lib/cicd/bootstrap.py check', ".bootstrap check", "i"),
    ('"/tmp/owned venv/bin/python3" "/tmp/CPP checkout/lib/cicd/bootstrap.py" check', ".bootstrap check", "i"),
    ('"$CPP_RUNNER_PYTHON" "$ROOT/lib/cicd/bootstrap.py" check', ".bootstrap check", "i"),
    ('python3 -S "$ROOT/lib/cicd/bootstrap.py" check', ".bootstrap check", "i"),
])
def test_direct_file_bootstrap_uses_existing_classification(
    tmp_path: Path, line: str, command: str, category: str,
) -> None:
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    source.write_text(line + "\n")
    rows = inventory(tmp_path)
    assert len(rows) == 1 and not rows[0]["error"]
    assert rows[0]["command"] == command and rows[0]["category"] == category
    assert rows[0]["handoff"] is False


@pytest.mark.parametrize("line", [
    'python3 "$ROOT/lib/cicd/${MODULE}.py" check',
    'python3 "$ROOT/lib/cicd/bootstrap.py" "$COMMAND"',
    'python3 "$ROOT/lib/cicd/unclassified.py" check',
    'python3 "$ROOT/lib/cicd/nested/unclassified.py" check',
    'python3 -X dev "$ROOT/lib/cicd/bootstrap.py" check',
    '"$P" "$ROOT/lib/cicd/bootstrap.py" check',
    'uv run python "$ROOT/lib/cicd/bootstrap.py" check',
    'python3 -m lib.cicd.bootstrap list; python3 "$ROOT/lib/cicd/bootstrap.py" check',
])
def test_unclassified_or_activated_file_launch_is_not_clean(tmp_path: Path, line: str) -> None:
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    source.write_text(line + "\n")
    rows = inventory(tmp_path)
    assert rows and any(row["error"] for row in rows)


def test_file_main_handoff_still_belongs_to_its_own_simple_command(tmp_path: Path) -> None:
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    prefix = 'env CPP_RUNNER_TARGET_PATH="${PATH-}" CPP_RUNNER_TARGET_PATH_PRESENT="${PATH+x}" '
    launch = 'uv run --project "$ROOT" python "$ROOT/lib/cicd/__main__.py" run'
    source.write_text(prefix + launch + "\n")
    good = inventory(tmp_path)
    assert len(good) == 1 and good[0]["handoff"] and not good[0]["error"]
    source.write_text(prefix + 'echo metadata; ' + launch + "\n")
    bad = inventory(tmp_path)
    assert len(bad) == 1 and not bad[0]["handoff"] and bad[0]["error"]


def test_a_file_existence_probe_is_not_a_direct_launch(tmp_path: Path) -> None:
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    source.write_text('if [ -n "$CPP_DIR" ] && [ -f "$CPP_DIR/lib/cicd/__init__.py" ]; then\n')
    assert inventory(tmp_path) == []
    source.write_text(source.read_text() + 'python3 "$CPP_DIR/lib/cicd/bootstrap.py" list\n')
    rows = inventory(tmp_path)
    assert len(rows) == 1 and rows[0]["command"] == ".bootstrap list"


@pytest.mark.parametrize("name", ["bad-split.md", "bad-variable.md", "bad-variable-command.md"])
def test_split_and_constructed_module_launches_cannot_evade_inventory(tmp_path: Path, name: str) -> None:
    fixture = ROOT / "tests/fixtures/cicd_launch_handoff"
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    statement = (fixture / name).read_text()
    assert "uv run" in statement and "-m" in statement
    source.write_text(statement)
    rows = inventory(tmp_path)
    assert rows and any(row["error"] for row in rows), name
    source.write_text((fixture / "good-split.md").read_text())
    rows = inventory(tmp_path)
    assert len(rows) == 1 and not rows[0]["error"]


def test_inventory_identity_survives_unrelated_line_shifts(tmp_path: Path) -> None:
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    statement = (ROOT / "tests/fixtures/cicd_launch_handoff/good.md").read_text()
    source.write_text(statement)
    before = inventory(tmp_path)
    source.write_text("An unrelated introductory paragraph.\n\n" + statement)
    after = inventory(tmp_path)
    assert before[0]["line"] != after[0]["line"]
    assert render_inventory(before) == render_inventory(after)
    source.write_text(statement + statement)
    assert render_inventory(inventory(tmp_path)) != render_inventory(before)


@pytest.mark.parametrize("separator", [";", "&&", "||", "|"])
def test_handoff_belongs_to_the_module_launch_command(tmp_path: Path, separator: str) -> None:
    fixture = ROOT / "tests/fixtures/cicd_launch_handoff"
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    source.write_text((fixture / "bad-earlier-uv.md").read_text().replace(";", separator))
    bad = inventory(tmp_path)
    assert len(bad) == 1 and bad[0]["error"]
    source.write_text((fixture / "good-earlier-uv.md").read_text().replace(";", separator))
    good = inventory(tmp_path)
    assert len(good) == 1 and not good[0]["error"]


@pytest.mark.parametrize("name", ["bad-inner-env.md", "bad-outer-env-unset.md", "bad-overwritten-record.md"])
def test_environment_wrappers_cannot_strip_or_replace_captured_policy(tmp_path: Path, name: str) -> None:
    fixture = ROOT / "tests/fixtures/cicd_launch_handoff"
    source = tmp_path / ".claude/commands/owned.md"
    source.parent.mkdir(parents=True)
    statement = (fixture / name).read_text()
    assert "CPP_RUNNER_TARGET_PATH=${PATH-}" in statement and "uv run" in statement
    source.write_text(statement)
    bad = inventory(tmp_path)
    assert len(bad) == 1 and bad[0]["error"]
    source.write_text((fixture / "good.md").read_text())
    good = inventory(tmp_path)
    assert len(good) == 1 and not good[0]["error"]

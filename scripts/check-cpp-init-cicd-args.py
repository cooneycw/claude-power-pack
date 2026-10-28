#!/usr/bin/env python3
"""Parse literal cpp:init/helper lib.cicd launchers without dispatching commands.

The input is the command document and statically referenced CPP helpers. Bash
statements are tokenized with shlex; unsupported module-launch shapes fail by
name. Shell values use stable representative strings, not environment values.
This checks argument syntax, not runtime values, command behavior or side effects.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import io
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: NEGATIVE-CONTROL: controls/cpp-init-cicd-args
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.cicd.cli import create_parser  # noqa: E402

DOCUMENT = ".claude/commands/cpp/init.md"
MIN_INVOCATIONS = 5
MODULE = "lib.cicd"
MODULE_HINT = re.compile(r"(?:(?<![\w.])lib\.cicd|(?<![\w.])-mlib\.cicd)(?![\w.])")
EXPANSION = re.compile(r"\$(?:[A-Za-z_]\w*|\{[A-Za-z_]\w*\})")
REFERENCE = re.compile(r"(?:\$\{?CPP_DIR\}?|\$\{?HOME\}?/\.claude|~/.claude|\$\{?SCRIPT_DIR\}?)/scripts/([\w.-]+)")
HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?")
PYTHON = re.compile(r"python(?:\d+(?:\.\d+)*)?")


@dataclass
class Invocation:
    path: str
    line: int
    argv: list[str]


@dataclass
class Report:
    invocations: list[Invocation] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    files: set[str] = field(default_factory=set)
    parsed: int = 0


def shell_lines(text: str, markdown: bool):
    """Yield logical shell statements, skipping heredoc data and comments."""
    active = not markdown
    heredoc = ""
    pending = ""
    start = 0
    for number, line in enumerate(text.splitlines(), 1):
        if heredoc:
            if line.lstrip("\t") == heredoc:
                heredoc = ""
            continue
        if markdown and re.fullmatch(r"\s*```(?:bash|sh)?\s*", line):
            active = line.strip() in {"```bash", "```sh"}
            continue
        if not active:
            if re.search(r"\bpython[\d.]*\s+-m\s+lib\.cicd\b", line):
                yield number, line, False
            continue
        if not pending and (not line.strip() or line.lstrip().startswith("#")):
            continue
        if not pending:
            start = number
        pending += line[:-1] + " " if line.endswith("\\") else line
        if line.endswith("\\"):
            continue
        yield start, pending, True
        match = HEREDOC.search(pending)
        if match:
            heredoc = match[1]
        pending = ""
    if pending:
        yield start, pending, False


CONTROL = "\0CPP_CONTROL:"
REDIRECT = "\0CPP_REDIRECT:"
DOLLAR = "\0CPP_LITERAL_DOLLAR"
TICK = "\0CPP_LITERAL_TICK"


def tokens(statement: str) -> list[str]:
    """Mark only unquoted operators, then let shlex parse shell words."""
    if "\0" in statement:
        raise ValueError("NUL in shell source")
    marked = []
    quote = ""
    braces = 0
    index = 0
    redirections = ("&>>", "<<<", "<<-", "&>", ">>", "<<", ">&", "<&", ">|", ">", "<")
    controls = ("&&", "||", ";", "|", "(", ")", "&")
    while index < len(statement):
        char = statement[index]
        if quote == "'":
            if char == "'":
                quote = ""
            marked.append(DOLLAR if char == "$" else TICK if char == "`" else char)
            index += 1
            continue
        if char == "\\" and index + 1 < len(statement):
            following = statement[index + 1]
            if following in "$`":
                marked.append(DOLLAR if following == "$" else TICK)
            else:
                marked.append(char + following)
            index += 2
            continue
        if quote == '"':
            marked.append(char)
            if char == '"':
                quote = ""
            index += 1
            continue
        if char in "'\"":
            quote = char
            marked.append(char)
            index += 1
            continue
        if statement.startswith("${", index):
            braces += 1
            marked.append("${")
            index += 2
            continue
        if braces:
            marked.append(char)
            if char == "}":
                braces -= 1
            index += 1
            continue
        if char == "#" and (index == 0 or statement[index - 1].isspace() or statement[index - 1] in ";|&()"):
            break
        operator = next((value for value in redirections if statement.startswith(value, index)), None)
        if operator:
            # An adjacent numeric word is an IO descriptor, not a CLI value.
            marked = [re.sub(r"(?<!\S)\d+$", "", "".join(marked))]
            marked.append(" " + REDIRECT + operator + " ")
        else:
            operator = next((value for value in controls if statement.startswith(value, index)), None)
            if operator:
                marked.append(" " + CONTROL + operator + " ")
        if operator:
            index += len(operator)
        else:
            marked.append(char)
            index += 1
    return shlex.split("".join(marked), comments=False, posix=True)


def actions(parser, command):
    for action in parser._actions:
        yield action
        if isinstance(action, argparse._SubParsersAction) and command in action.choices:
            yield from action.choices[command]._actions


def normalize(argv: list[str], parser) -> list[str]:
    options = {
        option: action for action in actions(parser, argv[0] if argv else "")
        for option in action.option_strings
    }
    result = []
    for index, value in enumerate(argv):
        if "`" in value:
            raise ValueError("unsupported command substitution in argv")
        if "$" not in value:
            result.append(value.replace(DOLLAR, "$").replace(TICK, "`"))
            continue
        option, separator, inline = value.partition("=")
        previous = option if separator and option.startswith("-") else argv[index - 1] if index else ""
        action = options.get(previous)
        candidate = inline if separator and option.startswith("-") else value
        if index == 0 or value.startswith("$") and action is None:
            raise ValueError("dynamic command/argument bundle is unrecognized")
        representative = str(next(iter(action.choices))) if action and action.choices else "1"
        replaced = EXPANSION.sub(representative, candidate)
        if "$" in replaced or "`" in replaced:
            raise ValueError("unsupported shell expansion in argv")
        normalized = option + "=" + replaced if separator and option.startswith("-") else replaced
        result.append(normalized.replace(DOLLAR, "$").replace(TICK, "`"))
    return result


def inspect_statement(report: Report, path: str, number: int, statement: str, supported: bool) -> None:
    if not MODULE_HINT.search(statement):
        return
    location = f"{path}:{number}"
    if not supported:
        report.findings.append(f"{location}: unrecognized invocation outside a supported shell statement")
        return
    try:
        words = tokens(statement)
    except ValueError:
        report.findings.append(f"{location}: unrecognized shell quoting")
        return
    if not any(MODULE_HINT.search(word) for word in words):
        return  # A trailing comment was removed; it is not a launcher.
    positions = [i for i, word in enumerate(words) if word == MODULE]
    if not positions:
        # Literal echo/printf text is not an executable module launcher.
        if re.match(r"\s*(?:echo|printf)\b", statement) and "$(" not in statement:
            return
        report.findings.append(f"{location}: unrecognized lib.cicd invocation shape")
        return
    for index in positions:
        prefix = words[:max(0, index - 2)]
        boundary = max((i for i, word in enumerate(prefix) if word.startswith(CONTROL)), default=-1)
        program = prefix[boundary + 1:]
        while program and program[0] in {"if", "then", "else", "do", "!"}:
            program.pop(0)
        if program and program[0] in {"echo", "printf"} and "$(" not in statement:
            continue
        if index < 2 or words[index - 1] != "-m" or not PYTHON.fullmatch(Path(words[index - 2]).name):
            report.findings.append(f"{location}: unrecognized lib.cicd launcher")
            continue
        tail = words[index + 1:]
        argv = []
        cursor = 0
        malformed = False
        while cursor < len(tail):
            word = tail[cursor]
            if word.startswith(CONTROL):
                break
            if word.startswith(REDIRECT):
                if cursor + 1 == len(tail) or tail[cursor + 1].startswith((CONTROL, REDIRECT)):
                    malformed = True
                    break
                cursor += 2  # Redirection and its target are not CLI arguments.
            else:
                argv.append(word)
                cursor += 1
        if malformed:
            report.findings.append(f"{location}: unrecognized shell redirection")
            continue
        report.invocations.append(Invocation(path, number, argv))
        parser = create_parser()
        try:
            normalized = normalize(argv, parser)
        except ValueError as error:
            report.findings.append(f"{location}: {error}")
            continue
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                parser.parse_args(normalized)
        except SystemExit as error:
            if error.code == 0:
                reason = "early parser exit; full argv unverified (help is unsupported)"
            else:
                # Do not print supplied values or parser diagnostics, which can contain credentials.
                reason = "arguments rejected by real lib.cicd parser"
            report.findings.append(f"{location}: {reason}")
        else:
            report.parsed += 1


def inspect_python(report, path, text):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        report.findings.append(f"{path}: unrecognized Python helper syntax")
        return
    handled = set()
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        for argument in call.args:
            if isinstance(argument, (ast.List, ast.Tuple)):
                values = [n.value for n in argument.elts if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                if MODULE not in values or "-m" not in values:
                    continue
                handled.update(id(n) for n in ast.walk(argument) if isinstance(n, ast.Constant))
                if len(values) != len(argument.elts):
                    report.findings.append(f"{path}:{argument.lineno}: unrecognized dynamic Python argv builder")
                else:
                    inspect_statement(report, path, argument.lineno, shlex.join(values), True)
            elif isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                if re.search(r"\bpython[\d.]*\s+-m\s+lib\.cicd\b", argument.value):
                    handled.add(id(argument))
                    inspect_statement(report, path, argument.lineno, argument.value, True)
                elif argument.value == MODULE and (
                    isinstance(call.func, ast.Name) and call.func.id == "__import__"
                    or isinstance(call.func, ast.Attribute) and call.func.attr == "import_module"
                ):
                    handled.add(id(argument))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == MODULE and id(node) not in handled:
            report.findings.append(f"{path}:{node.lineno}: unrecognized Python lib.cicd invocation builder")


def scan(root: Path, minimum: int = MIN_INVOCATIONS) -> Report:
    report = Report()
    queue = [DOCUMENT]
    while queue:
        path = queue.pop(0)
        if path in report.files:
            continue
        report.files.add(path)
        target = root / path
        try:
            if not target.resolve().is_relative_to(root.resolve()):
                raise ValueError("helper escapes source root")
            text = target.read_text()
        except (OSError, ValueError) as error:
            report.findings.append(f"{path}: unreadable population ({type(error).__name__})")
            continue
        if target.suffix == ".py":
            inspect_python(report, path, text)
            continue
        for number, statement, supported in shell_lines(text, path.endswith(".md")):
            inspect_statement(report, path, number, statement, supported)
            # Inspect literal CPP helper references, including copy/registration
            # operands. This is a conservative superset of direct helper calls.
            for match in REFERENCE.finditer(statement):
                helper = "scripts/" + match[1]
                if helper not in report.files and helper not in queue:
                    queue.append(helper)
    if len(report.invocations) < minimum:
        report.findings.append(f"population {len(report.invocations)} below measured floor {minimum}")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    report = scan(args.root)
    for finding in report.findings:
        print("CICD_ARGV_FINDING: " + finding)
    counts = (f"{report.parsed}/{len(report.invocations)} invocations parsed; floor {MIN_INVOCATIONS}; "
              f"{len(report.files)} source files examined")
    if report.findings:
        print(f"cpp-init-cicd-args: fail - {len(report.findings)} finding(s); {counts}")
        return 1
    print(f"cpp-init-cicd-args: ok - {counts}; syntax only, no command handlers executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

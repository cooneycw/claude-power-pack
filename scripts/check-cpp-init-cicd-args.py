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
VARIABLE_PATH = re.compile(r"^\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))/(.+)$")
SCRIPT_DIRECTORY = re.compile(
    r'^\s*([A-Za-z_]\w*)="\$\(\s*cd(?:\s+(?:--|-P))?\s+'
    r'"\$\(dirname(?:\s+--)?\s+"\$\{BASH_SOURCE\[0\]\}"\)"\s*&&\s*pwd(?:\s+-P)?\s*\)"\s*$'
)
PARENT_DIRECTORY = re.compile(r'^\s*([A-Za-z_]\w*)="\$\(dirname\s+"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))"\)"\s*$')
SOURCE_ERROR = "\0CPP_SOURCE_ERROR:"
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


def continues(statement: str) -> bool:
    """Only an unescaped backslash outside single quotes removes a newline."""
    quote = ""
    index = 0
    while index < len(statement):
        char = statement[index]
        if quote == "'":
            if char == "'":
                quote = ""
            index += 1
            continue
        if char == "\\":
            if index + 1 == len(statement):
                return True
            index += 2
            continue
        if char in "'\"":
            if not quote:
                quote = char
            elif quote == char:
                quote = ""
        if not quote and char == "#" and (
            index == 0 or statement[index - 1].isspace() or statement[index - 1] in ";|&()"
        ):
            return False
        index += 1
    return False


def shell_lines(text: str, markdown: bool):
    """Yield shell units; only real, unquoted heredoc operators open data."""
    active = not markdown
    heredocs = []
    pending = ""
    start = 0
    for number, line in enumerate(text.splitlines(), 1):
        fence = markdown and re.fullmatch(r"\s*```(?:bash|sh)?\s*", line)
        if heredocs:
            if fence:
                yield start, SOURCE_ERROR + "unterminated heredoc in shell block", False
                heredocs = []
                active = line.strip() in {"```bash", "```sh"}
            else:
                delimiter, strip_tabs = heredocs[0]
                if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                    heredocs.pop(0)
            continue
        if fence:
            if pending:
                yield start, SOURCE_ERROR + "unfinished continued shell statement", False
                pending = ""
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
        combined = pending + line
        if continues(combined):
            pending = combined[:-1]
            continue
        pending = combined
        yield start, pending, True
        try:
            words = tokens(pending)
        except ValueError:
            words = []  # The invocation/helper readers report relevant unsupported quoting.
        for index, word in enumerate(words):
            if word in {REDIRECT + "<<", REDIRECT + "<<-"}:
                if index + 1 == len(words):
                    yield start, SOURCE_ERROR + "heredoc delimiter missing", False
                else:
                    delimiter = words[index + 1].replace(DOLLAR, "$").replace(TICK, "`")
                    heredocs.append((delimiter, word.endswith("<<-")))
        pending = ""
    if pending:
        yield start, SOURCE_ERROR + "unfinished continued shell statement", False
    if heredocs:
        yield start, SOURCE_ERROR + "unterminated heredoc", False


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
    location = f"{path}:{number}"
    if statement.startswith(SOURCE_ERROR):
        report.findings.append(f"{location}: {statement[len(SOURCE_ERROR):]}")
        return
    if not MODULE_HINT.search(statement):
        return
    if not supported:
        report.findings.append(f"{location}: unrecognized invocation outside a supported shell statement")
        return
    try:
        words = tokens(statement)
    except ValueError:
        report.findings.append(f"{location}: unrecognized shell quoting")
        return
    segment = []
    for word in words + [CONTROL + ";"]:
        if word.startswith(CONTROL):
            inspect_command(report, path, number, segment)
            segment = []
        else:
            segment.append(word)


def inspect_command(report, path, number, words):
    location = f"{path}:{number}"
    if not any(MODULE_HINT.search(word) for word in words):
        return
    program = words[:]
    while program and (program[0] in {"if", "then", "else", "do", "!", "{"}
                       or re.match(r"^[A-Za-z_]\w*=", program[0])):
        program.pop(0)
    if program and program[0] in {"echo", "printf"} and not any("$(" in word for word in words):
        return
    positions = [i for i, word in enumerate(words) if word == MODULE]
    if not positions:
        report.findings.append(f"{location}: unrecognized lib.cicd invocation shape")
        return
    launchers = [i for i in positions if i >= 2 and words[i - 1] == "-m"
                 and PYTHON.fullmatch(Path(words[i - 2]).name)]
    if not launchers:
        report.findings.append(f"{location}: unrecognized lib.cicd launcher")
        return
    # Later occurrences are argv data; the real parser decides their validity.
    for index in launchers[:1]:
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
    docstrings = set()
    for scope in ast.walk(tree):
        if isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if scope.body and isinstance(scope.body[0], ast.Expr):
                docstrings.add(id(scope.body[0].value))
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
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in handled or id(node) in docstrings:
                continue
            if MODULE_HINT.search(node.value):
                report.findings.append(f"{path}:{node.lineno}: unrecognized Python lib.cicd invocation builder")


def helper_references(report, path, number, statement, bindings):
    if path != DOCUMENT:
        directory = SCRIPT_DIRECTORY.fullmatch(statement)
        parent = PARENT_DIRECTORY.fullmatch(statement)
        if directory:
            bindings[directory[1]] = Path(path).parent
        elif parent and (parent[2] or parent[3]) in bindings:
            bindings[parent[1]] = bindings[parent[2] or parent[3]].parent
        else:
            assignment = re.match(r"\s*([A-Za-z_]\w*)=", statement)
            if assignment and assignment[1] not in {"CPP_DIR", "HOME"}:
                bindings.pop(assignment[1], None)
    try:
        words = tokens(statement)
    except ValueError:
        if "/scripts/" in statement:
            report.findings.append(f"{path}:{number}: unrecognized helper-reference quoting")
        return
    for index, word in enumerate(words):
        prefix = words[:index]
        boundary = max((i for i, value in enumerate(prefix) if value.startswith(CONTROL)), default=-1)
        prefix = prefix[boundary + 1:]
        while prefix and (prefix[0] in {"if", "then", "else", "do", "!", "{"}
                          or re.match(r"^[A-Za-z_]\w*=", prefix[0])):
            prefix.pop(0)
        metadata = prefix and prefix[0] in {"echo", "printf", "[", "[[", "test", "for", "case"}
        runners = {"bash", "sh", "python", "python3", "exec"}
        runner = max((i for i, value in enumerate(prefix) if Path(value).name in runners), default=-1)
        callee = not metadata and (not prefix or runner >= 0 and all(v.startswith("-") for v in prefix[runner + 1:]))
        assignment = re.match(r"^[A-Za-z_]\w*=", word)
        if assignment:
            callee = False
        if re.match(r"^[A-Za-z_]\w*=", word):
            word = word.partition("=")[2]
        if word.startswith("~/"):
            name, suffix = "HOME", word[2:]
        else:
            match = VARIABLE_PATH.fullmatch(word)
            if not match:
                if callee and word.startswith("$") and "/scripts/" in word:
                    report.findings.append(f"{path}:{number}: unrecognized helper-root expansion")
                continue
            name, suffix = match[1] or match[2], match[3]
        target = None
        if name == "CPP_DIR" and suffix.startswith("scripts/"):
            target = Path(suffix)
        elif name == "HOME" and suffix.startswith(".claude/scripts/"):
            target = Path("scripts") / suffix.removeprefix(".claude/scripts/")
        elif name in bindings:
            target = bindings[name] / suffix
        elif callee and ("scripts/" in suffix or name in {"SCRIPT_DIR", "SCRIPTS_DIR"}):
            report.findings.append(f"{path}:{number}: unrecognized helper root {name}")
        if target is None or target.as_posix() == "scripts":
            continue
        if any(c in str(target) for c in "$*?[]"):
            if callee:
                report.findings.append(f"{path}:{number}: unrecognized dynamic helper path")
            continue
        yield target.as_posix()


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
        bindings = {}
        for number, statement, supported in shell_lines(text, path.endswith(".md")):
            inspect_statement(report, path, number, statement, supported)
            # Read literal CPP/helper-directory references, including non-call
            # operands; this conservatively exceeds the direct helper-call set.
            for helper in helper_references(report, path, number, statement, bindings):
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
    without_launches = report.files - {i.path for i in report.invocations} - {DOCUMENT}
    print(f"cpp-init-cicd-args: ok - {counts}; {len(without_launches)} helper sources reached without literal "
          "module launches; syntax only, no command handlers executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compare documented driver helper/plan-record-verb membership (#1810).

This checks command text, not live execution, flags, ordering, or the semantic
truth of an owner-approved equivalence. Missing/unreadable/ambiguous inputs are
UNKNOWN, never a smaller clean inventory. The 23-item floor is an anti-vacuity
guard, not the population: new calls are derived from flow:auto automatically.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
from pathlib import Path

#: NEGATIVE-CONTROL: controls/driver-parity

FLOW = ".claude/commands/flow/auto.md"
POLICY = "docs/agents/driver-parity.json"
DRIVERS = ("codex", "qwen", "gemma")
VERBS = frozenset({"approve", "compliance"})
FLOOR = 23
HELPER = re.compile(r"(?:^|/)scripts/([\w-]+\.(?:py|sh))$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})([^`~]*)$")
ISSUE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/issues/[1-9]\d*$")
NONRUN = re.compile(r"^(?:examples?\b|do not (?:run|execute)\b|wrong\b|forbidden\b|bad example\b)", re.I)


class Unknown(ValueError):
    """The input population could not be established."""


class Invalid(ValueError):
    """A policy input positively violates its contract."""


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise Unknown(f"cannot read {path}: {type(exc).__name__}") from exc


def compound_shell(text: str) -> bool:
    """Conservatively refuse unquoted shell chains; never lose a later call."""
    quote = ""
    escaped = False
    # Angle placeholders in the command docs are data, not shell pipelines.
    text = re.sub(r"<[^<>]+>", "", text)
    for character in text:
        if escaped:
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif quote:
            if character == quote:
                quote = ""
        elif character in {"'", '"'}:
            quote = character
        elif character in ";&|":
            return True
    return False


def strip_comments(text: str) -> str:
    """Shell comments start at an unquoted word boundary, on this line only."""
    quote = ""
    escaped = False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif quote:
            if character == quote:
                quote = ""
        elif character in {"'", '"'}:
            quote = character
        elif character == "#" and (index == 0 or text[index - 1].isspace() or text[index - 1] in ";&|()"):
            return text[:index]
    return text


def helper_mentions(text: str, helpers: set[str], aliases: dict[str, tuple[str, str] | None]) -> bool:
    return (
        bool(re.search(r"scripts/[\w-]+\.(?:py|sh)", text))
        or any(re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text) for name in helpers)
        or any(re.search(r"\$\{?" + re.escape(key) + r"(?!\w)", text) for key in aliases)
    )


def mask_substitutions(text: str, helpers: set[str], aliases: dict[str, tuple[str, str] | None]) -> str:
    """Non-helper substitutions are irrelevant argument data; helper ones are UNKNOWN.

    Keep single-quoted text literal. Do not use this masked text to validate an
    executable path: even a non-helper substitution is forbidden in that path.
    """
    result = ""
    quote = ""
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and quote != "'" and index + 1 < len(text):
            result += text[index : index + 2]
            index += 2
            continue
        if char == "'" and quote != '"':
            quote = "" if quote else "'"
        elif char == '"' and quote != "'":
            quote = "" if quote else '"'
        if quote != "'" and (text.startswith("$(", index) or char == "`"):
            backtick = char == "`"
            start = index + (1 if backtick else 2)
            end = start
            depth = 1
            inner_quote = ""
            while end < len(text):
                current = text[end]
                if current == "\\" and inner_quote != "'":
                    end += 2
                    continue
                if backtick and current == "`":
                    break
                if current in {"'", '"'}:
                    if not inner_quote:
                        inner_quote = current
                    elif inner_quote == current:
                        inner_quote = ""
                elif not inner_quote and not backtick:
                    if current == "(":
                        depth += 1
                    elif current == ")":
                        depth -= 1
                        if depth == 0:
                            break
                end += 1
            if end == len(text):
                raise Unknown("unclosed command substitution")
            if helper_mentions(text[start:end], helpers, aliases):
                raise Unknown("helper token inside command substitution")
            result += "SUBSTITUTION"
            index = end + 1
            continue
        result += char
        index += 1
    return result


def literal_path(value: str) -> re.Match[str] | None:
    """Closed literal segments/parameter expansions ending in a literal helper."""
    if any(marker in value for marker in ("$(", "`", "*", "?", "[", "]")):
        return None
    remainder = re.sub(r"\$\{[A-Za-z_]\w*(?::-[^{}$`]*|)\}|\$[A-Za-z_]\w*", "ENV", value)
    if any(character in remainder for character in "$(){}"):
        return None
    return HELPER.search(value)


def probe_operands(text: str) -> list[str] | None:
    """Closed non-executing file/string tests and location probes."""
    if any(marker in text for marker in ("$(", "`", "<(", ">(")):
        return None
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    words = list(lexer)
    if words[:1] == ["if"]:
        words = words[1:]
        if words[-2:] == [";", "then"]:
            words = words[:-2]
    if words[:1] == ["!"]:
        words = words[1:]
    groups: list[list[str]] = [[]]
    for word in words:
        if word in {"&&", "||"}:
            groups.append([])
        else:
            groups[-1].append(word)
    operands = []
    for group in groups:
        if group and group[0] in {"[", "[["}:
            closing = "]" if group[0] == "[" else "]]"
            if group[-1:] != [closing]:
                return None
            body = group[1:-1]
        elif group[:1] == ["test"]:
            body = group[1:]
        elif len(group) == 3 and group[:2] in [["command", "-v"], ["type", "-P"]]:
            operands.append(group[2])
            continue
        elif len(group) == 2 and group[0] == "which":
            operands.append(group[1])
            continue
        else:
            return None
        if body[:1] == ["!"]:
            body = body[1:]
        if len(body) != 2:
            return None
        operand = body[1]
        if body[0] in {"-n", "-z"}:
            if not (
                re.search(r"[\"']\$(?:[A-Za-z_]\w*|\{[A-Za-z_]\w*\})[\"']", text)
                and re.fullmatch(r"\$(?:[A-Za-z_]\w*|\{[A-Za-z_]\w*\})", operand)
            ):
                return None
        elif body[0] not in {"-d", "-e", "-f", "-r", "-s", "-x", "-L"}:
            return None
        operands.append(operand)
    return operands


def literal_output(text: str, helpers: set[str]) -> bool:
    """A quoted NOTE may name a helper but cannot execute one."""
    if not re.match(r"^(?:echo|printf)\s", text) or any(x in text for x in ("<(", ">(")):
        return False
    if compound_shell(re.sub(r">&[0-9]+", "", text)):
        return False
    outside = re.sub(r""""(?:[^"\\]|\\.)*"|'[^']*' """.strip(), "", text)
    if re.search(r"scripts/[\w-]+\.(?:py|sh)", outside):
        return False
    return not any(re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", outside) for name in helpers)


def command(
    text: str,
    aliases: dict[str, tuple[str, str] | None],
    *,
    helper_names: set[str],
    assigned: set[str],
    cleared: set[str],
    nonexecuting: list[tuple[str, str]],
) -> tuple[str, str, str] | None:
    """Deny unclassified helper tokens; preserve closed same-helper alias paths."""
    original = strip_comments(text).strip()
    stripped = mask_substitutions(original, helper_names, aliases)
    writes = set(re.findall(r"\b([A-Za-z_]\w*)=", stripped))
    empty = re.fullmatch(r"([A-Za-z_]\w*)=(?:\"\"|'')?", stripped)
    if empty:
        key = empty[1]
        cleared.add(key)
        assigned.add(key)
        prior = aliases.get(key)
        if prior:
            nonexecuting.append((prior[0], "empty alias clear; historical same-helper identity retained"))
        return None
    # Closed existing missing-helper branch: literal NOTE followed by a clear.
    branch = re.fullmatch(r"\[\s+-f\s+([^\]]+)\]\s*\|\|\s*\{\s*(.+)\s*\}", stripped)
    if branch:
        note_operand = shlex.split(branch[1])
        clear = re.fullmatch(r"(.+);\s*([A-Za-z_]\w*)=(?:\"\"|'')?;\s*", branch[2])
        if len(note_operand) == 1 and clear and note_operand[0].startswith("$"):
            key = note_operand[0].removeprefix("$").strip("{}")
            if key == clear[2] and literal_output(clear[1], helper_names | set(aliases)):
                cleared.add(key)
                prior = aliases.get(key)
                if prior:
                    nonexecuting.append((prior[0], "literal missing-helper NOTE and empty alias clear"))
                return None
    mentions = helper_mentions(stripped, helper_names, aliases)
    if (
        mentions
        and re.search(r"'[^']*\$[^']*'", stripped)
        and not literal_output(stripped, helper_names | set(aliases))
    ):
        raise Unknown("single-quoted parameter text is not an environment path")
    fallback = shlex.split(stripped, comments=False) if "||" in stripped else []
    if len(fallback) == 6 and fallback[0] == "[" and fallback[1] in {"-f", "-x", "-e"} and fallback[3:5] == ["]", "||"]:
        assignment = re.fullmatch(r"([A-Za-z_]\w*)=(.*)", fallback[5])
        key = fallback[2].removeprefix("$").strip("{}")
        if assignment and fallback[2].startswith("$") and assignment[1] == key and key in aliases:
            current = aliases[key]
            if assignment[2] == "":
                cleared.add(key)
                if current:
                    nonexecuting.append((current[0], "conditional empty alias clear"))
                return None
            target = literal_path(assignment[2])
            if (
                current is None
                or target is None
                or target[1] != current[0]
                or any(c in assignment[2] for c in ("$(", "`"))
            ):
                raise Unknown(f"fallback alias is not a literal path to the same helper: {key}")
            nonexecuting.append((current[0], "same-helper fallback path resolution"))
            return None
    if (
        stripped != original
        and mentions
        and (
            re.match(r"^[A-Za-z_]\w*=", stripped)
            or re.search(r"^\s*(?:(?:python3?|bash|sh)\s+)?[^\s]*SUBSTITUTION[^\s]*/scripts/", stripped)
        )
    ):
        raise Unknown("command substitution in helper path/assignment")
    reassigned = writes & set(aliases)
    if reassigned:
        single = shlex.split(stripped, comments=False)
        assignment = re.fullmatch(r"([A-Za-z_]\w*)=(.*)", single[0]) if len(single) == 1 else None
        target = literal_path(assignment[2]) if assignment else None
        key = assignment[1] if assignment else ""
        current = aliases.get(key)
        if (
            assignment
            and target
            and current
            and target[1] == current[0]
            and not any(c in assignment[2] for c in ("$(", "`"))
        ):
            aliases[key] = (target[1], assignment[2])
            nonexecuting.append((target[1], "same-helper literal path reassignment"))
            return None
        raise Unknown("helper alias reassigned/conditionally assigned: " + ", ".join(sorted(reassigned)))
    if mentions:
        operands = probe_operands(stripped)
        if operands is not None:
            for operand in operands:
                target = HELPER.search(operand)
                alias = aliases.get(operand.removeprefix("$").strip("{}")) if operand.startswith("$") else None
                names = (
                    {target[1]}
                    if target
                    else {alias[0]}
                    if alias
                    else {name for name in helper_names if name in operand}
                )
                nonexecuting.extend((name, "existence/location probe") for name in sorted(names))
            return None
    if mentions and literal_output(stripped, helper_names | set(aliases)):
        nonexecuting.extend((name, "quoted literal output") for name in sorted(helper_names) if name in stripped)
        return None
    if re.match(r"^(?:unset|read|local|declare|typeset|export|readonly)\b", stripped):
        if any(re.search(r"\b" + re.escape(key) + r"\b", stripped) for key in aliases):
            raise Unknown("helper alias modified outside a plain literal assignment")
    if not mentions:
        assigned.update(writes)
        return None
    try:
        words = shlex.split(stripped, comments=False)
    except ValueError as exc:
        raise Unknown("unparseable helper-bearing command") from exc
    assignment = re.fullmatch(r"([A-Za-z_]\w*)=(.*)", words[0]) if len(words) == 1 else None
    if assignment and not compound_shell(stripped) and "$(" not in stripped and "`" not in stripped:
        key, value = assignment.groups()
        match = literal_path(value)
        if match and (key not in assigned or key in cleared):
            aliases[key] = (match.group(1), value)
            assigned.add(key)
            nonexecuting.append((match[1], "literal alias binding"))
            return None
    assigned.update(writes)
    if compound_shell(stripped) or "$(" in stripped or "`" in stripped or "<(" in stripped or ">(" in stripped:
        raise Unknown("helper token in a non-plain shell construct")
    if words and words[0] in {"bash", "sh", "python", "python3"}:
        words.pop(0)
    if not words:
        raise Unknown("helper token without a plain command")
    token = words.pop(0)
    match = literal_path(token)
    if match:
        name, address = match.group(1), token
    elif token.startswith("$") and token.removeprefix("$").strip("{}") in aliases:
        alias = aliases[token.removeprefix("$").strip("{}")]
        if alias is None:
            raise Unknown("helper alias has no single literal identity")
        name, address = alias
    else:
        raise Unknown("helper token outside a plain command position")
    if any(re.search(r"(?<![\w-])" + re.escape(other) + r"(?![\w-])", " ".join(words)) for other in helper_names):
        raise Unknown("helper token in command arguments")
    return name, words[0] if words else "", address


def inventory(
    text: str,
    *,
    bundled_exempt: set[str] | None = None,
    bundled_helpers: set[str] | None = None,
    bundled_gates: set[str] | None = None,
    helper_names: set[str] | None = None,
    nonexecuting: list[dict[str, object]] | None = None,
    source: str = "document",
) -> dict[str, list[int]]:
    """Derive calls inside Instructions, retaining their physical source lines."""
    found: dict[str, list[int]] = {}
    helper_names = set(helper_names or ()) | set(re.findall(r"scripts/([\w-]+\.(?:py|sh))", text))
    assigned: set[str] = set()
    cleared: set[str] = set()
    aliases: dict[str, tuple[str, str] | None] = {}
    active = False
    fence: tuple[str, str, bool] | None = None
    excluded_heading: int | None = None
    excluded_next = False
    continuation = ""
    continuation_line = 0
    heredoc = ""

    def add(value: str, line: int) -> None:
        observed: list[tuple[str, str]] = []
        try:
            result = command(
                value, aliases, helper_names=helper_names, assigned=assigned, cleared=cleared, nonexecuting=observed
            )
        except ValueError as exc:
            raise Unknown(f"{source}:{line}: {exc}") from exc
        if nonexecuting is not None:
            nonexecuting.extend(
                {"source": source, "line": line, "helper": name, "kind": kind} for name, kind in observed
            )
        if result:
            name, verb, address = result
            if name == "flow-plan-record.py" and not re.fullmatch(r"[a-z][a-z0-9-]*", verb):
                raise Unknown("plan-record invocation has no unambiguous verb")
            key = f"{name} {verb}" if name == "flow-plan-record.py" else name
            if bundled_exempt is not None:
                bundled = re.fullmatch(r"\$\{CPP_SKILL_DIR(?::-[^}]*)?\}/scripts/[\w-]+\.(?:py|sh)", address)
                checkout_only = name in bundled_exempt and address == "scripts/" + name
                if (bundled or checkout_only) and bundled_gates is not None:
                    bundled_gates.add(key)
                if bundled and bundled_helpers is not None:
                    bundled_helpers.add(name)
            found.setdefault(key, []).append(line)

    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        marker = FENCE.match(line)
        if marker:
            ticks, language = marker.groups()
            if fence is None:
                fence = (ticks, language.strip(), excluded_heading is not None or excluded_next)
            elif ticks[0] == fence[0][0] and len(ticks) >= len(fence[0]):
                if continuation or heredoc:
                    raise Unknown("unfinished shell continuation/heredoc")
                fence = None
            continue
        if fence is not None:
            if not active or fence[2]:
                continue
            if fence[1] not in {"bash", "sh", "shell"}:
                if re.search(r"scripts/[\w-]+\.(?:py|sh)", line):
                    raise Unknown("helper reference in unsupported fenced language")
                continue
            if heredoc:
                if helper_mentions(line, helper_names, aliases):
                    raise Unknown(f"{source}:{number}: helper token in heredoc body")
                if stripped == heredoc:
                    heredoc = ""
                continue
            if not continuation:
                continuation_line = number
            stripped = strip_comments(line).strip()
            continuation += stripped.removesuffix("\\") + " "
            if stripped.endswith("\\"):
                continue
            add(continuation.strip(), continuation_line)
            match = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", continuation)
            heredoc = match.group(1) if match else ""
            continuation = ""
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level, title = len(heading[1]), heading[2]
            if title == "Instructions":
                active = True
            if excluded_heading is not None and level <= excluded_heading:
                excluded_heading = None
            if NONRUN.match(title.replace("*", "")):
                excluded_heading = level
            excluded_next = False
        elif stripped:
            excluded_next = bool(NONRUN.match(stripped.replace("*", "")))
        if active and excluded_heading is None and not excluded_next:
            for span in re.finditer(r"(?<!`)`([^`]+)`(?!`)", line):
                before = line[: span.start()]
                imperative = re.search(
                    r"\b(?:run|invoke|execute|call)(?:\s+(?:it|this|helper|exactly|bare|now|both|then|the))*\s+$",
                    before,
                    re.I,
                )
                conditional = re.match(r"^\s*-?\s*If\b", before, re.I) and "," in before
                # Argument-bearing citations and exit-127 fallback references
                # remain prose, not primary commands in the generated skill.
                if imperative or conditional:
                    add(span[1], number)
    if fence is not None or continuation or heredoc:
        raise Unknown("unclosed fenced command block")
    if not active:
        raise Unknown("no Instructions section")
    return found


def pairs_unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise Invalid(f"duplicate JSON key {key}")
        result[key] = value
    return result


def safe_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise Invalid("citation path must be repository-relative")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise Invalid("citation escapes repository")
    return path


def policies(root: Path, gates: set[str]) -> dict[tuple[str, str], dict]:
    try:
        data = json.loads(read(root / POLICY), object_pairs_hook=pairs_unique)
    except json.JSONDecodeError as exc:
        raise Invalid("parity table is not valid JSON") from exc
    if (
        not isinstance(data, dict)
        or set(data) != {"schema", "entries"}
        or (type(data["schema"]) is not int or data["schema"] != 1)
        or not isinstance(data["entries"], list)
    ):
        raise Invalid("parity table must have schema1 and entries")
    result = {}
    for entry in data["entries"]:
        required = {"gate", "driver", "disposition", "reason", "issue"}
        if isinstance(entry, dict) and "issue" not in entry:
            raise Invalid("missing issue link in parity entry")
        if not isinstance(entry, dict) or not required <= set(entry) or set(entry) - required - {"citations"}:
            raise Invalid("invalid parity entry fields")
        gate, driver, disposition = entry["gate"], entry["driver"], entry["disposition"]
        if not isinstance(gate, str) or gate not in gates:
            raise Invalid(f"stale/unknown gate entry {gate!r}")
        if (
            not isinstance(driver, str)
            or driver not in DRIVERS
            or not isinstance(disposition, str)
            or disposition not in {"run", "equivalent", "exempt"}
        ):
            raise Invalid("unknown driver or disposition")
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise Invalid(f"empty reason: {driver} {gate}")
        if not isinstance(entry["issue"], str) or not ISSUE.fullmatch(entry["issue"]):
            raise Invalid(f"missing/invalid issue link: {driver} {gate}")
        if gate in {f"flow-plan-record.py {verb}" for verb in VERBS} and disposition != "run":
            raise Invalid(f"never exemptable/equivalent: {driver} {gate}")
        citations = entry.get("citations", [])
        if not isinstance(citations, list) or (disposition == "equivalent" and not citations):
            raise Invalid("equivalent requires citations")
        if disposition == "equivalent" and not any(
            isinstance(c, dict) and c.get("file") == f".claude/commands/{driver}/auto.md" for c in citations
        ):
            raise Invalid("equivalent must cite its driver step")
        for citation in citations:
            if not isinstance(citation, dict) or set(citation) != {"file", "line", "text"}:
                raise Invalid("invalid citation fields")
            path = safe_path(root, citation["file"])
            number, expected = citation["line"], citation["text"]
            lines = read(path).splitlines()
            if (
                type(number) is not int
                or number < 1
                or number > len(lines)
                or not isinstance(expected, str)
                or not expected.strip()
                or expected not in lines[number - 1]
            ):
                raise Invalid(f"stale citation: {citation['file']}:{number}")
        key = (gate, driver)
        if key in result:
            raise Invalid(f"duplicate gate/driver pair {key}")
        result[key] = entry
    return result


def unpackaged(root: Path) -> set[str]:
    try:
        declared = ast.parse(read(root / "scripts/delegated-core-vendor.py"))
        drivers = next(
            ast.literal_eval(node.value)
            for node in declared.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "DRIVERS" for target in node.targets)
        )
        if tuple(drivers) != DRIVERS:
            raise Unknown("declared driver population changed; review surfaces")
        tree = ast.parse(read(root / "scripts/codex-skill-sync.py"))
        values = {}
        for node in tree.body:
            target = (
                node.target
                if isinstance(node, ast.AnnAssign)
                else node.targets[0]
                if isinstance(node, ast.Assign) and len(node.targets) == 1
                else None
            )
            if isinstance(target, ast.Name) and target.id in {
                "FAMILIES",
                "UNPACKAGED_FAMILIES",
                "CPP_CHECKOUT_RELATIVE_REFS",
            }:
                values[target.id] = ast.literal_eval(node.value)
        if not set(DRIVERS) <= set(values["UNPACKAGED_FAMILIES"]) or set(DRIVERS) & set(values["FAMILIES"]):
            raise Unknown("delegated mirror packaging policy changed; review surfaces")
        exceptions = values["CPP_CHECKOUT_RELATIVE_REFS"]
        if not isinstance(exceptions, (list, tuple)) or any(
            not isinstance(entry, (list, tuple))
            or len(entry) != 4
            or any(not isinstance(field, str) for field in entry)
            for entry in exceptions
        ):
            raise Unknown("cannot establish checkout-only helper exceptions")
        return {entry[1] for entry in exceptions if entry[0] == "flow/auto.md"}
    except (SyntaxError, ValueError, TypeError, KeyError, StopIteration) as exc:
        raise Unknown("cannot establish delegated mirror packaging policy") from exc


def evaluate(
    root: Path, generated: Path, *, nonexecuting: list[dict[str, object]] | None = None
) -> tuple[list[str], int]:
    derived = inventory(read(root / FLOW), source=FLOW, nonexecuting=nonexecuting)
    gates = set(derived)
    if len(derived) < FLOOR or not {f"flow-plan-record.py {v}" for v in VERBS} <= set(derived):
        raise Unknown(f"implausible inventory: {len(derived)} items (floor {FLOOR})")
    table = policies(root, set(derived))
    bundled_exempt = unpackaged(root)
    missing = []
    for driver in DRIVERS:
        actual = inventory(
            read(root / f".claude/commands/{driver}/auto.md"),
            helper_names={key.split()[0] for key in gates},
            source=f".claude/commands/{driver}/auto.md",
            nonexecuting=nonexecuting,
        )
        for gate in sorted(gates):
            entry = table.get((gate, driver))
            if (entry is None or entry["disposition"] == "run") and gate not in actual:
                missing.append(f"driver={driver} gate={gate}")
    for driver in DRIVERS:
        if (generated / f"{driver}-auto").exists():
            raise Unknown(f"unexpected packaged delegated mirror: {driver}")
    skill = generated / "flow-auto"
    primary = skill / "SKILL.md"
    entrypoint = read(primary)
    reference = skill / "reference.md"
    if reference.exists():
        if not re.search(r"Read\s+`reference\.md`\s+in this skill directory for the complete", entrypoint):
            raise Invalid("generated entry point does not direct the reader to its procedure")
        body = read(reference)
    else:
        body = entrypoint
    bundled_helpers: set[str] = set()
    bundled_gates: set[str] = set()
    rendered = inventory(
        body,
        bundled_exempt=bundled_exempt,
        bundled_helpers=bundled_helpers,
        bundled_gates=bundled_gates,
        source="generated-flow-auto",
        nonexecuting=nonexecuting,
    )
    if set(rendered) - bundled_gates:
        raise Invalid(
            "generated helper/verb has no invoked skill-bundled primary address: "
            + ", ".join(sorted(set(rendered) - bundled_gates))
        )
    for gate in sorted(gates - set(rendered)):
        missing.append(f"driver=generated-flow-auto gate={gate}")
    for name in sorted(bundled_helpers):
        if not (skill / "scripts" / name).is_file():
            raise Unknown(f"missing bundled helper {name}")
    return missing, len(gates)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--generated-root", type=Path)
    args = parser.parse_args(argv)
    events: list[dict[str, object]] = []

    def emit_nonexecuting() -> None:
        for event in events:
            print(
                f"DRIVER_PARITY_NON_EXECUTING: {event['source']}:{event['line']} "
                f"helper={event['helper']} kind={event['kind']}"
            )

    try:
        missing, count = evaluate(args.root, args.generated_root or args.root / "codex/skills", nonexecuting=events)
    except Unknown as exc:
        emit_nonexecuting()
        print(f"DRIVER_PARITY: unknown - {exc}")
        return 2
    except Invalid as exc:
        emit_nonexecuting()
        print(f"DRIVER_PARITY: fail - {exc}")
        return 1
    emit_nonexecuting()
    print("DRIVER_PARITY_SCOPE: helper/plan-record-verb membership; not flags, ordering or live execution")
    print("DRIVER_PARITY_MIRRORS: flow-auto checked; codex-auto/qwen-auto/gemma-auto intentionally unpackaged")
    for problem in missing:
        print(f"DRIVER_PARITY_MISSING: {problem}")
    print(
        f"DRIVER_PARITY: {'fail' if missing else 'ok'} - {count} items, "
        f"{count * len(DRIVERS)} canonical pairs, {len(missing)} missing"
    )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

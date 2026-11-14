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


def command(text: str, aliases: dict[str, str]) -> tuple[str, str] | None:
    """A documented command position; never execute or expand shell input."""
    stripped = text.strip()
    if not stripped or stripped.startswith("#"):
        return None
    plausible = re.match(r"(?:[\w]+=[^ ]|(?:bash|sh|python3?)\s|[\"']?(?:[~$./]|scripts/)|echo\s|printf\s)", stripped)
    if plausible and re.search(r"scripts/[\w-]+\.(?:py|sh)", stripped) and compound_shell(stripped):
        raise Unknown("compound helper command requires explicit inventory parsing")
    if stripped.startswith(("echo ", "printf ")):
        return None
    # Only parse plausible command/assignment positions. Shell block delimiters,
    # prose and conditions are not commands merely because they name a helper.
    if not re.match(r"(?:[\w]+=[^ ]|(?:bash|sh|python3?)\s|[\"']?(?:[~$./]|scripts/))", stripped):
        return None
    try:
        words = shlex.split(stripped, comments=True)
    except ValueError as exc:
        raise Unknown("unparseable documented shell command") from exc
    if not words:
        return None
    while words and re.match(r"^[A-Za-z_]\w*=", words[0]):
        key, value = words.pop(0).split("=", 1)
        match = HELPER.search(value)
        if match:
            aliases[key] = match.group(1)
    if words and words[0] in {"bash", "sh", "python", "python3"}:
        words.pop(0)
    if not words:
        return None
    token = words.pop(0)
    match = HELPER.search(token)
    name = (
        match.group(1) if match else aliases.get(token.removeprefix("$").strip("{}")) if token.startswith("$") else None
    )
    if not name:
        if re.search(r"scripts/[\w-]+\.(?:py|sh)", token):
            raise Unknown("unparseable helper command token")
        return None
    return name, words[0] if words else ""


def inventory(text: str) -> dict[str, list[int]]:
    """Derive calls inside Instructions, retaining their physical source lines."""
    found: dict[str, list[int]] = {}
    aliases: dict[str, str] = {}
    active = False
    fence: tuple[str, str, bool] | None = None
    excluded_heading: int | None = None
    excluded_next = False
    continuation = ""
    continuation_line = 0
    heredoc = ""

    def add(value: str, line: int) -> None:
        result = command(value, aliases)
        if result:
            name, verb = result
            if name == "flow-plan-record.py" and not re.fullmatch(r"[a-z][a-z0-9-]*", verb):
                raise Unknown("plan-record invocation has no unambiguous verb")
            key = f"{name} {verb}" if name == "flow-plan-record.py" else name
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
            if not active or fence[1] not in {"bash", "sh", "shell"} or fence[2]:
                continue
            if heredoc:
                if stripped == heredoc:
                    heredoc = ""
                continue
            if not continuation:
                continuation_line = number
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
            for inline in re.findall(r"(?<!`)`([^`]+)`(?!`)", line):
                # A path alone is a prose citation. Commands with arguments, or
                # a path explicitly introduced by Run/Invoke, are instructions.
                if " " in inline or re.search(r"\b(?:run|invoke)\s+`", line, re.I):
                    add(inline, number)
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


def unpackaged(root: Path) -> None:
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
            if isinstance(target, ast.Name) and target.id in {"FAMILIES", "UNPACKAGED_FAMILIES"}:
                values[target.id] = ast.literal_eval(node.value)
        if not set(DRIVERS) <= set(values["UNPACKAGED_FAMILIES"]) or set(DRIVERS) & set(values["FAMILIES"]):
            raise Unknown("delegated mirror packaging policy changed; review surfaces")
    except (SyntaxError, ValueError, TypeError, KeyError, StopIteration) as exc:
        raise Unknown("cannot establish delegated mirror packaging policy") from exc


def evaluate(root: Path, generated: Path) -> tuple[list[str], int]:
    derived = inventory(read(root / FLOW))
    gates = set(derived)
    if len(derived) < FLOOR or not {f"flow-plan-record.py {v}" for v in VERBS} <= set(derived):
        raise Unknown(f"implausible inventory: {len(derived)} items (floor {FLOOR})")
    table = policies(root, set(derived))
    unpackaged(root)
    missing = []
    for driver in DRIVERS:
        actual = inventory(read(root / f".claude/commands/{driver}/auto.md"))
        for gate in sorted(gates):
            entry = table.get((gate, driver))
            if (entry is None or entry["disposition"] == "run") and gate not in actual:
                missing.append(f"driver={driver} gate={gate}")
    for driver in DRIVERS:
        if (generated / f"{driver}-auto").exists():
            raise Unknown(f"unexpected packaged delegated mirror: {driver}")
    skill = generated / "flow-auto"
    primary = skill / "SKILL.md"
    read(primary)  # A reference without its skill entry point is not packaged.
    reference = skill / "reference.md"
    rendered = inventory(read(reference if reference.exists() else primary))
    for gate in sorted(gates - set(rendered)):
        missing.append(f"driver=generated-flow-auto gate={gate}")
    # Require the helpers actually addressed through the skill's bundled path.
    for match in re.finditer(
        r"\$\{CPP_SKILL_DIR[^}]*\}/scripts/([\w-]+\.(?:py|sh))", read(reference if reference.exists() else primary)
    ):
        if not (skill / "scripts" / match.group(1)).is_file():
            raise Unknown(f"missing bundled helper {match.group(1)}")
    return missing, len(gates)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--generated-root", type=Path)
    args = parser.parse_args(argv)
    try:
        missing, count = evaluate(args.root, args.generated_root or args.root / "codex/skills")
    except Unknown as exc:
        print(f"DRIVER_PARITY: unknown - {exc}")
        return 2
    except Invalid as exc:
        print(f"DRIVER_PARITY: fail - {exc}")
        return 1
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

#!/usr/bin/env python3
"""Resolve CPP-supplied installation promises in cpp:init (#1587).

The population is derived from disclosure entries, explicit Installs/Links
statements, checkout source references and installed helper/command paths.
Generated project files, consumer configuration and external dependencies are
classified and reported, not checked against this checkout. Retirement clauses
are historical references, not installation promises. Unknown promise shapes
and a population below the measured floor FAIL; they never mean clean.

This checks supplied paths, not registration, execution or generated content.
No list of promised assets is maintained separately from the document.
"""

from __future__ import annotations

import argparse
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

#: NEGATIVE-CONTROL: controls/cpp-init-promises

DOCUMENT = ".claude/commands/cpp/init.md"
# Measured on the fixed #1587 document: 43 distinct source expressions.
# An intentional retirement must update this floor deliberately.
MIN_PROMISES = 43
SOURCE = re.compile(r"(\$CPP_DIR|\$\{CPP_DIR[^}]*\}|\{CPP_DIR\})[\"']?/([^\s`\"'();,]+)")
HOME = re.compile(r"(?:~|\$HOME|\$\{HOME\})[\"']?/[^\s`\"'();,]+")
COMMAND = re.compile(r"(?<![\w/])/(?P<family>[a-z][\w-]*):(?P<name>[\w-]+)")
RELATIVE = re.compile(r"(?<![\w/@])(?:\.[\w-]+|[a-zA-Z][\w.-]*)/[^\s`\"'();,]+")
BARE_FILE = re.compile(r"(?<![\w./])(?:\.[\w-]+|[\w-]+\.[\w.-]+)(?![\w/])")
VERBS = r"(?:installs?|links?|ships?|writes?|creates?|generates?|copies)"
PROMISE = re.compile(
    rf"(?:(?<![\w-]){VERBS}\b\s*:\s*|^(?:[-*•]\s*)?(?-i:Installs|Links|Ships|Writes|Creates|Generates|Copies)\b\s+|"
    rf"(?<![\w-]){VERBS}\b\s+(?=[`~$./]|[\w-]+(?:/[\w<*]|\.[\w-])))",
    re.I,
)
RETIREMENT = re.compile(r"\b(?:retired|removed|no longer|used to)\b", re.I)


@dataclass(frozen=True)
class Claim:
    line: int
    kind: str
    target: str
    source: str = ""


@dataclass
class Report:
    claims: list[Claim]
    findings: list[str]

    @property
    def supplied(self) -> set[str]:
        return {c.source for c in self.claims if c.kind == "cpp"}


def clean(token: str) -> str:
    return token.rstrip(".?!:,\\").replace('\\"', "")


def scan(text: str, root: Path, minimum: int) -> Report:
    report = Report([], [])
    generated: dict[str, str] = {}
    disclosure = False
    scripts = False
    undo = False
    in_bash = False

    def add(line: int, kind: str, target: str, source: str = "") -> None:
        claim = Claim(line, kind, target, source)
        if claim not in report.claims:
            report.claims.append(claim)

    def supplied(line: int, target: str, relative: str) -> None:
        relative = clean(relative).rstrip("/")
        if Path(relative).is_absolute():
            report.findings.append(f"escaping promised path at {DOCUMENT}:{line}: {target}")
            return
        if "$" in relative or "{" in relative or "}" in relative:
            report.findings.append(f"unclassified promise at {DOCUMENT}:{line}: {target}")
            return
        if "<" in relative or ">" in relative:
            if relative != ".claude/commands/<family>":
                report.findings.append(f"unclassified promise at {DOCUMENT}:{line}: {target}")
                return
            relative = ".claude/commands/*"
        add(line, "cpp", target, relative)
        candidates = list(root.glob(relative)) if any(c in relative for c in "*?[") else [root / relative]
        if not candidates:
            report.findings.append(f"missing promised path at {DOCUMENT}:{line}: {target} -> {relative}")
        for candidate in candidates:
            if not candidate.resolve().is_relative_to(root.resolve()):
                report.findings.append(f"escaping promised path at {DOCUMENT}:{line}: {target}")
            elif not candidate.exists():
                report.findings.append(f"missing promised path at {DOCUMENT}:{line}: {target} -> {relative}")

    for number, original in enumerate(text.splitlines(), 1):
        if original.startswith("```"):
            in_bash = original.strip() == "```bash"
        if original.startswith("## Step 4:"):
            disclosure = True
        elif original.startswith("## Step 5:"):
            disclosure = False
        line = original.strip().strip("`")
        if disclosure and line.startswith("Proceed?"):
            undo = False
            scripts = False
            continue
        if line.startswith("#") and not line.startswith("###"):
            continue
        if disclosure and line.startswith(("### ", "[Tier ", "[Tier")):
            scripts = "~/.claude/scripts/" in line or "$HOME/.claude/scripts/" in line
            undo = False
        if disclosure and "To undo:" in line:
            undo = True
            scripts = False

        # Split explicit clauses, not whole lines: a retirement reference must
        # not conceal a new affirmative install on the other side of a semicolon.
        clauses = re.split(
            rf";\s*|\.\s+(?={VERBS}\b)|\s+but\s+|\s+(?:and )?now\s+(?={VERBS}\b)|(?:,\s*|\s+and\s+)(?={VERBS}\b)",
            line,
            flags=re.I,
        )
        for clause in clauses:
            historical = RETIREMENT.search(clause)
            affirmative = PROMISE.search(clause)
            negative = re.search(r"\b(?:no longer|used to)\s+(?:installs?|copies|copy|ships?|links?)", clause, re.I)
            active_source = SOURCE.search(clause) and (
                in_bash or re.match(r"^(?:if\s+!?\s*)?(?:cp|ln|install|exec|bash|sh|python3)\b|^\w+=", clause)
            )
            if historical and not active_source and (not affirmative or negative):
                if negative and len(list(PROMISE.finditer(clause))) > 1:
                    report.findings.append(f"unclassified promise at {DOCUMENT}:{number}: {clause}")
                    continue
                add(number, "retirement", clause)
                continue

            handled: list[tuple[int, int]] = []
            for match in re.finditer(r"https?://[^\s`\"'();,]+", clause):
                if disclosure or affirmative:
                    add(number, "external", match[0])
                    handled.append(match.span())
            for match in re.finditer(r"\bopen\(['\"]([^'\"]+)['\"]", clause):
                if disclosure:
                    add(number, "consumer", match[1])
                    handled.append(match.span())
            for match in SOURCE.finditer(clause):
                target = clean(match[0])
                if match[1] not in {"$CPP_DIR", "${CPP_DIR}", "{CPP_DIR}"}:
                    report.findings.append(f"unclassified promise at {DOCUMENT}:{number}: {target}")
                else:
                    supplied(number, target, match[2])
                handled.append(match.span())
            for match in HOME.finditer(clause):
                target = clean(match[0])
                suffix = re.sub(r"^(?:~|\$HOME|\$\{HOME\})[\"']?/", "", target)
                if "<name>" in suffix and "paths that will not exist" in clause and "echo" in clause:
                    add(number, "diagnostic", target)
                    handled.append(match.span())
                    continue
                if suffix.startswith(".claude/scripts/"):
                    supplied(number, target, "scripts/" + suffix.removeprefix(".claude/scripts/"))
                elif suffix.startswith(".claude/commands"):
                    supplied(number, target, suffix)
                elif disclosure or affirmative:
                    add(number, "consumer", target)
                handled.append(match.span())
            if disclosure or affirmative:
                for match in COMMAND.finditer(clause):
                    supplied(number, match[0], f".claude/commands/{match['family']}/{match['name']}.md")
                    handled.append(match.span())

                if scripts and re.match(r"^[•*-]\s+", clause):
                    word = re.sub(r"^[•*-]\s+", "", clause).split()[0]
                    if re.fullmatch(r"[\w.-]+", word):
                        supplied(number, word, "scripts/" + word)
                        handled.append((clause.index(word), clause.index(word) + len(word)))
                    else:
                        report.findings.append(f"unclassified promise at {DOCUMENT}:{number}: {clause}")

                action = re.search(rf"(?<![\w/.-])({VERBS}|configures?|adds?|downloads?)\b(?![/-])", clause, re.I)
                if action and re.search(r"\bollama\s+$", clause[: action.start()]):
                    add(number, "external", clause)
                    continue
                producing = bool(
                    action
                    and re.fullmatch(r"creates?|generates?|configures?|writes?|adds?|downloads?", action[1], re.I)
                )
                relation = re.search(r"\b(?:from|using|via)\s+", clause[action.end() :], re.I) if action else None
                source_start = action.end() + relation.end() if action and relation else len(clause) + 1
                tokens = [(clean(m[0]), m.start(), m.end()) for m in RELATIVE.finditer(clause)]
                if producing or affirmative:
                    tokens += [(m[0], m.start(), m.end()) for m in BARE_FILE.finditer(clause)]
                    if re.search(r"\bMakefile\b|\bDockerfile\b", clause):
                        tokens += [
                            (m[0], m.start(), m.end()) for m in re.finditer(r"\b(?:Makefile|Dockerfile)\b", clause)
                        ]
                elif undo and re.match(r"^rm\s+", clause):
                    for token in shlex.split(clause)[1:]:
                        if not token.startswith("-"):
                            start = clause.index(token)
                            tokens.append((token, start, start + len(token)))
                for target, start, end in dict.fromkeys(tokens):
                    if any(left <= start and end <= right for left, right in handled):
                        continue
                    if action and start <= action.start() < end:
                        continue
                    if target.startswith(("http:", "https:", "@")) or target in {
                        "npx/stdio",
                        "Gemini/OpenAI/Anthropic",
                    }:
                        add(number, "external", target)
                    elif re.search(rf"\b{re.escape(target)}\s*\(https?://", clause):
                        add(number, "external", target)
                    elif re.search(rf"\b{re.escape(target)}:\s+https?://", clause):
                        add(number, "external", target)
                    elif target in generated and undo and not affirmative:
                        add(number, generated[target], target)
                    elif producing and action and action.end() <= start < source_start:
                        generated[target] = "generated"
                        add(number, "generated", target)
                    elif target.startswith(("scripts/", "templates/", "lib/", "codex/", ".claude/")):
                        supplied(number, target, target)
                    elif producing and start >= source_start:
                        add(number, "consumer", target)
                    elif undo or affirmative:
                        report.findings.append(f"unclassified promise at {DOCUMENT}:{number}: {target}")
                    handled.append((start, end))
                field = re.match(rf"^(?:[-*•]\s*)?{VERBS}\b(?:\s+if absent)?\s*:\s*", clause, re.I)
                if affirmative and (field or re.match(r"^(?:[-*•]\s*)?(?:Installs|Links|Ships|Copies)\b", clause)):
                    # Each comma/and-separated operand must begin with a
                    # classified target. A recognized later path cannot excuse
                    # an unknown first operand, or an unknown last operand.
                    offset = field.end() if field else affirmative.end()
                    body = clause[offset:]
                    for operand in re.split(r",\s*|\s+and\s+", body, flags=re.I):
                        left = offset
                        right = left + len(operand)
                        spans = [(a, b) for a, b in handled if left <= a < right]
                        prefix = clause[left : min((a for a, _ in spans), default=right)].strip(" `\"'")
                        if operand.strip() and (not spans or prefix not in {"", "a", "an", "the"}):
                            report.findings.append(f"unclassified promise at {DOCUMENT}:{number}: {operand.strip()}")
                        # Find the next operand without losing the delimiter's
                        # actual width or confusing a repeated target string.
                        offset = right
                        delimiter = re.match(r",\s*|\s+and\s+", clause[offset:], re.I)
                        if delimiter:
                            offset += delimiter.end()
                elif affirmative and not handled and not tokens:
                    report.findings.append(f"unclassified promise at {DOCUMENT}:{number}: {clause}")

    if len(report.supplied) < minimum:
        report.findings.append(f"population floor: {len(report.supplied)} CPP-supplied promises, minimum {minimum}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--min-promises", type=int, default=MIN_PROMISES)
    args = parser.parse_args(argv)
    if args.min_promises < 1:
        parser.error("--min-promises must be positive")
    try:
        text = (args.root / DOCUMENT).read_text(encoding="utf-8")
        report = scan(text, args.root, args.min_promises)
    except (OSError, UnicodeError) as exc:
        print(f"cpp-init-promises: UNKNOWN - cannot read population ({type(exc).__name__})")
        return 2
    for claim in report.claims:
        if claim.kind != "cpp":
            print(f"CLASSIFIED {claim.kind} {DOCUMENT}:{claim.line}: {claim.target}")
    for finding in report.findings:
        print(f"PROMISE_FINDING: {finding}")
    if report.findings:
        print(
            f"cpp-init-promises: {len(report.findings)} invalid promises; "
            f"{len(report.supplied)} CPP-supplied paths examined"
        )
        return 1
    print(
        f"cpp-init-promises: ok - {len(report.supplied)} CPP-supplied paths resolve; "
        "generated/consumer/external targets unverified"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

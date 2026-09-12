#!/usr/bin/env python3
"""Resolve, render and refresh the task-context cache in a generated issue (#858).

A generated issue used to carry its provenance, its identity marker and its
dependencies - and nothing about the behaviour it was meant to produce. The task
title was the whole description, so a receiving agent could not tell which words
were the goal and which were somebody's suggested mechanism, and had nothing
pointing at the document that actually governs the work.

This helper resolves a task's DECLARED context and renders it into a bounded,
fingerprinted block. The block is a CACHE, not a second authority: the spec named
inside it stays authoritative, everything in it is traceable to a source section,
and every part carries a digest so drift is visible instead of silent.

What is declared, and therefore used:

  * the story tag on the task line (`- [ ] **T001** [US1] ...`), which names a
    `### US1:` section in the sibling spec.md
  * the Functional Requirements table's `User Story` column, which maps
    individual requirements to that story

What is NOT inferred: nothing is derived from task NUMBERS, and requirements with
no declared story mapping are never claimed as this task's. Non-Functional
Requirements and Out of Scope carry no story mapping at all, so they are indexed
as cross-cutting sections the consumer must read in the source - and they are
covered by the whole-file digest, so a changed global security or compatibility
constraint is visible even though it is not attributed to this task.

What a digest establishes, and what it does not: a differing digest means those
BYTES changed since the block was written. It is not a ruling that acceptance
changed, that the change is material to this task, or that anything was approved.
A reflow or a typo fix reads as a change. The states this helper reports are
deliberately named for what they observe.

Usage:
    speckit-context.py render  --tasks PATH --task T001 [--feature SLUG]
    speckit-context.py check   --body-file PATH [--root DIR]
    speckit-context.py refresh --body-file PATH --tasks PATH --task T001 [--feature SLUG]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

BLOCK_BEGIN = "<!-- speckit-context:v1"
BLOCK_END = "<!-- speckit-context:end -->"
DIGEST_LEN = 12

# Declared task -> story mapping, written by .specify/templates/tasks-template.md.
STORY_TAG_RE = re.compile(r"\[(US\d+(?:\s*,\s*US?\d+)*)\]", re.IGNORECASE)
STORY_ID_RE = re.compile(r"US\d+", re.IGNORECASE)
TASK_LINE_RE = re.compile(
    r"^\s*-\s*\[[ xX]\]\s*(?:\*\*|__)?(T\d{3})(?:\*\*|__)?(?![0-9A-Za-z])(.*)$"
)
STORY_HEADING_RE = re.compile(r"^###\s+(US\d+)\s*:\s*(.+?)\s*$", re.IGNORECASE)
ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
ACCEPTANCE_HEADING_RE = re.compile(r"^\*\*Acceptance Criteria:?\*\*\s*$", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*-\s*(?:\[[ xX]\]\s*)?(.+?)\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
# A structured, reviewable record that a requirements revision was accepted. The
# helper REPORTS it; it never decides that it is authorised, and a free-text
# "acknowledged" somewhere in the body is not this.
REVISION_RE = re.compile(
    r"^\s*Acceptance-revision:\s*source-digest=([0-9a-f]{6,64})\s*(?:ref=(\S.*))?$",
    re.MULTILINE,
)

CROSS_CUTTING_HEADINGS = ("Non-Functional Requirements", "Out of Scope")
# A cap keeps the cache bounded; beyond it the block points at the source instead
# of copying, and says that it did (an incomplete extract is never silence).
MAX_ITEMS = 12
MAX_ITEM_CHARS = 300


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:DIGEST_LEN]


@dataclass
class Resolution:
    """What the declared mappings produced for one task."""

    task_id: str
    task_wording: str
    source: Path | None = None
    story_ids: list[str] = field(default_factory=list)
    outcomes: list[tuple[str, str]] = field(default_factory=list)
    acceptance: list[tuple[str, str]] = field(default_factory=list)
    requirements: list[tuple[str, str]] = field(default_factory=list)
    cross_cutting: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)
    scope_text: str = ""
    source_text: str = ""


def _sections(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Heading text -> (start, end) line span, for top-level `##`/`###` headings."""
    spans: dict[str, tuple[int, int]] = {}
    current: str | None = None
    start = 0
    for index, line in enumerate(lines):
        if ANY_HEADING_RE.match(line):
            if current is not None:
                spans[current] = (start, index)
            current = line.lstrip("#").strip()
            start = index
    if current is not None:
        spans[current] = (start, len(lines))
    return spans


def _story_span(lines: list[str], story_id: str) -> tuple[int, int] | None:
    for index, line in enumerate(lines):
        match = STORY_HEADING_RE.match(line)
        if match and match.group(1).upper() == story_id.upper():
            for end in range(index + 1, len(lines)):
                if ANY_HEADING_RE.match(lines[end]):
                    return (index, end)
            return (index, len(lines))
    return None


def _story_outcome(block: list[str]) -> str:
    """The story's own sentence: the heading text plus its As/I want/So that lines."""
    parts: list[str] = []
    for line in block[1:]:
        stripped = line.strip()
        if not stripped:
            if parts:
                break
            continue
        if stripped.startswith("**Acceptance") or ANY_HEADING_RE.match(line):
            break
        parts.append(stripped)
    return " ".join(parts).strip()


def _story_acceptance(block: list[str]) -> list[str]:
    items: list[str] = []
    collecting = False
    for line in block:
        if ACCEPTANCE_HEADING_RE.match(line.strip()):
            collecting = True
            continue
        if collecting:
            if line.strip().startswith("**") or ANY_HEADING_RE.match(line):
                break
            bullet = BULLET_RE.match(line)
            if bullet:
                items.append(bullet.group(1))
            elif line.strip() and items:
                items[-1] = f"{items[-1]} {line.strip()}"
    return items


def _requirements_for(lines: list[str], story_ids: list[str]) -> list[tuple[str, str]]:
    """FR rows whose declared `User Story` column names one of these stories.

    The mapping is read from the table the spec template ships; a row with no
    story column, or one naming another story, is never attributed to this task.
    """
    wanted = {s.upper() for s in story_ids}
    spans = _sections(lines)
    span = spans.get("Functional Requirements")
    if span is None:
        return []
    rows: list[tuple[str, str]] = []
    header: list[str] | None = None
    for line in lines[span[0] : span[1]]:
        match = TABLE_ROW_RE.match(line)
        if not match:
            continue
        cells = [c.strip() for c in match.group(1).split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= {"-", ":"} for c in cells if c):
            continue
        if "user story" not in header:
            continue
        story_index = header.index("user story")
        if story_index >= len(cells):
            continue
        declared = {s.upper() for s in STORY_ID_RE.findall(cells[story_index])}
        if not declared & wanted:
            continue
        ident = cells[0] if cells else ""
        text_index = header.index("requirement") if "requirement" in header else 1
        text = cells[text_index] if text_index < len(cells) else ""
        priority_index = header.index("priority") if "priority" in header else None
        if priority_index is not None and priority_index < len(cells):
            text = f"{text} ({cells[priority_index]})"
        rows.append((ident, text))
    return rows


def resolve(tasks_path: Path, task_id: str) -> Resolution:
    """Resolve one task's declared context, disclosing whatever does not resolve."""
    tasks_text = tasks_path.read_text(encoding="utf-8")
    wording = ""
    story_ids: list[str] = []
    found = False
    for line in tasks_text.splitlines():
        match = TASK_LINE_RE.match(line)
        if not match or match.group(1).upper() != task_id.upper():
            continue
        found = True
        rest = match.group(2)
        for tag in STORY_TAG_RE.findall(rest):
            story_ids.extend(s.upper() for s in STORY_ID_RE.findall(tag))
        wording = STORY_TAG_RE.sub("", rest).replace("[P]", "").strip(" :\t")
        break

    resolution = Resolution(task_id=task_id.upper(), task_wording=wording)
    if not found:
        resolution.unresolved.append(f"{task_id} is not a task line in {tasks_path}")
        return resolution

    source = tasks_path.parent / "spec.md"
    if not source.is_file():
        resolution.unresolved.append(
            f"no spec.md beside {tasks_path} - no declared source to resolve against"
        )
        return resolution
    resolution.source = source
    resolution.source_text = source.read_text(encoding="utf-8")
    lines = resolution.source_text.splitlines()

    if not story_ids:
        resolution.unresolved.append(
            f"{resolution.task_id} declares no [USn] story tag, so its governing "
            "requirement is not resolvable from the task line"
        )

    scope_parts: list[str] = []
    for story_id in dict.fromkeys(story_ids):
        span = _story_span(lines, story_id)
        if span is None:
            resolution.unresolved.append(
                f"{story_id} is tagged on the task but has no '### {story_id}:' "
                f"section in {source.name}"
            )
            continue
        block = lines[span[0] : span[1]]
        scope_parts.append("\n".join(block))
        heading = STORY_HEADING_RE.match(block[0])
        title = heading.group(2) if heading else story_id
        outcome = _story_outcome(block)
        resolution.outcomes.append((story_id, f"{title}. {outcome}".strip()))
        for item in _story_acceptance(block):
            resolution.acceptance.append((story_id, item))

    for ident, text in _requirements_for(lines, story_ids):
        resolution.requirements.append((ident, text))
        scope_parts.append(f"{ident}|{text}")

    spans = _sections(lines)
    for heading in CROSS_CUTTING_HEADINGS:
        if heading in spans:
            resolution.cross_cutting.append(heading)

    resolution.scope_text = "\n".join(scope_parts)
    return resolution


def _cap(items: list[tuple[str, str]], label: str, truncated: list[str]) -> list[tuple[str, str]]:
    if len(items) > MAX_ITEMS:
        truncated.append(f"{label}: showing {MAX_ITEMS} of {len(items)}")
        items = items[:MAX_ITEMS]
    capped: list[tuple[str, str]] = []
    for ident, text in items:
        if len(text) > MAX_ITEM_CHARS:
            text = text[:MAX_ITEM_CHARS].rstrip() + " [...]"
            truncated.append(f"{label} {ident}: shortened")
        capped.append((ident, text))
    return capped


def render(resolution: Resolution, feature: str) -> str:
    """The managed block: bounded, sourced, fingerprinted, and honest about gaps."""
    truncated: list[str] = list(resolution.truncated)
    acceptance = _cap(resolution.acceptance, "acceptance", truncated)
    requirements = _cap(resolution.requirements, "requirements", truncated)

    body: list[str] = ["### Governing context (generated cache)", ""]
    if resolution.source is not None:
        body.append(
            f"**Authoritative source:** `{resolution.source}` - read the sections named "
            "below there before planning. This block is a task-scoped extract kept for "
            "convenience; where the two differ, the source governs."
        )
    else:
        body.append(
            "**Authoritative source:** none resolved. See the unresolved notes below."
        )
    body.append("")

    for story_id, outcome in resolution.outcomes:
        body.append(f"**Outcome ({story_id}):** {outcome}")
    if resolution.outcomes:
        body.append("")

    if acceptance:
        body.append("**Acceptance, as declared by the story:**")
        body.extend(f"- ({story_id}) {item}" for story_id, item in acceptance)
        body.append("")

    if requirements:
        body.append("**Requirements declared against this story:**")
        body.extend(f"- {ident}: {text}" for ident, text in requirements)
        body.append("")

    if resolution.cross_cutting:
        body.append(
            "**Cross-cutting sections to read in the source before planning** - these "
            "carry no story mapping, so they are named rather than attributed to this "
            "task: " + ", ".join(f"`{h}`" for h in resolution.cross_cutting)
        )
        body.append("")

    if resolution.task_wording:
        body.append(f'**Task wording (from tasks.md):** "{resolution.task_wording}"')
        body.append(
            "  Resolve its authority against the sections above before acting on it. It "
            "may propose an approach you are free to replace, or it may restate a binding "
            "constraint; the line alone does not say which."
        )
        body.append("")

    if resolution.outcomes:
        body.append(
            "**Granularity:** acceptance is declared at user-story level, so the items "
            "above may also cover sibling tasks of the same story. Narrow them to this "
            "task yourself; this block does not decide that for you."
        )
        body.append("")

    if resolution.unresolved:
        body.append("**Unresolved - incomplete context, not an absence of constraints:**")
        body.extend(f"- {note}" for note in resolution.unresolved)
        body.append("")

    if truncated:
        body.append("**Capped for size - read the source for the rest:**")
        body.extend(f"- {note}" for note in truncated)
        body.append("")

    content = "\n".join(body).rstrip() + "\n"
    header = [
        BLOCK_BEGIN,
        f"feature: {feature}",
        f"task: {resolution.task_id}",
        f"source: {resolution.source if resolution.source else '-'}",
        f"stories: {','.join(s for s, _ in resolution.outcomes) or '-'}",
        f"scope-digest: {digest(resolution.scope_text)}",
        f"source-digest: {digest(resolution.source_text)}",
        f"block-digest: {digest(content)}",
        "-->",
    ]
    return "\n".join(header) + "\n" + content + BLOCK_END + "\n"


@dataclass
class ParsedBlock:
    start: int
    end: int
    meta: dict[str, str]
    content: str


def find_block(body: str) -> tuple[ParsedBlock | None, str | None]:
    """Locate the managed block. Returns (block, fault); a fault forbids rewriting."""
    starts = [m.start() for m in re.finditer(re.escape(BLOCK_BEGIN), body)]
    ends = [m.start() for m in re.finditer(re.escape(BLOCK_END), body)]
    if not starts and not ends:
        return None, None
    if len(starts) > 1 or len(ends) > 1:
        return None, "duplicate context block boundaries"
    if not starts or not ends:
        return None, "damaged context block: one boundary is missing"
    start, end = starts[0], ends[0]
    if end < start:
        return None, "damaged context block: boundaries are out of order"
    header_end = body.find("-->", start)
    if header_end == -1 or header_end > end:
        return None, "damaged context block: header is unterminated"
    meta: dict[str, str] = {}
    for line in body[start + len(BLOCK_BEGIN) : header_end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    content = body[header_end + len("-->") : end].lstrip("\n")
    return ParsedBlock(start, end + len(BLOCK_END), meta, content), None


def recorded_revisions(body: str, block: ParsedBlock | None) -> list[tuple[str, str]]:
    """Structured revision records OUTSIDE the managed block.

    Reported, never judged: this helper cannot tell whether a record was written
    by someone with the authority to accept a requirements change, and a
    free-text "acknowledged" is deliberately not matched.
    """
    outside = body if block is None else body[: block.start] + body[block.end :]
    return [(m.group(1), (m.group(2) or "").strip()) for m in REVISION_RE.finditer(outside)]


def check(body: str, root: Path) -> tuple[str, list[str]]:
    """Freshness of the cache against its source. Returns (state, detail lines)."""
    block, fault = find_block(body)
    detail: list[str] = []
    if fault:
        return "block-damaged", [fault]
    if block is None:
        return "absent", ["this issue carries no generated context block"]

    detail.append(f"task={block.meta.get('task', '-')} source={block.meta.get('source', '-')}")
    if digest(block.content) != block.meta.get("block-digest", ""):
        detail.append(
            "the block's own text has been edited since it was generated; a refresh "
            "would overwrite that edit and is refused"
        )
        return "block-edited", detail

    source_name = block.meta.get("source", "-")
    if source_name in ("-", ""):
        return "source-unresolved", detail + [
            "no source was resolved when this block was written; its notes say why"
        ]
    source = root / source_name
    if not source.is_file():
        return "source-missing", detail + [f"{source_name} is no longer present"]

    source_text = source.read_text(encoding="utf-8")
    source_now = digest(source_text)
    source_then = block.meta.get("source-digest", "")
    for recorded, ref in recorded_revisions(body, block):
        detail.append(
            f"recorded revision: source-digest={recorded} ref={ref or '-'} "
            "(a record found in the issue body; this helper does not judge whether it "
            "was authorised - resolve it under the existing authority model)"
        )
        if recorded == source_now:
            detail.append("that record names the CURRENT source version")

    if source_now == source_then:
        return "current", detail + ["source bytes are unchanged since generation"]

    stories = [s for s in block.meta.get("stories", "").split(",") if s and s != "-"]
    task_id = block.meta.get("task", "")
    scope_now = ""
    if task_id and stories:
        tasks_path = source.parent / "tasks.md"
        if tasks_path.is_file():
            scope_now = digest(resolve(tasks_path, task_id).scope_text)
    if scope_now and scope_now != block.meta.get("scope-digest", ""):
        return "changed-in-scope", detail + [
            "bytes changed inside the sections this task maps to. That is a byte "
            "difference, not a ruling that acceptance changed - assess it against the "
            "source before continuing."
        ]
    return "changed-outside-scope", detail + [
        "the source file changed, but not inside the sections this task maps to. The "
        "change may still matter (cross-cutting requirements carry no story mapping), "
        "so read it; nothing here claims it is relevant to this task."
    ]


def refresh(body: str, block_text: str) -> tuple[str | None, str]:
    """Replace ONLY the managed block. Any doubt leaves the body byte-identical."""
    block, fault = find_block(body)
    if fault:
        return None, f"refused: {fault}. The body is unchanged; repair the block by hand."
    if block is None:
        return body.rstrip("\n") + "\n\n" + block_text, "attached: the issue had no block"
    if digest(block.content) != block.meta.get("block-digest", ""):
        return None, (
            "refused: the block's text was edited after it was generated. The body is "
            "unchanged. Move the edit outside the block, or delete the block to have it "
            "regenerated, if you want the cache refreshed."
        )
    updated = body[: block.start] + block_text.rstrip("\n") + body[block.end :]
    if updated == body:
        return updated, "unchanged: the regenerated block is identical"
    return updated, "refreshed: the block was replaced; text outside it is untouched"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_render = sub.add_parser("render", help="print the managed block for one task")
    p_render.add_argument("--tasks", type=Path, required=True)
    p_render.add_argument("--task", required=True)
    p_render.add_argument("--feature", default="")

    p_check = sub.add_parser("check", help="report cache freshness for an issue body")
    p_check.add_argument("--body-file", type=Path, required=True)
    p_check.add_argument("--root", type=Path, default=Path("."))

    p_refresh = sub.add_parser("refresh", help="replace only the managed block")
    p_refresh.add_argument("--body-file", type=Path, required=True)
    p_refresh.add_argument("--tasks", type=Path, required=True)
    p_refresh.add_argument("--task", required=True)
    p_refresh.add_argument("--feature", default="")

    args = parser.parse_args(argv)

    if args.command == "render":
        resolution = resolve(args.tasks, args.task)
        sys.stdout.write(render(resolution, args.feature or str(args.tasks)))
        return 0

    if args.command == "check":
        body = args.body_file.read_text(encoding="utf-8")
        state, detail = check(body, args.root)
        for line in detail:
            print(f"  {line}")
        print(f"SPECKIT_CONTEXT_STATE: {state}")
        return 0 if state in ("current", "absent") else 3

    body = args.body_file.read_text(encoding="utf-8")
    resolution = resolve(args.tasks, args.task)
    block_text = render(resolution, args.feature or str(args.tasks))
    updated, message = refresh(body, block_text)
    print(f"SPECKIT_CONTEXT_REFRESH: {message}", file=sys.stderr)
    if updated is None:
        return 4
    sys.stdout.write(updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

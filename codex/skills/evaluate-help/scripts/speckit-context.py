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
# `---` under an acceptance list is a horizontal rule, and `- -` is how a naive
# bullet regex reads it: the real shipped template produced a phantom acceptance
# item of "--". Rules end a list, they are never items in it.
HRULE_RE = re.compile(r"^\s*([-*_])\s*(?:\1\s*){2,}$")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
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
MAX_PROSE_CHARS = 600
MAX_BLOCK_CHARS = 8000
REQUIRED_META = ("feature", "task", "tasks", "source", "integrity")


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
    task_text: str = ""
    tasks_rel: str | None = None
    source_rel: str | None = None


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


def _story_spans(lines: list[str], story_id: str) -> list[tuple[int, int]]:
    """Every span declaring this story. More than one is ambiguity, not a choice."""
    spans: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = STORY_HEADING_RE.match(line)
        if match and match.group(1).upper() == story_id.upper():
            end = len(lines)
            for candidate in range(index + 1, len(lines)):
                if ANY_HEADING_RE.match(lines[candidate]):
                    end = candidate
                    break
            spans.append((index, end))
    return spans


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


def _strip_fences(lines: list[str]) -> list[str]:
    """Blank out fenced blocks: a sample inside a fence is an example, not a declaration."""
    out: list[str] = []
    inside = False
    for line in lines:
        if FENCE_RE.match(line):
            inside = not inside
            out.append("")
            continue
        out.append("" if inside else line)
    return out


def _story_acceptance(block: list[str]) -> list[str]:
    items: list[str] = []
    collecting = False
    for line in block:
        if ACCEPTANCE_HEADING_RE.match(line.strip()):
            collecting = True
            continue
        if collecting:
            if HRULE_RE.match(line):
                break
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


def project_root(start: Path, explicit: Path | None = None) -> Path:
    """The root every persisted path is relative to.

    Persisting the path as GIVEN was a defect: an absolute source recorded by the
    producer's checkout kept resolving back to that checkout, so a consumer in a
    different clone checked the wrong tree and was told `current` while its own
    spec had changed. Paths are stored relative to this root and re-resolved
    against the consumer's `--root`.
    """
    if explicit is not None:
        return explicit.resolve()
    here = start.resolve()
    here = here if here.is_dir() else here.parent
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists():
            return candidate
    return here


def relative_to_root(path: Path, root: Path) -> str | None:
    """Project-relative spelling, or None when the path escapes the root."""
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def resolve(tasks_path: Path, task_id: str, root: Path | None = None) -> Resolution:
    """Resolve one task's declared context, disclosing whatever does not resolve."""
    base = project_root(tasks_path, root)
    tasks_text = tasks_path.read_text(encoding="utf-8")
    wording = ""
    story_ids: list[str] = []
    duplicates = 0
    found = False
    # A task line inside a fence is an EXAMPLE. Reading declarations out of fenced
    # samples let a documentation snippet outrank the real task and supply the wrong
    # story mapping, so tasks.md gets the same fence handling as the spec.
    for line in _strip_fences(tasks_text.splitlines()):
        match = TASK_LINE_RE.match(line)
        if not match or match.group(1).upper() != task_id.upper():
            continue
        if found:
            duplicates += 1
            continue
        found = True
        rest = match.group(2)
        for tag in STORY_TAG_RE.findall(rest):
            story_ids.extend(s.upper() for s in STORY_ID_RE.findall(tag))
        wording = STORY_TAG_RE.sub("", rest).replace("[P]", "").strip(" :\t")

    resolution = Resolution(task_id=task_id.upper(), task_wording=wording)
    if duplicates:
        resolution.unresolved.append(
            f"{task_id.upper()} is declared {duplicates + 1} times in {tasks_path.name}; "
            "the first was used and the ambiguity is reported rather than resolved here"
        )
    resolution.tasks_rel = relative_to_root(tasks_path, base)
    if resolution.tasks_rel is None:
        resolution.unresolved.append(
            f"{tasks_path} lies outside the project root {base}; its location cannot be "
            "recorded portably, so a consumer in another checkout cannot re-resolve it"
        )
    # The task line is a governing input in its own right: its wording can carry a
    # constraint, and its [USn] tag decides which requirements apply. A digest over
    # the spec alone left a re-tagged or re-worded task reading as unchanged.
    resolution.task_text = f"{task_id.upper()}|{','.join(sorted(set(story_ids)))}|{wording}"
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
    resolution.source_rel = relative_to_root(source, base)
    resolution.source_text = source.read_text(encoding="utf-8")
    lines = _strip_fences(resolution.source_text.splitlines())

    if not story_ids:
        resolution.unresolved.append(
            f"{resolution.task_id} declares no [USn] story tag, so its governing "
            "requirement is not resolvable from the task line"
        )

    scope_parts: list[str] = []
    for story_id in dict.fromkeys(story_ids):
        spans = _story_spans(lines, story_id)
        if not spans:
            resolution.unresolved.append(
                f"{story_id} is tagged on the task but has no '### {story_id}:' "
                f"section in {source.name}"
            )
            continue
        if len(spans) > 1:
            resolution.unresolved.append(
                f"{story_id} is declared {len(spans)} times in {source.name}; the "
                "ambiguity is reported rather than resolved here - read the source"
            )
            continue
        span = spans[0]
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


def _clip(text: str, limit: int, label: str, truncated: list[str]) -> str:
    if len(text) <= limit:
        return text
    truncated.append(f"{label}: shortened to {limit} characters - read the source")
    return text[:limit].rstrip() + " [...]"


def _meta_digest(meta: dict[str, str], content: str) -> str:
    """Integrity over the MANAGED METADATA and the content, minus the field itself.

    Covering only the visible text left `task:`, `source:` and the other digests
    editable in place: the block could be re-pointed at another task's source and
    a refresh would accept it as its own.
    """
    payload = "\n".join(f"{k}={meta[k]}" for k in sorted(meta) if k != "integrity")
    return digest(payload + "\n--\n" + content)


def render(resolution: Resolution, feature: str) -> str:
    """The managed block: bounded, sourced, fingerprinted, and honest about gaps."""
    truncated: list[str] = list(resolution.truncated)
    acceptance = _cap(resolution.acceptance, "acceptance", truncated)
    requirements = _cap(resolution.requirements, "requirements", truncated)

    body: list[str] = ["### Governing context (generated cache)", ""]
    if resolution.source is not None:
        body.append(
            f"**Reference source:** `{resolution.source_rel or resolution.source}` - read "
            "the sections named below there before planning. This block is a task-scoped "
            "extract taken at the version recorded above. A difference between the two is "
            "a CHANGED VERSION to resolve under the existing authority model - it does not "
            "by itself override a constraint or plan already accepted on this issue."
        )
    else:
        body.append(
            "**Reference source:** none resolved. See the unresolved notes below."
        )
    body.append("")

    for story_id, outcome in resolution.outcomes:
        body.append(
            f"**Outcome ({story_id}):** "
            + _clip(outcome, MAX_PROSE_CHARS, f"outcome {story_id}", truncated)
        )
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
        wording = _clip(resolution.task_wording, MAX_PROSE_CHARS, "task wording", truncated)
        body.append(f'**Task wording (from tasks.md):** "{wording}"')
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
    if len(content) > MAX_BLOCK_CHARS:
        keep = content[:MAX_BLOCK_CHARS].rstrip()
        content = (
            keep
            + "\n\n**Capped for size - this extract is INCOMPLETE.** Read the "
            "authoritative source named above before planning; the constraints that "
            "make the decision are not guaranteed to be among the lines kept here.\n"
        )
    meta = {
        "feature": feature,
        "task": resolution.task_id,
        "tasks": resolution.tasks_rel or "-",
        "source": resolution.source_rel or "-",
        "stories": ",".join(story for story, _ in resolution.outcomes) or "-",
        "task-digest": digest(resolution.task_text),
        "scope-digest": digest(resolution.scope_text),
        "source-digest": digest(resolution.source_text),
    }
    meta["integrity"] = _meta_digest(meta, content)
    header = [BLOCK_BEGIN] + [f"{k}: {meta[k]}" for k in meta] + ["-->"]
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
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key in meta:
            return None, f"damaged context block: duplicate metadata field '{key}'"
        meta[key] = value.strip()
    missing = [name for name in REQUIRED_META if name not in meta]
    if missing:
        return None, "damaged context block: missing metadata " + ", ".join(missing)
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
    if _meta_digest(block.meta, block.content) != block.meta.get("integrity", ""):
        detail.append(
            "the block has been edited since it was generated - its text, or the "
            "metadata naming its task and source. A refresh would overwrite that edit "
            "and is refused"
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

    # The task line is a governing input too: a re-tagged or re-worded task changes
    # which requirements apply, without touching the spec at all.
    tasks_name = block.meta.get("tasks", "-")
    task_id = block.meta.get("task", "")
    tasks_path = root / tasks_name if tasks_name not in ("-", "") else None
    task_state: str | None = None
    if tasks_path is None or not tasks_path.is_file():
        detail.append(
            f"the tasks file recorded for this block ({tasks_name}) is not present under "
            "this root, so the task side of the mapping cannot be re-checked"
        )
        task_state = "tasks-missing"
    else:
        current = resolve(tasks_path, task_id, root)
        if digest(current.task_text) != block.meta.get("task-digest", ""):
            detail.append(
                "the task line itself changed - its wording, or the [USn] tag that "
                "decides which requirements apply. The mapping this block was built "
                "from no longer matches the plan."
            )
            task_state = "changed-task"

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
        elif recorded == source_then:
            detail.append(
                "that record names the version THIS BLOCK CACHED, not the current source - "
                "so the decision it records predates the change below and must be resolved, "
                "not assumed to cover it"
            )
        else:
            detail.append(
                "that record names neither the current source nor the cached version; it "
                "refers to some third version and cannot be matched automatically"
            )

    if task_state is not None:
        return task_state, detail

    if source_now == source_then:
        return "current", detail + ["source and task bytes are unchanged since generation"]

    scope_now = ""
    if tasks_path is not None and tasks_path.is_file():
        scope_now = digest(resolve(tasks_path, task_id, root).scope_text)
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
    if _meta_digest(block.meta, block.content) != block.meta.get("integrity", ""):
        return None, (
            "refused: the block's text was edited after it was generated. The body is "
            "unchanged. Move the edit outside the block, or delete the block to have it "
            "regenerated, if you want the cache refreshed."
        )
    incoming, fault = find_block(block_text)
    if incoming is None:
        return None, f"refused: the replacement block is unusable ({fault})"
    for key in ("feature", "task"):
        if block.meta.get(key) != incoming.meta.get(key):
            return None, (
                f"refused: identity mismatch - this block is {key}="
                f"{block.meta.get(key)} and the replacement is {key}="
                f"{incoming.meta.get(key)}. The body is unchanged; refreshing one "
                "task's context with another's is never a refresh."
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
    p_render.add_argument("--root", type=Path, default=None)

    p_check = sub.add_parser("check", help="report cache freshness for an issue body")
    p_check.add_argument("--body-file", type=Path, required=True, help="'-' reads stdin")
    p_check.add_argument("--root", type=Path, default=Path("."))

    p_refresh = sub.add_parser("refresh", help="replace only the managed block")
    p_refresh.add_argument("--body-file", type=Path, required=True)
    p_refresh.add_argument("--tasks", type=Path, required=True)
    p_refresh.add_argument("--task", required=True)
    p_refresh.add_argument("--feature", default="")
    p_refresh.add_argument("--root", type=Path, default=None)

    args = parser.parse_args(argv)

    if args.command == "render":
        resolution = resolve(args.tasks, args.task, args.root)
        sys.stdout.write(render(resolution, args.feature or str(args.tasks)))
        return 0

    if args.command == "check":
        body = (
            sys.stdin.read()
            if str(args.body_file) == "-"
            else args.body_file.read_text(encoding="utf-8")
        )
        state, detail = check(body, args.root)
        for line in detail:
            print(f"  {line}")
        print(f"SPECKIT_CONTEXT_STATE: {state}")
        return 0 if state in ("current", "absent") else 3

    body = args.body_file.read_text(encoding="utf-8")
    resolution = resolve(args.tasks, args.task, args.root)
    block_text = render(resolution, args.feature or str(args.tasks))
    updated, message = refresh(body, block_text)
    print(f"SPECKIT_CONTEXT_REFRESH: {message}", file=sys.stderr)
    if updated is None:
        return 4
    sys.stdout.write(updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

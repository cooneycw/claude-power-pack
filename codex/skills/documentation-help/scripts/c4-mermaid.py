#!/usr/bin/env python3
"""Render a C4 architecture model to GitHub-friendly Mermaid diagrams.

This is the rendering engine behind ``/documentation:c4`` (issue #411). It
replaces the removed ``nano-banana`` MCP server with a zero-dependency,
pure-Python renderer:

- **L1-L3** are emitted as Mermaid ``flowchart`` diagrams with ``subgraph``
  boundaries and ``classDef`` C4 colours. Flowchart syntax renders inline on
  GitHub, mermaid.live, and VS Code (unlike the Mermaid C4 extension, which
  GitHub does not bundle and shows as raw text).
- **L4** is emitted as a Mermaid ``classDiagram`` (Simon Brown models the code
  level as UML); ``classDiagram`` also renders natively on GitHub.

The engine also restores the edge-validity QA gate that the ``nano-banana``
renderer provided: every edge/relation endpoint must reference a defined node,
and dense diagrams are flagged for splitting.

Input is a JSON C4 model (see ``/documentation:c4`` for the schema). Output is
one ``.mmd`` file per level plus ``index.md`` (embeds every diagram in a
```mermaid fence) and ``c4-manifest.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# C4 node type -> (fill colour, text colour). Matches the palette documented in
# .claude/skills/documentation.md and .claude/commands/documentation/help.md.
C4_COLORS: dict[str, tuple[str, str]] = {
    "person": ("#08427b", "#ffffff"),
    "system": ("#6b7280", "#ffffff"),
    "system-focus": ("#1168bd", "#ffffff"),
    "container": ("#15803d", "#ffffff"),
    "component": ("#7e22ce", "#ffffff"),
    "code": ("#92400e", "#ffffff"),
}

# Node shape wrappers keyed by an optional per-node "shape" hint. ``person``
# defaults to a circle; everything else defaults to a rectangle.
SHAPES: dict[str, tuple[str, str]] = {
    "rect": ("[", "]"),
    "round": ("(", ")"),
    "circle": ("((", "))"),
    "cylinder": ("[(", ")]"),
    "hexagon": ("{{", "}}"),
}

# Diagrams larger than this are flagged for splitting (density QA equivalent).
DENSITY_LIMIT = 20

HIGH = "high"
MEDIUM = "medium"
LOW = "low"


class C4ModelError(ValueError):
    """Raised when the input model is structurally unusable."""


def slugify(text: str) -> str:
    """Lowercase, hyphenate, and trim a label for use in filenames/ids."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:50] or "diagram"


def safe_id(raw: str) -> str:
    """Sanitize a node/boundary id into a Mermaid-safe token.

    Mermaid node ids must be alphanumeric/underscore and not start with a digit;
    spaces, dots, hyphens, and brackets in an id break the parser. Labels keep
    the original text - only the id token is sanitized.
    """
    token = re.sub(r"[^A-Za-z0-9_]", "_", str(raw))
    if token and token[0].isdigit():
        token = f"id_{token}"
    return token or "id_node"


def class_token(c4_type: str) -> str:
    """Sanitize a C4 type into a Mermaid ``classDef`` / ``:::`` selector.

    Mermaid class selectors do not reliably accept hyphens or spaces, so e.g.
    ``system-focus`` becomes ``system_focus``.
    """
    return re.sub(r"[^A-Za-z0-9_]", "_", str(c4_type)) or "component"


def _shape_for(node: dict[str, Any]) -> tuple[str, str]:
    hint = node.get("shape")
    if hint in SHAPES:
        return SHAPES[hint]
    if node.get("type") == "person":
        return SHAPES["circle"]
    return SHAPES["rect"]


def _escape(label: str) -> str:
    """Escape a label for use inside a Mermaid node bracket.

    Collapses newlines to ``<br/>`` (a raw newline breaks the parser) and
    replaces double quotes with the HTML entity.
    """
    text = str(label).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")
    return text.replace('"', "&quot;")


def _escape_member(member: str) -> str:
    """Escape a classDiagram class name / member.

    Mermaid classDiagram treats ``<`` / ``>`` as relation operators, so generics
    such as ``List<User>`` must use tildes (``List~User~``) to render.
    """
    return re.sub(r"<([^<>]*)>", r"~\1~", str(member))


def _node_line(node: dict[str, Any]) -> str:
    open_b, close_b = _shape_for(node)
    token = class_token(node.get("type", "component"))
    label = _escape(str(node.get("label", node["id"])))
    return f'{safe_id(node["id"])}{open_b}"{label}"{close_b}:::{token}'


def _edge_line(edge: dict[str, Any]) -> str:
    src, tgt = safe_id(edge["source"]), safe_id(edge["target"])
    label = edge.get("label")
    if label:
        return f'{src} -->|"{_escape(str(label))}"| {tgt}'
    return f"{src} --> {tgt}"


def render_flowchart(level: dict[str, Any]) -> str:
    """Render an L1-L3 level as a Mermaid flowchart."""
    nodes: list[dict[str, Any]] = level.get("nodes", [])
    edges: list[dict[str, Any]] = level.get("edges", [])
    boundaries: list[dict[str, Any]] = level.get("boundaries", [])

    grouped: set[str] = set()
    lines = ["flowchart TB"]

    used_boundary_ids: set[str] = set()
    for idx, boundary in enumerate(boundaries):
        member_ids = boundary.get("nodes", [])
        raw_id = boundary.get("id") or slugify(boundary.get("label", f"boundary-{idx}"))
        b_id = safe_id(raw_id)
        while b_id in used_boundary_ids:
            b_id = f"{b_id}_{idx}"
        used_boundary_ids.add(b_id)
        b_label = _escape(str(boundary.get("label", b_id)))
        lines.append(f'  subgraph {b_id}["{b_label}"]')
        for node in nodes:
            if node["id"] in member_ids:
                lines.append(f"    {_node_line(node)}")
                grouped.add(node["id"])
        lines.append("  end")

    for node in nodes:
        if node["id"] not in grouped:
            lines.append(f"  {_node_line(node)}")

    for edge in edges:
        lines.append(f"  {_edge_line(edge)}")

    # classDef selector must be sanitized (e.g. system-focus -> system_focus) and
    # de-duplicated in case two raw types collapse to the same token.
    emitted_tokens: set[str] = set()
    for c4_type in sorted({n.get("type", "component") for n in nodes}):
        token = class_token(c4_type)
        if token in emitted_tokens:
            continue
        emitted_tokens.add(token)
        fill, color = C4_COLORS.get(c4_type, ("#334155", "#ffffff"))
        lines.append(f"  classDef {token} fill:{fill},color:{color},stroke:#0f172a")

    return "\n".join(lines) + "\n"


def render_classdiagram(level: dict[str, Any]) -> str:
    """Render an L4 level as a Mermaid classDiagram."""
    classes: list[dict[str, Any]] = level.get("classes", [])
    relations: list[dict[str, Any]] = level.get("relations", [])
    lines = ["classDiagram"]

    for cls in classes:
        name = _escape_member(cls["name"])
        members = cls.get("members", [])
        if members:
            lines.append(f"  class {name} {{")
            for member in members:
                lines.append(f"    {_escape_member(member)}")
            lines.append("  }")
        else:
            lines.append(f"  class {name}")

    for rel in relations:
        arrow = rel.get("kind", "-->")
        label = rel.get("label")
        line = f'  {_escape_member(rel["source"])} {arrow} {_escape_member(rel["target"])}'
        if label:
            line += f" : {label}"
        lines.append(line)

    return "\n".join(lines) + "\n"


def validate_level(level: dict[str, Any]) -> list[dict[str, str]]:
    """Return QA warnings for one level. High severity == invalid references."""
    warnings: list[dict[str, str]] = []
    diagram_id = level.get("id", level.get("level", "?"))
    kind = level.get("kind", "flowchart")

    if kind == "classdiagram":
        names = [c["name"] for c in level.get("classes", [])]
        defined = set(names)
        for name in names:
            if names.count(name) > 1:
                warnings.append(_warn(diagram_id, HIGH, "duplicate_class", f"class '{name}' defined more than once"))
        for rel in level.get("relations", []):
            for end in ("source", "target"):
                if rel.get(end) not in defined:
                    warnings.append(
                        _warn(diagram_id, HIGH, "relation_validity", f"relation {end} '{rel.get(end)}' is not a class")
                    )
        return _dedupe(warnings)

    nodes = level.get("nodes", [])
    ids = [n["id"] for n in nodes]
    defined = set(ids)
    for node_id in ids:
        if ids.count(node_id) > 1:
            warnings.append(_warn(diagram_id, HIGH, "duplicate_node", f"node id '{node_id}' defined more than once"))

    # Distinct raw ids that sanitize to the same Mermaid id would silently merge.
    safe_seen: dict[str, str] = {}
    for node_id in dict.fromkeys(ids):
        token = safe_id(node_id)
        if token in safe_seen:
            warnings.append(_warn(diagram_id, HIGH, "id_collision",
                                  f"ids '{safe_seen[token]}' and '{node_id}' both map to Mermaid id '{token}'"))
        else:
            safe_seen[token] = node_id

    connected: set[str] = set()
    for edge in level.get("edges", []):
        for end in ("source", "target"):
            ref = edge.get(end)
            if ref not in defined:
                warnings.append(_warn(diagram_id, HIGH, "edge_validity", f"edge {end} '{ref}' is not a defined node"))
            else:
                connected.add(ref)

    for boundary in level.get("boundaries", []):
        for ref in boundary.get("nodes", []):
            if ref not in defined:
                warnings.append(
                    _warn(diagram_id, MEDIUM, "boundary_validity", f"boundary member '{ref}' is not a defined node")
                )

    for node_id in ids:
        if node_id not in connected:
            warnings.append(_warn(diagram_id, LOW, "orphan_node", f"node '{node_id}' has no edges"))

    if len(nodes) > DENSITY_LIMIT:
        warnings.append(
            _warn(diagram_id, MEDIUM, "density", f"{len(nodes)} nodes exceeds {DENSITY_LIMIT}; consider splitting")
        )

    return _dedupe(warnings)


def _warn(diagram: str, severity: str, check: str, message: str) -> dict[str, str]:
    return {"diagram": diagram, "severity": severity, "check": check, "message": message}


def _dedupe(warnings: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, ...]] = set()
    out: list[dict[str, str]] = []
    for w in warnings:
        key = tuple(w.values())
        if key not in seen:
            seen.add(key)
            out.append(w)
    return out


def render_level(level: dict[str, Any]) -> str:
    """Render a level to Mermaid based on its ``kind``."""
    kind = level.get("kind", "flowchart")
    if kind == "classdiagram":
        return render_classdiagram(level)
    return render_flowchart(level)


def _counts(level: dict[str, Any]) -> tuple[int, int]:
    if level.get("kind") == "classdiagram":
        return len(level.get("classes", [])), len(level.get("relations", []))
    return len(level.get("nodes", [])), len(level.get("edges", []))


def build_index(project: str, entries: list[dict[str, Any]], timestamp: str) -> str:
    """Build index.md embedding every diagram in a ```mermaid fence."""
    lines = [f"# C4 Architecture - {project}", ""]
    for entry in entries:
        lines.append(f"## {entry['title']}")
        lines.append("")
        lines.append(f"_{entry['level']} - {entry['node_count']} nodes, {entry['edge_count']} edges - "
                     f"[`{entry['file']}`]({entry['file']})_")
        lines.append("")
        lines.append("```mermaid")
        lines.append(entry["mermaid"].rstrip("\n"))
        lines.append("```")
        lines.append("")
    lines.append(f"_Generated {timestamp}_")
    return "\n".join(lines) + "\n"


def build_manifest(project: str, entries: list[dict[str, Any]], timestamp: str) -> dict[str, Any]:
    return {
        "project": project,
        "generated_at": timestamp,
        "engine": "c4-mermaid",
        "diagrams": [
            {k: entry[k] for k in ("id", "level", "title", "file", "node_count", "edge_count", "parent")}
            for entry in entries
        ],
    }


def process_model(model: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Render every level, returning (entries, warnings)."""
    levels = model.get("levels")
    if not levels:
        raise C4ModelError("model has no 'levels'")

    entries: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    for level in levels:
        if "id" not in level:
            raise C4ModelError(f"level missing 'id': {level.get('level', level)}")
        mermaid = render_level(level)
        node_count, edge_count = _counts(level)
        entries.append({
            "id": level["id"],
            "level": level.get("level", ""),
            "title": level.get("title", level["id"]),
            "file": f"{level['id']}.mmd",
            "node_count": node_count,
            "edge_count": edge_count,
            "parent": level.get("parent"),
            "mermaid": mermaid,
        })
        warnings.extend(validate_level(level))
    return entries, warnings


def write_outputs(out_dir: Path, project: str, entries: list[dict[str, Any]], timestamp: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        (out_dir / entry["file"]).write_text(entry["mermaid"], encoding="utf-8")
    (out_dir / "index.md").write_text(build_index(project, entries, timestamp), encoding="utf-8")
    manifest = build_manifest(project, entries, timestamp)
    (out_dir / "c4-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _report(entries: list[dict[str, Any]], warnings: list[dict[str, str]], out_dir: Path) -> None:
    print(f"C4 Mermaid diagrams written to {out_dir}/")
    for entry in entries:
        print(f"  {entry['file']:32} {entry['node_count']:>3} nodes, {entry['edge_count']:>3} edges")
    print(f"  index.md, c4-manifest.json ({len(entries)} diagrams)")
    highs = [w for w in warnings if w["severity"] == HIGH]
    if warnings:
        print("\nQA warnings:")
        for w in warnings:
            print(f"  [{w['severity']:>6}] {w['diagram']}: {w['check']} - {w['message']}")
    print(f"\nHigh-severity (invalid reference) warnings: {len(highs)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a C4 model to GitHub-friendly Mermaid diagrams.")
    parser.add_argument("--model", required=True, help="Path to the C4 model JSON file.")
    parser.add_argument("--out", default="docs/architecture", help="Output directory (default: docs/architecture).")
    parser.add_argument("--project", help="Project name override (default: model.project).")
    parser.add_argument("--timestamp", default="", help="ISO timestamp stamped into index/manifest.")
    parser.add_argument("--lenient", action="store_true", help="Do not exit non-zero on invalid-reference warnings.")
    args = parser.parse_args(argv)

    try:
        model = json.loads(Path(args.model).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read model '{args.model}': {exc}", file=sys.stderr)
        return 2

    project = args.project or model.get("project", "Project")
    try:
        entries, warnings = process_model(model)
    except C4ModelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    write_outputs(Path(args.out), project, entries, args.timestamp)
    _report(entries, warnings, Path(args.out))

    highs = [w for w in warnings if w["severity"] == HIGH]
    if highs and not args.lenient:
        print("\nFAILED: invalid references present (re-run with --lenient to force).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

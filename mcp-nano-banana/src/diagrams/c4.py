"""C4 model diagram generator - multi-level architecture visualization.

Supports all four C4 levels:
  L1 System Context - actors, external systems, system of interest
  L2 Container - applications, databases, services within a system boundary
  L3 Component - components within a container boundary
  L4 Code - classes, modules, interfaces within a component

Node types map to C4 concepts:
  person       → Actor / User (rounded pill with icon)
  system       → External System (grey)
  system-focus → System of Interest (blue)
  container    → Container (green)
  component    → Component (purple)
  code         → Code element (amber)

Use the ``description`` field for technology labels (e.g., "Python / FastAPI").
"""

from __future__ import annotations

from diagrams.base import DiagramSpec, _css_reset, _esc


# C4-specific color palette - all combos meet WCAG AA >= 4.5:1
#
# | Type         | BG      | Text    | Ratio |
# |--------------|---------|---------|-------|
# | person       | #1e40af | #ffffff | 8.72  |
# | system       | #374151 | #f3f4f6 | 9.37  |
# | system-focus | #1d4ed8 | #ffffff | 6.70  |
# | container    | #15803d | #ffffff | 5.02  |
# | component    | #7e22ce | #ffffff | 6.98  |
# | code         | #92400e | #ffffff | 7.09  |
_C4_COLORS = {
    "person":       ("#1e40af", "#3b82f6", "#ffffff"),  # dark blue
    "system":       ("#374151", "#6b7280", "#f3f4f6"),  # grey - external
    "system-focus": ("#1d4ed8", "#60a5fa", "#ffffff"),  # blue - focus
    "container":    ("#15803d", "#22c55e", "#ffffff"),  # green
    "component":    ("#7e22ce", "#a855f7", "#ffffff"),  # purple
    "code":         ("#92400e", "#f59e0b", "#ffffff"),  # amber - darkened bg, white text
}

_DEFAULT_COLOR = ("#334155", "#475569", "#e2e8f0")


def _c4_color(node_type: str) -> tuple[str, str, str]:
    """Return (bg, border, text) for a C4 node type."""
    return _C4_COLORS.get(node_type, _DEFAULT_COLOR)


def _person_svg(fill: str = "#ffffff") -> str:
    """Inline SVG stick-figure icon for person nodes."""
    return (
        f'<svg width="40" height="40" viewBox="0 0 40 40" fill="none">'
        f'<circle cx="20" cy="10" r="7" fill="{fill}" opacity="0.9"/>'
        f'<path d="M10 38 L20 22 L30 38" stroke="{fill}" stroke-width="3" '
        f'fill="none" stroke-linecap="round"/>'
        f'<line x1="8" y1="30" x2="32" y2="30" stroke="{fill}" '
        f'stroke-width="3" stroke-linecap="round"/>'
        f'</svg>'
    )


def generate_c4_diagram(
    spec: DiagramSpec,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Generate an HTML C4 model diagram.

    Nodes are rendered as styled cards with technology labels.
    Edges are shown as labelled arrows between nodes.
    Boundary groupings are inferred from node types - nodes of the same
    ``type`` are visually grouped inside a dashed boundary box.
    """
    css = _css_reset(width, height)

    # ── group nodes by type for boundary rendering ──────────────────
    type_order = ["person", "system-focus", "container", "component", "code", "system"]
    groups: dict[str, list] = {}
    for node in spec.nodes:
        groups.setdefault(node.type, []).append(node)

    # ── build node HTML ─────────────────────────────────────────────
    nodes_by_id: dict[str, int] = {}
    all_nodes_html = []

    for idx, node in enumerate(spec.nodes):
        nodes_by_id[node.id] = idx
        bg, border, text = _c4_color(node.type)
        is_person = node.type == "person"

        icon_html = _person_svg(text) if is_person else ""
        tech_html = (
            f'<div class="c4-tech">[{_esc(node.description)}]</div>'
            if node.description else ""
        )

        shape_class = "c4-person" if is_person else "c4-box"

        all_nodes_html.append(f"""
        <div class="c4-node {shape_class}" id="node-{_esc(node.id)}"
             data-type="{_esc(node.type)}"
             style="background:{bg}; border-color:{border}; color:{text};">
            {icon_html}
            <div class="c4-label">{_esc(node.label)}</div>
            {tech_html}
        </div>
        """)

    # ── build boundary wrappers ─────────────────────────────────────
    # Group nodes into boundary sections for visual clarity
    boundary_labels = {
        "person": "Actors",
        "system": "External Systems",
        "system-focus": "System Boundary",
        "container": "Containers",
        "component": "Components",
        "code": "Code",
    }

    sections_html = []
    rendered_ids: set[str] = set()

    for t in type_order:
        if t not in groups:
            continue
        g_nodes = groups[t]
        if not g_nodes:
            continue

        node_ids = [n.id for n in g_nodes]
        rendered_ids.update(node_ids)

        inner = "\n".join(
            html for html, node in zip(all_nodes_html, spec.nodes)
            if node.id in node_ids
        )

        _, border, _ = _c4_color(t)
        label = boundary_labels.get(t, t.title())

        if t in ("person", "system"):
            # No boundary box for external actors/systems
            sections_html.append(f"""
            <div class="c4-section c4-section-open">
                <div class="c4-section-label" style="color:{border}">{label}</div>
                <div class="c4-section-nodes">{inner}</div>
            </div>
            """)
        else:
            sections_html.append(f"""
            <div class="c4-section c4-section-bounded" style="border-color:{border}40">
                <div class="c4-section-label" style="color:{border}">{label}</div>
                <div class="c4-section-nodes">{inner}</div>
            </div>
            """)

    # Any remaining nodes not in type_order
    remaining = [
        html for html, node in zip(all_nodes_html, spec.nodes)
        if node.id not in rendered_ids
    ]
    if remaining:
        sections_html.append(f"""
        <div class="c4-section c4-section-open">
            <div class="c4-section-nodes">{''.join(remaining)}</div>
        </div>
        """)

    # ── build edge labels overlay ───────────────────────────────────
    edge_labels_html = []
    for edge in spec.edges:
        dash = ""
        if edge.style == "dashed":
            dash = "stroke-dasharray: 8 4;"
        elif edge.style == "dotted":
            dash = "stroke-dasharray: 2 4;"

        label_html = (
            f'<span class="c4-edge-label">{_esc(edge.label)}</span>'
            if edge.label else ""
        )
        edge_labels_html.append(f"""
        <div class="c4-edge" data-from="{_esc(edge.source)}" data-to="{_esc(edge.target)}"
             data-dash="{dash}">
            <span class="c4-edge-from">{_esc(edge.source)}</span>
            <span class="c4-edge-arrow">&#x2192;</span>
            {label_html}
            <span class="c4-edge-to">{_esc(edge.target)}</span>
        </div>
        """)

    subtitle = _esc(spec.description) if spec.description else "C4 Architecture Diagram"
    edges_section = ""
    if edge_labels_html:
        edges_section = f"""
        <div class="c4-edges-panel">
            <div class="c4-edges-title">Relationships</div>
            {''.join(edge_labels_html)}
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}">
<title>{_esc(spec.title)}</title>
<style>
{css}
.c4-layout {{
    display: flex;
    flex-direction: column;
    gap: 20px;
    width: 100%;
    max-width: {width - 80}px;
    flex: 1;
}}
.c4-sections {{
    display: flex;
    flex-wrap: wrap;
    gap: 24px;
    justify-content: center;
    align-items: flex-start;
    flex: 1;
}}
.c4-section {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 16px;
    border-radius: 12px;
    min-width: 200px;
    flex: 1;
    max-width: 50%;
}}
.c4-section-bounded {{
    border: 2px dashed;
    background: rgba(255,255,255,0.03);
}}
.c4-section-open {{
    border: none;
}}
.c4-section-label {{
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 4px;
}}
.c4-section-nodes {{
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    justify-content: center;
}}
.c4-node {{
    padding: 16px 20px;
    border-radius: 10px;
    border: 2px solid;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    min-width: 160px;
    max-width: 240px;
    flex: 0 1 auto;
}}
.c4-person {{
    border-radius: 50px;
    padding: 20px 24px;
}}
.c4-label {{
    font-size: 16px;
    font-weight: 700;
    margin: 4px 0;
}}
.c4-tech {{
    font-size: 12px;
    opacity: 0.8;
    margin-top: 4px;
    font-style: italic;
}}
.c4-edges-panel {{
    background: rgba(255,255,255,0.04);
    border-radius: 8px;
    padding: 12px 20px;
    margin-top: 8px;
}}
.c4-edges-title {{
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #64748b;
    margin-bottom: 8px;
}}
.c4-edge {{
    font-size: 13px;
    color: #94a3b8;
    padding: 3px 0;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.c4-edge-from, .c4-edge-to {{
    font-weight: 600;
    color: #cbd5e1;
}}
.c4-edge-arrow {{
    color: #64748b;
    font-size: 16px;
}}
.c4-edge-label {{
    color: #60a5fa;
    font-style: italic;
}}
</style>
</head>
<body>
<div class="diagram-container">
    <div class="diagram-title">{_esc(spec.title)}</div>
    <div class="diagram-subtitle">{subtitle}</div>
    <div class="diagram-body">
        <div class="c4-layout">
            <div class="c4-sections">
                {''.join(sections_html)}
            </div>
            {edges_section}
        </div>
    </div>
</div>
</body>
</html>"""

"""C4 model diagram generator - multi-level architecture visualization.

Supports all four C4 levels:
  L1 System Context - actors, external systems, system of interest
  L2 Container - applications, databases, services within a system boundary
  L3 Component - components within a container boundary
  L4 Code - classes, modules, interfaces within a component

Node types map to C4 concepts:
  person       -> Actor / User (rounded pill with icon)
  system       -> External System (grey)
  system-focus -> System of Interest (blue)
  container    -> Container (green)
  component    -> Component (purple)
  code         -> Code element (amber)

Use the ``description`` field for technology labels (e.g., "Python / FastAPI").
"""

from __future__ import annotations

from diagrams.base import DiagramSpec, ThemeTokens, _css_reset, _esc, _DEFAULT_THEME


def _c4_color(
    node_type: str,
    theme: ThemeTokens | None = None,
) -> tuple[str, str, str]:
    """Return (bg, border, text) for a C4 node type."""
    t = theme or _DEFAULT_THEME
    colors = {
        "person": t.c4_person,
        "system": t.c4_system,
        "system-focus": t.c4_system_focus,
        "container": t.c4_container,
        "component": t.c4_component,
        "code": t.c4_code,
    }
    return colors.get(node_type, t.c4_default)


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
    theme: ThemeTokens | None = None,
) -> str:
    """Generate an HTML C4 model diagram.

    Nodes are rendered as styled cards with technology labels.
    Edges are shown as labelled arrows between nodes.
    Boundary groupings are inferred from node types - nodes of the same
    ``type`` are visually grouped inside a dashed boundary box.
    """
    t = theme or _DEFAULT_THEME
    css = _css_reset(width, height, t)

    # -- group nodes by type for boundary rendering --
    type_order = ["person", "system-focus", "container", "component", "code", "system"]
    groups: dict[str, list] = {}
    for node in spec.nodes:
        groups.setdefault(node.type, []).append(node)

    # -- build node HTML --
    nodes_by_id: dict[str, int] = {}
    all_nodes_html = []

    for idx, node in enumerate(spec.nodes):
        nodes_by_id[node.id] = idx
        bg, border, text = _c4_color(node.type, t)
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

    # -- build boundary wrappers --
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

    for tp in type_order:
        if tp not in groups:
            continue
        g_nodes = groups[tp]
        if not g_nodes:
            continue

        node_ids = [n.id for n in g_nodes]
        rendered_ids.update(node_ids)

        inner = "\n".join(
            html for html, node in zip(all_nodes_html, spec.nodes)
            if node.id in node_ids
        )

        _, border, _ = _c4_color(tp, t)
        label = boundary_labels.get(tp, tp.title())

        if tp in ("person", "system"):
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

    # -- build edge labels overlay --
    id_to_label = {node.id: node.label for node in spec.nodes}
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
        from_label = id_to_label.get(edge.source, edge.source)
        to_label = id_to_label.get(edge.target, edge.target)
        edge_labels_html.append(f"""
        <div class="c4-edge" data-from="{_esc(edge.source)}" data-to="{_esc(edge.target)}"
             data-dash="{dash}">
            <span class="c4-edge-from">{_esc(from_label)}</span>
            <span class="c4-edge-arrow">&#x2192;</span>
            {label_html}
            <span class="c4-edge-to">{_esc(to_label)}</span>
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
    background: {t.boundary_bg};
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
    background: {t.panel_bg};
    border-radius: 8px;
    padding: 12px 20px;
    margin-top: 8px;
    max-height: 200px;
    overflow-y: auto;
    flex-shrink: 0;
}}
.c4-edges-title {{
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: {t.text_tertiary};
    margin-bottom: 8px;
}}
.c4-edge {{
    font-size: 13px;
    color: {t.text_secondary};
    padding: 3px 0;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.c4-edge-from, .c4-edge-to {{
    font-weight: 600;
    color: {t.edge_from_to_color};
}}
.c4-edge-arrow {{
    color: {t.arrow_color};
    font-size: 16px;
}}
.c4-edge-label {{
    color: {t.highlight_color};
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

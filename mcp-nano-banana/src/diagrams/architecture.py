"""Architecture diagram generator - layered system architecture visualization."""

from __future__ import annotations

from diagrams.base import DiagramSpec, _css_reset, _esc, _node_color


def generate_architecture_diagram(
    spec: DiagramSpec,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Generate an HTML architecture diagram with layered components.

    Renders nodes as boxes arranged in a responsive grid layout with
    connection lines between related components.
    """
    css = _css_reset(width, height)

    # Build node HTML
    nodes_html = []
    for i, node in enumerate(spec.nodes):
        bg, border, text = _node_color(node.type)
        icon_html = f'<div class="node-icon">{_esc(node.icon)}</div>' if node.icon else ""
        desc_html = f'<div class="node-desc">{_esc(node.description)}</div>' if node.description else ""
        nodes_html.append(f"""
        <div class="arch-node" id="node-{_esc(node.id)}" style="
            background: {bg};
            border: 2px solid {border};
            color: {text};
        ">
            {icon_html}
            <div class="node-label">{_esc(node.label)}</div>
            {desc_html}
        </div>
        """)

    # Build SVG edges
    edges_svg = ""
    if spec.edges:
        edges_svg = '<svg class="edges-layer" width="100%" height="100%">'
        edges_svg += '<defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#64748b"/></marker></defs>'
        edges_svg += "</svg>"

    subtitle = _esc(spec.description) if spec.description else "System Architecture"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}">
<title>{_esc(spec.title)}</title>
<style>
{css}
.arch-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 24px;
    width: 100%;
    max-width: {width - 80}px;
}}
.arch-node {{
    padding: 20px 24px;
    border-radius: 12px;
    text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    position: relative;
    z-index: 2;
}}
.arch-node:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}}
.node-label {{
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 4px;
}}
.node-desc {{
    font-size: 13px;
    opacity: 0.85;
    margin-top: 6px;
}}
.node-icon {{
    font-size: 28px;
    margin-bottom: 8px;
}}
.edges-layer {{
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: none;
    z-index: 1;
}}
</style>
</head>
<body>
<div class="diagram-container">
    <div class="diagram-title">{_esc(spec.title)}</div>
    <div class="diagram-subtitle">{subtitle}</div>
    <div class="diagram-body">
        {edges_svg}
        <div class="arch-grid">
            {''.join(nodes_html)}
        </div>
    </div>
</div>
</body>
</html>"""

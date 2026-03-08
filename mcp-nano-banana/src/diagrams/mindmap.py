"""Mind map / concept map diagram generator."""

from __future__ import annotations

import math

from diagrams.base import DiagramSpec, _css_reset, _esc, _node_color


def generate_mindmap_diagram(
    spec: DiagramSpec,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Generate an HTML mind map with a central topic and radiating branches.

    First node is the central topic; remaining nodes radiate outward.
    """
    css = _css_reset(width, height)

    if not spec.nodes:
        return _empty_diagram(spec.title, width, height, css)

    center = spec.nodes[0]
    branches = spec.nodes[1:]
    num_branches = len(branches)

    cx, cy = (width - 80) // 2, (height - 200) // 2
    radius = min(cx, cy) - 100

    # Central node
    bg, border, text = _node_color(center.type if center.type != "default" else "primary")
    center_html = f"""
    <div class="mm-center" style="
        left: {cx - 80}px; top: {cy - 40}px;
        background: {bg}; border-color: {border}; color: {text};
    ">
        <div class="mm-label">{_esc(center.label)}</div>
    </div>
    """

    # Branch nodes + SVG lines
    branch_html = []
    lines_svg = []
    for i, node in enumerate(branches):
        angle = (2 * math.pi * i / num_branches) - math.pi / 2
        nx = int(cx + radius * math.cos(angle))
        ny = int(cy + radius * math.sin(angle))
        bg, border, text = _node_color(node.type)
        desc_html = f'<div class="mm-desc">{_esc(node.description)}</div>' if node.description else ""

        branch_html.append(f"""
        <div class="mm-branch" style="
            left: {nx - 70}px; top: {ny - 30}px;
            background: {bg}; border-color: {border}; color: {text};
        ">
            <div class="mm-label">{_esc(node.label)}</div>
            {desc_html}
        </div>
        """)

        lines_svg.append(
            f'<line x1="{cx}" y1="{cy}" x2="{nx}" y2="{ny}" '
            f'stroke="{border}" stroke-width="2" opacity="0.6"/>'
        )

    subtitle = _esc(spec.description) if spec.description else "Concept Map"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}">
<title>{_esc(spec.title)}</title>
<style>
{css}
.mm-canvas {{
    position: relative;
    width: 100%;
    height: 100%;
}}
.mm-center {{
    position: absolute;
    padding: 18px 28px;
    border-radius: 50%;
    border: 3px solid;
    text-align: center;
    box-shadow: 0 0 24px rgba(59, 130, 246, 0.4);
    z-index: 3;
    min-width: 160px;
}}
.mm-branch {{
    position: absolute;
    padding: 12px 18px;
    border-radius: 10px;
    border: 2px solid;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    z-index: 2;
    min-width: 140px;
}}
.mm-label {{
    font-size: 15px;
    font-weight: 600;
}}
.mm-desc {{
    font-size: 12px;
    opacity: 0.85;
    margin-top: 4px;
}}
.mm-lines {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
}}
</style>
</head>
<body>
<div class="diagram-container">
    <div class="diagram-title">{_esc(spec.title)}</div>
    <div class="diagram-subtitle">{subtitle}</div>
    <div class="diagram-body">
        <div class="mm-canvas">
            <svg class="mm-lines" viewBox="0 0 {width - 80} {height - 200}">
                {''.join(lines_svg)}
            </svg>
            {center_html}
            {''.join(branch_html)}
        </div>
    </div>
</div>
</body>
</html>"""


def _empty_diagram(title: str, width: int, height: int, css: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>{_esc(title)}</title>
<style>{css}</style></head>
<body><div class="diagram-container">
<div class="diagram-title">{_esc(title)}</div>
<div class="diagram-subtitle">No nodes provided</div>
<div class="diagram-body"><p style="color:#94a3b8;">Add nodes to generate a mind map.</p></div>
</div></body></html>"""

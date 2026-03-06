"""Flowchart diagram generator - process flow visualization."""

from __future__ import annotations

from diagrams.base import DiagramSpec, _css_reset, _node_color


def generate_flowchart_diagram(
    spec: DiagramSpec,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Generate an HTML flowchart with connected process steps.

    Renders nodes as rounded rectangles connected by arrows,
    arranged in a top-down or left-right flow.
    """
    css = _css_reset(width, height)

    nodes_html = []
    for i, node in enumerate(spec.nodes):
        bg, border, text = _node_color(node.type)
        shape_class = "flow-diamond" if node.type == "warning" else "flow-rect"
        desc_html = f'<div class="flow-desc">{node.description}</div>' if node.description else ""
        nodes_html.append(f"""
        <div class="flow-step">
            <div class="{shape_class}" style="background: {bg}; border-color: {border}; color: {text};">
                <div class="flow-label">{node.label}</div>
                {desc_html}
            </div>
            {"<div class='flow-arrow'>&#x2193;</div>" if i < len(spec.nodes) - 1 else ""}
        </div>
        """)

    subtitle = spec.description or "Process Flow"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}">
<title>{spec.title}</title>
<style>
{css}
.flow-container {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    width: 100%;
    overflow-y: auto;
    max-height: {height - 160}px;
}}
.flow-step {{
    display: flex;
    flex-direction: column;
    align-items: center;
}}
.flow-rect {{
    padding: 18px 36px;
    border-radius: 12px;
    border: 2px solid;
    min-width: 240px;
    max-width: 480px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}}
.flow-diamond {{
    padding: 18px 36px;
    border-radius: 4px;
    border: 2px solid;
    min-width: 200px;
    max-width: 400px;
    text-align: center;
    transform: rotate(0deg);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);
    padding: 40px 60px;
}}
.flow-label {{
    font-size: 17px;
    font-weight: 600;
}}
.flow-desc {{
    font-size: 13px;
    opacity: 0.85;
    margin-top: 6px;
}}
.flow-arrow {{
    font-size: 28px;
    color: #64748b;
    line-height: 1;
    padding: 4px 0;
}}
</style>
</head>
<body>
<div class="diagram-container">
    <div class="diagram-title">{spec.title}</div>
    <div class="diagram-subtitle">{subtitle}</div>
    <div class="diagram-body">
        <div class="flow-container">
            {''.join(nodes_html)}
        </div>
    </div>
</div>
</body>
</html>"""

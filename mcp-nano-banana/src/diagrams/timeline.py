"""Timeline / roadmap diagram generator."""

from __future__ import annotations

from diagrams.base import DiagramSpec, ThemeTokens, _css_reset, _esc, _node_color


def generate_timeline_diagram(
    spec: DiagramSpec,
    width: int = 1920,
    height: int = 1080,
    theme: ThemeTokens | None = None,
) -> str:
    """Generate an HTML timeline/roadmap visualization.

    Nodes are milestones arranged along a horizontal timeline.
    """
    from diagrams.base import _DEFAULT_THEME
    t = theme or _DEFAULT_THEME
    css = _css_reset(width, height, t)
    milestones = spec.nodes

    items_html = []
    for i, node in enumerate(milestones):
        bg, border, text = _node_color(node.type, t)
        desc_html = f'<div class="tl-desc">{_esc(node.description)}</div>' if node.description else ""
        side = "top" if i % 2 == 0 else "bottom"
        items_html.append(f"""
        <div class="tl-item tl-{side}">
            <div class="tl-dot" style="background: {bg}; border-color: {border};"></div>
            <div class="tl-card" style="background: {bg}; border-color: {border}; color: {text};">
                <div class="tl-label">{_esc(node.label)}</div>
                {desc_html}
            </div>
        </div>
        """)

    subtitle = _esc(spec.description) if spec.description else "Project Timeline"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}">
<title>{_esc(spec.title)}</title>
<style>
{css}
.tl-track {{
    display: flex;
    align-items: center;
    justify-content: space-around;
    width: 100%;
    position: relative;
    height: 400px;
}}
.tl-track::before {{
    content: '';
    position: absolute;
    top: 50%;
    left: 40px;
    right: 40px;
    height: 4px;
    background: linear-gradient(90deg, {t.gradient_start}, {t.gradient_mid}, {t.gradient_end});
    border-radius: 2px;
    transform: translateY(-50%);
}}
.tl-item {{
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
    z-index: 2;
    flex: 1;
}}
.tl-top .tl-card {{
    margin-bottom: 20px;
    order: -1;
}}
.tl-bottom .tl-card {{
    margin-top: 20px;
}}
.tl-dot {{
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: 3px solid;
    box-shadow: 0 0 12px {t.glow_color};
}}
.tl-card {{
    padding: 14px 18px;
    border-radius: 10px;
    border: 2px solid;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    min-width: 120px;
    max-width: 200px;
}}
.tl-label {{
    font-size: 15px;
    font-weight: 600;
}}
.tl-desc {{
    font-size: 12px;
    opacity: 0.85;
    margin-top: 4px;
}}
</style>
</head>
<body>
<div class="diagram-container">
    <div class="diagram-title">{_esc(spec.title)}</div>
    <div class="diagram-subtitle">{subtitle}</div>
    <div class="diagram-body">
        <div class="tl-track">
            {''.join(items_html)}
        </div>
    </div>
</div>
</body>
</html>"""

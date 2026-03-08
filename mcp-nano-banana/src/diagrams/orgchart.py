"""Org chart / hierarchy diagram generator."""

from __future__ import annotations

from diagrams.base import DiagramSpec, ThemeTokens, _css_reset, _esc, _node_color


def generate_orgchart_diagram(
    spec: DiagramSpec,
    width: int = 1920,
    height: int = 1080,
    theme: ThemeTokens | None = None,
) -> str:
    """Generate an HTML org chart / hierarchy diagram.

    Nodes are arranged in a tree layout using CSS flexbox nesting.
    Edges define parent-child relationships.
    """
    from diagrams.base import _DEFAULT_THEME
    t = theme or _DEFAULT_THEME
    css = _css_reset(width, height, t)

    # Build tree from edges
    children_map: dict[str, list[str]] = {}
    has_parent: set[str] = set()
    node_map = {n.id: n for n in spec.nodes}

    for edge in spec.edges:
        children_map.setdefault(edge.source, []).append(edge.target)
        has_parent.add(edge.target)

    # Find root nodes (no parent)
    roots = [n.id for n in spec.nodes if n.id not in has_parent]
    if not roots and spec.nodes:
        roots = [spec.nodes[0].id]

    def render_node(node_id: str, depth: int = 0) -> str:
        node = node_map.get(node_id)
        if not node:
            return ""
        bg, border, text = _node_color(node.type, t)
        desc_html = f'<div class="org-desc">{_esc(node.description)}</div>' if node.description else ""

        kids = children_map.get(node_id, [])
        kids_html = ""
        if kids:
            kids_inner = "".join(render_node(k, depth + 1) for k in kids)
            kids_html = f'<div class="org-children">{kids_inner}</div>'

        return f"""
        <div class="org-branch">
            <div class="org-card" style="background: {bg}; border-color: {border}; color: {text};">
                <div class="org-name">{_esc(node.label)}</div>
                {desc_html}
            </div>
            {kids_html}
        </div>
        """

    tree_html = "".join(render_node(r) for r in roots)
    subtitle = _esc(spec.description) if spec.description else "Organization Chart"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}">
<title>{_esc(spec.title)}</title>
<style>
{css}
.org-tree {{
    display: flex;
    justify-content: center;
    width: 100%;
}}
.org-branch {{
    display: flex;
    flex-direction: column;
    align-items: center;
}}
.org-card {{
    padding: 14px 22px;
    border-radius: 10px;
    border: 2px solid;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    min-width: 140px;
    max-width: 220px;
}}
.org-name {{
    font-size: 15px;
    font-weight: 600;
}}
.org-desc {{
    font-size: 12px;
    opacity: 0.85;
    margin-top: 4px;
}}
.org-children {{
    display: flex;
    gap: 24px;
    margin-top: 20px;
    padding-top: 20px;
    border-top: 2px solid {t.connection_color};
    position: relative;
}}
.org-children::before {{
    content: '';
    position: absolute;
    top: -2px;
    left: 50%;
    width: 0;
    height: 20px;
    border-left: 2px solid {t.connection_color};
    transform: translateX(-50%);
    top: -20px;
}}
</style>
</head>
<body>
<div class="diagram-container">
    <div class="diagram-title">{_esc(spec.title)}</div>
    <div class="diagram-subtitle">{subtitle}</div>
    <div class="diagram-body">
        <div class="org-tree">
            {tree_html}
        </div>
    </div>
</div>
</body>
</html>"""

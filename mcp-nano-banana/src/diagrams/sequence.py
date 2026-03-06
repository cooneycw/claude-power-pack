"""Sequence diagram generator - interaction/message sequence visualization."""

from __future__ import annotations

from diagrams.base import DiagramSpec, _css_reset, _node_color


def generate_sequence_diagram(
    spec: DiagramSpec,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Generate an HTML sequence diagram showing interactions between participants.

    Nodes are participants (columns), edges are messages (rows).
    """
    css = _css_reset(width, height)

    participants = spec.nodes
    messages = spec.edges
    num_participants = len(participants)

    if num_participants == 0:
        num_participants = 1

    col_width = min(250, (width - 120) // num_participants)

    # Build participant headers
    headers_html = []
    for i, p in enumerate(participants):
        bg, border, text = _node_color(p.type)
        headers_html.append(f"""
        <div class="seq-participant" style="
            width: {col_width}px;
            background: {bg};
            border-color: {border};
            color: {text};
        ">
            <div class="seq-name">{p.label}</div>
        </div>
        """)

    # Build lifeline SVG
    lifeline_gap = col_width
    lifeline_start_y = 80
    lifeline_end_y = height - 200

    lifelines_svg = ""
    for i in range(num_participants):
        x = 60 + i * lifeline_gap + lifeline_gap // 2
        lifelines_svg += f'<line x1="{x}" y1="{lifeline_start_y}" x2="{x}" y2="{lifeline_end_y}" stroke="#475569" stroke-width="2" stroke-dasharray="6,4"/>'

    # Build messages
    messages_svg = ""
    msg_y = lifeline_start_y + 40
    msg_step = max(40, (lifeline_end_y - lifeline_start_y - 60) // max(len(messages), 1))

    # Map participant IDs to indices
    id_to_idx = {p.id: i for i, p in enumerate(participants)}

    for edge in messages:
        src_idx = id_to_idx.get(edge.source, 0)
        tgt_idx = id_to_idx.get(edge.target, 0)
        x1 = 60 + src_idx * lifeline_gap + lifeline_gap // 2
        x2 = 60 + tgt_idx * lifeline_gap + lifeline_gap // 2

        # Arrow
        if x1 != x2:
            messages_svg += f'<line x1="{x1}" y1="{msg_y}" x2="{x2}" y2="{msg_y}" stroke="#60a5fa" stroke-width="2" marker-end="url(#seq-arrow)"/>'
        else:
            # Self-message (loop)
            messages_svg += f'<path d="M {x1} {msg_y} C {x1 + 60} {msg_y - 15}, {x1 + 60} {msg_y + 15}, {x1} {msg_y + 20}" stroke="#60a5fa" stroke-width="2" fill="none" marker-end="url(#seq-arrow)"/>'

        # Label
        label_x = (x1 + x2) // 2
        label_y = msg_y - 8
        messages_svg += f'<text x="{label_x}" y="{label_y}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="Segoe UI, system-ui, sans-serif">{edge.label}</text>'

        msg_y += msg_step

    subtitle = spec.description or "Sequence Diagram"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}">
<title>{spec.title}</title>
<style>
{css}
.seq-header {{
    display: flex;
    justify-content: center;
    gap: 0;
    margin-bottom: 0;
    position: relative;
    z-index: 2;
}}
.seq-participant {{
    padding: 12px 16px;
    border-radius: 8px;
    border: 2px solid;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}}
.seq-name {{
    font-size: 15px;
    font-weight: 600;
}}
.seq-canvas {{
    position: relative;
    flex: 1;
    width: 100%;
}}
.seq-canvas svg {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}}
</style>
</head>
<body>
<div class="diagram-container">
    <div class="diagram-title">{spec.title}</div>
    <div class="diagram-subtitle">{subtitle}</div>
    <div class="diagram-body" style="flex-direction: column; align-items: stretch;">
        <div class="seq-header">
            {''.join(headers_html)}
        </div>
        <div class="seq-canvas">
            <svg width="100%" height="100%" viewBox="0 0 {width - 80} {height - 200}">
                <defs>
                    <marker id="seq-arrow" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="#60a5fa"/>
                    </marker>
                </defs>
                {lifelines_svg}
                {messages_svg}
            </svg>
        </div>
    </div>
</div>
</body>
</html>"""

"""Base models and utilities for diagram generation."""

from __future__ import annotations

import html as _html_mod
from dataclasses import dataclass, field


def _esc(text: str) -> str:
    """HTML-escape user-provided text to prevent XSS injection.

    Must be applied to all node labels, descriptions, icons, edge labels,
    spec titles, and spec descriptions before embedding in HTML output.
    """
    return _html_mod.escape(str(text), quote=True)


def _relative_luminance(hex_color: str) -> float:
    """Calculate relative luminance per WCAG 2.1 definition."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255

    def _linearize(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _contrast_ratio(fg: str, bg: str) -> float:
    """Calculate WCAG 2.1 contrast ratio between two hex colors.

    Returns a value >= 1.0 where 4.5:1 is the WCAG AA minimum for normal text
    and 3.0:1 is the minimum for large text (>= 18px bold).
    """
    l1, l2 = _relative_luminance(fg), _relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


DIAGRAM_TYPES = [
    "architecture",
    "c4",
    "flowchart",
    "sequence",
    "orgchart",
    "timeline",
    "mindmap",
]


@dataclass
class DiagramNode:
    """A node in a diagram."""
    id: str
    label: str
    type: str = "default"  # default, primary, secondary, accent, warning, success
    description: str = ""
    icon: str = ""


@dataclass
class DiagramEdge:
    """An edge connecting two nodes."""
    source: str
    target: str
    label: str = ""
    style: str = "solid"  # solid, dashed, dotted


@dataclass
class DiagramSpec:
    """Specification for a diagram."""
    title: str
    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)
    description: str = ""


def _css_reset(width: int, height: int) -> str:
    """Shared CSS reset and base styles for all diagrams."""
    return f"""
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        width: {width}px;
        height: {height}px;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #e2e8f0;
        overflow: hidden;
    }}
    .diagram-container {{
        width: {width}px;
        height: {height}px;
        padding: 40px;
        display: flex;
        flex-direction: column;
    }}
    .diagram-title {{
        font-size: 36px;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 8px;
        letter-spacing: -0.5px;
    }}
    .diagram-subtitle {{
        font-size: 16px;
        color: #94a3b8;
        margin-bottom: 30px;
    }}
    .diagram-body {{
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
    }}
    """


def _node_color(node_type: str) -> tuple[str, str, str]:
    """Return (bg, border, text) colors for a node type.

    All combinations meet WCAG AA contrast ratio >= 4.5:1 for normal text.

    | Type      | BG      | Text    | Ratio |
    |-----------|---------|---------|-------|
    | primary   | #2563eb | #ffffff | 5.17  |
    | secondary | #7c3aed | #ffffff | 5.70  |
    | accent    | #f59e0b | #1e293b | 6.81  |
    | warning   | #dc2626 | #ffffff | 4.83  |
    | success   | #047857 | #ffffff | 5.48  |
    | default   | #334155 | #e2e8f0 | 8.40  |
    """
    colors = {
        "primary": ("#2563eb", "#3b82f6", "#ffffff"),
        "secondary": ("#7c3aed", "#a78bfa", "#ffffff"),
        "accent": ("#f59e0b", "#fbbf24", "#1e293b"),
        "warning": ("#dc2626", "#f87171", "#ffffff"),
        "success": ("#047857", "#34d399", "#ffffff"),
        "default": ("#334155", "#475569", "#e2e8f0"),
    }
    return colors.get(node_type, colors["default"])

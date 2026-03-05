"""Base models and utilities for diagram generation."""

from __future__ import annotations

from dataclasses import dataclass, field


DIAGRAM_TYPES = [
    "architecture",
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
    """Return (bg, border, text) colors for a node type."""
    colors = {
        "primary": ("#3b82f6", "#60a5fa", "#ffffff"),
        "secondary": ("#8b5cf6", "#a78bfa", "#ffffff"),
        "accent": ("#f59e0b", "#fbbf24", "#1e293b"),
        "warning": ("#ef4444", "#f87171", "#ffffff"),
        "success": ("#10b981", "#34d399", "#ffffff"),
        "default": ("#334155", "#475569", "#e2e8f0"),
    }
    return colors.get(node_type, colors["default"])

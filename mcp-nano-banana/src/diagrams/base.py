"""Base models and utilities for diagram generation."""

from __future__ import annotations

import dataclasses
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


# ---------------------------------------------------------------------------
# Theme token system
# ---------------------------------------------------------------------------

@dataclass
class ThemeTokens:
    """Shared color tokens for cross-diagram consistency.

    All text/background combinations must meet WCAG AA >= 4.5:1 contrast.
    """

    # Background
    background_primary: str = "#0f172a"
    background_secondary: str = "#1e293b"

    # Text
    text_primary: str = "#f8fafc"
    text_secondary: str = "#94a3b8"
    text_body: str = "#e2e8f0"
    text_tertiary: str = "#64748b"

    # Utility colors
    arrow_color: str = "#64748b"
    lifeline_color: str = "#475569"
    highlight_color: str = "#60a5fa"
    connection_color: str = "#475569"
    glow_color: str = "rgba(59, 130, 246, 0.4)"

    # Timeline gradient
    gradient_start: str = "#3b82f6"
    gradient_mid: str = "#8b5cf6"
    gradient_end: str = "#f59e0b"

    # Section/panel backgrounds
    boundary_bg: str = "rgba(255,255,255,0.03)"
    panel_bg: str = "rgba(255,255,255,0.04)"
    edge_from_to_color: str = "#cbd5e1"

    # Generic node colors (bg, border, text)
    node_primary: tuple[str, str, str] = ("#2563eb", "#3b82f6", "#ffffff")
    node_secondary: tuple[str, str, str] = ("#7c3aed", "#a78bfa", "#ffffff")
    node_accent: tuple[str, str, str] = ("#f59e0b", "#fbbf24", "#1e293b")
    node_warning: tuple[str, str, str] = ("#dc2626", "#f87171", "#ffffff")
    node_success: tuple[str, str, str] = ("#047857", "#34d399", "#ffffff")
    node_default: tuple[str, str, str] = ("#334155", "#475569", "#e2e8f0")

    # C4-specific node colors (bg, border, text)
    c4_person: tuple[str, str, str] = ("#1e40af", "#3b82f6", "#ffffff")
    c4_system: tuple[str, str, str] = ("#374151", "#6b7280", "#f3f4f6")
    c4_system_focus: tuple[str, str, str] = ("#1d4ed8", "#60a5fa", "#ffffff")
    c4_container: tuple[str, str, str] = ("#15803d", "#22c55e", "#ffffff")
    c4_component: tuple[str, str, str] = ("#7e22ce", "#a855f7", "#ffffff")
    c4_code: tuple[str, str, str] = ("#92400e", "#f59e0b", "#ffffff")
    c4_default: tuple[str, str, str] = ("#334155", "#475569", "#e2e8f0")


THEMES: dict[str, ThemeTokens] = {
    "c4-default-dark-v1": ThemeTokens(),
}

_DEFAULT_THEME = THEMES["c4-default-dark-v1"]


def get_theme(
    theme_id: str = "c4-default-dark-v1",
    overrides: dict | None = None,
) -> ThemeTokens:
    """Resolve a theme by ID with optional token overrides.

    Args:
        theme_id: Named theme from ``THEMES`` registry.
        overrides: Dict of token names to override values. List values for
            node color fields are converted to tuples automatically.

    Returns:
        A ``ThemeTokens`` instance (possibly a modified copy).
    """
    if theme_id not in THEMES:
        raise ValueError(
            f"Unknown theme '{theme_id}'. Available: {list(THEMES.keys())}"
        )
    theme = THEMES[theme_id]
    if overrides:
        valid = {k: v for k, v in overrides.items() if hasattr(theme, k)}
        # Convert list overrides to tuples for node color fields
        for k, v in list(valid.items()):
            if isinstance(v, list) and k.startswith(("node_", "c4_")):
                valid[k] = tuple(v)
        theme = dataclasses.replace(theme, **valid)
    return theme


# ---------------------------------------------------------------------------
# Diagram type registry and models
# ---------------------------------------------------------------------------

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


def _css_reset(
    width: int,
    height: int,
    theme: ThemeTokens | None = None,
) -> str:
    """Shared CSS reset and base styles for all diagrams."""
    t = theme or _DEFAULT_THEME
    return f"""
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        width: {width}px;
        height: {height}px;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        background: linear-gradient(135deg, {t.background_primary} 0%, {t.background_secondary} 100%);
        color: {t.text_body};
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
        color: {t.text_primary};
        margin-bottom: 8px;
        letter-spacing: -0.5px;
    }}
    .diagram-subtitle {{
        font-size: 16px;
        color: {t.text_secondary};
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


def _node_color(
    node_type: str,
    theme: ThemeTokens | None = None,
) -> tuple[str, str, str]:
    """Return (bg, border, text) colors for a node type.

    All combinations meet WCAG AA contrast ratio >= 4.5:1 for normal text.
    """
    t = theme or _DEFAULT_THEME
    colors = {
        "primary": t.node_primary,
        "secondary": t.node_secondary,
        "accent": t.node_accent,
        "warning": t.node_warning,
        "success": t.node_success,
        "default": t.node_default,
    }
    return colors.get(node_type, t.node_default)

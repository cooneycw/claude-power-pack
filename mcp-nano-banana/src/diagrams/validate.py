"""Diagram validation - quality checks before or after generation.

Mirrors the validate_pptx_slides pattern: returns a dict with passed (bool),
issue_count, high_severity count, issues list, and suggestions list.
"""

from __future__ import annotations

from dataclasses import dataclass

from diagrams.base import _node_color
from diagrams.c4 import _C4_COLORS, _DEFAULT_COLOR


@dataclass
class _ValidationIssue:
    """Internal representation of a validation finding."""

    check: str
    severity: str  # high, medium, low
    message: str
    node_id: str = ""
    edge_index: int = -1


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string to (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Calculate WCAG 2.1 relative luminance from sRGB values."""

    def linearize(v: int) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r_lin = linearize(r)
    g_lin = linearize(g)
    b_lin = linearize(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Calculate WCAG 2.1 contrast ratio between two hex colors.

    Returns a value >= 1.0. WCAG AA requires >= 4.5 for normal text,
    >= 3.0 for large text (>= 18px bold or >= 24px).
    """
    lum1 = _relative_luminance(*_hex_to_rgb(fg_hex))
    lum2 = _relative_luminance(*_hex_to_rgb(bg_hex))
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def _get_palette_colors(
    diagram_type: str,
    node_type: str,
) -> tuple[str, str, str]:
    """Get (bg, border, text) colors for a given diagram/node type combo."""
    if diagram_type == "c4":
        return _C4_COLORS.get(node_type, _DEFAULT_COLOR)
    return _node_color(node_type)


def score_diagram_density(
    node_count: int,
    edge_count: int,
    width: int = 1920,
    height: int = 1080,
    avg_node_width: int = 200,
    avg_node_height: int = 100,
) -> dict:
    """Score diagram density and suggest actions.

    Returns a dict with density ratio, capacity, status, and suggestion.

    Thresholds:
        <= 0.8: ok - no action needed
        0.8-1.0: warning - near capacity, suggest tighter layout
        1.0-1.5: overflow - recommend splitting into sub-diagrams
        > 1.5: critical - must split, diagram will be unreadable
    """
    usable_area = width * height * 0.65  # 35% reserved for headers, padding, edges panel
    node_area = avg_node_width * avg_node_height * 1.5  # 1.5x for margins between nodes
    capacity = int(usable_area / node_area) if node_area > 0 else 1

    density = node_count / max(capacity, 1)

    if density <= 0.8:
        status = "ok"
        suggestion = None
    elif density <= 1.0:
        status = "warning"
        suggestion = "Near capacity - consider tighter layout or reducing labels"
    elif density <= 1.5:
        status = "overflow"
        suggestion = "Consider splitting into summary + detail sub-diagrams"
    else:
        status = "critical"
        suggestion = "Must split - diagram will be unreadable at this density"

    return {
        "density": round(density, 2),
        "capacity": capacity,
        "node_count": node_count,
        "edge_count": edge_count,
        "status": status,
        "suggestion": suggestion,
    }


def validate_diagram(
    nodes: list[dict],
    edges: list[dict] | None = None,
    width: int = 1920,
    height: int = 1080,
    diagram_type: str = "c4",
) -> dict:
    """Validate a diagram spec for quality issues.

    Checks (ordered by severity):
        HIGH: viewport_fit, edge_validity, duplicate_ids
        MEDIUM: readability, orphan_nodes, contrast
        LOW: long_labels

    Returns:
        dict with passed (bool), issue_count, high_severity,
        issues (list of dicts), suggestions (list of str),
        and density (dict with scoring metadata).
    """
    edges = edges or []
    issues: list[_ValidationIssue] = []

    node_ids = [n.get("id", f"n{i}") for i, n in enumerate(nodes)]
    node_id_set = set(node_ids)

    # Compute density score up front for use in checks
    density = score_diagram_density(
        node_count=len(nodes),
        edge_count=len(edges),
        width=width,
        height=height,
    )

    # --- HIGH: duplicate_ids ---
    seen: set[str] = set()
    for nid in node_ids:
        if nid in seen:
            issues.append(_ValidationIssue(
                check="duplicate_ids",
                severity="high",
                message=f"Duplicate node ID: '{nid}'",
                node_id=nid,
            ))
        seen.add(nid)

    # --- HIGH: edge_validity ---
    for i, edge in enumerate(edges):
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        if src and src not in node_id_set:
            issues.append(_ValidationIssue(
                check="edge_validity",
                severity="high",
                message=f"Edge {i} source '{src}' does not match any node ID",
                edge_index=i,
            ))
        if tgt and tgt not in node_id_set:
            issues.append(_ValidationIssue(
                check="edge_validity",
                severity="high",
                message=f"Edge {i} target '{tgt}' does not match any node ID",
                edge_index=i,
            ))

    # --- HIGH: viewport_fit (uses density scoring) ---
    node_count = len(nodes)
    if density["status"] in ("overflow", "critical"):
        severity = "high"
        issues.append(_ValidationIssue(
            check="viewport_fit",
            severity=severity,
            message=(
                f"Density {density['density']:.2f} ({density['status']}): "
                f"{node_count} nodes exceed viewport capacity of ~{density['capacity']} "
                f"at {width}x{height}. {density['suggestion']}"
            ),
        ))

    # --- MEDIUM: readability (uses density scoring) ---
    if density["status"] == "warning":
        issues.append(_ValidationIssue(
            check="readability",
            severity="medium",
            message=(
                f"Density {density['density']:.2f} (warning): "
                f"{node_count} nodes near capacity of ~{density['capacity']}. "
                f"{density['suggestion']}"
            ),
        ))

    # --- MEDIUM: orphan_nodes ---
    standalone_types = {"person", "system"}
    if edges:
        connected: set[str] = set()
        for edge in edges:
            connected.add(edge.get("source", ""))
            connected.add(edge.get("target", ""))
        for i, n in enumerate(nodes):
            nid = n.get("id", f"n{i}")
            ntype = n.get("type", "default")
            if nid not in connected and ntype not in standalone_types:
                issues.append(_ValidationIssue(
                    check="orphan_nodes",
                    severity="medium",
                    message=f"Node '{nid}' has no edges (orphan)",
                    node_id=nid,
                ))

    # --- MEDIUM: contrast ---
    checked_types: set[str] = set()
    for n in nodes:
        ntype = n.get("type", "default")
        if ntype in checked_types:
            continue
        checked_types.add(ntype)
        bg, _border, text = _get_palette_colors(diagram_type, ntype)
        ratio = _contrast_ratio(text, bg)
        if ratio < 4.5:
            issues.append(_ValidationIssue(
                check="contrast",
                severity="medium",
                message=(
                    f"Color contrast {ratio:.1f}:1 for type '{ntype}' "
                    f"(bg={bg}, text={text}) fails WCAG AA minimum 4.5:1"
                ),
            ))

    # --- LOW: long_labels ---
    for i, n in enumerate(nodes):
        nid = n.get("id", f"n{i}")
        label = n.get("label", "")
        desc = n.get("description", "")
        if len(label) > 40:
            issues.append(_ValidationIssue(
                check="long_labels",
                severity="low",
                message=f"Node '{nid}' label is {len(label)} chars (> 40) - may overflow card",
                node_id=nid,
            ))
        if len(desc) > 80:
            issues.append(_ValidationIssue(
                check="long_labels",
                severity="low",
                message=f"Node '{nid}' description is {len(desc)} chars (> 80) - may overflow card",
                node_id=nid,
            ))

    # --- Build result ---
    high_count = sum(1 for iss in issues if iss.severity == "high")
    medium_count = sum(1 for iss in issues if iss.severity == "medium")
    low_count = sum(1 for iss in issues if iss.severity == "low")

    suggestions: list[str] = []
    if high_count > 0:
        suggestions.append("Fix all HIGH severity issues before generating the diagram.")
    if any(iss.check == "viewport_fit" for iss in issues):
        suggestions.append(
            "Consider splitting the diagram into summary + detail views, "
            "or increase the viewport dimensions."
        )
    if any(iss.check == "readability" for iss in issues):
        suggestions.append(
            "Group related nodes into clusters or split into multiple diagrams."
        )
    if any(iss.check == "contrast" for iss in issues):
        suggestions.append(
            "Adjust text or background colors to meet WCAG AA 4.5:1 contrast ratio."
        )

    issue_dicts = [
        {
            "check": iss.check,
            "severity": iss.severity,
            "message": iss.message,
            **({"node_id": iss.node_id} if iss.node_id else {}),
            **({"edge_index": iss.edge_index} if iss.edge_index >= 0 else {}),
        }
        for iss in issues
    ]

    summary_parts = []
    if high_count:
        summary_parts.append(f"{high_count} high")
    if medium_count:
        summary_parts.append(f"{medium_count} medium")
    if low_count:
        summary_parts.append(f"{low_count} low")
    summary = (
        f"{len(issues)} issues ({', '.join(summary_parts)})"
        if issues
        else "All checks passed"
    )

    return {
        "passed": high_count == 0,
        "issue_count": len(issues),
        "high_severity": high_count,
        "issues": issue_dicts,
        "suggestions": suggestions,
        "summary": summary,
        "density": density,
    }

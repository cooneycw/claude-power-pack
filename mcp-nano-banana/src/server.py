"""
MCP Nano-Banana - Diagram generation and PowerPoint creation server.

Generates best-in-class HTML/SVG diagrams at 1920x1080 for professional
presentations. Includes PowerPoint builder for embedding diagrams into slides.

Port: 8084 (default)
Transport: SSE or stdio
"""

import argparse
import logging
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import Config
from diagrams import (
    DIAGRAM_TYPES,
    DiagramSpec,
    DiagramNode,
    DiagramEdge,
    THEMES,
    get_theme,
    generate_architecture_diagram,
    generate_c4_diagram,
    generate_flowchart_diagram,
    generate_sequence_diagram,
    generate_orgchart_diagram,
    generate_timeline_diagram,
    generate_mindmap_diagram,
    validate_diagram as _validate_diagram_impl,
)
from pptx_builder import create_presentation, validate_slides

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP(Config.SERVER_NAME)

# Map diagram type to generator function
_GENERATORS = {
    "architecture": generate_architecture_diagram,
    "c4": generate_c4_diagram,
    "flowchart": generate_flowchart_diagram,
    "sequence": generate_sequence_diagram,
    "orgchart": generate_orgchart_diagram,
    "timeline": generate_timeline_diagram,
    "mindmap": generate_mindmap_diagram,
}


@mcp.custom_route("/", methods=["GET"])
async def root_health_check(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "server": Config.SERVER_NAME,
        "version": Config.SERVER_VERSION,
        "diagram_types": DIAGRAM_TYPES,
    })


@mcp.tool()
async def list_diagram_types() -> dict:
    """List all supported diagram types with descriptions.

    Returns the available diagram types and their capabilities so you can
    choose the right one for your visualization needs.
    """
    return {
        "diagram_types": {
            "architecture": "Layered system architecture - boxes in a grid layout showing components and services",
            "c4": "C4 model - multi-level architecture (Context, Container, Component, Code) with boundary groupings",
            "flowchart": "Process flow - sequential steps connected by arrows, with decision points",
            "sequence": "Interaction sequence - participants (columns) exchanging messages (arrows between lifelines)",
            "orgchart": "Hierarchy / org chart - tree structure with parent-child relationships",
            "timeline": "Timeline / roadmap - milestones along a horizontal timeline, alternating top/bottom",
            "mindmap": "Mind map / concept map - central topic with radiating branch nodes",
        },
        "default_dimensions": {
            "width": Config.DIAGRAM_WIDTH,
            "height": Config.DIAGRAM_HEIGHT,
        },
        "output_formats": ["html", "pptx"],
        "available_themes": list(THEMES.keys()),
    }


@mcp.tool()
async def generate_diagram(
    diagram_type: str,
    title: str,
    nodes: list[dict],
    edges: Optional[list[dict]] = None,
    description: str = "",
    width: Optional[int] = None,
    height: Optional[int] = None,
    save_path: Optional[str] = None,
    theme_id: str = "c4-default-dark-v1",
    theme_tokens: Optional[dict] = None,
    diagram_set_id: Optional[str] = None,
) -> dict:
    """Generate an HTML diagram at presentation quality (1920x1080).

    Creates a self-contained HTML file with embedded CSS for the specified diagram type.
    The output can be viewed in any browser or captured as a screenshot for PowerPoint embedding.

    Args:
        diagram_type: Type of diagram. One of: architecture, c4, flowchart, sequence, orgchart, timeline, mindmap.
        title: Diagram title displayed at the top.
        nodes: List of node dicts. Each node has:
            - id (str): Unique identifier
            - label (str): Display text
            - type (str, optional): Color theme - primary, secondary, accent, warning, success, default
            - description (str, optional): Additional text below label
            - icon (str, optional): Emoji or text icon
        edges: List of edge dicts connecting nodes. Each edge has:
            - source (str): Source node id
            - target (str): Target node id
            - label (str, optional): Edge label text
            - style (str, optional): Line style - solid, dashed, dotted
        description: Subtitle text below the title.
        width: Diagram width in pixels (default: 1920).
        height: Diagram height in pixels (default: 1080).
        save_path: Optional file path to save the HTML. If not provided, returns HTML as string.
        theme_id: Named theme for consistent colors across diagrams. Default: "c4-default-dark-v1".
        theme_tokens: Optional dict of token overrides to customize the named theme.
            Keys match ThemeTokens fields (e.g. background_primary, node_primary, c4_person).
            Node color fields accept [bg, border, text] lists.
        diagram_set_id: Optional identifier to group related diagrams (e.g. all L1-L4 C4 diagrams).
            Returned in metadata for tracking; ensures grouped diagrams share the same theme.

    Returns:
        dict with html content, file path (if saved), and metadata.
    """
    if diagram_type not in _GENERATORS:
        return {
            "success": False,
            "error": f"Unknown diagram type '{diagram_type}'. Use list_diagram_types to see options.",
        }

    # Resolve theme
    try:
        theme = get_theme(theme_id, overrides=theme_tokens)
    except ValueError as exc:
        return {
            "success": False,
            "error": str(exc),
        }

    w = width or Config.DIAGRAM_WIDTH
    h = height or Config.DIAGRAM_HEIGHT

    # Parse nodes and edges
    parsed_nodes = [
        DiagramNode(
            id=n.get("id", f"n{i}"),
            label=n.get("label", f"Node {i}"),
            type=n.get("type", "default"),
            description=n.get("description", ""),
            icon=n.get("icon", ""),
        )
        for i, n in enumerate(nodes)
    ]

    parsed_edges = []
    if edges:
        parsed_edges = [
            DiagramEdge(
                source=e.get("source", ""),
                target=e.get("target", ""),
                label=e.get("label", ""),
                style=e.get("style", "solid"),
            )
            for e in edges
        ]

    spec = DiagramSpec(
        title=title,
        nodes=parsed_nodes,
        edges=parsed_edges,
        description=description,
    )

    # Generate HTML
    generator = _GENERATORS[diagram_type]
    html = generator(spec, width=w, height=h, theme=theme)

    # Run validation and include warnings
    validation = _validate_diagram_impl(
        nodes=nodes,
        edges=edges,
        width=w,
        height=h,
        diagram_type=diagram_type,
        theme_id=theme_id,
    )
    warnings = [
        iss for iss in validation.get("issues", [])
    ]

    result = {
        "success": True,
        "diagram_type": diagram_type,
        "dimensions": {"width": w, "height": h},
        "node_count": len(parsed_nodes),
        "edge_count": len(parsed_edges),
        "theme_id": theme_id,
    }

    if diagram_set_id:
        result["diagram_set_id"] = diagram_set_id

    # Include density scoring metadata
    if "density" in validation:
        result["density"] = validation["density"]

    if warnings:
        result["warnings"] = warnings
        result["validation_summary"] = validation["summary"]

    # Save or return HTML
    if save_path:
        path = Path(save_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding="utf-8")
            result["file_path"] = str(path.resolve())
            result["html_preview"] = html[:500] + "..." if len(html) > 500 else html
        except PermissionError:
            logger.warning(
                f"Cannot write to '{save_path}' (permission denied - likely a host path "
                f"outside the container). Returning HTML content instead."
            )
            result["html"] = html
            result["save_path_error"] = (
                f"Permission denied writing to '{save_path}'. "
                f"When running in Docker, save_path must be within the container filesystem "
                f"or a mounted volume. Use the returned HTML content and save it with the Write tool."
            )
    else:
        result["html"] = html

    return result


@mcp.tool()
async def create_pptx(
    title: str,
    slides: list[dict],
    save_path: str,
    author: str = "Nano-Banana",
) -> dict:
    """Create a PowerPoint presentation file.

    Generates a PPTX file with a professional dark theme. Slides can include
    text content, embedded diagram images, two-column layouts, and speaker notes.

    Args:
        title: Presentation title (used on the title slide).
        slides: List of slide definitions. Each slide dict has:
            - layout (str): "title", "content", "diagram", "two-column", or "blank"
            - title (str): Slide title text
            - subtitle (str, optional): Subtitle (for title slides)
            - content (str, optional): Body text (newlines = new paragraphs, "- " = bullets)
            - left_content (str, optional): Left column text (for two-column layout)
            - right_content (str, optional): Right column text (for two-column layout)
            - image_base64 (str, optional): Base64-encoded PNG image (for diagram slides)
            - notes (str, optional): Speaker notes
        save_path: File path to save the .pptx file.
        author: Author name for file metadata.

    Returns:
        dict with file path, slide count, and file size.
    """
    # Run QC validation before building
    qc = validate_slides(slides)
    if not qc["passed"]:
        return {
            "success": False,
            "error": f"QC validation failed: {qc['summary']}",
            "qc": qc,
        }

    try:
        pptx_bytes = create_presentation(title, slides, author)

        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pptx_bytes)

        return {
            "success": True,
            "file_path": str(path.resolve()),
            "slide_count": len(slides),
            "file_size_bytes": len(pptx_bytes),
            "file_size_kb": round(len(pptx_bytes) / 1024, 1),
            "qc": qc,
        }
    except Exception as e:
        logger.error(f"Failed to create PPTX: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
async def validate_pptx_slides(
    slides: list[dict],
    prohibited_terms: Optional[list[str]] = None,
) -> dict:
    """Validate slide definitions before creating a PPTX.

    Runs quality control checks on slide content:
    - Framework/corporate name attribution (McKinsey, BCG, GAME Framework, etc.)
    - Placeholder text ([insert...], [TODO], lorem ipsum)
    - Missing images on diagram slides
    - Empty content on content/two-column slides

    Use this before create_pptx to catch issues early. create_pptx also runs
    validation automatically and blocks on high-severity issues.

    Args:
        slides: List of slide definitions (same format as create_pptx).
        prohibited_terms: Additional terms to flag (case-insensitive).

    Returns:
        dict with passed (bool), issues list, and summary.
    """
    return validate_slides(slides, prohibited_terms)


@mcp.tool()
async def validate_diagram(
    nodes: list[dict],
    edges: Optional[list[dict]] = None,
    width: int = 1920,
    height: int = 1080,
    diagram_type: str = "c4",
    theme_id: str = "c4-default-dark-v1",
) -> dict:
    """Validate a diagram spec for quality issues before or after generation.

    Runs quality checks on nodes and edges:
    - Duplicate node IDs (HIGH)
    - Invalid edge references (HIGH)
    - Viewport overflow / density estimation (HIGH)
    - Readability warnings for dense diagrams (MEDIUM)
    - Orphan nodes with no connections (MEDIUM)
    - WCAG AA color contrast validation (MEDIUM)
    - Long labels that may overflow node cards (LOW)

    Use this before generate_diagram to catch issues early. generate_diagram
    also runs validation automatically and includes warnings in its response.

    Args:
        nodes: List of node dicts (same format as generate_diagram).
        edges: List of edge dicts (same format as generate_diagram).
        width: Viewport width in pixels (default: 1920).
        height: Viewport height in pixels (default: 1080).
        diagram_type: Diagram type for palette-specific checks (default: c4).
        theme_id: Named theme for palette-specific contrast checks (default: c4-default-dark-v1).

    Returns:
        dict with passed (bool), issue_count, high_severity, issues list,
        suggestions list, and summary string.
    """
    return _validate_diagram_impl(
        nodes=nodes,
        edges=edges,
        width=width,
        height=height,
        diagram_type=diagram_type,
        theme_id=theme_id,
    )


@mcp.tool()
async def diagram_to_pptx(
    diagram_type: str,
    title: str,
    nodes: list[dict],
    edges: Optional[list[dict]] = None,
    description: str = "",
    save_path: str = "",
    additional_slides: Optional[list[dict]] = None,
) -> dict:
    """Generate a diagram and create a PowerPoint presentation in one step.

    This is a convenience tool that combines generate_diagram + create_pptx.
    It generates the HTML diagram, then creates a PPTX with:
    1. A title slide
    2. The diagram as a content slide (HTML embedded as a description since
       screenshot capture requires Playwright)
    3. Any additional slides you specify

    Note: For actual image embedding, use generate_diagram to create the HTML,
    then use Playwright to screenshot it, then pass the base64 image to create_pptx
    with a "diagram" layout slide.

    Args:
        diagram_type: Type of diagram (architecture, c4, flowchart, sequence, orgchart, timeline, mindmap).
        title: Presentation and diagram title.
        nodes: Node definitions (see generate_diagram for format).
        edges: Edge definitions (see generate_diagram for format).
        description: Diagram subtitle / description.
        save_path: File path for the .pptx output. If empty, uses /tmp/nano-banana-{title}.pptx.
        additional_slides: Extra slides to append after the diagram slide.

    Returns:
        dict with diagram HTML, PPTX file path, and metadata.
    """
    # Generate the diagram HTML
    diagram_result = await generate_diagram(
        diagram_type=diagram_type,
        title=title,
        nodes=nodes,
        edges=edges,
        description=description,
    )

    if not diagram_result.get("success"):
        return diagram_result

    html = diagram_result.get("html", "")

    # Build slides
    slides = [
        {
            "layout": "title",
            "title": title,
            "subtitle": description or f"{diagram_type.title()} Diagram",
        },
        {
            "layout": "content",
            "title": f"{diagram_type.title()} - {title}",
            "content": _html_to_text_summary(html, nodes, edges),
            "notes": f"Full HTML diagram available. Use Playwright screenshot for image embedding.\nDiagram type: {diagram_type}",
        },
    ]

    if additional_slides:
        slides.extend(additional_slides)

    # Determine save path
    if not save_path:
        slug = title.lower().replace(" ", "-")[:40]
        save_path = f"/tmp/nano-banana-{slug}.pptx"

    pptx_result = await create_pptx(
        title=title,
        slides=slides,
        save_path=save_path,
    )

    return {
        "success": True,
        "diagram": {
            "type": diagram_type,
            "html_length": len(html),
            "node_count": len(nodes),
            "edge_count": len(edges) if edges else 0,
        },
        "pptx": pptx_result,
        "html": html,
        "tip": "For best results: save the HTML diagram, use Playwright to screenshot it at 1920x1080, then use create_pptx with a 'diagram' layout slide and the screenshot as image_base64.",
    }


def _html_to_text_summary(html: str, nodes: list[dict], edges: list | None) -> str:
    """Create a text summary of a diagram for the PPTX content slide."""
    lines = []
    lines.append("Components:")
    for n in nodes:
        label = n.get("label", "?")
        desc = n.get("description", "")
        if desc:
            lines.append(f"- {label}: {desc}")
        else:
            lines.append(f"- {label}")

    if edges:
        lines.append("")
        lines.append("Connections:")
        for e in edges:
            src = e.get("source", "?")
            tgt = e.get("target", "?")
            label = e.get("label", "")
            if label:
                lines.append(f"- {src} -> {tgt}: {label}")
            else:
                lines.append(f"- {src} -> {tgt}")

    return "\n".join(lines)


def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="MCP Nano-Banana Diagram Server")
    parser.add_argument("--stdio", action="store_true", help="Run in stdio transport mode")
    args = parser.parse_args()

    logger.info(f"Starting {Config.SERVER_NAME} v{Config.SERVER_VERSION}")

    if args.stdio:
        logger.info("Transport: stdio")
        mcp.run(transport="stdio")
    else:
        logger.info(f"Transport: SSE on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
        mcp.run(
            transport="sse",
            host=Config.SERVER_HOST,
            port=Config.SERVER_PORT,
        )


if __name__ == "__main__":
    main()

# MCP Nano-Banana - Diagram & PowerPoint Server

Best-in-class diagram generation MCP server for Claude Code. Generates professional 1920x1080 HTML diagrams and PowerPoint presentations.

## Features

- **7 diagram types**: C4, Architecture, Flowchart, Sequence, Org Chart, Timeline, Mind Map
- **Shared theme tokens**: Consistent color palette across all diagram types via `ThemeTokens`
- **Presentation-quality**: All diagrams render at 1920x1080 (16:9 widescreen)
- **PowerPoint builder**: Create PPTX files with embedded diagrams, dark theme
- **Self-contained HTML**: No external dependencies, works offline
- **MCP integration**: 4 tools for diagram generation and PPTX creation

## Quick Start

```bash
# stdio mode (recommended - Claude Code auto-manages)
claude mcp add nano-banana --transport stdio -- uv run --directory /path/to/mcp-nano-banana python src/server.py --stdio

# SSE mode (manual start)
./start-server.sh
claude mcp add nano-banana --transport sse --url http://127.0.0.1:8084/sse
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `list_diagram_types` | List available diagram types, themes, and descriptions |
| `generate_diagram` | Generate an HTML diagram with theme support |
| `validate_diagram` | Validate diagram spec for quality issues (contrast, density, etc.) |
| `create_pptx` | Create a PowerPoint file with slides and embedded images |
| `validate_pptx_slides` | Validate slide definitions before creating a PPTX |
| `diagram_to_pptx` | One-step: generate diagram + create PPTX |

## Diagram Types

| Type | Use Case |
|------|----------|
| `c4` | C4 model - multi-level architecture (Context, Container, Component, Code) |
| `architecture` | System components in a grid layout |
| `flowchart` | Sequential process steps with arrows |
| `sequence` | Message exchange between participants |
| `orgchart` | Tree hierarchy (org charts, taxonomies) |
| `timeline` | Milestones along a horizontal track |
| `mindmap` | Central topic with radiating branches |

## End-to-End Workflow

For the highest quality diagram embedding in PowerPoint:

1. **Generate diagram HTML** with `generate_diagram`
2. **Save HTML** to a file
3. **Screenshot** with Playwright at 1920x1080
4. **Create PPTX** with `create_pptx` using the screenshot as `image_base64`

Or use `diagram_to_pptx` for a quick text-based PPTX.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_SERVER_HOST` | `127.0.0.1` | Server bind address |
| `MCP_SERVER_PORT` | `8084` | Server port |
| `DIAGRAM_WIDTH` | `1920` | Default diagram width |
| `DIAGRAM_HEIGHT` | `1080` | Default diagram height |

## Theme System

All diagrams use a shared `ThemeTokens` contract for consistent colors. Pass `theme_id` to
`generate_diagram` and `validate_diagram` to select a named theme. Use `theme_tokens` to
override individual tokens.

**Available themes:** `c4-default-dark-v1` (default)

**Key parameters:**

| Parameter | Purpose |
|-----------|---------|
| `theme_id` | Named theme (e.g. `c4-default-dark-v1`) |
| `theme_tokens` | Dict of token overrides (e.g. `{"background_primary": "#000"}`) |
| `diagram_set_id` | Groups related diagrams for tracking |

## Node Types (Color Themes)

### Generic (architecture, flowchart, sequence, orgchart, timeline, mindmap)

| Type | Color | Use |
|------|-------|-----|
| `primary` | Blue | Main components |
| `secondary` | Purple | Supporting components |
| `accent` | Amber | Highlights, callouts |
| `warning` | Red | Alerts, critical items |
| `success` | Green | Completed, healthy |
| `default` | Slate | Standard elements |

### C4-specific

| Type | Color | Use |
|------|-------|-----|
| `person` | Dark blue | Actors / Users |
| `system` | Grey | External systems |
| `system-focus` | Blue | System of interest |
| `container` | Green | Containers |
| `component` | Purple | Components |
| `code` | Amber | Code elements |

## Requirements

- Python 3.11+
- uv (dependency manager)
- python-pptx (for PPTX generation)
- Playwright MCP (optional, for HTML-to-screenshot conversion)

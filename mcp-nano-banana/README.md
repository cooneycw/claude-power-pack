# MCP Nano-Banana - Diagram & PowerPoint Server

Best-in-class diagram generation MCP server for Claude Code. Generates professional 1920x1080 HTML diagrams and PowerPoint presentations.

## Features

- **6 diagram types**: Architecture, Flowchart, Sequence, Org Chart, Timeline, Mind Map
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
| `list_diagram_types` | List available diagram types and their descriptions |
| `generate_diagram` | Generate an HTML diagram (architecture, flowchart, sequence, etc.) |
| `create_pptx` | Create a PowerPoint file with slides and embedded images |
| `diagram_to_pptx` | One-step: generate diagram + create PPTX |

## Diagram Types

| Type | Use Case |
|------|----------|
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

## Node Types (Color Themes)

| Type | Color | Use |
|------|-------|-----|
| `primary` | Blue | Main components |
| `secondary` | Purple | Supporting components |
| `accent` | Amber | Highlights, callouts |
| `warning` | Red | Alerts, critical items |
| `success` | Green | Completed, healthy |
| `default` | Slate | Standard elements |

## Requirements

- Python 3.11+
- uv (dependency manager)
- python-pptx (for PPTX generation)
- Playwright MCP (optional, for HTML-to-screenshot conversion)

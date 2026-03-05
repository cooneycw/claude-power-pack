---
description: Overview of documentation and diagram commands
---

# Documentation & Diagram Commands

Generate architecture documentation and professional presentations using the Nano-Banana MCP server.

## Commands

| Command | Purpose |
|---------|---------|
| `/documentation:c4` | Generate C4 architecture diagrams (all 4 levels) |
| `/documentation:pptx` | Create PowerPoint presentations with optional diagrams |
| `/documentation:help` | This help overview |

## MCP Server: Nano-Banana

The Nano-Banana MCP server (`mcp-nano-banana/`, port 8084) provides diagram generation and PPTX creation tools.

### Setup

```bash
# stdio (recommended)
claude mcp add nano-banana --transport stdio -- uv run --directory ~/Projects/claude-power-pack/mcp-nano-banana python src/server.py --stdio

# SSE
cd ~/Projects/claude-power-pack/mcp-nano-banana && ./start-server.sh
claude mcp add nano-banana --transport sse --url http://127.0.0.1:8084/sse
```

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `list_diagram_types` | List supported diagram types |
| `generate_diagram` | Generate HTML diagram at 1920x1080 |
| `create_pptx` | Create PowerPoint from slide definitions |
| `diagram_to_pptx` | Combined: diagram + PPTX in one step |

### Diagram Types

- **architecture** — System component grid layout
- **c4** — C4 model with boundary groupings (Context, Container, Component, Code)
- **flowchart** — Sequential process steps with arrows
- **sequence** — Participant message exchange (UML-style)
- **orgchart** — Tree hierarchy visualization
- **timeline** — Milestone roadmap on horizontal track
- **mindmap** — Central topic with radiating branches

### C4 Node Types

| Type | C4 Concept | Color |
|------|-----------|-------|
| `person` | Actor / User | Dark blue (pill shape) |
| `system` | External System | Grey |
| `system-focus` | System of Interest | Blue |
| `container` | Container (app, DB, service) | Green |
| `component` | Component within container | Purple |
| `code` | Class / module / interface | Amber |

### End-to-End Best Quality

1. `generate_diagram` -> save HTML file
2. Playwright screenshot at 1920x1080
3. `create_pptx` with image_base64 on "diagram" layout

### Makefile Integration

Add an `update_docs` target to your Makefile to run C4 diagram generation and doc review as part of `/flow:auto` and `/flow:finish`.

### Related

- `/load-mcp-docs` — Load all MCP server documentation
- MCP Playwright — Browser automation for screenshots

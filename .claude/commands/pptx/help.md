---
description: Overview of PowerPoint and diagram commands
---

# PowerPoint & Diagram Commands

Create professional diagrams and PowerPoint presentations using the Nano-Banana MCP server.

## Commands

| Command | Purpose |
|---------|---------|
| `/pptx:create` | Guided PowerPoint creation with optional diagrams |
| `/pptx:help` | This help overview |

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
- **flowchart** — Sequential process steps with arrows
- **sequence** — Participant message exchange (UML-style)
- **orgchart** — Tree hierarchy visualization
- **timeline** — Milestone roadmap on horizontal track
- **mindmap** — Central topic with radiating branches

### End-to-End Best Quality

1. `generate_diagram` → save HTML file
2. Playwright screenshot at 1920x1080
3. `create_pptx` with image_base64 on "diagram" layout

### Related

- `/load-mcp-docs` — Load all MCP server documentation
- MCP Playwright — Browser automation for screenshots

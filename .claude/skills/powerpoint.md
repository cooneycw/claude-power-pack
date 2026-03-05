---
name: PowerPoint & Diagrams
description: Create diagrams and PowerPoint presentations using the Nano-Banana MCP server
trigger: powerpoint, pptx, diagram, flowchart, architecture diagram, sequence diagram, org chart, timeline, mind map, presentation, slides
---

# PowerPoint & Diagrams Skill

When the user asks about creating diagrams, PowerPoint presentations, or visual content for slides, use the Nano-Banana MCP server tools.

## Quick Reference

### MCP Tools (mcp__nano-banana__)

| Tool | Purpose |
|------|---------|
| `list_diagram_types` | See available diagram types |
| `generate_diagram` | Create HTML diagram (architecture, flowchart, sequence, orgchart, timeline, mindmap) |
| `create_pptx` | Build PowerPoint file with slides |
| `diagram_to_pptx` | One-step diagram + PPTX creation |

### Commands

| Command | Purpose |
|---------|---------|
| `/pptx:create` | Guided PowerPoint creation with diagrams |
| `/pptx:help` | Overview of PowerPoint commands |

### End-to-End Workflow (Best Quality)

1. Use `generate_diagram` → save HTML to file
2. Use Playwright MCP to screenshot at 1920x1080
3. Use `create_pptx` with screenshot as `image_base64` on a "diagram" layout slide

### Quick Workflow

Use `diagram_to_pptx` for a text-based PPTX without screenshots.

### Diagram Types

| Type | Best For |
|------|----------|
| `architecture` | System components, services, infrastructure |
| `flowchart` | Processes, decision trees, workflows |
| `sequence` | API calls, message passing, interactions |
| `orgchart` | Hierarchies, taxonomies, team structure |
| `timeline` | Roadmaps, milestones, project phases |
| `mindmap` | Brainstorming, concept maps, topic exploration |

### Node Types (Colors)

- `primary` (blue) — Main components
- `secondary` (purple) — Supporting
- `accent` (amber) — Highlights
- `warning` (red) — Critical items
- `success` (green) — Completed/healthy
- `default` (slate) — Standard

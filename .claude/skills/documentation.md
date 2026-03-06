---
name: Documentation & Diagrams
description: Generate C4 architecture diagrams, other diagram types, and PowerPoint presentations using the Nano-Banana MCP server
trigger: documentation, c4, c4 diagram, architecture diagram, update docs, powerpoint, pptx, diagram, flowchart, sequence diagram, org chart, timeline, mind map, presentation, slides
---

# Documentation & Diagrams Skill

When the user asks about creating diagrams, architecture documentation, C4 models, PowerPoint presentations, or visual content for slides, use the Nano-Banana MCP server tools.

## Quick Reference

### MCP Tools (mcp__nano-banana__)

| Tool | Purpose |
|------|---------|
| `list_diagram_types` | See available diagram types |
| `generate_diagram` | Create HTML diagram (architecture, c4, flowchart, sequence, orgchart, timeline, mindmap) |
| `create_pptx` | Build PowerPoint file with slides |
| `diagram_to_pptx` | One-step diagram + PPTX creation |

### Commands

| Command | Purpose |
|---------|---------|
| `/documentation:c4` | Generate C4 architecture diagrams (all 4 levels) |
| `/documentation:pptx` | Guided PowerPoint creation with diagrams |
| `/documentation:help` | Overview of documentation commands |

### C4 Diagram Workflow

1. Analyze project (CLAUDE.md, README, directory structure)
2. Generate 4 levels: L1 Context, L2 Container, L3 Component, L4 Code
3. Save HTML to `docs/architecture/`
4. Optionally screenshot via Playwright for PNG versions

### C4 Node Types

| Type | C4 Concept | Color |
|------|-----------|-------|
| `person` | Actor / User | Dark blue (pill) |
| `system` | External System | Grey |
| `system-focus` | System of Interest | Blue |
| `container` | Container | Green |
| `component` | Component | Purple |
| `code` | Code element | Amber |

### PowerPoint Workflow (Best Quality)

1. Use `generate_diagram` -> save HTML to file
2. Use Playwright MCP to screenshot at 1920x1080
3. Use `create_pptx` with screenshot as `image_base64` on a "diagram" layout slide

### Quick PowerPoint Workflow

Use `diagram_to_pptx` for a text-based PPTX without screenshots.

### All Diagram Types

| Type | Best For |
|------|----------|
| `architecture` | System components, services, infrastructure |
| `c4` | C4 model - multi-level architecture with boundaries |
| `flowchart` | Processes, decision trees, workflows |
| `sequence` | API calls, message passing, interactions |
| `orgchart` | Hierarchies, taxonomies, team structure |
| `timeline` | Roadmaps, milestones, project phases |
| `mindmap` | Brainstorming, concept maps, topic exploration |

### Node Types (Colors - non-C4 diagrams)

- `primary` (blue) - Main components
- `secondary` (purple) - Supporting
- `accent` (amber) - Highlights
- `warning` (red) - Critical items
- `success` (green) - Completed/healthy
- `default` (slate) - Standard

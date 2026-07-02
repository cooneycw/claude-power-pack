---
description: Overview of documentation and diagram commands
---

# Documentation & Diagram Commands

Generate architecture documentation and professional presentations.

## Commands

| Command | Purpose |
|---------|---------|
| `/documentation:c4` | Generate C4 architecture diagrams (all 4 levels) |
| `/documentation:pptx` | Create PowerPoint presentations with optional diagrams |
| `/documentation:help` | This help overview |

## PowerPoint Generation

PowerPoint/PPTX generation is provided by the native Anthropic `pptx` skill (not an MCP server). Install it into a project with:

```bash
npx skills add anthropics/skills@pptx
```

`/documentation:pptx` drives the skill to build slide decks.

## C4 Diagram Rendering

`/documentation:c4` renders C4 diagrams as GitHub-renderable Mermaid via a zero-dependency Python engine (`scripts/c4-mermaid.py`, issue #411). It analyzes the project, builds a C4 model (`docs/architecture/c4-model.json`), then emits L1-L3 as Mermaid `flowchart` (with `subgraph` boundaries and C4 `classDef` colors) and L4 as `classDiagram`. Output is one `.mmd` per level plus an `index.md` that renders inline on GitHub, and a `c4-manifest.json`. The engine enforces an edge-validity QA gate (every edge/relation endpoint must be a defined node) and flags dense diagrams for splitting.

### C4 Node Types

| Type | C4 Concept | Color |
|------|-----------|-------|
| `person` | Actor / User | Dark blue (pill shape) |
| `system` | External System | Grey |
| `system-focus` | System of Interest | Blue |
| `container` | Container (app, DB, service) | Green |
| `component` | Component within container | Purple |
| `code` | Class / module / interface | Amber |

### Makefile Integration

Add an `update_docs` target to your Makefile to run C4 diagram generation and doc review as part of `/flow:auto` and `/flow:finish`.

### Related

- `/load-mcp-docs` - Load all MCP server documentation
- MCP Playwright - Browser automation for screenshots

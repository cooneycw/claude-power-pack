# Implementation Plan: PowerPoint Skill + Nano-Banana Diagram MCP

> **Issue:** #161
> **Spec:** [spec.md](./spec.md)
> **Created:** 2026-03-04
> **Status:** Draft

---

## Summary

Build two interconnected components: (1) a `/pptx` CPP skill that wraps Anthropic's native PowerPoint capability with diagram awareness, and (2) the nano-banana MCP server - a lightweight Python/FastAPI service that generates professional 1920x1080 HTML diagrams using pure HTML/CSS/SVG (no JS frameworks). The Playwright MCP handles PNG rendering, and python-pptx embeds the results into slide decks.

---

## Technical Context

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Language | Python 3.11+ | CPP standard, python-pptx ecosystem |
| MCP Framework | FastAPI + SSE | Matches existing MCP servers (second-opinion, playwright) |
| Diagram Rendering | HTML/CSS/SVG | Zero JS deps, browser-renderable, Playwright-screenshotable |
| PNG Export | Playwright MCP | Already installed in CPP, persistent sessions |
| Slide Generation | python-pptx | Industry standard, Anthropic's native skill uses it |
| Package Manager | uv | CPP standard |
| Port | 8084 | Next available after 8080/8081 |

---

## Constitution Check

- [x] **P1 Context Efficiency:** Skill uses progressive disclosure (help -> usage -> advanced)
- [x] **P2 Issue-Driven:** Issue #161 tracks this work
- [x] **P3 Spec-First:** This spec + plan created before implementation
- [ ] **P4 Test-Driven:** Test scenarios defined in spec
- [x] **P5 Cross-Platform:** Python + HTML, works on Linux/Mac/Windows

---

## Architecture

### Component Overview

```
User Prompt
    |
    v
/pptx skill (Claude Code command)
    |
    +---> Anthropic native PPTX skill (slide structure)
    |
    +---> nano-banana MCP (diagram generation)
    |         |
    |         v
    |     HTML/CSS/SVG @ 1920x1080
    |         |
    |         v
    |     Playwright MCP (screenshot -> PNG)
    |
    v
python-pptx (embed PNG into slides)
    |
    v
output.pptx
```

### Nano-Banana MCP Tools

| Tool | Purpose | Inputs | Output |
|------|---------|--------|--------|
| `generate_diagram` | Create diagram from description | type, data, theme | HTML string |
| `list_diagram_types` | Show available types | - | type list |
| `render_to_png` | Convert HTML to PNG via Playwright | html, width, height | base64 PNG |
| `get_diagram_template` | Get blank template for a type | type | HTML template |
| `health_check` | Server health | - | status |

### Key Design Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Diagram engine | Mermaid, D3.js, HTML/CSS/SVG | HTML/CSS/SVG | Zero deps, NFR5 compliance, full styling control |
| Rendering | Self-contained, Playwright, wkhtmltoimage | Playwright MCP | Already available in CPP, high quality |
| MCP transport | stdio, SSE | SSE | Matches other CPP MCP servers |
| Skill approach | Vendor Anthropic's, wrap native, standalone | Wrap native | Leverage built-in capability, add diagram layer |

---

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| python-pptx | >=1.0.0 | PowerPoint file generation |
| fastapi | >=0.104 | MCP server framework |
| uvicorn | >=0.24 | ASGI server |
| mcp | >=1.0 | MCP protocol SDK |
| Pillow | >=10.0 | Image processing for PPTX embedding |

### Internal Dependencies

| Module | Purpose |
|--------|---------|
| `mcp-playwright-persistent` | PNG rendering of HTML diagrams |
| `.claude/skills/` | Skill registration |
| `.claude/commands/` | Command registration |

---

## File Structure

```
mcp-nano-banana/
├── pyproject.toml
├── start-server.sh
├── README.md
├── src/
│   ├── server.py              # MCP server entry point
│   ├── diagrams/
│   │   ├── __init__.py        # Diagram type registry
│   │   ├── base.py            # Base diagram class
│   │   ├── architecture.py    # Architecture diagrams
│   │   ├── flowchart.py       # Flowcharts / process diagrams
│   │   ├── sequence.py        # Sequence diagrams
│   │   ├── timeline.py        # Timeline / roadmap
│   │   ├── hierarchy.py       # Org charts / trees
│   │   ├── mindmap.py         # Concept maps
│   │   └── chart.py           # Data visualizations
│   ├── templates/
│   │   └── base.html          # Base HTML template (1920x1080)
│   ├── themes/
│   │   ├── default.py         # Default professional theme
│   │   ├── dark.py            # Dark mode theme
│   │   └── minimal.py         # Clean minimal theme
│   └── renderer.py            # Playwright integration for PNG export
└── tests/
    ├── test_diagrams.py
    └── test_server.py

.claude/
├── commands/
│   └── pptx/
│       ├── help.md            # /pptx:help
│       └── create.md          # /pptx (main skill)
└── skills/
    └── pptx.md                # Skill loader
```

---

## Implementation Phases

### Phase 1: Nano-Banana MCP Server Core (Wave 1)

| Task ID | Description | Files | Dependencies |
|---------|-------------|-------|--------------|
| T001 | Scaffold mcp-nano-banana with pyproject.toml, start-server.sh | `mcp-nano-banana/` | - |
| T002 | Implement base diagram class and HTML template (1920x1080) | `src/diagrams/base.py`, `src/templates/` | T001 |
| T003 | Implement architecture diagram type | `src/diagrams/architecture.py` | T002 |
| T004 | Implement flowchart diagram type | `src/diagrams/flowchart.py` | T002 |
| T005 | Implement sequence diagram type | `src/diagrams/sequence.py` | T002 |
| T006 | MCP server with generate_diagram + list_diagram_types tools | `src/server.py` | T002 |
| T007 | Default theme with professional styling | `src/themes/default.py` | T002 |

### Phase 2: Rendering Pipeline + PowerPoint (Wave 2)

| Task ID | Description | Files | Dependencies |
|---------|-------------|-------|--------------|
| T008 | Playwright integration for HTML -> PNG rendering | `src/renderer.py` | T006 |
| T009 | render_to_png MCP tool | `src/server.py` | T008 |
| T010 | `/pptx` skill wrapping native capability + diagram embedding | `.claude/commands/pptx/` | T009 |
| T011 | python-pptx slide generation with embedded PNG diagrams | `src/pptx_builder.py` | T009 |

### Phase 3: Extended Diagram Types + Polish (Wave 3)

| Task ID | Description | Files | Dependencies |
|---------|-------------|-------|--------------|
| T012 | Timeline / roadmap diagram type | `src/diagrams/timeline.py` | T002 |
| T013 | Hierarchy / org chart diagram type | `src/diagrams/hierarchy.py` | T002 |
| T014 | Mind map / concept map diagram type | `src/diagrams/mindmap.py` | T002 |
| T015 | Data visualization (charts) diagram type | `src/diagrams/chart.py` | T002 |
| T016 | Dark + minimal themes | `src/themes/` | T007 |
| T017 | Documentation: README, /pptx:help, CLAUDE.md updates | `docs/` | T010 |
| T018 | Unit tests for diagram generation and MCP tools | `tests/` | T006 |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Playwright MCP unavailable | Low | Med | SVG fallback path, graceful degradation |
| HTML diagrams look unprofessional | Med | High | Invest in theme CSS, test at target resolution |
| python-pptx image embedding quirks | Low | Med | Test early with sample PNGs, fallback to placeholder |
| Anthropic native PPTX skill changes | Med | Med | Wrap loosely, don't depend on internals |
| Port 8083 conflicts | Low | Low | Make configurable via env var |

---

## Testing Strategy

### Unit Tests
- Each diagram type generates valid HTML
- HTML contains correct dimensions (1920x1080 viewport)
- Theme application produces correct CSS
- MCP tools return valid responses

### Integration Tests
- End-to-end: generate_diagram -> render_to_png -> valid PNG
- PPTX builder embeds PNG correctly
- MCP server starts and responds to health check

### Manual Testing
- Visual review of each diagram type in browser
- PPTX opens correctly in PowerPoint/LibreOffice
- Diagram quality at presentation resolution

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

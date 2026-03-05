# Feature Specification: PowerPoint Skill + Nano-Banana Diagram MCP

> **Issue:** #161
> **Created:** 2026-03-04
> **Status:** Draft

---

## Overview

Integrate Anthropic's built-in PowerPoint skill into Claude Power Pack as a CPP skill, and build a lightweight MCP server ("nano-banana") that generates best-in-class 1920x1080 HTML diagrams for embedding in PowerPoint presentations and standalone browser viewing.

**Key insight:** Anthropic already ships a native PPTX skill (python-pptx based, beta). CPP's role is to wrap it with diagram generation superpowers — the nano-banana MCP provides professional diagram content that the PowerPoint skill can embed as images.

---

## User Stories

### US1: PowerPoint Skill Integration [P1]

**As a** Claude Code user with CPP installed,
**I want** a `/pptx` skill that leverages Anthropic's native PowerPoint capability,
**So that** I can generate professional presentations directly from Claude Code.

**Acceptance Criteria:**
- [ ] `/pptx` skill available in CPP command set
- [ ] Skill wraps/enhances Anthropic's native PPTX skill with CPP conventions
- [ ] Supports creating presentations from prompts, outlines, or existing templates
- [ ] Generates `.pptx` files in the current working directory
- [ ] Help text with usage examples (`/pptx:help`)

**Test Scenarios:**
1. Given a topic prompt, when `/pptx` is invoked, then a valid .pptx file is created
2. Given an existing template, when `/pptx` references it, then output preserves template styling

---

### US2: Nano-Banana Diagram MCP Server [P1]

**As a** Claude Code user,
**I want** an MCP server that generates professional diagrams as 1920x1080 HTML,
**So that** I can create architecture diagrams, flowcharts, and visualizations for presentations and documentation.

**Acceptance Criteria:**
- [ ] MCP server runs on configurable port (default 8083)
- [ ] Generates HTML diagrams at 1920x1080 (16:9 widescreen)
- [ ] Supports at least 5 diagram types (see US3)
- [ ] HTML output viewable standalone in browser
- [ ] PNG/SVG export via Playwright MCP integration
- [ ] Follows CPP conventions (pyproject.toml, uv, start-server.sh)

**Test Scenarios:**
1. Given a diagram request, when MCP tool is called, then valid HTML is returned
2. Given HTML output, when opened in browser, then diagram renders at 1920x1080
3. Given HTML output, when screenshotted via Playwright, then PNG is presentation-quality

---

### US3: Diagram Type Library [P2]

**As a** presentation author,
**I want** a variety of diagram types available,
**So that** I can visually communicate different concepts effectively.

**Acceptance Criteria:**
- [ ] Architecture diagrams (boxes, connections, layers)
- [ ] Flowcharts / process diagrams (decision trees, workflows)
- [ ] Sequence diagrams (actor interactions, message flows)
- [ ] Timeline / roadmap visualizations (milestones, phases)
- [ ] Org charts / hierarchy diagrams (tree structures)
- [ ] Concept maps / mind maps (radial/cluster layouts)
- [ ] Data visualizations (bar, line, pie charts)
- [ ] Each type has a default template with professional styling

---

### US4: PowerPoint + Diagram Integration [P1]

**As a** user creating presentations,
**I want** diagrams automatically embedded into PowerPoint slides,
**So that** I get a complete deck with rich visuals in one workflow.

**Acceptance Criteria:**
- [ ] End-to-end: prompt -> nano-banana diagram -> render to PNG -> embed in PPTX
- [ ] Diagrams sized correctly for 16:9 slide layouts
- [ ] Support for full-slide diagrams and half-slide (with text) layouts
- [ ] Pipeline can be invoked as single `/pptx` command with diagram intent detected

**Test Scenarios:**
1. Given "create a presentation about our microservices architecture", when processed, then deck contains architecture diagram slides
2. Given "add a timeline slide showing Q1-Q4 milestones", when processed, then deck includes timeline diagram

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| No Playwright MCP available | Fallback to SVG-only output (no PNG rendering) |
| Diagram too complex for single slide | Split into multiple slides or simplify |
| User requests unsupported diagram type | Graceful error with list of supported types |
| Template file not found | Use built-in default templates |
| Very long text in diagram nodes | Text truncation with tooltip/full-text option |

---

## Out of Scope

- **Excel/Word skills** — separate future issue
- **Interactive diagrams** — HTML output is static (no JS interactivity needed in PPTX)
- **Real-time collaboration** — single-user generation only
- **Mermaid integration** — nano-banana uses HTML/CSS/SVG natively (no Mermaid dependency)
- **Video/animation in slides** — static content only

---

## Requirements

### Functional Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | `/pptx` skill wrapping native Anthropic PPTX capability | Must | US1 |
| R2 | nano-banana MCP server with diagram generation tools | Must | US2 |
| R3 | 1920x1080 HTML diagram output | Must | US2 |
| R4 | PNG export via Playwright screenshot | Must | US4 |
| R5 | SVG fallback when Playwright unavailable | Should | US2 |
| R6 | At least 5 diagram types with templates | Must | US3 |
| R7 | End-to-end prompt-to-deck pipeline | Must | US4 |
| R8 | `/pptx:help` with usage examples | Must | US1 |
| R9 | Professional color schemes and typography | Should | US3 |
| R10 | Configurable port and server settings | Should | US2 |

### Non-Functional Requirements

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR1 | Diagram generation speed | < 2s per diagram |
| NFR2 | HTML output file size | < 500KB per diagram |
| NFR3 | PNG render quality | >= 150 DPI at 1920x1080 |
| NFR4 | MCP server startup time | < 3s |
| NFR5 | Zero external JS dependencies | HTML/CSS/inline-SVG only |

---

## Success Criteria

- [ ] All acceptance criteria met
- [ ] MCP server starts and responds to health checks
- [ ] At least 3 diagram types produce professional output
- [ ] End-to-end demo: prompt -> deck with embedded diagrams
- [ ] Documentation in README and `/pptx:help`
- [ ] No regressions in existing CPP functionality

---

## Open Questions

- [ ] Should nano-banana support theming (dark mode, brand colors)?
- [ ] Should diagram templates be user-extensible (custom HTML templates)?
- [ ] What's the best port number? (8083 proposed, check for conflicts)
- [ ] Should we vendor Anthropic's PPTX skill or just reference the native one?
- [ ] Community skill `tfriedel/claude-office-skills` — worth evaluating as prior art?

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

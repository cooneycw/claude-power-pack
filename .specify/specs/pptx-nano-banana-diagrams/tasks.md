# Tasks: PowerPoint Skill + Nano-Banana Diagram MCP

> **Plan:** [plan.md](./plan.md)
> **Created:** 2026-03-04
> **Status:** Complete

---

## Task Format

```
[ID] [P?] [Story] Description (depends on X, Y)
```

- **ID**: Task identifier (T001, T002, etc.)
- **[P]**: Parallelizable - can run simultaneously with other [P] tasks
- **Dependencies**: Tasks that must complete first

---

## Wave 1: Nano-Banana MCP Server Core

### US2: Nano-Banana Diagram MCP Server

- [x] **T001** [US2] Scaffold `mcp-nano-banana/` with pyproject.toml, start-server.sh, README stub `mcp-nano-banana/`
- [x] **T002** [US2] Implement base diagram class + 1920x1080 HTML template `src/diagrams/base.py`, `src/templates/base.html` (depends on T001)
- [x] **T003** [P] [US3] Implement architecture diagram type `src/diagrams/architecture.py` (depends on T002)
- [x] **T004** [P] [US3] Implement flowchart diagram type `src/diagrams/flowchart.py` (depends on T002)
- [x] **T005** [P] [US3] Implement sequence diagram type `src/diagrams/sequence.py` (depends on T002)
- [x] **T006** [US2] MCP server with `generate_diagram` + `list_diagram_types` tools `src/server.py` (depends on T002)
- [x] **T007** [P] [US2] Default professional theme with color palette + typography `src/themes/default.py` (depends on T002)

**Checkpoint:** MCP server starts, generates 3 diagram types as HTML at 1920x1080

---

## Wave 2: Rendering Pipeline + PowerPoint Skill

### US4: PowerPoint + Diagram Integration

- [x] **T008** [US4] Playwright integration - HTML to PNG renderer `src/renderer.py` (depends on T006)
- [x] **T009** [US2] Add `render_to_png` MCP tool `src/server.py` (depends on T008)
- [x] **T010** [US1] Create `/pptx` skill + `/pptx:help` command `.claude/commands/pptx/create.md`, `.claude/commands/pptx/help.md` (depends on T009)
- [x] **T011** [US4] python-pptx builder: embed PNG diagrams into slides `src/pptx_builder.py` (depends on T009)

**Checkpoint:** End-to-end works - prompt -> diagram HTML -> PNG -> embedded in .pptx

---

## Wave 3: Extended Types, Themes & Polish

### US3: Diagram Type Library (Extended)

- [x] **T012** [P] [US3] Timeline / roadmap diagram type `src/diagrams/timeline.py` (depends on T002)
- [x] **T013** [P] [US3] Hierarchy / org chart diagram type `src/diagrams/hierarchy.py` (depends on T002)
- [x] **T014** [P] [US3] Mind map / concept map diagram type `src/diagrams/mindmap.py` (depends on T002)
- [x] **T015** [P] [US3] Data visualization (bar, line, pie) diagram type `src/diagrams/chart.py` (depends on T002)
- [x] **T016** [P] [US2] Dark + minimal themes `src/themes/dark.py`, `src/themes/minimal.py` (depends on T007)

### Documentation & Tests

- [x] **T017** [US1,US2] Documentation: README, /pptx:help, update CLAUDE.md `mcp-nano-banana/README.md`, `CLAUDE.md` (depends on T010)
- [x] **T018** [P] [US2,US3] Unit tests for diagram generation + MCP tools `tests/test_diagrams.py`, `tests/test_server.py` (depends on T006)
- [x] **T019** [US4] Integration test: full pipeline prompt -> .pptx with diagrams `tests/test_pipeline.py` (depends on T011)

**Checkpoint:** All 7 diagram types functional, tests passing, docs complete

---

## Issue Sync

> Use `/spec:sync` to create GitHub issues from these tasks.

| Task | Issue | Status |
|------|-------|--------|
| T001-T007 (Wave 1: MCP Core) | #161 sub-issue | complete |
| T008-T011 (Wave 2: Pipeline + PPTX) | #161 sub-issue | complete |
| T012-T019 (Wave 3: Extended + Polish) | #161 sub-issue | complete |

---

## Notes

- Tasks T003-T005 and T012-T015 are parallelizable (independent diagram types)
- Wave 1 is self-contained: MCP server works standalone for HTML diagram viewing
- Wave 2 adds the PowerPoint integration pipeline
- Wave 3 extends diagram types and adds quality/docs
- Diagram types can be developed independently once T002 (base class) is done

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

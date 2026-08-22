# Implementation Plan: Tavily MCP Integration

> **Spec:** [spec.md](./spec.md)
> **Created:** 2026-08-22
> **Status:** Draft

---

## Summary

Integrate the upstream [tavily-ai/tavily-mcp](https://github.com/tavily-ai/tavily-mcp)
server into Claude Power Pack's Tier 3 MCP surface. This follows the exact
pattern established by the Playwright integration - an upstream npx/stdio
package registered at user scope by `/cpp:init`, tracked by drift detection in
`/cpp:update`, and reported by `/cpp:status`. No new Python dependencies, no
container runtime, no custom code beyond registration commands and documentation.

The API key (`TAVILY_API_KEY`) is already stored in the `claude-power-pack/mcp-keys`
AWS Secrets Manager secret. The Tavily MCP server itself is maintained by
Tavily (tavily-ai org); CPP only consumes it.

---

## Technical Context

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| MCP Server | `tavily-mcp` (npm) | Official upstream package from tavily-ai |
| Transport | npx/stdio | Same pattern as Playwright; no always-on server needed |
| Node.js | 20+ | tavily-mcp requirement |
| API Key Storage | AWS Secrets Manager | Existing `claude-power-pack/mcp-keys` secret |
| New Dependencies | None | Registration is shell commands in init.md |

---

## Constitution Check

- [x] **P1 Context Efficiency:** No new always-loaded context; tavily is mentioned
  alongside existing servers in existing sections
- [x] **P2 Issue-Driven:** Spec created for this work
- [x] **P3 Spec-First:** This spec
- [x] **P4 Test-Driven:** Test scenarios defined in spec
- [x] **P5 Cross-Platform:** npx/stdio works on Linux/Mac/Windows

---

## Architecture

### Integration Points

```
/cpp:init (Tier 3, section 3c)
  └── claude mcp add tavily --transport stdio --scope user
        -e TAVILY_API_KEY="$TAVILY_API_KEY"
        -- npx -y tavily-mcp@latest

/cpp:update (Step 6b)
  └── expected-servers list: second-opinion, playwright, tavily

/cpp:status (Step 4)
  └── MCP check loops: second-opinion, playwright, tavily

AWS Secrets Manager
  └── claude-power-pack/mcp-keys
        ├── GEMINI_API_KEY
        ├── OPENAI_API_KEY
        ├── ANTHROPIC_API_KEY
        └── TAVILY_API_KEY        ← added
```

### Key Design Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Custom vs upstream | Build mcp-tavily repo, Use official tavily-mcp | Upstream | Official package covers all 4 tools; no value in wrapping |
| Transport | streamable-http, npx/stdio | npx/stdio | No always-on server needed; consistent with Playwright pattern |
| Scope | project, user | user | Global availability across all projects |
| Key delivery | .env file, -e flag, remote MCP OAuth | -e flag | Simplest; key baked into registration at init time |

---

## File Structure

No new files or directories. Changes are additions to existing files:

```
.claude/commands/cpp/
  ├── init.md      ← add tavily registration block (section 3c)
  ├── update.md    ← add tavily to expected-servers list (step 6b)
  └── status.md    ← add tavily to all MCP check loops
.env.example       ← add TAVILY_API_KEY placeholder
CLAUDE.md          ← mention tavily in MCP Servers section
README.md          ← document tavily in 3 sections
tests/
  └── (new or updated test for tavily doc pins)
```

Additional files to audit (may need updates depending on content):
```
.claude/commands/cpp/dockers.md      ← MCP server lists
.claude/commands/cpp/load-mcp-docs.md ← MCP reference docs
.claude/commands/flow/doctor.md       ← MCP health checks
docs/HOST_MANAGED_ARTIFACTS.md        ← host artifact inventory
docs/commands-reference.md            ← command detail docs
```

---

## Implementation Phases

### Phase 1: Core Registration (US1, US2, US3) - PARTIALLY DONE

| Task ID | Description | Files | Status |
|---------|-------------|-------|--------|
| T001 | Add TAVILY_API_KEY to AWS SM `claude-power-pack/mcp-keys` | AWS console | Done |
| T002 | Add tavily registration block to init.md section 3c | `.claude/commands/cpp/init.md` | Done |
| T003 | Add tavily to expected-servers in update.md step 6b | `.claude/commands/cpp/update.md` | Done |
| T004 | Add tavily to all MCP check loops in status.md | `.claude/commands/cpp/status.md` | Done |
| T005 | Register tavily MCP at user scope on dev machine | `~/.claude.json` | Done |

### Phase 2: Documentation (US4)

| Task ID | Description | Files | Dependencies |
|---------|-------------|-------|--------------|
| T006 | Update README.md (3 sections) | `README.md` | Done |
| T007 | Update CLAUDE.md MCP section | `CLAUDE.md` | Done |
| T008 | Add TAVILY_API_KEY to .env.example | `.env.example` | Done |
| T009 | Audit and update cpp/dockers.md | `.claude/commands/cpp/dockers.md` | T002 |
| T010 | Audit and update cpp/load-mcp-docs.md | `.claude/commands/cpp/load-mcp-docs.md` | T002 |
| T011 | Audit and update flow/doctor.md | `.claude/commands/flow/doctor.md` | T002 |
| T012 | Audit and update docs/HOST_MANAGED_ARTIFACTS.md | `docs/HOST_MANAGED_ARTIFACTS.md` | T002 |
| T013 | Audit and update docs/commands-reference.md | `docs/commands-reference.md` | T002 |

### Phase 3: Tests and Validation (US6)

| Task ID | Description | Files | Dependencies |
|---------|-------------|-------|--------------|
| T014 | Add/update tavily doc-pin test | `tests/test_mcp_json_override.py` or new file | T006-T013 |
| T015 | Run `make verify` and fix any failures | All | T014 |
| T016 | Verify `/cpp:status` output includes tavily | Manual | T004 |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| tavily-mcp npm package renamed or deprecated | Low | Med | Pin version or track upstream; registration uses `@latest` |
| Node.js not installed on target machine | Med | Low | Graceful fallback with warning message; same as Playwright |
| TAVILY_API_KEY not available at init time | Med | Low | Warning with manual command; key can be added later |
| Upstream package adds breaking tool-name changes | Low | Low | MCP tools are discovered dynamically; no CPP-side hardcoding |

---

## Testing Strategy

### Automated Tests
- Doc-pin test: verify tavily is mentioned in README, CLAUDE.md, init.md,
  update.md, status.md (same pattern as `test_mcp_json_override.py`)
- `make verify` must pass clean

### Manual Testing
- Run `/cpp:init` on a clean setup and verify tavily registration
- Run `/cpp:status` and verify tavily appears in Tier 3 output
- Run `/cpp:update` and verify tavily in drift report
- Invoke a tavily tool (e.g., `tavily-search`) from Claude Code to confirm
  end-to-end functionality

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

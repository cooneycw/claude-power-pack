# Feature Specification: Tavily MCP Integration

> **Created:** 2026-08-22
> **Status:** Draft

---

## Overview

Add the official [tavily-ai/tavily-mcp](https://github.com/tavily-ai/tavily-mcp)
server as a Tier 3 MCP asset in Claude Power Pack. Tavily provides four web
intelligence tools - search, extract, crawl, and map - exposed through a single
npx/stdio MCP server, following the same upstream-package pattern already used
for Playwright (`@playwright/mcp`). The API key is stored in
`claude-power-pack/mcp-keys` in AWS Secrets Manager alongside the existing
Gemini/OpenAI/Anthropic keys.

This spec covers the full integration surface: registration, drift detection,
status reporting, documentation, tests, and secrets provisioning.

---

## User Stories

### US1: Tavily MCP Registration via /cpp:init [P1]

**As a** CPP user running `/cpp:init`,
**I want** the Tavily MCP server automatically registered at user scope,
**So that** I have web search, extract, crawl, and map tools available in every
Claude Code session without manual setup.

**Acceptance Criteria:**
- [ ] `/cpp:init` Tier 3 section 3c registers `tavily` via npx/stdio at user scope
- [ ] Registration passes `TAVILY_API_KEY` as an environment variable via `-e`
- [ ] Graceful fallback when `npx` is not available (warning + manual command)
- [ ] Graceful fallback when `TAVILY_API_KEY` is not set (warning + instructions)
- [ ] Idempotent - skips if already registered
- [ ] Node.js 20+ requirement documented in the warning message

**Test Scenarios:**
1. Given npx is available and `TAVILY_API_KEY` is set, when `/cpp:init` runs
   Tier 3, then tavily is registered at user scope with the key
2. Given npx is available but `TAVILY_API_KEY` is unset, when `/cpp:init` runs,
   then a warning is printed with the manual registration command
3. Given npx is not available, when `/cpp:init` runs, then a warning is printed
   noting Node.js 20+ is required
4. Given tavily is already registered, when `/cpp:init` runs, then it prints
   "already registered (skipped)"

---

### US2: Drift Detection and Update [P1]

**As a** CPP user running `/cpp:update`,
**I want** the drift report to include the tavily MCP server,
**So that** missing or broken registrations are detected and reported.

**Acceptance Criteria:**
- [ ] `tavily` is listed in the "expected servers" inventory in update.md
- [ ] Drift report table includes tavily with OK/NOT REGISTERED status
- [ ] `/cpp:update` can re-register tavily if it's missing (same logic as init)

**Test Scenarios:**
1. Given tavily is registered, when `/cpp:update` runs drift detection, then
   tavily shows status OK
2. Given tavily is not registered, when `/cpp:update` runs drift detection,
   then tavily shows status NOT REGISTERED

---

### US3: Status Reporting [P1]

**As a** CPP user running `/cpp:status`,
**I want** to see the tavily MCP registration state,
**So that** I can verify it's properly configured.

**Acceptance Criteria:**
- [ ] Tier 3 MCP Servers check includes tavily in both Claude and Codex loops
- [ ] MCP Server Wiring section shows tavily as npx/stdio (no port to probe)
- [ ] MCP Server Projects note mentions tavily alongside playwright
- [ ] Summary example includes tavily

---

### US4: Documentation [P2]

**As a** CPP user or contributor,
**I want** Tavily documented across all relevant surfaces,
**So that** I understand what it provides and how it's configured.

**Acceptance Criteria:**
- [ ] README.md lists Tavily under MCP servers (What It Does, Host setup, MCP
  Servers sections)
- [ ] CLAUDE.md MCP Servers and Secrets section mentions Tavily
- [ ] `.env.example` includes `TAVILY_API_KEY` placeholder
- [ ] `cpp/load-mcp-docs.md` includes Tavily reference documentation
- [ ] `flow/doctor.md` includes tavily in MCP health checks (if applicable)
- [ ] `cpp/dockers.md` updated if it references MCP server lists

---

### US5: Secrets Provisioning [P2]

**As a** CPP user,
**I want** the Tavily API key stored in AWS Secrets Manager,
**So that** it follows the same secrets pattern as the other MCP keys.

**Acceptance Criteria:**
- [ ] `TAVILY_API_KEY` stored in `claude-power-pack/mcp-keys` secret
- [ ] `/secrets:*` commands can retrieve/rotate the key
- [ ] Key is never printed in logs or responses (existing masking hook covers it)
- [ ] `aws-secret-exports.py` in mcp-second-opinion (or equivalent) updated if
  it needs to export the Tavily key for any consumer

---

### US6: Test Coverage [P2]

**As a** CPP contributor,
**I want** tests that pin the Tavily integration,
**So that** regressions are caught before merge.

**Acceptance Criteria:**
- [ ] `test_mcp_json_override.py` or new test file validates tavily presence in
  docs where MCP servers are listed
- [ ] No existing tests broken by the addition
- [ ] `make verify` passes clean

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Node.js < 20 installed | npx present but tavily-mcp may fail at runtime; init prints version requirement in warning |
| TAVILY_API_KEY contains special chars | `-e` flag passes it correctly; shell quoting handled |
| User already has tavily registered at project scope | User-scope registration still proceeds (different scope) |
| tavily-mcp npm package unavailable | npx fails at Claude Code startup; server shows failed-to-connect; no CPP-side crash |
| API key expired or invalid | Tavily tools return auth errors at call time; not a CPP concern |
| User removes tavily registration manually | `/cpp:status` reports it as not registered; `/cpp:update` re-registers if desired |

---

## Out of Scope

- Building a custom Tavily MCP server (the upstream tavily-ai/tavily-mcp is used as-is)
- Adding Tavily-specific skills or slash commands to CPP (tools are exposed directly via MCP)
- Remote/streamable-http transport (tavily uses npx/stdio, not an always-on server)
- Tavily Research API integration (not included in the upstream MCP server as of v0.2.22)
- Node.js installation automation (user's responsibility)
- Tavily API key provisioning UI (use `/secrets:set` or AWS console)

---

## Requirements

### Functional Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | `/cpp:init` registers tavily MCP at user scope | Must | US1 |
| R2 | Registration requires `TAVILY_API_KEY` env var | Must | US1 |
| R3 | Registration requires npx (Node.js 20+) | Must | US1 |
| R4 | Drift detection includes tavily in expected servers | Must | US2 |
| R5 | `/cpp:status` reports tavily registration state | Must | US3 |
| R6 | All docs surfaces updated | Should | US4 |
| R7 | API key in `claude-power-pack/mcp-keys` AWS secret | Should | US5 |
| R8 | Test coverage for tavily doc pins | Could | US6 |

### Non-Functional Requirements

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR1 | No new Python dependencies | 0 new deps |
| NFR2 | No container runtime required | npx/stdio only |
| NFR3 | Secret masking covers TAVILY_API_KEY | Existing hook pattern |
| NFR4 | `make verify` passes clean | Exit 0 |

---

## Success Criteria

- [ ] All acceptance criteria met
- [ ] `make verify` passes
- [ ] `claude mcp list` shows tavily after `/cpp:init` Tier 3
- [ ] `/cpp:status` reports tavily as registered
- [ ] `/cpp:update` drift report includes tavily
- [ ] Documentation updated across all surfaces
- [ ] No regressions in existing functionality

---

## Open Questions

- [x] Custom wrapper vs upstream package? - **Resolved:** use upstream tavily-ai/tavily-mcp
- [x] Transport: stdio vs streamable-http? - **Resolved:** npx/stdio (same as Playwright)
- [x] Where to store API key? - **Resolved:** `claude-power-pack/mcp-keys` in AWS SM
- [ ] Should `flow/doctor.md` health-check tavily? It's stdio, so there's no
  port to probe - the check would be limited to registration presence
- [ ] Should `cpp/load-mcp-docs.md` include Tavily API reference? If so, how
  much (the full OpenAPI spec is large)

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

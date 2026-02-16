# Feature Specification: Wave 6 — Polish, Quality & DX

> **Created:** 2026-02-16
> **Status:** Approved

---

## Overview

Wave 5 shipped 15 issues overhauling the `/flow` workflow, secrets management, and security scanning. It left behind orphaned files, no test coverage, a chess-hardcoded QA skill, and DX gaps. Wave 6 addresses the highest-impact items across cleanup, quality, and new capabilities to bring CPP to production-grade 5.0.0.

---

## User Stories

### US1: Codebase Hygiene [P1]

**As a** CPP maintainer,
**I want** orphaned files and stale commands removed,
**So that** the project structure matches the documented v4.0 architecture.

**Acceptance Criteria:**
- [ ] Root `mcp-coordination/` directory deleted (moved to `extras/` in v4.0)
- [ ] `.claude/commands/coordination/` deleted (replaced by `/flow:finish`, `/flow:merge`)
- [ ] No dangling references to removed paths in CLAUDE.md or README
- [ ] File permissions normalized (`.claude/skills/project-deploy.md` → 644)

---

### US2: Project-Agnostic QA [P1]

**As a** developer using CPP on any project,
**I want** `/qa:test` to work with configurable test areas,
**So that** I can run browser-based QA without chess-specific hardcoding.

**Acceptance Criteria:**
- [ ] `/qa:test` reads test configuration from `.claude/qa.yml`
- [ ] Config supports: project URL, test areas (name + path + description), shortcuts
- [ ] Falls back to sensible defaults when no config exists
- [ ] Chess-agent config moved to chess-agent project's `.claude/qa.yml`

---

### US3: Test Coverage [P1]

**As a** CPP contributor,
**I want** unit tests for the Python libraries,
**So that** regressions are caught before merge.

**Acceptance Criteria:**
- [ ] `tests/` directory with pytest configuration
- [ ] Tests for `lib/spec_bridge/` (parser, status)
- [ ] Tests for `lib/security/` (models, orchestrator, native scanners)
- [ ] Tests for `lib/creds/` (base, config, masking, project identity)
- [ ] CPP Makefile with `test` and `lint` targets

---

### US4: Developer Experience [P2]

**As a** developer setting up a new project with CPP,
**I want** health checks, templates, and docs,
**So that** I can get started quickly and troubleshoot issues.

**Acceptance Criteria:**
- [ ] `/flow:doctor` reports MCP server connectivity status
- [ ] `/cpp:status` shows which MCP servers are reachable
- [ ] Stack-specific Makefile templates available (Python, Node.js, Django)
- [ ] Security gate behavior documented in `/flow:help`

---

### US5: Secret Lifecycle [P2]

**As a** developer managing secrets,
**I want** a `/secrets:delete` command,
**So that** I can remove compromised or unused secrets.

**Acceptance Criteria:**
- [ ] Delete operation supported in dotenv and AWS providers
- [ ] CLI: `python -m lib.creds delete KEY`
- [ ] `/secrets:delete KEY` skill command
- [ ] Audit log records delete operations

---

### US6: Pre-Commit Validation [P2]

**As a** developer iterating on code,
**I want** a lightweight check command,
**So that** I can validate lint + security before running the full finish flow.

**Acceptance Criteria:**
- [ ] `/flow:check` runs lint (via Makefile) and security quick scan
- [ ] Does NOT commit, push, or create PR
- [ ] Reports pass/fail per check with clear output
- [ ] Exit code reflects overall pass/fail

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| No `.claude/qa.yml` exists | QA skill prompts user to create one or uses interactive mode |
| MCP server not configured | Health check reports "not configured" (not error) |
| Delete non-existent secret | Clear error message, no crash |
| No Makefile for /flow:check | Skip lint, run security only, warn about missing Makefile |

---

## Out of Scope

- Redis coordination removal (already in `extras/`, keep as-is)
- New MCP server development
- CI/CD pipeline setup
- Cross-platform (Windows) testing

---

## Success Criteria

- [ ] All acceptance criteria met
- [ ] All new tests passing
- [ ] CHANGELOG updated for 5.0.0
- [ ] README and CLAUDE.md reflect current state
- [ ] No regressions in existing functionality

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

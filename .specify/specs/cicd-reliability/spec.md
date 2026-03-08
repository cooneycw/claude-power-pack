# Feature Specification: CI/CD Deterministic Reliability

> **Issue:** #243
> **Created:** 2026-03-08
> **Status:** Draft

---

## Overview

Replace prompt-driven CI/CD orchestration with a deterministic Python runner backed by a typed task manifest. Flow commands remain the user-facing interface but delegate execution to the runner, eliminating nondeterminism while preserving the Claude Code UX.

**Core insight:** CPP's prompt-driven flows are strong as a UX layer but weak as a state machine. Moving orchestration to Python with persistent state enables resumable, retryable, rollback-capable pipelines while keeping the conversational interface users value.

---

## User Stories

### US1: Deterministic Runner [P0 - Critical]

**As a** CPP user running `/flow:auto` or `/flow:finish`,
**I want** pipeline steps to execute deterministically with persistent state,
**So that** failures are resumable and execution is reproducible across sessions.

**Acceptance Criteria:**
- [ ] Runner executes steps sequentially with typed results (success/fail/skip)
- [ ] State persisted to `.claude/runs/<run_id>.json` after each step
- [ ] Resume from last failed step via `python -m lib.cicd resume <run_id>`
- [ ] Retry policy per step (max attempts, backoff)
- [ ] Timeout enforcement per step
- [ ] Structured JSON output for LLM consumption
- [ ] CLI: `python -m lib.cicd run --plan <name>` and `resume`

### US2: Typed Task Manifest [P1 - High]

**As a** project maintainer,
**I want** to define CI/CD step semantics (timeouts, retries, rollback, artifacts) in a typed manifest,
**So that** the runner knows how to handle each step beyond just "run make X".

**Acceptance Criteria:**
- [ ] `.claude/cicd_tasks.yml` schema with version, plans, steps
- [ ] Pydantic v2 validation with clear error messages
- [ ] Auto-generation from detected framework + existing Makefile
- [ ] Plans compose steps by name (finish, auto, deploy)
- [ ] Steps define: command, timeout, retry, idempotent, artifacts, rollback
- [ ] Backwards compatible - existing projects work without manifest (defaults generated)

### US3: Deployment Strategy Patterns [P2 - Critical/High]

**As a** developer deploying to Docker Compose, AWS SSM, or bare metal,
**I want** pluggable deployment strategies with readiness gates and rollback,
**So that** deploys verify health before declaring success and can roll back on failure.

**Acceptance Criteria:**
- [ ] DeploymentStrategy Protocol with deploy/rollback/check_readiness methods
- [ ] DockerComposeStrategy implementation (primary)
- [ ] ReadinessPolicy with polling, exponential backoff, consecutive success threshold
- [ ] Rollback invoked automatically on readiness failure
- [ ] Strategy selected via manifest `strategy:` field

### US4: Schema Validation [P3 - High]

**As a** CPP user editing `.claude/cicd.yml`,
**I want** typos and invalid config to be caught immediately,
**So that** I don't get silent misconfigurations that cause runtime failures.

**Acceptance Criteria:**
- [ ] Pydantic v2 models replace dataclass config
- [ ] `extra="ignore"` for backwards compatibility (phase 1)
- [ ] `python -m lib.cicd validate` command with fix suggestions
- [ ] JSON Schema auto-generated for IDE autocompletion
- [ ] Existing configs load without errors

### US5: Woodpecker Hardening [P4 - Medium-High]

**As a** CPP maintainer running Woodpecker CI,
**I want** pinned image digests, deploy concurrency locks, and JUnit reports,
**So that** CI is supply-chain hardened and provides better observability.

**Acceptance Criteria:**
- [ ] Docker images pinned by SHA256 digest in .woodpecker.yml
- [ ] Deploy step uses flock for concurrency control
- [ ] pytest produces JUnit XML reports
- [ ] Tailscale ACL recommendations documented

### US6: Drift Detection [P5 - Medium]

**As a** maintainer of multiple CPP-managed repos,
**I want** a `cpp sync` command that detects config drift and opens PRs,
**So that** repos stay aligned with CPP best practices over time.

**Acceptance Criteria:**
- [ ] `python -m lib.cicd sync` regenerates artifacts and diffs
- [ ] `--create-pr` opens a PR with drift fixes
- [ ] `--dry-run` shows what would change
- [ ] Works on single repo and multi-repo (via config)

---

## Non-Goals

- Replacing Makefile as the build executor (Make stays, manifest adds metadata)
- Building a full workflow engine (no Temporal/Argo complexity)
- Changing the user-facing prompt experience (prompts remain .md files)
- Supporting non-Python runtimes for the runner itself

---

## Technical Constraints

- Python 3.11+, uv for dependencies
- Pydantic v2 for validation (new dependency for lib/cicd)
- No external state stores (state is local JSON files)
- Must work without manifest (auto-generate defaults from Makefile)
- Runner CLI must produce structured JSON output for LLM parsing

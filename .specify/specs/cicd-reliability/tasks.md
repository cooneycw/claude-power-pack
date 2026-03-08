# Tasks: CI/CD Deterministic Reliability

> **Plan:** [plan.md](./plan.md)
> **Created:** 2026-03-08
> **Status:** In Progress

---

## Task Format

```
[ID] [P?] [Story] Description (depends on X, Y)
```

- **ID**: Task identifier (T001, T002, etc.)
- **[P]**: Parallelizable - can run simultaneously with other [P] tasks
- **Dependencies**: Tasks that must complete first

---

## Wave 1: Deterministic Runner Core

### US1: Deterministic Runner

- [ ] **T001** [US1] Create `lib/cicd/state.py` - RunState dataclass with JSON persistence, step status tracking, save/load/cleanup
- [ ] **T002** [US1] Create `lib/cicd/steps.py` - ShellStep implementation with subprocess timeout, retry with backoff, structured StepResult output (depends on T001)
- [ ] **T003** [US1] Create `lib/cicd/runner.py` - DeterministicRunner with execute/resume, step iteration, state management, structured JSON output (depends on T001, T002)
- [ ] **T004** [US1] Add `run` and `resume` subcommands to `lib/cicd/cli.py` (depends on T003)
- [ ] **T005** [US1] Add StepStatus, StepResult, RunResult to `lib/cicd/models.py` (depends on T001)
- [ ] **T006** [P] [US1] Unit tests for state persistence (save, load, resume from index, cleanup on success) `tests/test_runner_state.py` (depends on T001)
- [ ] **T007** [P] [US1] Unit tests for runner execution (success path, failure halt, retry, resume) `tests/test_runner.py` (depends on T003)

**Checkpoint:** `python -m lib.cicd run --plan finish` executes lint+test steps deterministically with state file

---

## Wave 2: Typed Task Manifest

### US2: Typed Task Manifest

- [ ] **T008** [US2] Create `lib/cicd/manifest.py` - Pydantic v2 models: TaskManifest, PlanDef, StepDef with validation (depends on T003)
- [ ] **T009** [US2] Add manifest auto-generation from detected framework + existing Makefile `lib/cicd/manifest.py` (depends on T008)
- [ ] **T010** [US2] Create CPP's own `.claude/cicd_tasks.yml` manifest for the claude-power-pack repo (depends on T008)
- [ ] **T011** [US2] Add `init-manifest` subcommand to CLI for generating default manifest (depends on T009)
- [ ] **T012** [P] [US2] Unit tests for manifest loading, validation, and auto-generation `tests/test_manifest.py` (depends on T008)

**Checkpoint:** `python -m lib.cicd init-manifest` generates valid cicd_tasks.yml from detected framework

---

## Wave 3: Deployment Strategies + Readiness Gates

### US3: Deployment Strategy Patterns

- [ ] **T013** [US3] Create `lib/cicd/deploy/__init__.py` and `lib/cicd/deploy/strategy.py` - DeploymentStrategy Protocol, ReadinessPolicy, poll_readiness() (depends on T003)
- [ ] **T014** [US3] Create `lib/cicd/deploy/docker_compose.py` - DockerComposeStrategy with deploy/rollback/check_readiness (depends on T013)
- [ ] **T015** [US3] Create DeployStep in `lib/cicd/steps.py` that loads strategy from manifest and executes deploy+readiness+rollback (depends on T013, T008)
- [ ] **T016** [P] [US3] Unit tests for readiness polling (mock HTTP, consecutive success, timeout) `tests/test_deploy.py` (depends on T013)
- [ ] **T017** [P] [US3] Integration test: deploy + readiness gate + rollback scenario `tests/test_deploy_integration.py` (depends on T014, T015)

**Checkpoint:** Runner can execute deploy steps with readiness gates and automatic rollback on failure

---

## Wave 4: Schema Validation + Flow Prompt Integration

### US4: Schema Validation

- [ ] **T018** [US4] Migrate `lib/cicd/config.py` from dataclasses to Pydantic v2 models with `extra="ignore"` (depends on T008)
- [ ] **T019** [US4] Add `validate` subcommand to CLI with fix suggestions (depends on T018)
- [ ] **T020** [P] [US4] Unit tests for config validation (valid, invalid, backwards-compat) `tests/test_config_validation.py` (depends on T018)

### Flow Prompt Integration

- [ ] **T021** [US1] Update `/flow:finish` prompt to call runner as primary path with fallback (depends on T004)
- [ ] **T022** [US1] Update `/flow:auto` prompt to call runner as primary path with fallback (depends on T004)
- [ ] **T023** [US1] Update `/flow:deploy` prompt to call runner with deploy strategy (depends on T015)

**Checkpoint:** Flow commands call runner; existing behavior preserved as fallback

---

## Wave 5: Woodpecker Hardening

### US5: Woodpecker Hardening

- [ ] **T024** [P] [US5] Pin Docker images by SHA256 digest in `.woodpecker.yml`
- [ ] **T025** [P] [US5] Add flock concurrency lock to deploy-mcp step
- [ ] **T026** [P] [US5] Add `--junitxml=reports/junit.xml` to pytest in validate step
- [ ] **T027** [US5] Document Tailscale ACL restrictions for CI agent in `docs/woodpecker-security.md`
- [ ] **T028** [US5] Create `scripts/woodpecker-setup.sh` for reproducible server provisioning

**Checkpoint:** Woodpecker pipeline uses pinned images, locked deploys, and JUnit reports

---

## Wave 6: Drift Detection + Polish

### US6: Drift Detection

- [ ] **T029** [US6] Create `lib/cicd/sync.py` - regenerate artifacts, diff, report drift (depends on T009)
- [ ] **T030** [US6] Add `sync` subcommand to CLI with --dry-run and --create-pr flags (depends on T029)
- [ ] **T031** [P] [US6] Unit tests for drift detection `tests/test_sync.py` (depends on T029)

### Workflow Integration

- [ ] **T032** [US1] Make `/spec:create` a non-optional step in `/project:init` (Step 5 becomes mandatory)
- [ ] **T033** [US2] Make `/cicd:pipeline` consult `cicd_tasks.yml` manifest before generating pipeline YAML (depends on T008)

### Documentation + Version

- [ ] **T034** [US1] Update CLAUDE.md with runner commands and cicd_tasks.yml reference (depends on T023)
- [ ] **T035** [US1] Update README.md with CI/CD reliability features (depends on T034)
- [ ] **T036** [US1] Add CHANGELOG entries and bump version to 5.2.0 (depends on T035)

**Checkpoint:** `cpp sync --dry-run` shows drift; docs and version updated

---

## Issue Sync

> Use `/spec:sync` to create GitHub issues from these tasks.

| Wave | Tasks | Issue | Status |
|------|-------|-------|--------|
| 1 | T001-T007 | - | pending |
| 2 | T008-T012 | - | pending |
| 3 | T013-T017 | - | pending |
| 4 | T018-T023 | - | pending |
| 5 | T024-T028 | - | pending |
| 6 | T029-T036 | - | pending |

---

## Notes

- Wave 1 is the foundation - everything else depends on the runner
- Waves 2-3 can partially overlap (manifest loading is needed for deploy strategy)
- Wave 4 integrates everything into the user-facing flow commands
- Waves 5-6 are independent improvements that can ship separately
- Total: 34 tasks across 6 waves (~3-4 weeks)
- Each wave has a checkpoint verifying the deliverable works end-to-end

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

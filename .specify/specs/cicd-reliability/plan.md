# Implementation Plan: CI/CD Deterministic Reliability

> **Issue:** #243
> **Spec:** [spec.md](./spec.md)
> **Created:** 2026-03-08
> **Status:** Draft

---

## Summary

Build a deterministic Python runner that executes CI/CD steps from a typed task manifest, replacing LLM-driven orchestration. Implement deployment strategies with readiness gates, add Pydantic schema validation, harden Woodpecker CI, and add drift detection. All changes are incremental - existing projects work unchanged.

---

## Technical Context

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Language | Python 3.11+ | CPP standard |
| Validation | Pydantic v2 | 4-model consensus; auto JSON Schema, great errors |
| State Storage | Local JSON files | No external deps; `.claude/runs/` directory |
| Manifest Format | YAML | Matches existing cicd.yml convention |
| CLI Framework | argparse (existing) | No new deps; extend existing lib/cicd CLI |
| Deploy Strategy | Protocol + implementations | Pluggable; DockerCompose first |

---

## Architecture

```
User: /flow:auto 42
  |
  v
Prompt (.md) --> "Run: python -m lib.cicd run --plan auto"
  |
  v
Runner (runner.py)
  |-- loads manifest (cicd_tasks.yml or auto-generated)
  |-- creates/resumes RunState (.claude/runs/<id>.json)
  |-- executes steps sequentially
  |     |-- ShellStep: subprocess with timeout + retry
  |     |-- DeployStep: strategy.deploy() + readiness gate
  |     |-- GitStep: git operations
  |-- on failure: saves state, returns structured error JSON
  |-- on success: cleans up state file
  |
  v
LLM reads output:
  - Success: reports completion
  - Failure: reads error, fixes code, re-runs same command
  - Runner resumes from failed step automatically
```

---

## File Structure

```
lib/cicd/
  runner.py           # DeterministicRunner engine
  manifest.py         # TaskManifest, StepDef, PlanDef (Pydantic v2)
  state.py            # RunState persistence
  steps.py            # Step implementations (ShellStep, GitStep)
  deploy/
    __init__.py
    strategy.py       # DeploymentStrategy Protocol, ReadinessPolicy
    docker_compose.py # DockerComposeStrategy
  sync.py             # Drift detection (cpp sync)
  # Existing files modified:
  cli.py              # Add run/resume/validate/sync subcommands
  config.py           # Migrate to Pydantic v2
  models.py           # Add StepStatus, StepResult, RunResult
```

---

## Migration Strategy

1. **Phase 1 (Wave 1-2):** Runner and manifest ship alongside existing flows. Flow prompts unchanged.
2. **Phase 2 (Wave 3):** Update flow prompts to call runner. Old behavior still works if runner not available.
3. **Phase 3 (future):** Runner becomes default. Direct prompt orchestration deprecated.

At no point do existing users break - the runner is additive.

---

## Dependencies

- `pydantic>=2.0` added to pyproject.toml dev/optional deps
- No other new dependencies (uses subprocess, json, pathlib)

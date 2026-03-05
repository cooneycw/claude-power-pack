# Tasks: Wave 6 — Polish, Quality & DX

> **Plan:** [plan.md](./plan.md)
> **Created:** 2026-02-16
> **Status:** Complete

---

## Wave 1: Remove orphaned files and stale commands

- [x] **T001** [US1] Delete root `mcp-coordination/` directory (moved to extras/ in v4.0)
- [x] **T002** [US1] Delete `.claude/commands/coordination/` directory (pr-create.md, merge-main.md)
- [x] **T003** [US1] Remove stale references to coordination/ and env/ from CLAUDE.md
- [x] **T004** [US1] Fix `.claude/skills/project-deploy.md` permissions (600 → 644)

**Checkpoint:** `git status` shows only deletions and permission fixes; no broken references in docs

---

## Wave 2: Generalize QA skill for any project

- [x] **T005** [US2] Define `.claude/qa.yml` config schema (project URL, test areas, shortcuts)
- [x] **T006** [US2] Refactor `/qa:test` command to read from `.claude/qa.yml` `qa/test.md`
- [x] **T007** [US2] Add fallback behavior when no qa.yml exists (interactive prompt)
- [x] **T008** [US2] Update `/qa:help` with new config documentation `qa/help.md`

**Checkpoint:** `/qa:test` works with a sample `.claude/qa.yml` on a non-chess project

---

## Wave 3: Add unit tests for Python libraries

- [x] **T009** [US3] Create `tests/` directory with `conftest.py` and pytest config in `pyproject.toml`
- [x] **T010** [P] [US3] Add tests for `lib/spec_bridge/parser.py` (parse_tasks, parse_spec)
- [x] **T011** [P] [US3] Add tests for `lib/spec_bridge/status.py` (get_all_status)
- [x] **T012** [P] [US3] Add tests for `lib/security/models.py` and `lib/security/orchestrator.py`
- [x] **T013** [P] [US3] Add tests for native scanners (gitignore, permissions, secrets, debug_flags)
- [x] **T014** [P] [US3] Add tests for `lib/creds/base.py`, `lib/creds/config.py`, `lib/creds/masking.py`
- [x] **T015** [US3] Create CPP `Makefile` with `test` and `lint` targets (depends on T009)

**Checkpoint:** `make test` passes with all new tests; `make lint` passes

---

## Wave 4: Consolidate MCP health checks

- [x] **T016** [US4] Add MCP server connectivity check to `/flow:doctor` `flow/doctor.md`
- [x] **T017** [US4] Add MCP status section to `/cpp:status` `cpp/status.md`
- [x] **T018** [US4] Check ports 8080 (second-opinion), 8081 (playwright)

**Checkpoint:** `/flow:doctor` and `/cpp:status` report MCP server status correctly

---

## Wave 5: Add /secrets:delete command

- [x] **T019** [US5] Add `delete_secret()` to dotenv provider `lib/creds/providers/dotenv.py`
- [x] **T020** [US5] Add `delete_secret()` to AWS provider `lib/creds/providers/aws.py`
- [x] **T021** [US5] Add `delete` subcommand to CLI `lib/creds/cli.py`
- [x] **T022** [US5] Create `/secrets:delete` command file `.claude/commands/secrets/delete.md`
- [x] **T023** [US5] Add audit logging for delete operations `lib/creds/audit.py`

**Checkpoint:** `python -m lib.creds delete TEST_KEY` removes secret; audit log records action

---

## Wave 6: Stack-specific Makefile templates

- [x] **T024** [P] [US4] Create `templates/Makefile.python` (uv + pytest + ruff)
- [x] **T025** [P] [US4] Create `templates/Makefile.node` (npm + jest + eslint)
- [x] **T026** [P] [US4] Create `templates/Makefile.django` (uv + pytest + ruff + manage.py + deploy)
- [x] **T027** [US4] Update `/flow:doctor` to suggest relevant template when no Makefile found

**Checkpoint:** Each template has working `test`, `lint`, and `deploy` targets

---

## Wave 7: Document security gate behavior

- [x] **T028** [US4] Expand `/flow:help` with security gate integration section `flow/help.md`
- [x] **T029** [US4] Add annotated `.claude/security.yml` example to docs `docs/security-gates.md`
- [x] **T030** [US4] Document CRITICAL/HIGH gate effects on `/flow:finish` and `/flow:deploy`

**Checkpoint:** `/flow:help` output includes security gate documentation

---

## Wave 8: Update CHANGELOG and version to 5.0.0

- [x] **T031** [US1] Add CHANGELOG entries for all Wave 5 features (15 issues)
- [x] **T032** [US1] Add CHANGELOG entries for Wave 6 features
- [x] **T033** [US1] Bump version to 5.0.0 in README.md and CLAUDE.md

**Checkpoint:** CHANGELOG.md is current; version references updated

---

## Wave 9: Add /flow:check command

- [x] **T034** [US6] Create `/flow:check` command file `.claude/commands/flow/check.md`
- [x] **T035** [US6] Implement lint check via Makefile target detection
- [x] **T036** [US6] Implement security quick scan integration
- [x] **T037** [US6] Report pass/fail per check with clear output

**Checkpoint:** `/flow:check` runs lint + security and reports results without committing

---

## Wave 10: Integration and documentation update

- [x] **T038** [US1,US4] Update README.md with Wave 6 features (QA, /flow:check, /secrets:delete)
- [x] **T039** [US1,US4] Update CLAUDE.md repository structure section
- [x] **T040** [US1,US4] Verify all `/help` commands reference new additions
- [x] **T041** [US1,US4] Final QA pass — all commands documented, no broken references

**Checkpoint:** All documentation reflects current state; no stale references

---

## Issue Sync

| Wave | Tasks | Issue | Status |
|------|-------|-------|--------|
| 1 | T001-T004 | - | pending |
| 2 | T005-T008 | - | pending |
| 3 | T009-T015 | - | pending |
| 4 | T016-T018 | - | pending |
| 5 | T019-T023 | - | pending |
| 6 | T024-T027 | - | pending |
| 7 | T028-T030 | - | pending |
| 8 | T031-T033 | - | pending |
| 9 | T034-T037 | - | pending |
| 10 | T038-T041 | - | pending |

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

## Issue Sync

| Wave | Tasks | Issue | Status |
|------|-------|-------|--------|
| 1 | T001, T002, T003, T004 | #117 | complete |
| 2 | T005, T006, T007, T008 | #118 | complete |
| 3 | T009, T010, T011, T012, T013, T014, T015 | #119 | complete |
| 4 | T016, T017, T018 | #120 | complete |
| 5 | T019, T020, T021, T022, T023 | #121 | complete |
| 6 | T024, T025, T026, T027 | #122 | complete |
| 7 | T028, T029, T030 | #123 | complete |
| 8 | T031, T032, T033 | #124 | complete |
| 9 | T034, T035, T036, T037 | #125 | complete |
| 10 | T038, T039, T040, T041 | #126 | complete |

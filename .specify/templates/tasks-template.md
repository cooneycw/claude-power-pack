# Tasks: {FEATURE_NAME}

> **Plan:** [plan.md](./plan.md)
> **Created:** {DATE}
> **Status:** Draft | Ready | In Progress | Complete

---

## Task Format

```
[ID] [P?] [Story] Description (depends on X, Y)
```

- **ID**: Task identifier (T001, T002, etc.)
- **[P]**: Parallelizable - can run simultaneously with other [P] tasks
- **[Story]**: User story reference (US1, US2, etc.)
- **Dependencies**: Tasks that must complete first

---

## Wave 1: Core Implementation

### US1: {Primary User Story}

- [ ] **T001** [US1] {Task description} `path/to/file.py`
- [ ] **T002** [US1] {Task description} `path/to/file.py` (depends on T001)
- [ ] **T003** [P] [US1] {Parallelizable task} `path/to/other.py`

**Checkpoint:** US1 functionality works independently

---

## Wave 2: Extended Features

### US2: {Secondary User Story}

- [ ] **T004** [US2] {Task description} `path/to/file.py` (depends on T001)
- [ ] **T005** [P] [US2] {Parallelizable task} `path/to/file.py`
- [ ] **T006** [US2] {Task description} (depends on T004, T005)

**Checkpoint:** US2 functionality works independently

---

## Wave 3: Integration & Polish

- [ ] **T007** [US1,US2] Integration testing `tests/`
- [ ] **T008** [P] Documentation updates `docs/`, `README.md`
- [ ] **T009** [P] Update CLAUDE.md with new commands

**Checkpoint:** All tests pass, documentation complete

---

## Issue Sync

> Use `/spec:sync` to create GitHub issues from these tasks.

| Task | Issue | Status |
|------|-------|--------|
| T001-T003 (Wave 1) | #{N} | pending |
| T004-T006 (Wave 2) | #{N} | pending |
| T007-T009 (Wave 3) | #{N} | pending |

---

## Notes

- Tasks prefixed with [P] can be developed in parallel
- Each wave should be a separate GitHub issue
- Use worktrees for parallel development

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

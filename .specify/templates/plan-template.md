# Implementation Plan: {FEATURE_NAME}

> **Branch:** `issue-{N}-{feature-slug}`
> **Spec:** [spec.md](./spec.md)
> **Created:** {DATE}
> **Status:** Draft | Approved

---

## Summary

{One-paragraph summary of what's being built and the technical approach.}

---

## Technical Context

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Language | Python 3.11+ | {Why} |
| Framework | {Framework} | {Why} |
| Storage | {Storage approach} | {Why} |
| Testing | pytest | Standard for project |

---

## Constitution Check

Before proceeding, verify alignment with your project constitution.
Replace the placeholders below with your project's actual principles:

- [ ] **P1:** {First principle — does this change align?}
- [ ] **P2:** {Second principle — does this change align?}
- [ ] **Proportional response:** Is this the lightest process that fits?

---

## Architecture

### Component Overview

```
{ASCII diagram or description of component relationships}
```

### Key Design Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| {Decision 1} | A, B, C | A | {Why A was chosen} |
| {Decision 2} | X, Y | Y | {Why Y was chosen} |

---

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| {package} | {version} | {why needed} |

### Internal Dependencies

| Module | Purpose |
|--------|---------|
| `lib/{module}` | {purpose} |

---

## File Structure

```
{feature-name}/
├── __init__.py
├── {core_module}.py
├── {support_module}.py
└── tests/
    └── test_{feature}.py
```

---

## Implementation Phases

### Phase 1: Core Functionality

| Task ID | Description | Files | Dependencies |
|---------|-------------|-------|--------------|
| T001 | {Task description} | `path/to/file.py` | - |
| T002 | {Task description} | `path/to/file.py` | T001 |

### Phase 2: Integration

| Task ID | Description | Files | Dependencies |
|---------|-------------|-------|--------------|
| T003 | {Task description} | `path/to/file.py` | T001, T002 |

### Phase 3: Polish

| Task ID | Description | Files | Dependencies |
|---------|-------------|-------|--------------|
| T004 | {Task description} | `docs/*.md` | T003 |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| {Risk 1} | Low/Med/High | Low/Med/High | {Mitigation strategy} |

---

## Testing Strategy

### Unit Tests
- {What will be unit tested}

### Integration Tests
- {What integration points will be tested}

### Manual Testing
- {Any manual verification needed}

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

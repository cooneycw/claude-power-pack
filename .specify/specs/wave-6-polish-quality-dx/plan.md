# Implementation Plan: Wave 6 — Polish, Quality & DX

> **Spec:** [spec.md](./spec.md)
> **Created:** 2026-02-16
> **Status:** Approved

---

## Summary

Wave 6 cleans up technical debt from v4.0, adds test infrastructure, generalizes the QA framework, improves developer experience with health checks and templates, and adds missing capabilities (`/secrets:delete`, `/flow:check`). The wave culminates in a version bump to 5.0.0.

---

## Technical Context

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Language | Python 3.11+ | Existing project standard |
| Package Manager | uv | Existing project standard |
| Testing | pytest | Standard Python testing; new to this project |
| Config Format | YAML | Consistent with existing `.claude/security.yml`, `.claude/secrets.yml` |

---

## Architecture

### Key Design Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| QA config format | JSON, YAML, TOML | YAML | Consistent with security.yml and secrets.yml |
| Test framework | pytest, unittest | pytest | Industry standard, better DX |
| Health check approach | Dedicated command, integrate into existing | Integrate into /flow:doctor + /cpp:status | No new commands needed, leverages existing tools |
| /flow:check scope | Lint only, lint+test, lint+security | Lint + security quick | Fast feedback without slow test suites |

---

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | >=7.0 | Test runner (new dev dependency) |
| pyyaml | >=6.0 | QA config parsing (already in spec_bridge) |

### Internal Dependencies

| Module | Purpose |
|--------|---------|
| `lib/creds/` | Add delete operation to providers |
| `lib/security/` | Used by /flow:check for quick scan |
| `lib/spec_bridge/` | Test target |

---

## File Structure

### New Files

```
tests/
├── conftest.py                          # Shared fixtures
├── test_spec_bridge/
│   ├── test_parser.py
│   └── test_status.py
├── test_security/
│   ├── test_models.py
│   ├── test_orchestrator.py
│   └── test_native_scanners.py
└── test_creds/
    ├── test_base.py
    ├── test_config.py
    ├── test_masking.py
    └── test_project.py

templates/
├── Makefile.example                     # Existing
├── Makefile.python                      # New: uv + pytest + ruff
├── Makefile.node                        # New: npm + jest + eslint
└── Makefile.django                      # New: uv + manage.py + deploy

.claude/commands/
├── flow/check.md                        # New: lightweight validation
├── secrets/delete.md                    # New: secret deletion
└── qa/test.md                           # Modified: project-agnostic
```

### Modified Files

```
.claude/commands/flow/doctor.md          # Add MCP health checks
.claude/commands/flow/help.md            # Document security gates, /flow:check
.claude/commands/cpp/status.md           # Add MCP status section
.claude/commands/qa/test.md              # Generalize for any project
.claude/commands/qa/help.md              # Update for new config
lib/creds/cli.py                         # Add delete subcommand
lib/creds/providers/dotenv.py            # Add delete method
lib/creds/providers/aws.py               # Add delete method
CHANGELOG.md                             # v5.0.0 entries
README.md                                # Version bump, new features
CLAUDE.md                                # Structure update, new commands
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| spec:sync creates duplicate issues | Low | Medium | Check existing labels before creating |
| Tests too coupled to implementation | Medium | Low | Test public APIs only, use fixtures |
| QA config breaks existing chess-agent usage | Low | Medium | Keep backward compat, graceful fallback |

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*

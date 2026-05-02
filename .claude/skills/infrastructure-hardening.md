---
name: Infrastructure Hardening
description: Validation gates, runtime contracts, canary validation, sentinel files for infrastructure resilience
trigger: repeated failure, infrastructure hardening, validation gate, runtime contract, canary validation, sentinel file, pipeline hardening, SRE pattern
---

# Infrastructure Hardening Skill

When repeated infrastructure or pipeline failures are detected, or the user asks about hardening, validation gates, runtime contracts, canary checks, or sentinel files, load the full reference:

```
Read docs/skills/infrastructure-hardening.md
```

## Quick Reference

### Pattern Detection

```python
from lib.cicd.failure_patterns import analyze_failure_patterns
report = analyze_failure_patterns()
if report.has_patterns:
    print(report.summary())
```

### Validation Gate Types

| Gate | Use When |
|------|----------|
| Runtime contract | Shell compat, implicit detection, dependency failures |
| Sentinel file | Implicit artifact detection (e.g., `.git` checks) |
| Canary validation | Deploy failures surfacing only in production |
| Auth bootstrap | Repeated credential/permission failures |
| Capability readiness | Services pass ping but fail on first real request |
| Deploy lock | Resource contention on shared infrastructure |

### Key Principle

After 2+ failures from the same root cause: stop patching symptoms, propose systemic hardening.

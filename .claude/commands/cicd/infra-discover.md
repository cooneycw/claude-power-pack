---
description: Generate cloud resource discovery script for IaC import
allowed-tools: Bash(PYTHONPATH=*), Bash(python3:*), Bash(bash:*), Bash(ls:*), Read, AskUserQuestion
---

# /cicd:infra-discover — Cloud Resource Discovery

Generate a discovery script that audits existing cloud resources and outputs them in a format suitable for IaC import (`terraform import`, etc.).

## Instructions

1. **Detect cloud provider** from `.claude/cicd.yml` or ask the user (aws/azure/gcp).

2. **Generate the discovery script:**

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd infra-discover --path "$(pwd)" --cloud aws --write
```

3. **Optionally run the script** if the user has CLI tools configured:

```bash
bash infra/scripts/discover-aws.sh
```

4. **Report findings** and suggest which resources to import first (most critical/fragile).

## When to Use

- Starting IaC from scratch ("no documentation exists yet")
- Auditing what exists before codifying it
- Building a manifest for `terraform import`

## Key Principle

Even if you only plan to run infrastructure changes once, codify them. The value is having an executable runbook, not a stale wiki page.

## Related

- `/cicd:infra-init` — Scaffold IaC directory structure
- `/cicd:infra-pipeline` — Generate CI/CD pipelines with approval gates

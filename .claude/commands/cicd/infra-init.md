---
description: Scaffold IaC directory with tiered structure (foundation/platform/app)
allowed-tools: Bash(PYTHONPATH=*), Bash(python3:*), Bash(ls:*), Bash(cat:*), Read, AskUserQuestion
---

# /cicd:infra-init — Scaffold Infrastructure as Code

Generate a tiered IaC directory structure for your project.

## Instructions

1. **Check for existing IaC** by running detection:

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd infra-init --path "$(pwd)" --json
```

2. **If no `.claude/cicd.yml` exists**, ask the user for:
   - IaC provider: terraform (default), pulumi, or bicep
   - Cloud provider: aws (default), azure, or gcp
   - Remote state backend type (s3, azure-storage, gcs)
   - Tagging conventions (managed-by, repo, owner)

3. **If `.claude/cicd.yml` exists** with an `infrastructure` section, use those settings.

4. **Generate the scaffold:**

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd infra-init --path "$(pwd)" --write
```

5. **Report what was created** and suggest next steps.

## Three-Tier Model

- **foundation/** — Run once, touch rarely. DNS zones, resource groups, networking, identity. Manual approval gates.
- **platform/** — Shared services. Container registries, key vaults, shared databases. Less frequent deploys.
- **app/** — Application-specific infrastructure. Deployed with application CI/CD.

## Configuration

Add to `.claude/cicd.yml`:

```yaml
infrastructure:
  provider: terraform
  cloud: aws
  state_backend:
    type: s3
    bucket: my-tf-state
    lock: true
  tagging:
    managed-by: terraform
    repo: my-project
    owner: platform-team
  tiers:
    foundation:
      approval_required: true
      separate_credentials: true
    platform:
      approval_required: false
    app:
      approval_required: false
```

## Related

- `/cicd:infra-discover` — Audit existing cloud resources
- `/cicd:infra-pipeline` — Generate CI/CD pipelines with approval gates

---
description: Generate CI/CD pipelines for infrastructure tiers with approval gates
allowed-tools: Bash(PYTHONPATH=*), Bash(python3:*), Bash(ls:*), Read, AskUserQuestion
---

# /cicd:infra-pipeline - Infrastructure CI/CD Pipelines

Generate separate CI/CD pipelines for each infrastructure tier with appropriate approval gates.

## Step 1: Locate CPP Source

```bash
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done

if [ -z "$CPP_DIR" ]; then
  echo "ERROR: claude-power-pack not found"
  exit 1
fi
```

---

## Instructions

1. **Read configuration** from `.claude/cicd.yml`, including the recorded
   `pipeline.providers` list. Use `python -m lib.cicd provider --json`; unknown
   stops generation. An explicit `--providers NAME[,NAME]` override is deliberate.
   Generate each selected provider; legacy `--provider both` remains readable.

2. **Preview** without `--write`. Review every emitted path for all selected
   providers; ask before overwriting existing files. Then generate the reviewed files:

```bash
PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" python -m lib.cicd infra-pipeline --path "$(pwd)" --write
```

3. **Report what was generated** and explain the approval model:
   - Foundation: requires environment approval in GitHub (or manual in Woodpecker)
   - Platform: auto-deploy on merge (configurable)
   - App: auto-deploy on merge

## Pipeline Model

Each tier gets its own workflow file, triggered only by changes to that tier's directory:

- `.github/workflows/infra-foundation.yml` - Manual approval required
- `.github/workflows/infra-platform.yml` - Auto-deploy (configurable)
- `.github/workflows/infra-app.yml` - Auto-deploy

Woodpecker emits `.woodpecker/infra-<tier>.yml` for each tier. Selecting both
providers emits both path families. These path-filtered workflows do not supply
unconditional required contexts for every PR; `cicd checks` reports that boundary.

### Hardening and caller setup

GitHub's workflow root and each plan/apply job grant only `contents: read`, for
checkout, with `persist-credentials: false`. Cloud authentication is the caller's
setup. A consumer adding an OIDC cloud login must grant `id-token: write` on the
job that needs it; these workflows do not emit a cloud login or request that grant.
Install/configure the selected tool on the GitHub runner and supply its cloud
credentials, backend and stack configuration before using the generated commands.

Named generator defaults limit GitHub plan jobs to 30 minutes and apply jobs to
120 minutes. The apply budget is deliberately loose: interrupting a normal apply
can leave a state lock held and resources partly created. Inspect and repair the
cloud/state outcome after an interrupted apply before retrying.

Woodpecker's pipeline deadline is a **project setting**, outside the emitted YAML;
configure it before running infrastructure jobs. The generated file states this
limit. Plan and apply use the selected Terraform, Pulumi or Bicep commands, shared
with GitHub's generator. Supply tool credentials and any Pulumi backend/stack
setup. Bicep uses GitHub's `vars.AZURE_LOCATION`, or Woodpecker's runtime
`AZURE_LOCATION` environment variable; missing runtime location fails explicitly.
Woodpecker's `$$` escaping preserves the runtime shell expansion.

Woodpecker pulls fixed release tags plus multi-architecture index digests from
the shared constants in `lib/cicd/actions.py`: Terraform 1.17.2, Pulumi Python
3.276.0, and Azure CLI 2.92.0 (resolved 2026-11-13). These pins stop following
`:latest` updates until a reviewed regeneration changes them.

Only `infrastructure.provider: terraform`, `pulumi` or `bicep` is supported for
pipeline generation. `none` and `cloudformation` are rejected before writing any
file, including through the CLI config path; they no longer fall back to Terraform.

Existing consumers must regenerate and review their workflows by hand. No content
drift check or notification tells them their committed generated files are stale.

### Approval Gates

Foundation tier uses GitHub Environments with required reviewers. Set up:
1. Go to repo Settings > Environments
2. Create `infra-foundation` environment
3. Add required reviewers

## Related

- `/cicd:infra-init` - Scaffold IaC directory structure
- `/cicd:infra-discover` - Audit existing cloud resources
- `/cicd:pipeline` - Application-layer pipeline generation

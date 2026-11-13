# Infrastructure workflow setup

## Hardening and caller setup

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

## Related

- `/cicd:infra-init` - Scaffold IaC directory structure
- `/cicd:infra-discover` - Audit existing cloud resources
- `/cicd:pipeline` - Application-layer pipeline generation

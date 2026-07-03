# Woodpecker Self-Hosted CI

Practical patterns for running production-grade CI on a self-hosted
[Woodpecker](https://woodpecker-ci.org) server. The whole Claude Code / skills
ecosystem assumes GitHub Actions; this is the uncovered ground. If you run your
own CI on a home lab or private cloud, this is the reference.

Load this doc when generating or hardening a `.woodpecker.yml`, standing up a
Woodpecker server + agent, or debugging a self-hosted pipeline. Generate the
pipeline with `/cicd:woodpecker`; scaffold the server/agent with the templates
in `templates/woodpecker/`.

## Why self-hosted Woodpecker

- No per-minute billing and no third-party access to your source or secrets.
- Runs next to private infrastructure (Tailscale, LAN Docker registries,
  LocalStack) that hosted runners cannot reach.
- Small audience, zero competition: nobody packages this knowledge, so the
  operational gotchas below are the entire value.

The trade-off: GitHub Actions gives you a Marketplace of pre-built actions
(secret scanning, CVE gates, SBOM) for free. Self-hosted CI has none of that -
every gate is wired explicitly. The `/cicd:woodpecker` codegen and the hardening
flags exist to wire them for you.

## Architecture: server + agent(s)

Woodpecker splits into two long-running services:

- **Server** - web UI + API + pipeline scheduler. One instance. Exposes an HTTP
  port (UI/API) and a gRPC port that agents dial in on.
- **Agent(s)** - execute pipeline steps as Docker containers. One or more, on any
  host that can reach the server's gRPC port. Each agent mounts the Docker
  socket and runs `WOODPECKER_MAX_WORKFLOWS` concurrent workflows.

```
  developer push -> forge (GitHub) -> webhook -> Woodpecker Server
                                                   |  gRPC :9001
                                        +----------+----------+
                                        |                     |
                                   Agent (VM A)          Agent (VM B)
                                   docker.sock           docker.sock
```

Keep the gRPC port private. In a home lab, expose it over Tailscale only, never
on the public internet. The server needs a forge OAuth app (GitHub client id +
secret) and a shared agent secret; agents authenticate with that same secret.

See `templates/woodpecker/docker-compose.server.yml.example` and
`docker-compose.agent.yml.example`.

## Install

1. **Server** - copy `docker-compose.server.yml.example`, set the admin user and
   forge, then bring it up:

   ```bash
   docker compose -f docker-compose.server.yml up -d
   ```

2. **Secrets bootstrap** - the server needs `WOODPECKER_GITHUB_CLIENT`,
   `WOODPECKER_GITHUB_SECRET`, `WOODPECKER_AGENT_SECRET`, and a host URL. Rather
   than commit them, fetch from AWS Secrets Manager into a gitignored `.env`:

   ```bash
   python3 bootstrap-secrets.py --secret-name my-woodpecker-secret --region us-east-1
   ```

   (Copy `templates/woodpecker/bootstrap-secrets.py.example`.) The generated
   `docker.env` is referenced by the compose `env_file:` and is never committed.

3. **Agent** - on each executor host, copy `docker-compose.agent.yml.example`,
   set `WOODPECKER_SERVER` (the gRPC address) and `WOODPECKER_AGENT_SECRET`, then:

   ```bash
   docker compose -f docker-compose.agent.yml up -d
   ```

4. **CLI (optional)** - the `woodpecker-cli` binary drives the server from your
   workstation (list repos, trigger builds, read logs). Authenticate with a host
   URL + API token, both storable in AWS Secrets Manager. CPP ships
   `scripts/setup-woodpecker-cli.sh` as a working reference.

## Pipeline syntax essentials

A `.woodpecker.yml` has a top-level `when:` (which events trigger the pipeline)
and `steps:` (the work). Each step is a container image plus `commands:`.

```yaml
when:
  branch: [main]
  event: [push, pull_request]

steps:
  - name: lint
    image: python:3.12
    commands:
      - pip install uv
      - uv sync
      - make lint
```

- **Sequential vs DAG.** With no `depends_on` anywhere, steps run top-to-bottom
  in listed order. As soon as one step declares `depends_on`, the pipeline
  switches to DAG mode and only declared edges order execution. The
  `/cicd:woodpecker` codegen relies on emission order (no `depends_on`) so the
  base pipeline stays simple; add `depends_on` by hand only when you want
  parallel fan-out.
- **Run steps as `make` targets**, not raw tool invocations. This keeps CI in
  lockstep with local `make lint` / `make test`, so a green local run predicts a
  green pipeline.
- **Path gating** - expensive stages (image builds, smoke) should only run when
  relevant files change. Woodpecker supports `when: path:` per step:

  ```yaml
  when:
    - event: [push, pull_request]
      path:
        include: ['Dockerfile', 'docker-compose*.yml', 'src/**']
  ```

## The four hardening stages

Self-hosted CI must supply what the GitHub Marketplace gives away. The
`/cicd:woodpecker` generator emits these as opt-in stages
(`WoodpeckerConfig.secret_scan` / `image_security` / `runtime_smoke`):

### 1. Secret scanning (gitleaks)

There is no native secret scanning. Run [gitleaks](https://github.com/gitleaks/gitleaks)
as the **first** stage so credentials never reach later steps or logs:

```yaml
  - name: secret-scan
    image: zricethezav/gitleaks:v8.30.1
    commands:
      - gitleaks detect --source . --config .gitleaks.toml --verbose
```

Gate everything else behind it (`depends_on: [secret-scan]` in DAG mode).

### 2. Image security (Trivy)

Two levels, increasing cost:

- **Self-contained (codegen default)** - [Trivy](https://trivy.dev) `config` scan
  (Dockerfile + compose misconfiguration) plus `fs` scan (dependency CVEs). No
  image build, so no privileged docker socket:

  ```yaml
  - name: image-security
    image: aquasec/trivy:0.66.0
    commands:
      - trivy config --exit-code 1 --severity HIGH,CRITICAL .
      - trivy fs --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed .
  ```

- **Full built-image CVE + SBOM** - build the actual images, scan them, and emit
  SBOMs. This needs the privileged `docker-buildx` plugin and Docker Hub creds.
  See CPP's own `.woodpecker.yml` `image-security` step for the reference. Only
  reach for this when you ship container images.

`--ignore-unfixed` fails only on CVEs that have a fix available, which is the
sane policy: do not block on vulnerabilities you cannot patch.

### 3. Runtime smoke

"Validate the deployment, not just the code." After images build, stand the
stack up on random ports, probe readiness, and tear it down. The codegen emits a
thin stage wired to a project `make` target:

```yaml
  - name: runtime-smoke
    image: python:3.12
    commands:
      - pip install uv
      - uv sync
      - make smoke
```

The `make smoke` target owns the real work. CPP's `scripts/runtime-smoke.sh` is a
worked example: it brings the stack up with `docker compose up --wait`, proves
cross-container reachability, and drives a real secret through a LocalStack
Secrets Manager - no production credentials. Retry readiness probes (transient
connection-refused right after `--wait` is normal) and always `docker compose
down -v` on exit.

### 4. Secrets bootstrap

- **Pipeline secrets** are injected with `from_secret:`, which pulls from a
  Woodpecker-stored secret (repo, org, or global). Woodpecker lowercases secret
  names.

  ```yaml
  environment:
    DOCKERHUB_TOKEN:
      from_secret: dockerhub_token
  ```

- **Deploy secrets** are better fetched at deploy time from AWS Secrets Manager
  with boto3, written to a transient `.env.deploy`, sourced, then deleted - so
  the credential never sits in the Woodpecker secret store. The codegen emits
  exactly this when `secrets_source: aws-secrets-manager`.
- **Never host-publish internal ports.** A secrets sidecar (or the gRPC port)
  should be reachable cross-container by service name, not published to the host.
  A compose-policy step that greps the rendered `docker compose config` for
  `published:` regressions is cheap insurance.

## Hard-won gotchas

These cost real debugging time on CPP's own pipeline. They are the reason this
doc exists.

- **Two-layer Trivy DB drift.** When you build and scan images, the CVE gate can
  go red from either the OS base image digest **or** the app's pinned
  dependencies. Both must be green in the same branch. Bump the base image digest
  (the Debian base self-patches via `apt`) *and* run `uv lock --upgrade-package`
  for the flagged dep. Fixing one layer while the other still drifts stays red.
- **The `validate` container has no git.** `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`
  ships bash but not git. Any test that shells out to a real `git` subprocess
  fails in CI even though it passes locally. Guard those tests with
  `@pytest.mark.skipif(shutil.which("git") is None, ...)`.
- **gitleaks runs first and can block everything.** If `validate` depends on
  `secret-scan`, a test fixture containing a literal secret-shaped string fails
  CI before your tests even run. Add a path allowlist in `.gitleaks.toml` for
  doc/test false positives. Reproduce locally with
  `docker run ... gitleaks detect --no-git`.
- **Pin every image by digest, and rotate.** Pin base images and plugins to
  `tag@sha256:...`, never `:latest`, so a build traces to an exact image. Then
  run Renovate (or equivalent) on a schedule so pinning does not freeze security
  updates. Tag deployable images with the short git SHA, not `:latest`, so
  rollbacks have provenance.
- **A red self-hosted pipeline may not block a merge.** Woodpecker status is not
  automatically a required GitHub check. If you want it to gate merges, wire the
  commit status back to the forge and mark it required in branch protection -
  otherwise a red build is advisory only.
- **Keep `image-security` and `runtime-smoke` path filters in sync.** If both are
  gated on the same file globs, editing one and forgetting the other silently
  skips a gate on the exact change that needed it.

## Local runs

Woodpecker can execute a pipeline locally without a server, which is the fastest
feedback loop for editing `.woodpecker.yml`:

```bash
woodpecker exec .woodpecker.yml
```

This runs each step in its container against the current working tree. Set
`WoodpeckerConfig.local = true` to keep the generated pipeline `woodpecker exec`
friendly (avoid steps that require server-only secrets).

## Generating and configuring

```bash
# Generate a hardened .woodpecker.yml
/cicd:woodpecker
```

Enable the hardening stages in `.claude/cicd.yml`:

```yaml
pipeline:
  provider: woodpecker
  branches:
    main: [lint, test, typecheck, deploy]
    pr: [lint, test, typecheck]
  secrets_source: aws-secrets-manager
  aws_secret_name: my-app-deploy-secrets
  woodpecker:
    local: true
    secret_scan: true       # gitleaks stage (first)
    image_security: true    # Trivy config + fs CVE scan
    runtime_smoke: true      # make smoke after build
    smoke_target: smoke      # make target for runtime-smoke
    secret_scan_config: .gitleaks.toml
```

All hardening flags default to `false`, so an unconfigured project gets the plain
lint/test/deploy pipeline and opts into each gate deliberately.

## Related

- `/cicd:woodpecker` - generate a hardened `.woodpecker.yml` + scaffold pointers
- `/cicd:pipeline` - generate GitHub Actions or Woodpecker from config provider
- `/cicd:smoke` - run the smoke tests the runtime-smoke stage invokes
- `templates/woodpecker/` - server + agent compose and secrets bootstrap examples
- `docs/skills/cicd-verification.md` - framework detection + Makefile conventions

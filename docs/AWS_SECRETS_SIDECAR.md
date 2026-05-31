# AWS Secrets Manager Sidecar

The `aws-secrets-agent` is a Rust-based sidecar container that injects API keys into MCP server containers at startup, eliminating plaintext secrets from `.env` files.

## Architecture

```
.env or CI environment (AWS creds only)
  |
  v
aws-secrets-agent (port 2773)        <-- fetches from AWS Secrets Manager
  | (compose network only, expose       caches in-memory (300s TTL)
  |  not ports - never on the host)      SSRF token protection
  v
fetch-secrets.sh (entrypoint wrapper)   <-- app container, NO AWS creds,
  |                                          only SSRF token + secret name
  v
MCP server (python server.py)        <-- secrets exported as env vars
```

### Exposure model

- The agent is published only on the internal compose network
  (`http://aws-secrets-agent:2773`) via `expose:`, never to the host. A
  host-published port combined with a shared default token would let any local
  process pull allowed secrets.
- App containers (`mcp-second-opinion`, `mcp-woodpecker-ci`) do not receive the
  root `.env` and therefore carry no AWS credentials. They reach the agent with
  only the SSRF token (`AWS_TOKEN`) plus their non-secret `AWS_SECRET_NAME` /
  `SECRETS_AGENT_URL` config.
- `AWS_TOKEN` must be a unique, non-default value. `make docker-up` preflight
  (`scripts/check-docker-aws-env.py`) refuses to start when it resolves to empty
  or the insecure `default-token` (set `CPP_ALLOW_DEFAULT_TOKEN=1` for offline
  local dev only).
- The agent and app containers run with `no-new-privileges:true`, and the agent
  image runs as the non-root `agent` user. (`cap_drop: ALL` is intentionally not
  applied to the agent: the upstream binary fails to exec under an empty
  capability set.)

For host-side debugging or offline local dev, opt into `docker-compose.dev.yml`
(loopback only, never CI/prod):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up
```

It binds the agent to `127.0.0.1:2773`, restores the `.env` env_file for app
containers, and sets `ALLOW_ENV_FALLBACK=true` so a fully offline stack (no AWS)
can read API keys from `.env` instead of failing closed.

## How It Works

1. The `aws-secrets-agent` container starts and connects to AWS Secrets Manager using credentials from `.env` or the deploy environment
2. It runs as a local HTTP daemon on port 2773, serving secrets to other containers on the Docker network
3. Each MCP container uses `fetch-secrets.sh` as its entrypoint, which:
   - Checks if `AWS_SECRET_NAME` is set (skips fetch if not - local dev mode)
   - Queries the sidecar for the named secret
   - Parses the JSON secret value and exports each key-value pair as an environment variable
   - **Fails closed** if a required secret cannot be fetched or parsed: it exits non-zero instead of starting a keyless server (unless `ALLOW_ENV_FALLBACK=true`)
   - Execs the original command (e.g., `python server.py`)

### Fail-closed behaviour (issue #347)

When `AWS_SECRET_NAME` is set, a failed fetch or parse is treated as fatal: the
entrypoint exits non-zero and the container never starts. This prevents the
"killer chain" (#346) where a keyless server passes the liveness (`/`)
healthcheck and `docker compose up --wait` tears down the known-good container.

The entrypoint honours these optional tunables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ALLOW_ENV_FALLBACK` | `false` | `true` re-enables the old fail-open behaviour (start with `env_file` variables on fetch/parse failure). **Local dev only.** |
| `REQUIRED_SECRET_KEYS` | _(empty)_ | Space-separated keys that must be present and non-empty after the fetch, or the entrypoint fails closed. |
| `SECRETS_FETCH_MAX_RETRIES` | `30` | Fetch attempts before giving up. |
| `SECRETS_FETCH_RETRY_INTERVAL` | `2` | Seconds between attempts. |

For convenience, `docker-compose.dev.yml` sets `ALLOW_ENV_FALLBACK=true` for the
secret-consuming services:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## Required Credentials

Local development can store only AWS credentials on disk:

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_TOKEN=my-ssrf-protection-token
```

CI and deploy jobs can provide the same variables through the job environment. The root `.env` file is optional so a clean checkout can still run `docker compose` when credentials are injected by the platform.

`AWS_TOKEN` is an arbitrary string used for SSRF protection - the sidecar validates it on every request. Choose a unique, non-guessable value and keep it consistent across the agent and its consumers. The `make docker-up` preflight rejects an empty or `default-token` value.

## AWS Secrets Manager Setup

### Required Secrets

| Secret Name | Used By | Expected Keys |
|-------------|---------|---------------|
| `codex_llm_apikeys` | mcp-second-opinion | `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY` |
| `essent-ai` | mcp-woodpecker-ci | `WOODPECKER_URL`, `WOODPECKER_API_TOKEN` |

### Required IAM Permissions

The AWS credentials in `.env` need read access scoped to exactly the two named
secrets, plus `kms:Decrypt` for the CMK that encrypts them (scoped via
`kms:ViaService` so the key is only usable through Secrets Manager). Omit the KMS
statement if the secrets use the AWS-managed `aws/secretsmanager` key.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadNamedSecrets",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:codex_llm_apikeys-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:essent-ai-*"
      ]
    },
    {
      "Sid": "DecryptViaSecretsManager",
      "Effect": "Allow",
      "Action": "kms:Decrypt",
      "Resource": "arn:aws:kms:us-east-1:ACCOUNT:key/CMK-KEY-ID",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "secretsmanager.us-east-1.amazonaws.com"
        }
      }
    }
  ]
}
```

### Creating Secrets

```bash
aws secretsmanager create-secret \
  --name codex_llm_apikeys \
  --secret-string '{"GEMINI_API_KEY":"...","OPENAI_API_KEY":"...","ANTHROPIC_API_KEY":"...","MISTRAL_API_KEY":"...","GROQ_API_KEY":"...","OPENROUTER_API_KEY":"...","DEEPSEEK_API_KEY":"..."}'

aws secretsmanager create-secret \
  --name essent-ai \
  --secret-string '{"WOODPECKER_URL":"...","WOODPECKER_API_TOKEN":"..."}'
```

## Validation

```bash
# Check AWS credentials and secret availability
make docker-secrets-check

# Check running container secret source
docker logs mcp-second-opinion 2>&1 | head -5
# Should show: INFO: Loaded secrets from AWS Secrets Manager (codex_llm_apikeys)
```

## Local Development (Without AWS)

If you don't have AWS credentials or prefer local development:

1. Don't set `AWS_SECRET_NAME` in `docker-compose.yml` (remove or comment the line)
2. Put API keys directly in `.env`:
   ```
   GEMINI_API_KEY=...
   OPENAI_API_KEY=...
   ANTHROPIC_API_KEY=...
   ```
3. The `fetch-secrets.sh` entrypoint will skip the fetch and pass through to the server
4. Start with the dev override so the app containers actually receive `.env` (the
   base compose no longer mounts `.env` into app containers):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up
   ```

Alternatively, if `AWS_SECRET_NAME` is set but the agent is unreachable, the entrypoint **fails closed** by default (exits non-zero, never starts keyless). For local development, use `docker-compose.dev.yml` (or set `ALLOW_ENV_FALLBACK=true` in your shell) to start with `env_file` variables instead. The base compose deliberately keeps AWS creds and `.env` out of app containers.

## Sidecar Configuration

The sidecar is configured via `aws-secrets-agent/config.toml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `log_level` | `INFO` | Agent log verbosity |
| `http_port` | `2773` | Local HTTP port |
| `region` | `us-east-1` | AWS region for Secrets Manager |
| `ttl_seconds` | `300` | Cache TTL (secrets refreshed every 5 min) |
| `cache_size` | `1000` | Max cached secrets |
| `ssrf_env_variables` | `["AWS_TOKEN"]` | Env var name for SSRF protection token |

## Docker Compose Profiles

The sidecar is included in both `core` and `cicd` profiles and starts automatically when dependent services are activated:

- `make docker-up PROFILE=core` - starts sidecar + second-opinion + nano-banana
- `make docker-up PROFILE=cicd` - starts sidecar + woodpecker-ci
- `make docker-up PROFILE="core cicd"` - starts sidecar + all secret-dependent services

## Dockerfile Patches

The sidecar builds the [upstream AWS agent](https://github.com/aws/aws-secretsmanager-agent) from source, pinned by **commit SHA** (`AGENT_SHA` in the Dockerfile, not a mutable tag), with two tracked patches in `aws-secrets-agent/patches/`:

1. **Bind 0.0.0.0** (`0001-bind-all-interfaces.patch`) - upstream hardcodes `127.0.0.1`, blocking cross-container traffic
2. **Remove TTL=1 restriction** (`0002-remove-ttl-hop-limit.patch`) - upstream `set_ttl` call blocks DNS resolution across Docker networks

Patches are applied with `git apply --check && git apply`, followed by build-time `grep` assertions that each patch took effect. If an upstream reformat breaks a patch, the **build fails loudly** rather than silently shipping an agent still bound to `127.0.0.1` (the old `sed`-based approach exited 0 on a no-op match). See `aws-secrets-agent/patches/README.md` for how to regenerate patches after a SHA bump.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `no_api_keys` in health_check | Secrets not loaded | Check `docker logs aws-secrets-agent` for AWS auth errors |
| `Failed to fetch secrets after 30 retries` | Agent not healthy | Run `make docker-secrets-check`, verify AWS creds |
| `FATAL: refusing to start without required secret` | Required secret fetch/parse failed (fail-closed) | Fix the sidecar/AWS creds; for local dev set `ALLOW_ENV_FALLBACK=true` |
| `aws-secrets-agent cannot start: AWS credentials empty/missing` | Sidecar was created with empty `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` | Fix `.env` or shell AWS env, then run `docker compose --profile core --profile cicd up -d --force-recreate aws-secrets-agent mcp-second-opinion mcp-woodpecker-ci` |
| Secret-dependent MCP containers stay `Created` with no logs | `aws-secrets-agent` is unhealthy before dependents can start | Run `make docker-health PROFILE="core cicd"` for the force-recreate remedy |
| Container starts but keys are stale | Secret cache TTL | Wait 300s or restart `aws-secrets-agent` |
| `FAIL: AWS credentials invalid` | Expired or wrong creds | Refresh `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` in `.env` |
| `WARNING: skipping invalid key` | Secret JSON key has invalid chars | Fix the key name in AWS Secrets Manager |

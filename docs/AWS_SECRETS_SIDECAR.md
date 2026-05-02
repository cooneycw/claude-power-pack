# AWS Secrets Manager Sidecar

The `aws-secrets-agent` is a Rust-based sidecar container that injects API keys into MCP server containers at startup, eliminating plaintext secrets from `.env` files.

## Architecture

```
.env (AWS creds only)
  |
  v
aws-secrets-agent (port 2773)        <-- fetches from AWS Secrets Manager
  |                                      caches in-memory (300s TTL)
  |                                      SSRF token protection
  v
fetch-secrets.sh (entrypoint wrapper)
  |
  v
MCP server (python server.py)        <-- secrets exported as env vars
```

## How It Works

1. The `aws-secrets-agent` container starts and connects to AWS Secrets Manager using credentials from `.env`
2. It runs as a local HTTP daemon on port 2773, serving secrets to other containers on the Docker network
3. Each MCP container uses `fetch-secrets.sh` as its entrypoint, which:
   - Checks if `AWS_SECRET_NAME` is set (skips fetch if not - local dev mode)
   - Queries the sidecar for the named secret
   - Parses the JSON secret value and exports each key-value pair as an environment variable
   - Falls back to existing `env_file` variables if the agent is unreachable
   - Execs the original command (e.g., `python server.py`)

## Required `.env` File

Only AWS credentials are stored on disk:

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_TOKEN=my-ssrf-protection-token
```

`AWS_TOKEN` is an arbitrary string used for SSRF protection - the sidecar validates it on every request. Choose any value and keep it consistent.

## AWS Secrets Manager Setup

### Required Secrets

| Secret Name | Used By | Expected Keys |
|-------------|---------|---------------|
| `claude-power-pack/mcp-keys` | mcp-second-opinion | `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| `essent-ai` | mcp-woodpecker-ci | `WOODPECKER_URL`, `WOODPECKER_API_TOKEN` |

### Required IAM Permissions

The AWS credentials in `.env` need:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:claude-power-pack/mcp-keys-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:essent-ai-*"
      ]
    }
  ]
}
```

### Creating Secrets

```bash
aws secretsmanager create-secret \
  --name claude-power-pack/mcp-keys \
  --secret-string '{"GEMINI_API_KEY":"...","OPENAI_API_KEY":"...","ANTHROPIC_API_KEY":"..."}'

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
# Should show: INFO: Loaded secrets from AWS Secrets Manager (claude-power-pack/mcp-keys)
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

Alternatively, if `AWS_SECRET_NAME` is set but the agent is unreachable, the entrypoint warns and falls back to `env_file` variables.

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

The sidecar builds the [upstream AWS agent](https://github.com/aws/aws-secretsmanager-agent) from source with two patches:

1. **Bind 0.0.0.0** - upstream hardcodes `127.0.0.1`, blocking cross-container traffic
2. **Remove TTL=1 restriction** - upstream `set_ttl` call blocks DNS resolution across Docker networks

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `no_api_keys` in health_check | Secrets not loaded | Check `docker logs aws-secrets-agent` for AWS auth errors |
| `Failed to fetch secrets after 30 retries` | Agent not healthy | Run `make docker-secrets-check`, verify AWS creds |
| Container starts but keys are stale | Secret cache TTL | Wait 300s or restart `aws-secrets-agent` |
| `FAIL: AWS credentials invalid` | Expired or wrong creds | Refresh `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` in `.env` |
| `WARNING: skipping invalid key` | Secret JSON key has invalid chars | Fix the key name in AWS Secrets Manager |

---
name: Secrets Management
description: Secure credential access with tiered providers, output masking, and web UI
trigger: secrets, credentials, database password, api key, aws secrets, environment variables, .env, get credentials, connection string, secret management
---

# Secrets Management Skill

When the user asks about accessing secrets, credentials, or database connections, follow these security principles and patterns.

## Security Rules (CRITICAL)

1. **NEVER log or display actual secret values**
2. **ALWAYS use masked representations** in output
3. **Use `SecretValue` wrapper** for any sensitive data
4. **Validate credentials without exposing them**
5. **Default to READ_ONLY** database access

## Tiered Architecture

| Tier | Provider | Storage | Use Case |
|------|----------|---------|----------|
| **0** | `dotenv-global` | `~/.config/claude-power-pack/secrets/{project_id}/.env` | Local dev (default) |
| **1** | `env-file` | Environment variables / `.env` in repo | Legacy compat |
| **2** | `aws-secrets-manager` | AWS Secrets Manager | Production |

## Project Identity

Secrets are scoped per-project using a stable ID derived from the git repo root:

```python
from lib.creds.project import get_project_id
project_id = get_project_id()  # e.g., "claude-power-pack"
```

All worktrees for the same repo share the same project_id and secrets.

## Bundle API (Recommended)

```python
from lib.creds import get_bundle_provider
from lib.creds.project import get_project_id

provider = get_bundle_provider()
bundle = provider.get_bundle(get_project_id())
print(bundle)  # Keys visible, values masked

# Set a secret
from lib.creds.base import SecretBundle
update = SecretBundle(project_id=get_project_id(), secrets={"API_KEY": "value"})
provider.put_bundle(update, mode="merge")
```

## Secret Injection

Run commands with secrets as environment variables (never in CLI args):

```bash
python -m lib.creds run -- make deploy
python -m lib.creds run -- ansible-playbook deploy.yaml
```

## Usage Patterns

### Getting Database Credentials

```python
from lib.creds import get_credentials

creds = get_credentials()  # Auto-detect provider
print(creds.connection_string)  # postgresql://user:****@host:5432/db
conn = await asyncpg.connect(**creds.dsn)  # dsn has real password
```

### Masking Output

```python
from lib.creds import mask_output
safe = mask_output("password=secret123")  # "password=****"
```

## Commands

| Command | Purpose |
|---------|---------|
| `/secrets:get [id]` | Get credentials (masked output) |
| `/secrets:set KEY VALUE` | Set or update a secret |
| `/secrets:list` | List all secret keys (masked) |
| `/secrets:run -- CMD` | Run command with secrets injected |
| `/secrets:validate` | Test credential configuration |
| `/secrets:ui` | Launch web UI for management |
| `/secrets:rotate KEY` | Rotate a secret value |
| `/secrets:help` | Overview of all commands |

## CLI Usage

```bash
PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"
python3 -m lib.creds <command> [options]
```

## Best Practices

1. **Store secrets in global config, not repo** - Use `creds set`
2. **Use get_credentials() helper** - Handles provider detection
3. **Inject with `creds run`** - Never pass secrets as CLI args
4. **Launch UI for bulk management** - `creds ui`
5. **Audit log tracks all actions** - `~/.config/claude-power-pack/audit.log`

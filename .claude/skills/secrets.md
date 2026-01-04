---
name: Secrets Management
description: Secure credential access with provider abstraction and masking
trigger: secrets, credentials, database password, api key, aws secrets, environment variables, .env, get credentials, connection string
---

# Secrets Management Skill

When the user asks about accessing secrets, credentials, or database connections, follow these security principles and patterns.

## Security Rules (CRITICAL)

1. **NEVER log or display actual secret values**
2. **ALWAYS use masked representations** in output
3. **Use `SecretValue` wrapper** for any sensitive data
4. **Validate credentials without exposing them**
5. **Default to READ_ONLY** database access

## Provider Priority

The secrets module auto-detects providers in this order:

1. **Environment variables** (fastest, for local dev)
   - Looks for `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
   - Or `{PREFIX}_*` pattern for other secrets
   - Always available

2. **AWS Secrets Manager** (for production)
   - Requires `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
   - Or IAM role if running on AWS infrastructure
   - Secret ID can be name or ARN

## Usage Patterns

### Getting Database Credentials

```python
from lib.creds import get_credentials

# Auto-detect provider and get credentials
creds = get_credentials()  # Uses DB_* env vars or AWS

# Display is always masked
print(creds)
# DatabaseCredentials(host='localhost', port=5432, database='myapp',
#                     username='appuser', password=SecretValue('****'))

print(creds.connection_string)
# postgresql://appuser:****@localhost:5432/myapp

# For actual database connection (use sparingly):
import asyncpg
conn = await asyncpg.connect(**creds.dsn)  # dsn contains real password
```

### Using Explicit Provider

```python
from lib.creds.providers import AWSSecretsProvider, EnvSecretsProvider

# Force AWS
aws = AWSSecretsProvider(region="us-east-1")
if aws.is_available():
    creds = get_credentials("prod/database", provider=aws)

# Force environment
env = EnvSecretsProvider()
creds = get_credentials("DB", provider=env)
```

### Masking Output

```python
from lib.creds import mask_output, register_secret

# Mask known patterns
safe = mask_output("password=secret123")  # "password=****"

# Register custom secrets
api_key = os.getenv("MY_API_KEY")
register_secret(api_key)  # Now masked everywhere
```

## Database Access Levels

| Level | Operations | Use Case |
|-------|------------|----------|
| `READ_ONLY` | SELECT only | Development queries (DEFAULT) |
| `READ_WRITE` | SELECT, INSERT, UPDATE | Data modification |
| `ADMIN` | All including DELETE/DROP | Schema changes |

### Permission Checking

```python
from lib.creds import PermissionConfig, AccessLevel, OperationType

# Default: read-only
config = PermissionConfig()

allowed, reason = config.can_execute(OperationType.SELECT, "users")
# (True, "Allowed")

allowed, reason = config.can_execute(OperationType.DELETE, "users")
# (False, "Operation delete requires admin access")

# Upgrade when needed
config = PermissionConfig(access_level=AccessLevel.READ_WRITE)
```

## Bash Scripts

For non-Python workflows:

```bash
# Get credentials (masked output)
~/.claude/scripts/secrets-get.sh

# Validate configuration
~/.claude/scripts/secrets-validate.sh --db

# Mask sensitive output
some_command | ~/.claude/scripts/secrets-mask.sh
```

## Commands

- `/secrets:get [secret_id]` - Get and display credentials (masked)
- `/secrets:validate` - Test credential configuration

## Best Practices

1. **Store secrets in providers, not code** - Use env vars or AWS
2. **Use get_credentials() helper** - Handles provider detection
3. **Check permissions before writes** - Use PermissionConfig
4. **Mask all output** - Use connection_string, not connection_string_real
5. **Clear cache after rotation** - Call `provider.clear_cache()`

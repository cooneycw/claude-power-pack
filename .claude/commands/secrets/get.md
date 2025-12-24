---
description: Get credentials securely with masking
allowed-tools: Bash(python:*), Bash(PYTHONPATH=*), Read(*.py), Read(*.env)
---

# Get Credentials

Retrieve credentials from the configured provider with automatic masking.

## Usage

```
/secrets:get [secret_id] [--provider aws|env] [--json]
```

## Arguments

- `secret_id` - Secret identifier (default: "DB")
  - For env provider: variable prefix (e.g., "DB" looks for DB_HOST, etc.)
  - For AWS: secret name or ARN
- `--provider` - Force specific provider (aws or env)
- `--json` - Output as JSON (masked)

## Process

1. Detect available provider (env first, then AWS)
2. Retrieve credentials using the secrets module
3. Display masked summary (never shows real passwords)
4. Optionally output as JSON for scripting

## Example Output

```
Provider: env-file
Secret ID: DB

Host: localhost
Port: 5432
Database: myapp_dev
Username: developer
Password: ****

Connection String: postgresql://developer:****@localhost:5432/myapp_dev
```

## Security Notes

- Actual secret values are NEVER displayed
- Connection strings show `****` for passwords
- Use the Python API for actual connections:
  ```python
  creds = get_credentials()
  conn = await asyncpg.connect(**creds.dsn)  # dsn has real password
  ```

## Run Command

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python -m lib.secrets get "$@"
```

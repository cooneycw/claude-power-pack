---
description: Validate credentials without exposing them
allowed-tools: Bash(python:*), Bash(PYTHONPATH=*), Bash(aws:*), Bash(psql:*)
---

# Validate Credentials

Test that credentials are configured and accessible without displaying actual values.

## Usage

```
/secrets:validate [--env] [--aws] [--db]
```

## Options

- `--env` - Validate environment variables (DB_HOST, DB_USER, etc.)
- `--aws` - Validate AWS credentials (test sts:GetCallerIdentity)
- `--db` - Test database connection
- (default) - Run all validations

## Checks Performed

### Environment (--env)
- DB_HOST is set
- DB_USER is set
- DB_PASSWORD is set (shown as ****)
- DB_NAME is set
- .env file exists

### AWS (--aws)
- AWS_ACCESS_KEY_ID is set (shows first 4 chars)
- AWS_SECRET_ACCESS_KEY is set (shown as ****)
- AWS_DEFAULT_REGION is set
- Credentials are valid (via aws sts get-caller-identity)

### Database (--db)
- Credentials load successfully
- PostgreSQL connection works (if psql available)

## Example Output

```
=== Environment Variables ===

✓ DB_HOST is set: localhost
✓ DB_USER is set: developer
✓ DB_PASSWORD is set: ****
✓ DB_NAME is set: myapp_dev
✓ .env file exists

=== AWS Credentials ===

✓ AWS_ACCESS_KEY_ID is set: AKIA...
✓ AWS_SECRET_ACCESS_KEY is set: ****
✓ AWS_DEFAULT_REGION: us-east-1
✓ AWS credentials valid: arn:aws:iam::123456789:user/developer

=== Database Connection ===

✓ Credentials loaded: postgresql://developer:****@localhost:5432/myapp_dev
✓ Database connection successful
```

## Run Command

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python -m lib.secrets validate "$@"
```

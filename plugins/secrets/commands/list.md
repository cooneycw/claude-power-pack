# List Secrets

List all secret keys for the current project (values masked).

## Arguments

- `PROJECT` (optional): Override auto-detected project ID

## Instructions

When the user invokes `/secrets:list`, run:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds list
```

With project override:
```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds list --project "$PROJECT"
```

Report the result showing key names with masked values.

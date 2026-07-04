# Set a Secret

Set or update a secret value in the project's global config store.

## Arguments

- `KEY` (required): Secret key name (e.g., `DB_PASSWORD`, `API_KEY`)
- `VALUE` (required): Secret value

## Instructions

When the user invokes `/secrets:set KEY VALUE`, run:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds set "$KEY" "$VALUE"
```

If `--project` is specified, add it:
```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds set "$KEY" "$VALUE" --project "$PROJECT"
```

**IMPORTANT:** Never echo or display the secret value in output. Only confirm the key name was set.

Report the result to the user.

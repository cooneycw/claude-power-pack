# Delete a Secret

Remove a secret key from the project's store. Logs the deletion
to the audit log (never the value).

## Arguments

- `KEY` (required): Secret key name to delete (e.g., `DB_PASSWORD`)

## Instructions

When the user invokes `/secrets:delete KEY`, run:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds delete "$KEY" --force
```

If `--project` is specified, add it:
```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds delete "$KEY" --force --project "$PROJECT"
```

**Note:** `--force` skips the interactive confirmation prompt since Claude Code is non-interactive.

**IMPORTANT:** Never echo or display secret values in output. Only confirm the key name was deleted.

Report the result to the user.

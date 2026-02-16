# Rotate a Secret

Update an existing secret with a new value. Logs the rotation action
to the audit log (never the value).

## Arguments

- `KEY` (required): Secret key to rotate
- `VALUE` (optional): New value (prompts interactively if not provided)

## Instructions

When the user invokes `/secrets:rotate KEY [VALUE]`, run:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds rotate "$KEY" "$VALUE"
```

Without value (interactive prompt):
```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds rotate "$KEY"
```

**IMPORTANT:** Never echo or display the secret value in output.

Report the rotation result to the user.

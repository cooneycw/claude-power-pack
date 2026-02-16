# Run with Secrets

Execute a command with project secrets injected as environment variables.
Secrets never appear in CLI arguments, logs, or output.

## Arguments

- `COMMAND` (required): The command to run (after --)

## Instructions

When the user invokes `/secrets:run -- COMMAND`, run:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds run -- $COMMAND
```

With provider override:
```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds run --provider aws -- $COMMAND
```

**IMPORTANT:**
- Never display secret values in output
- Secrets are injected as environment variables in the subprocess only
- The parent process environment is not modified

Report the command exit code.

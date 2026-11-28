# Secrets Commands

Overview of all secrets management commands.

## Instructions

Display the following help information:

```
Secrets Management Commands

  /secrets:get [ID]        Get credentials (masked output)
  /secrets:set KEY VALUE   Set or update a secret value
  /secrets:delete KEY      Delete a secret key (with confirmation)
  /secrets:list            List all secret keys (values masked)
  /secrets:run -- CMD      Run command with secrets injected as env vars
  /secrets:validate        Validate credential configuration
  /secrets:ui              Launch web UI for secrets management
  /secrets:rotate KEY      Rotate a secret value
  /secrets:help            This help message

Providers:
  dotenv-global: local plaintext .env bundles outside the repository
  env-file: environment variables and project .env files (legacy get)
  AWS Secrets Manager: optional; requires boto3 and configured AWS credentials

Local storage:
  Files are plaintext, not encrypted. Output masking does not encrypt storage.
  The default dotenv-global provider enforces file mode 0600 and directory 0700.
  Selection depends on the command; local set/delete/rotate use dotenv-global.

CLI Usage:
  PYTHONPATH="$HOME/Projects/claude-power-pack:$PYTHONPATH"
  uv run --project "$HOME/Projects/claude-power-pack" python -m lib.creds <command> [options]

Configuration:
  Project-level: .claude/secrets.yml
  Audit log:     ${XDG_CONFIG_HOME:-~/.config}/claude-power-pack/audit.log
  Secret store:  ${XDG_CONFIG_HOME:-~/.config}/claude-power-pack/secrets/{project_id}/.env
```

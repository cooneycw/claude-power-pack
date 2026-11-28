# Secrets Commands

## Instructions

Display:

```
Secrets Management Commands

  /secrets:get [ID]        Get credentials (masked)
  /secrets:set KEY VALUE   Set/update a secret
  /secrets:delete KEY      Delete key (with confirmation)
  /secrets:list            List keys (masked)
  /secrets:run -- CMD      Run command with secrets injected as env vars
  /secrets:validate        Validate credential configuration
  /secrets:ui              Launch secrets UI
  /secrets:rotate KEY      Rotate a secret value
  /secrets:help            Help

Providers:
  dotenv-global: plaintext .env bundles outside the repository
  env-file: environment variables/project .env files (legacy get)
  AWS Secrets Manager: optional; requires boto3 and AWS credentials

Local storage:
  Plaintext, not encrypted; masking only hides output.
  Default dotenv-global enforces file mode 0600 and directory 0700.
  Local set/delete/rotate use dotenv-global; other commands select independently.

CLI Usage:
  PYTHONPATH="$HOME/Projects/claude-power-pack:$PYTHONPATH"
  uv run --project "$HOME/Projects/claude-power-pack" python -m lib.creds <command> [options]

Configuration:
  Project-level: .claude/secrets.yml
  Audit log:     ${XDG_CONFIG_HOME:-~/.config}/claude-power-pack/audit.log
  Secret store:  ${XDG_CONFIG_HOME:-~/.config}/claude-power-pack/secrets/{project_id}/.env
```

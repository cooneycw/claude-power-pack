# `setup-woodpecker-cli` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `setup-woodpecker-cli`

- setup-woodpecker-cli - installs the Woodpecker CLI when missing, fetches credentials from AWS Secrets Manager and creates a `woodpecker-cli` context for the default server. It exists because the token lives in an AWS secret rather than a shell profile, which is the gap that made `flow-ci-status.sh`'s predecessor improvise a `curl` lookup gated on an env var that was usually unset (#516)

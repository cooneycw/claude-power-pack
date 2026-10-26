# Woodpecker deployment and persistent identity

The server and Docker agent pins in this directory are Woodpecker 3.19.0,
matching the operator's fleet upgrade reported in [#1572](https://github.com/cooneycw/claude-power-pack/issues/1572).
`bootstrap-agent-host.sh` uses the same agent image digest. Changing these
repository files does not deploy them or verify a running host.

## Agent identity

`docker-compose.agent.yml` already persists `./agent-config:/etc/woodpecker`
and requires `WOODPECKER_HOSTNAME` and `WOODPECKER_AGENT_LABELS` in a host-local,
gitignored `.env` file. This interface was committed in
`fb588389` ([#1553](https://github.com/cooneycw/claude-power-pack/pull/1553), fixing #1551).
Choose a stable name and labels for each host; do not copy another host's
identity or replace the mandatory variables with repository-wide literals.
`agent.env` supplies `WOODPECKER_SERVER` (the gRPC endpoint) and
`WOODPECKER_AGENT_SECRET`.

Keep the same `agent-config` directory when recreating the container: its
`agent.conf` holds the server-assigned ID. A plain `docker run` deployment
likewise needs a durable host directory mounted at `/etc/woodpecker` and a
stable `WOODPECKER_HOSTNAME`. Do not delete that directory as container cleanup.

The operator [reported](https://github.com/cooneycw/claude-power-pack/issues/1572#issuecomment-6406071352)
that hosts 119 and 131 now write `agent.conf` and each retained its ID across
one restart. This is reported host evidence, not a measurement made by the
repository checks. Pruning their stale server records remains operator work;
identify the current connected IDs before removing older records.

## Server gRPC signing secret

`WOODPECKER_GRPC_SECRET` signs agent connection tokens. It is distinct from
`WOODPECKER_AGENT_SECRET`, which authenticates agents. Keep the agent secret
unchanged while persisting the signing secret. Woodpecker 3.19 generates a
temporary signing secret when none is configured; it changes on every server
start and causes agents to reauthenticate. Rotation also invalidates existing
tokens; it does not by itself require agents to restart or change their ID.
See [upstream 3.19 configuration](https://github.com/woodpecker-ci/woodpecker/blob/v3.19.0/docs/versioned_docs/version-3.19/30-administration/10-configuration/10-server.md#grpc_secret).

The server compose loads the gitignored `docker.env`. Store one signing secret
durably in a protected host file or secret manager and keep the **same**
value in `docker.env` across server starts. Protect both files with mode
0600 and the containing directory with permissions appropriate to the server
operator. Never print their contents, enable shell tracing, pass secret values
on command arguments, or commit them.

**Regeneration behavior:** `bootstrap-secrets.py` preserves an existing nonempty
`WOODPECKER_GRPC_SECRET` assignment in `docker.env`, even when AWS supplies a
different value. An empty, duplicate, or malformed local assignment fails before
replacing the file. Logical quoted assignments are read as units so assignment-like
text inside a multiline neighbouring value cannot supply the signing key.
Literal single-quoted tokens and double-quoted tokens without interpolation
retain their quoting; unquoted or double-quoted dollar expressions are refused
before replacement because their dependencies would not survive regeneration.
Multiline signing values and mixed quote syntax are also refused.

If the key is absent locally, a nonempty value from the
named AWS secret supplies it; absent or empty AWS values leave it unset. The
generator accepts AWS signing values only from the literal-safe alphabet
`A-Z a-z 0-9 . _ ~ + / = -` (including the generated hex format); other values
fail before replacement rather than being silently interpolated, unquoted, or
cut at a comment. The generator never generates a signing key or falls back
to a literal. Only this
local key survives regeneration; other keys come from AWS. Validation and writes
use a protected temporary file and atomic replacement, so a failed regeneration
does not truncate the previous file. The shipped template has the same behavior;
its `--keys` controls AWS imports (the default includes the signing key), while
an existing signing key is preserved regardless of that option.

Store the signing key in the operator-owned secret manager as well as the local
file so a replacement host can recover the same value. To rotate it, explicitly
update the durable source and local assignment together; changing AWS alone
intentionally does not silently rotate the existing local key. Existing older
copies of the generator still drop this key; deploy the updated script before
relying on preservation in boot automation.

For an existing deployment, first retain and securely back up its current
signing key. Use the updated generator to preserve the local assignment,
including one with leading whitespace. Do not generate a replacement key or
manually reconstruct `docker.env` during routine regeneration. Recovering a
missing file should use the same value from the durable secret manager.

For initial provisioning only, when no signing key exists in either the local
file or the durable source, an operator can create a protected random 32-byte
key file without displaying it:

```sh
set +x
(umask 077; set -C; openssl rand -hex 32 > grpc-signing-key.env)
```

The exclusive redirection refuses to overwrite an existing key file. Keep this
file protected and outside version control (`*.env` is ignored here). Import
its value into the named AWS secret's `WOODPECKER_GRPC_SECRET` field using a
secret manager's secure file-input facility or a protected editor; do not pass
the value on command arguments or print it. The repository bootstrap uses the
`essent-ai` AWS secret; the distributed template uses its `--secret-name`.
Then run the updated bootstrap to write `docker.env` atomically. No independent
runbook parser or in-place rewrite is needed. If the source has not been set,
the generator deliberately leaves the key absent; provision it before starting
the server. Securely retain the key in the durable secret manager for recovery.

Install the updated generator in the operator-owned boot sequence and retain
the generated `docker.env` across restarts; restore from the durable source
before starting a replacement host. Then verify the setting is present without printing its value,
restart during an approved maintenance window, and check that the server no
longer warns about a temporary gRPC secret and that agents reconnect with their
existing IDs. These live checks and durable secret configuration are operator
follow-ups; repository tests do not establish them.

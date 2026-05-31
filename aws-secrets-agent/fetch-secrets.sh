#!/bin/sh
set -e

# Resolve secrets from the aws-secrets-agent sidecar, then exec the server.
#
# Security posture: FAIL CLOSED. When a secret is required (AWS_SECRET_NAME is
# set) and the fetch or parse fails, this script exits non-zero instead of
# starting a keyless server. A keyless server still passes a liveness ("/")
# healthcheck, which lets "docker compose up --wait" tear down the known-good
# container and route to the broken one (issue #346 "killer chain").
#
# For local development ONLY, set ALLOW_ENV_FALLBACK=true to restore the old
# behaviour of starting with whatever env_file variables happen to be present.
#
# Tunables (all optional):
#   SECRETS_AGENT_URL            sidecar base URL (default http://aws-secrets-agent:2773)
#   AWS_SECRET_NAME              secret to fetch; unset = local dev passthrough
#   AWS_TOKEN                    SSRF protection token (default default-token)
#   SECRETS_FETCH_MAX_RETRIES    fetch attempts before giving up (default 30)
#   SECRETS_FETCH_RETRY_INTERVAL seconds between attempts (default 2)
#   ALLOW_ENV_FALLBACK           true = start anyway on fetch/parse failure (dev only)
#   REQUIRED_SECRET_KEYS         space-separated keys that must be present + non-empty

AGENT_URL="${SECRETS_AGENT_URL:-http://aws-secrets-agent:2773}"
SECRET_ID="${AWS_SECRET_NAME:-}"
TOKEN="${AWS_TOKEN:-default-token}"
MAX_RETRIES="${SECRETS_FETCH_MAX_RETRIES:-30}"
RETRY_INTERVAL="${SECRETS_FETCH_RETRY_INTERVAL:-2}"
ALLOW_ENV_FALLBACK="${ALLOW_ENV_FALLBACK:-false}"
REQUIRED_SECRET_KEYS="${REQUIRED_SECRET_KEYS:-}"

# Start with whatever env_file variables exist. Only reached on the local-dev
# passthrough or the explicit ALLOW_ENV_FALLBACK opt-in.
start_with_env_fallback() {
    echo "WARNING: starting with env_file variables only - server may be keyless (LOCAL DEV)" >&2
    exec "$@"
}

if [ -z "$SECRET_ID" ]; then
    echo "INFO: AWS_SECRET_NAME not set - using env_file variables (local dev mode)"
    exec "$@"
fi

ERR_FILE="${TMPDIR:-/tmp}/fetch-secrets-err.$$"
i=0
RESPONSE=""
while [ "$i" -lt "$MAX_RETRIES" ]; do
    if RESPONSE=$(python3 -c "
import urllib.request, sys
req = urllib.request.Request(
    '${AGENT_URL}/secretsmanager/get?secretId=${SECRET_ID}',
    headers={'X-Aws-Parameters-Secrets-Token': '${TOKEN}'}
)
try:
    resp = urllib.request.urlopen(req, timeout=5)
    sys.stdout.write(resp.read().decode())
except Exception as exc:
    sys.stderr.write('%s: %s' % (type(exc).__name__, exc))
    sys.exit(1)
" 2>"$ERR_FILE"); then
        break
    fi
    RESPONSE=""
    i=$((i + 1))
    sleep "$RETRY_INTERVAL"
done

if [ -z "$RESPONSE" ]; then
    echo "ERROR: failed to fetch secret '${SECRET_ID}' from ${AGENT_URL} after ${MAX_RETRIES} attempts" >&2
    if [ -s "$ERR_FILE" ]; then
        echo "ERROR: last fetch error: $(cat "$ERR_FILE")" >&2
    fi
    rm -f "$ERR_FILE"
    if [ "$ALLOW_ENV_FALLBACK" = "true" ]; then
        echo "WARNING: ALLOW_ENV_FALLBACK=true - ignoring secret fetch failure" >&2
        start_with_env_fallback "$@"
    fi
    echo "FATAL: refusing to start without required secret '${SECRET_ID}' (set ALLOW_ENV_FALLBACK=true to override for local dev)" >&2
    exit 1
fi
rm -f "$ERR_FILE"

SECRET_EXPORTS=$(echo "$RESPONSE" | python3 -c "
import sys, json, re
try:
    data = json.load(sys.stdin)
    secrets = json.loads(data['SecretString'])
except Exception as exc:
    sys.stderr.write('parse error: %s: %s' % (type(exc).__name__, exc))
    sys.exit(1)
for k, v in secrets.items():
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', k):
        print(f'echo \"WARNING: skipping invalid key: {k}\" >&2', flush=True)
        continue
    safe_v = v.replace(\"'\", \"'\\\\''\" )
    print(f\"export {k}='{safe_v}'\")
") || {
    echo "FATAL: failed to parse secret payload for '${SECRET_ID}'" >&2
    if [ "$ALLOW_ENV_FALLBACK" = "true" ]; then
        echo "WARNING: ALLOW_ENV_FALLBACK=true - ignoring secret parse failure" >&2
        start_with_env_fallback "$@"
    fi
    exit 1
}
eval "$SECRET_EXPORTS"

# Fail closed if any explicitly-required key is missing or empty after load.
if [ -n "$REQUIRED_SECRET_KEYS" ]; then
    missing=""
    for key in $REQUIRED_SECRET_KEYS; do
        eval "value=\${$key:-}"
        if [ -z "$value" ]; then
            missing="$missing $key"
        fi
    done
    if [ -n "$missing" ]; then
        echo "FATAL: required secret keys missing or empty after fetch:${missing}" >&2
        exit 1
    fi
fi

echo "INFO: Loaded secrets from AWS Secrets Manager (${SECRET_ID})"
exec "$@"

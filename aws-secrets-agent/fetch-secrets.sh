#!/bin/sh
set -e

AGENT_URL="${SECRETS_AGENT_URL:-http://aws-secrets-agent:2773}"
SECRET_ID="${AWS_SECRET_NAME:-}"
TOKEN="${AWS_TOKEN:-default-token}"
MAX_RETRIES=30
RETRY_INTERVAL=2

if [ -z "$SECRET_ID" ]; then
    echo "INFO: AWS_SECRET_NAME not set - using env_file variables (local dev mode)"
    exec "$@"
fi

i=0
RESPONSE=""
while [ "$i" -lt "$MAX_RETRIES" ]; do
    RESPONSE=$(python3 -c "
import urllib.request, sys
req = urllib.request.Request(
    '${AGENT_URL}/secretsmanager/get?secretId=${SECRET_ID}',
    headers={'X-Aws-Parameters-Secrets-Token': '${TOKEN}'}
)
try:
    resp = urllib.request.urlopen(req, timeout=5)
    sys.stdout.write(resp.read().decode())
except Exception:
    sys.exit(1)
" 2>/dev/null) && break
    i=$((i + 1))
    sleep "$RETRY_INTERVAL"
done

if [ -z "$RESPONSE" ]; then
    echo "WARNING: Failed to fetch secrets from agent after ${MAX_RETRIES} retries" >&2
    echo "WARNING: Falling back to env_file variables (if present)" >&2
    exec "$@"
fi

eval "$(echo "$RESPONSE" | python3 -c "
import sys, json, re
data = json.load(sys.stdin)
secrets = json.loads(data['SecretString'])
for k, v in secrets.items():
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', k):
        print(f'echo \"WARNING: skipping invalid key: {k}\" >&2', flush=True)
        continue
    safe_v = v.replace(\"'\", \"'\\\\''\" )
    print(f\"export {k}='{safe_v}'\")
")"

echo "INFO: Loaded secrets from AWS Secrets Manager (${SECRET_ID})"
exec "$@"

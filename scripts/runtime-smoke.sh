#!/bin/sh
# Claude Power Pack - runtime smoke test (driven from .woodpecker.yml).
#
# Logic lives in this script file rather than inline in .woodpecker.yml because
# Woodpecker mangles nested quotes in inline commands. Run it from a step that
# has the Docker socket mounted, after installing curl + docker-cli-compose and
# running scripts/ci-docker-login.sh (so base-image pulls are authenticated).
#
# It does three things:
#   1. Brings the stack up and checks readiness on each MCP server (/readyz -
#      the same endpoint the `--wait` gate uses). The secrets-agent is
#      internal-only (expose, not ports); it is checked for liveness (/ping)
#      from inside its container and asserted to have NO published host port.
#      MCP servers run keyless (empty secret names); dummy keys are injected via
#      the compose env passthrough purely so /readyz reports ready.
#   2. Cross-container reachability: from a SEPARATE container, hits the agent at
#      http://aws-secrets-agent:2773. The internal /ping curls localhost and
#      would pass even if the 0.0.0.0 bind regressed, so this is the only check
#      that proves another container can actually reach it. (issue #350)
#   3. Client secret-fetch path: stands up a hermetic fake agent and runs the
#      REAL fetch-secrets.sh (in the real mcp-second-opinion image) against it
#      with a NON-EMPTY AWS_SECRET_NAME, proving the CLIENT's fetch -> parse ->
#      export works end-to-end without production AWS credentials. (issue #350)
#   4. REAL-agent secret fetch: seeds a secret into a LocalStack Secrets Manager,
#      points the REAL aws-secrets-agent binary at LocalStack (AWS_ENDPOINT_URL),
#      and runs the REAL fetch-secrets.sh THROUGH that agent. This closes the
#      gap left by (3): the real binary actually performs an AWS SDK
#      GetSecretValue and a consumer receives the result - still no production
#      AWS credentials. (issue #377)
set -eu

PROJECT="cpp-smoke-${CI_PIPELINE_NUMBER:-local}"

# Keep smoke runs independent from real developer stacks and real AWS secrets.
# The prefix gives every container a project-unique name so a smoke run never
# collides with a real stack (which uses the empty-prefix default names).
export CPP_CONTAINER_PREFIX="cpp-smoke-${CI_PIPELINE_NUMBER:-local}-"
export AWS_ACCESS_KEY_ID=cpp-smoke-access-key
export AWS_SECRET_ACCESS_KEY=cpp-smoke-secret-key
export AWS_SESSION_TOKEN=cpp-smoke-session-token
export AWS_TOKEN=cpp-smoke-token
export MCP_SECOND_OPINION_PORT_MAPPING=8080
export MCP_PLAYWRIGHT_PORT_MAPPING=8081
export MCP_NANO_BANANA_PORT_MAPPING=8084
export SECOND_OPINION_AWS_SECRET_NAME=

# The fake AWS creds above mean the real secrets-agent cannot fetch, so the
# secret-consuming servers start in local-dev (keyless) mode. Inject dummy keys
# through the compose env passthrough so /readyz reports ready and the `--wait`
# readiness gate can succeed. These are never used to call a provider - /readyz
# only checks that config is present.
export GEMINI_API_KEY=cpp-smoke-gemini-key

# Compose invocation that includes the CI-only smoke override (fake agent +
# fetch-probe, both under the "smoke" profile).
SMOKE_FILES="-f docker-compose.yml -f docker-compose.smoke.yml"

cleanup() {
  docker compose -p "$PROJECT" $SMOKE_FILES \
    --profile core --profile browser --profile cicd --profile smoke down -v || true
}
trap cleanup EXIT INT TERM

if ! docker compose -p "$PROJECT" --profile core --profile browser --profile cicd up --build --wait; then
  docker compose -p "$PROJECT" --profile core --profile browser --profile cicd ps || true
  docker compose -p "$PROJECT" logs aws-secrets-agent || true
  exit 1
fi
docker compose -p "$PROJECT" --profile core --profile browser --profile cicd ps

# Retry an in-container readiness probe up to PROBE_RETRIES times (PROBE_INTERVAL
# seconds apart) before giving up. A service can pass the compose `--wait`
# readiness gate yet briefly refuse a fresh in-container connection (restart
# backoff, keep-alive churn), so a single refused connection is a transient race,
# not a real failure. Bounded retries absorb that race instead of hard-failing
# the build on the first refusal. On exhaustion, dump actionable diagnostics
# (compose ps + the failing service's recent logs + one stderr-visible probe
# attempt) instead of an opaque exit code, then exit 1. (issue #375)
PROBE_RETRIES=10
PROBE_INTERVAL=3
probe_until_ok() {
  service="$1"
  shift

  attempt=1
  while [ "$attempt" -le "$PROBE_RETRIES" ]; do
    if "$@" >/dev/null 2>&1; then
      return 0
    fi
    if [ "$attempt" -lt "$PROBE_RETRIES" ]; then
      echo "  probe $service: attempt $attempt/$PROBE_RETRIES refused, retrying in ${PROBE_INTERVAL}s ..."
      sleep "$PROBE_INTERVAL"
    fi
    attempt=$((attempt + 1))
  done

  echo "ERROR: $service probe still failing after $PROBE_RETRIES attempts; diagnostics follow:" >&2
  docker compose -p "$PROJECT" ps || true
  docker compose -p "$PROJECT" logs --tail 50 "$service" || true
  echo "--- final probe attempt (stderr visible) ---" >&2
  "$@" || true
  exit 1
}

check_http() {
  service="$1"
  container_port="$2"
  check_path="$3"

  published="$(docker compose -p "$PROJECT" port "$service" "$container_port" | awk -F: 'END {print $NF}')"
  if [ -z "$published" ]; then
    echo "ERROR: no published port for $service:$container_port"
    exit 1
  fi

  # Woodpecker runs this step inside a Docker job container, so host published
  # ports are not reachable via 127.0.0.1 from here. Assert the service HTTP
  # endpoint from inside the service container, then report the published host
  # port to confirm the CI-only random port mapping exists and cannot collide
  # with a workstation stack. The probe is retried (see probe_until_ok) to
  # tolerate a transient post-`--wait` connection refusal.
  url="http://127.0.0.1:$container_port$check_path"
  py="import urllib.request; urllib.request.urlopen('$url', timeout=10)"
  probe_until_ok "$service" \
    docker compose -p "$PROJECT" exec -T "$service" python -c "$py"
  echo "OK: $service:$container_port$check_path via host port $published"
}

# The secrets agent is internal-only (expose, not ports). Confirm it has NO
# published host port, then probe /ping from inside the container.
check_internal_http() {
  service="$1"
  container_port="$2"
  check_path="$3"
  header="$4"

  # `docker compose port` prints port 0 (e.g. ":0") for an unpublished mapping
  # rather than empty output, so treat empty or 0 as "not published" and
  # anything else as a real host binding.
  published="$(docker compose -p "$PROJECT" port "$service" "$container_port" 2>/dev/null | awk -F: 'END {print $NF}')"
  if [ -n "$published" ] && [ "$published" != "0" ]; then
    echo "ERROR: $service:$container_port must not be published to the host (found $published)"
    exit 1
  fi

  # Probe is retried (see probe_until_ok) to tolerate a transient
  # post-`--wait` connection refusal from inside the container.
  url="http://127.0.0.1:$container_port$check_path"
  probe_until_ok "$service" \
    docker compose -p "$PROJECT" exec -T "$service" \
    curl -sf -H "$header" --max-time 10 "$url"
  echo "OK (internal only): $service:$container_port$check_path"
}

# aws-secrets-agent is internal-only and exposes only liveness (/ping). Every
# MCP server is probed on /readyz - the same endpoint the compose `--wait` gate
# uses - so the smoke fails if a server comes up live-but-not-ready.
check_internal_http aws-secrets-agent 2773 /ping "X-Aws-Parameters-Secrets-Token: $AWS_TOKEN"
check_http mcp-second-opinion 8080 /readyz
check_http mcp-playwright-persistent 8081 /readyz
check_http mcp-nano-banana 8084 /readyz

# --- (2) Cross-container reachability of the REAL agent ---------------------
# Reach the agent by its compose network name from a different container. The
# internal /ping above curls localhost inside the agent, so it cannot detect a
# regressed 0.0.0.0 bind; this can.
echo "Cross-container check: mcp-second-opinion -> http://aws-secrets-agent:2773/ping ..."
docker compose -p "$PROJECT" exec -T mcp-second-opinion python -c "
import os, urllib.request
req = urllib.request.Request(
    'http://aws-secrets-agent:2773/ping',
    headers={'X-Aws-Parameters-Secrets-Token': os.environ.get('AWS_TOKEN', 'default-token')},
)
urllib.request.urlopen(req, timeout=10)
"
echo "OK: aws-secrets-agent reachable from a separate container (0.0.0.0 bind verified)"

# --- (3) Real secret fetch/parse/export path via the hermetic fake agent ----
echo "Secret-fetch check: starting fake-secrets-agent ..."
docker compose -p "$PROJECT" $SMOKE_FILES up -d --build --wait fake-secrets-agent

echo "Secret-fetch check: running real fetch-secrets.sh against fake agent ..."
PROBE_OUT="$(docker compose -p "$PROJECT" $SMOKE_FILES run --rm --no-deps fetch-probe)"
echo "fetch-probe output: $PROBE_OUT"
case "$PROBE_OUT" in
  *FETCHED:loaded-via-agent*)
    echo "OK: real secret fetch/parse/export path verified (non-empty AWS_SECRET_NAME)" ;;
  *)
    echo "ERROR: secret-fetch path did not export the expected secret." >&2
    echo "ERROR: fetch-secrets.sh fell back to local-dev mode or failed to parse." >&2
    exit 1 ;;
esac

# --- (4) REAL agent serving a real Secrets Manager fetch (issue #377) --------
# Stage (3) proves the CLIENT, but against a fake server. This drives a secret
# through the REAL agent binary: seed it into LocalStack, point the real agent
# at LocalStack, then fetch THROUGH the real agent with the real fetch-secrets.sh.
REAL_SECRET_ID="cpp/smoke/real"
REAL_SENTINEL="loaded-via-real-agent"

echo "Real-agent check: starting LocalStack Secrets Manager ..."
docker compose -p "$PROJECT" $SMOKE_FILES up -d --wait localstack

echo "Real-agent check: seeding secret '${REAL_SECRET_ID}' into LocalStack ..."
# awslocal ships in the LocalStack image and targets the in-container endpoint.
# The sentinel differs from stage (3) so this assertion cannot pass on the fake.
docker compose -p "$PROJECT" $SMOKE_FILES exec -T localstack \
  awslocal secretsmanager create-secret \
    --name "$REAL_SECRET_ID" \
    --secret-string '{"CPP_SMOKE_SENTINEL":"loaded-via-real-agent","OPENAI_API_KEY":"sk-cpp-smoke-real","ANTHROPIC_API_KEY":"sk-ant-cpp-smoke-real"}' \
    --region us-east-1 >/dev/null

echo "Real-agent check: starting the REAL aws-secrets-agent against LocalStack ..."
# No --build: reuse the agent image already built by the stage-1 `up --build`.
docker compose -p "$PROJECT" $SMOKE_FILES up -d --wait real-secrets-agent

echo "Real-agent check: fetching '${REAL_SECRET_ID}' THROUGH the real agent ..."
REAL_PROBE_OUT="$(docker compose -p "$PROJECT" $SMOKE_FILES run --rm --no-deps real-fetch-probe)"
echo "real-fetch-probe output: $REAL_PROBE_OUT"
case "$REAL_PROBE_OUT" in
  *FETCHED:${REAL_SENTINEL}*)
    echo "OK: REAL agent served a real Secrets Manager fetch and a consumer received it" ;;
  *)
    echo "ERROR: real-agent fetch path did not export the expected secret." >&2
    echo "ERROR: the real agent failed to fetch from LocalStack, or fetch-secrets.sh failed to parse/export." >&2
    docker compose -p "$PROJECT" $SMOKE_FILES logs real-secrets-agent localstack || true
    exit 1 ;;
esac

echo "Runtime smoke complete."

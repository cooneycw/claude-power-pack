#!/usr/bin/env bash
# Strict deploy-time environment preflight for Docker production refreshes.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROFILE_VALUE="${PROFILE:-core}"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

usage() {
  cat <<'USAGE'
Usage: scripts/assert-prod-env.sh [--profiles "core browser cicd"] [--env-file .env]

Checks:
  - AWS credentials and AWS_TOKEN are present for sidecar profiles
  - AWS_TOKEN is never the insecure default token for deploys
  - Secret-consuming profiles set explicit AWS Secrets Manager secret names
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profiles)
      PROFILE_VALUE="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

python3 "$SCRIPT_DIR/check-docker-aws-env.py" --profiles "$PROFILE_VALUE" --env-file "$ENV_FILE"

profiles_need_sidecar=false
required_secret_vars=()
for profile in $PROFILE_VALUE; do
  case "$profile" in
    core)
      profiles_need_sidecar=true
      required_secret_vars+=(SECOND_OPINION_AWS_SECRET_NAME)
      ;;
    cicd)
      profiles_need_sidecar=true
      required_secret_vars+=(WOODPECKER_CI_AWS_SECRET_NAME)
      ;;
  esac
done

resolve_env_value() {
  local name="$1"
  if printenv "$name" >/dev/null 2>&1; then
    printenv "$name"
    return
  fi

  python3 - "$ENV_FILE" "$name" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
name = sys.argv[2]
if not path.exists():
    raise SystemExit(0)

for raw_line in path.read_text().splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[len("export "):].strip()
    if "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key.strip() != name:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    print(value)
    break
PY
}

errors=()

if [[ "$profiles_need_sidecar" == true ]]; then
  aws_token="$(resolve_env_value AWS_TOKEN)"
  if [[ -z "${aws_token//[[:space:]]/}" ]]; then
    errors+=("AWS_TOKEN is required for production deploy profiles.")
  elif [[ "$aws_token" == "default-token" ]]; then
    errors+=("AWS_TOKEN must not be the insecure default 'default-token' for deploys.")
  fi
fi

seen_secret_vars=""
for var_name in "${required_secret_vars[@]}"; do
  if [[ " $seen_secret_vars " == *" $var_name "* ]]; then
    continue
  fi
  seen_secret_vars="$seen_secret_vars $var_name"
  value="$(resolve_env_value "$var_name")"
  if [[ -z "${value//[[:space:]]/}" ]]; then
    errors+=("$var_name must be set to the AWS Secrets Manager secret name for deploys.")
  fi
done

if [[ ${#errors[@]} -gt 0 ]]; then
  echo "ERROR: production deploy environment is incomplete." >&2
  for error in "${errors[@]}"; do
    echo "  - $error" >&2
  done
  exit 1
fi

echo "OK: production Docker deploy environment is explicit and non-default."

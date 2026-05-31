#!/usr/bin/env bash
# Rebuild and restart the Docker Compose stack with a rollback image snapshot.
#
# Before replacing containers, this script tags each currently running service
# image as :previous. If docker compose --wait fails, it tears down the failed
# candidate stack and restarts the captured services with CPP_IMAGE_TAG=previous.

set -Eeuo pipefail

PROFILE_VALUE="${PROFILE:-core}"

usage() {
  cat <<'USAGE'
Usage: scripts/docker-refresh-transactional.sh [--profiles "core browser cicd"]

Environment:
  PROFILE        Space-separated Docker Compose profiles (default: core)
  CPP_IMAGE_TAG  Candidate image tag consumed by docker-compose.yml
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profiles)
      PROFILE_VALUE="${2:-}"
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

profile_args=()
for profile in $PROFILE_VALUE; do
  profile_args+=(--profile "$profile")
done

compose() {
  docker compose "${profile_args[@]}" "$@"
}

image_repo_from_ref() {
  local image_ref="$1"
  local tail

  if [[ "$image_ref" == *@* ]]; then
    printf '%s\n' "${image_ref%@*}"
    return
  fi

  tail="${image_ref##*/}"
  if [[ "$tail" == *:* ]]; then
    printf '%s\n' "${image_ref%:*}"
  else
    printf '%s\n' "$image_ref"
  fi
}

current_containers=()
if ! mapfile -t current_containers < <(compose ps -q 2>/dev/null); then
  current_containers=()
fi

rollback_services=()

for container_id in "${current_containers[@]}"; do
  [[ -n "$container_id" ]] || continue

  service_name="$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.service" }}' "$container_id")"
  image_ref="$(docker inspect --format '{{ .Config.Image }}' "$container_id")"
  image_id="$(docker inspect --format '{{ .Image }}' "$container_id")"

  if [[ -z "$service_name" || -z "$image_ref" || -z "$image_id" ]]; then
    echo "ERROR: could not inspect current compose container $container_id" >&2
    exit 1
  fi

  previous_ref="$(image_repo_from_ref "$image_ref"):previous"
  echo "Snapshotting $service_name image $image_id as $previous_ref"
  docker image tag "$image_id" "$previous_ref"
  rollback_services+=("$service_name")
done

echo "Starting candidate stack for profiles: ${PROFILE_VALUE:-<none>}"
if compose up -d --build --wait --remove-orphans; then
  echo "Docker refresh complete."
  exit 0
else
  refresh_exit=$?
fi

echo "ERROR: candidate stack failed health wait. Rolling back to :previous images." >&2

compose down || echo "WARNING: failed to stop candidate stack before rollback" >&2

if [[ ${#rollback_services[@]} -eq 0 ]]; then
  echo "ERROR: no previous running services were available to roll back." >&2
  exit "$refresh_exit"
fi

if CPP_IMAGE_TAG=previous docker compose "${profile_args[@]}" up -d --wait --no-build --remove-orphans "${rollback_services[@]}"; then
  echo "Rollback complete. Previous stack restored." >&2
else
  echo "ERROR: rollback to :previous images failed." >&2
  exit 1
fi

exit "$refresh_exit"

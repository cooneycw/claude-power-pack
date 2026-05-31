#!/bin/sh
# Authenticate Docker Hub pulls in CI so base-image pulls do not use the
# anonymous rate limit. Kept in a script file because Woodpecker mangles nested
# quotes in inline commands. Non-fatal when secrets are absent, preserving
# fork/PR behaviour where repository secrets may not be exposed.
set -eu

if [ -n "${DOCKERHUB_TOKEN:-}" ] && [ -n "${DOCKERHUB_USERNAME:-}" ]; then
  echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
  echo "INFO: authenticated to Docker Hub as $DOCKERHUB_USERNAME"
else
  echo "INFO: DOCKERHUB_USERNAME/DOCKERHUB_TOKEN not set; pulling unauthenticated"
fi

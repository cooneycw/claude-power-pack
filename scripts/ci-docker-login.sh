#!/bin/sh
# Authenticate Docker Hub for the runtime-smoke step so compose base-image pulls
# are not subject to the anonymous pull rate limit (issue #370). Kept in a script
# file rather than inline because Woodpecker mangles nested quotes in inline
# commands. Non-fatal when the secret is absent (e.g. forked PRs): the build
# simply pulls unauthenticated, preserving prior behaviour.
set -eu

if [ -n "${DOCKERHUB_TOKEN:-}" ] && [ -n "${DOCKERHUB_USERNAME:-}" ]; then
  echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
  echo "INFO: authenticated to Docker Hub as $DOCKERHUB_USERNAME"
else
  echo "INFO: DOCKERHUB_USERNAME/DOCKERHUB_TOKEN not set; pulling unauthenticated"
fi

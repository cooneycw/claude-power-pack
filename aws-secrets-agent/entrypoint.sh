#!/bin/sh
set -eu

missing=""
for name in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
    eval "value=\${$name:-}"
    if [ -z "$value" ]; then
        if [ -n "$missing" ]; then
            missing="$missing, $name"
        else
            missing="$name"
        fi
    fi
done

if [ -n "$missing" ]; then
    echo "ERROR: aws-secrets-agent cannot start: AWS credentials empty/missing ($missing)." >&2
    echo "ERROR: Docker Compose captures environment at container create time; restart will not reload fixed creds." >&2
    echo "ERROR: Fix .env or shell env, then force-recreate the sidecar and dependent MCP containers:" >&2
    echo "ERROR:   docker compose --profile core --profile cicd up -d --force-recreate aws-secrets-agent mcp-second-opinion mcp-woodpecker-ci" >&2
    exit 78
fi

exec ./aws-secrets-agent --config config.toml

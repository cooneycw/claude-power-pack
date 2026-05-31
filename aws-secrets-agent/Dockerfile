# syntax=docker/dockerfile:1
FROM rust:1.96.0-slim@sha256:26abcef3d79b8d890c4ceb17093154573e1f6479cf6dd7c1450043b8458350f6 AS builder

RUN apt-get update && apt-get install -y git pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Pin upstream by immutable commit SHA, not a mutable tag.
# AGENT_SHA is the commit the v2.1.0 tag pointed to when this was vendored.
# Upstream `main` is ahead of the latest release and has regressed startup
# credential handling (the agent exits with CredentialsNotLoaded even when
# placeholder creds are present), which breaks credential-less CI smoke runs.
# This release commit starts cleanly and serves /ping as a pure liveness probe.
ARG AGENT_REPO=https://github.com/aws/aws-secretsmanager-agent.git
ARG AGENT_SHA=e374c491bbe2f590c0cdeea4f8213189eb656689

# Shallow-fetch the exact commit, then verify HEAD matches the pin. A moved or
# rewritten upstream ref fails the build here instead of silently building
# something else.
RUN git init -q . \
    && git remote add origin "${AGENT_REPO}" \
    && git fetch -q --depth 1 origin "${AGENT_SHA}" \
    && git checkout -q FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${AGENT_SHA}" \
        || { echo "ERROR: upstream HEAD != pinned AGENT_SHA (${AGENT_SHA})"; exit 1; }

# Apply tracked patches instead of brittle in-Dockerfile sed. `git apply
# --check` fails loudly if upstream reformats the patched lines, so drift
# fails the build rather than silently no-op'ing and shipping a misconfigured
# agent. Patches are applied in lexical order.
COPY patches/ /build/patches/
RUN for p in /build/patches/*.patch; do \
        echo "Applying $p"; \
        git apply --check "$p" && git apply "$p" \
            || { echo "ERROR: patch $p failed to apply (upstream drift?)"; exit 1; }; \
    done

# Build-time assertions: prove each patch took effect. If a patch silently
# matched nothing (the old sed failure mode) these catch it at build time,
# not at runtime where /ping on localhost would still pass green.
RUN grep -q '\[0, 0, 0, 0\], config.http_port()' aws_secretsmanager_agent/src/main.rs \
        || { echo "ERROR: bind patch did not take effect (agent still bound to 127.0.0.1)"; exit 1; }
RUN if grep -q 'set_ttl' aws_secretsmanager_agent/src/server.rs; then \
        echo "ERROR: set_ttl hop limit still present (blocks cross-container traffic)"; exit 1; \
    fi

# Cache the cargo registry across builds to offset crate-download cost. The
# target dir is left as a normal directory (not a cache mount) so the release
# binary persists in the builder layer and can be COPY'd directly into the
# final image - copying it out of a cache mount produced a binary the runtime
# refused to exec ("Permission denied" / exit 126).
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    cargo build --release --locked

FROM debian:trixie-slim@sha256:b6e2a152f22a40ff69d92cb397223c906017e1391a73c952b588e51af8883bf8

RUN apt-get update && apt-get install -y ca-certificates curl && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 agent && mkdir -p /app && chown agent:agent /app
WORKDIR /app

COPY --from=builder /build/target/release/aws_secretsmanager_agent ./aws-secrets-agent
COPY config.toml ./config.toml
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

USER agent

EXPOSE 2773

# Keep these timings in sync with docker-compose.yml. /ping is a local
# liveness probe only; it does not call AWS or fetch cached secrets.
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -sf -H "X-Aws-Parameters-Secrets-Token: ${AWS_TOKEN}" http://localhost:2773/ping || exit 1

ENTRYPOINT ["./entrypoint.sh"]

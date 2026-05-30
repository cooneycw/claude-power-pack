FROM rust:slim AS builder

RUN apt-get update && apt-get install -y git pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /build
# Pin to a released tag. Upstream `main` is ahead of the latest release and has
# regressed startup credential handling (the agent exits with CredentialsNotLoaded
# even when placeholder creds are present), which breaks credential-less CI smoke
# runs. v2.1.0 starts cleanly and serves /ping as a pure liveness probe.
RUN git clone --depth 1 --branch v2.1.0 https://github.com/aws/aws-secretsmanager-agent.git .

# Patch: bind to 0.0.0.0 instead of 127.0.0.1 for Docker networking
RUN sed -i 's/\[127, 0, 0, 1\]/[0, 0, 0, 0]/' aws_secretsmanager_agent/src/main.rs

# Patch: remove TTL=1 restriction that blocks cross-container traffic
RUN sed -i '/set_ttl/d' aws_secretsmanager_agent/src/server.rs

RUN cargo build --release

FROM debian:trixie-slim

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

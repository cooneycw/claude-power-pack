FROM rust:slim AS builder

RUN apt-get update && apt-get install -y git pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone https://github.com/aws/aws-secretsmanager-agent.git .

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

USER agent

EXPOSE 2773

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -sf -H "X-Aws-Parameters-Secrets-Token: ${AWS_TOKEN}" http://localhost:2773/ping || exit 1

ENTRYPOINT ["./aws-secrets-agent", "--config", "config.toml"]

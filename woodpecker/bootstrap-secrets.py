#!/usr/bin/env python3
"""Pull Woodpecker secrets from AWS Secrets Manager and write docker .env

RUNS ON THE WOODPECKER HOST, UNDER THE SYSTEM INTERPRETER - not from this
project's environment (issue #1041). `boto3` is imported below and is declared in
no dependency metadata here, deliberately: this file is operator tooling for the
CI host, it is imported by nothing in this repository, and `tests/test_bootstrap.py`
gives its remediation as `python woodpecker/bootstrap-secrets.py`.
`templates/woodpecker/bootstrap-secrets.py.example` ships the same program for
other projects to copy.

boto3 IS declared, as the `aws` extra, because `lib/creds/providers/aws.py`
needs it too - so `make undeclared-import-audit` has nothing to report here and
`.undeclared-import-allow` carries no entry for this file. That is the outcome
#1041 preferred: an exception recorded in a ledger is worth less than a
declaration, and the ledger's own stale check is what established it. Running this
from the project environment therefore works under `uv sync --extra aws`; running
it on the host under the system interpreter, as the CI bootstrap does, is what it
is actually for.
"""
import json
import os
import re
import tempfile
from pathlib import Path

import boto3

GRPC_KEY = "WOODPECKER_GRPC_SECRET"


def quoted_end(value: str) -> int | None:
    """Find the closing quote without treating escaped quotes as delimiters."""
    escaped = False
    for index, char in enumerate(value[1:], 1):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == value[0]:
            return index
    return None


def local_signing_token(text: str) -> str | None:
    """Read logical assignments; preserve literal tokens, never dependencies."""
    existing = None
    lines = iter(text.splitlines())
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        match = re.match(r"^\s*(?:export\s+)?([^=:\s]+)\s*[:=](.*)$", line)
        if match is None:
            if re.match(r"^\s*(?:export\s+)?WOODPECKER_GRPC_SECRET(?:\s|$)", line):
                raise ValueError("WOODPECKER_GRPC_SECRET: malformed local assignment")
            continue
        key, raw = match.groups()
        raw = raw.lstrip()
        quoted = raw.startswith(("'", '"'))
        if quoted:
            end = quoted_end(raw)
            while end is None:
                continuation = next(lines, None)
                if continuation is None:
                    raise ValueError("WOODPECKER_GRPC_SECRET: unclosed local environment quote")
                raw += "\n" + continuation
                end = quoted_end(raw)
            token = raw[:end + 1]
            tail = raw[end + 1:].strip()
        else:
            token = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
            tail = ""
        if key != GRPC_KEY:
            continue
        if existing is not None:
            raise ValueError("WOODPECKER_GRPC_SECRET: duplicate local assignment")
        if quoted and tail and not tail.startswith("#"):
            raise ValueError("WOODPECKER_GRPC_SECRET: content after closing quote")
        if not token or token.startswith("#") or (quoted and not token[1:-1]):
            raise ValueError("WOODPECKER_GRPC_SECRET: empty local assignment")
        if "\n" in token or "\r" in token:
            raise ValueError("WOODPECKER_GRPC_SECRET: multiline local key is unsupported")
        if not quoted and ("'" in token or '"' in token):
            raise ValueError("WOODPECKER_GRPC_SECRET: mixed local quoting is unsupported")
        if "$" in token and not token.startswith("'"):
            raise ValueError("WOODPECKER_GRPC_SECRET: local interpolation is unsupported")
        existing = token
    return existing


def write_env(path: str, values: dict, keys: list[str]) -> list[str]:
    """Preserve only the signing key, validate before atomically replacing output."""
    target = Path(path)
    existing = local_signing_token(target.read_text()) if target.exists() else None
    lines = []
    written = []
    for key in dict.fromkeys([*keys, *([GRPC_KEY] if existing is not None else [])]):
        if key == GRPC_KEY and existing is not None:
            value = existing
        elif key not in values:
            continue
        else:
            value = values[key]
            if key == GRPC_KEY:
                if value is None or value == "":
                    continue
                if not isinstance(value, str):
                    raise ValueError("WOODPECKER_GRPC_SECRET: supplied value must be text")
                if "\n" in value or "\r" in value:
                    raise ValueError("WOODPECKER_GRPC_SECRET: supplied value must occupy one line")
                if not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", value):
                    raise ValueError("WOODPECKER_GRPC_SECRET: supplied value requires unsupported dotenv syntax")
            value = str(value)
        if "\n" in value or "\r" in value:
            raise ValueError("Environment values must occupy one line")
        lines.append(f"{key}={value}\n")
        written.append(key)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, prefix=".docker-env-", delete=False) as output:
            temporary = output.name
            output.write("".join(lines))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)
    return written


def main():
    session = boto3.Session(
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    client = session.client("secretsmanager")
    resp = client.get_secret_value(SecretId="essent-ai")
    secrets = json.loads(resp["SecretString"])

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docker.env")
    write_env(env_path, secrets, [
        "WOODPECKER_GITHUB_CLIENT",
        "WOODPECKER_GITHUB_SECRET",
        "WOODPECKER_AGENT_SECRET",
        "WOODPECKER_HOST",
        GRPC_KEY,
    ])
    print(f"Wrote {env_path} with secrets from essent-ai")


if __name__ == "__main__":
    main()

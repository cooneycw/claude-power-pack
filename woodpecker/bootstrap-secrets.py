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

import boto3


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
    with open(env_path, "w") as f:
        for key in [
            "WOODPECKER_GITHUB_CLIENT",
            "WOODPECKER_GITHUB_SECRET",
            "WOODPECKER_AGENT_SECRET",
            "WOODPECKER_HOST",
        ]:
            if key in secrets:
                f.write(f"{key}={secrets[key]}\n")
    print(f"Wrote {env_path} with secrets from essent-ai")


if __name__ == "__main__":
    main()

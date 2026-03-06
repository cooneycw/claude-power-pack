#!/usr/bin/env python3
"""Pull Woodpecker secrets from AWS Secrets Manager and write docker .env"""
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

#!/usr/bin/env python3
"""Validate Docker AWS credential inputs before creating aws-secrets-agent."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Mapping

AWS_SIDECAR_PROFILES = {"core", "cicd"}
REQUIRED_AWS_ENV = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _profiles_need_aws(profiles: list[str]) -> bool:
    return bool(AWS_SIDECAR_PROFILES.intersection(profiles))


def _validate_credentials(
    env_file_values: Mapping[str, str],
    environ: Mapping[str, str],
) -> list[str]:
    errors: list[str] = []

    for name in REQUIRED_AWS_ENV:
        if name in environ:
            if not environ[name].strip():
                errors.append(
                    f"{name} is set but empty in the shell environment. Docker Compose will bake "
                    "that empty value into aws-secrets-agent and override .env."
                )
            continue

        if name not in env_file_values:
            errors.append(f"{name} is missing from both the shell environment and .env.")
        elif not env_file_values[name].strip():
            errors.append(f"{name} is present but empty in .env.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profiles",
        default="core",
        help="Space-separated Docker Compose profiles requested by make docker-up",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        type=Path,
        help="Path to the Docker env file",
    )
    args = parser.parse_args()

    profiles = [profile for profile in args.profiles.split() if profile]
    if not _profiles_need_aws(profiles):
        print("OK: requested Docker profiles do not start aws-secrets-agent")
        return 0

    env_file_values = _parse_env_file(args.env_file)
    errors = _validate_credentials(env_file_values, os.environ)

    if errors:
        print("ERROR: aws-secrets-agent requires non-empty AWS credentials before Docker Compose starts.")
        for error in errors:
            print(f"  - {error}")
        print("")
        print("Fix: set non-empty AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env or the shell.")
        print("If a stale sidecar was already created with empty creds, force-recreate it after fixing env:")
        print(
            "  docker compose --profile core --profile cicd up -d --force-recreate "
            "aws-secrets-agent mcp-second-opinion mcp-woodpecker-ci"
        )
        return 1

    print("OK: AWS credentials available for aws-secrets-agent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate AWS Secrets Manager secret key presence without printing values."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretSpec:
    name: str
    keys: tuple[str, ...]
    required: bool


def parse_secret_spec(raw: str, *, required: bool) -> SecretSpec:
    """Parse NAME:KEY,KEY into a typed spec."""
    if ":" not in raw:
        raise argparse.ArgumentTypeError("expected NAME:KEY,KEY")

    name, raw_keys = raw.split(":", 1)
    keys = tuple(key.strip() for key in raw_keys.split(",") if key.strip())
    if not name.strip() or not keys:
        raise argparse.ArgumentTypeError("expected non-empty secret name and keys")

    return SecretSpec(name=name.strip(), keys=keys, required=required)


def _run_aws(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["aws", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _severity(spec: SecretSpec) -> str:
    return "FAIL" if spec.required else "WARN"


def validate_secret(spec: SecretSpec) -> bool:
    """Return True when a secret exists and contains all expected non-empty keys."""
    describe = _run_aws(
        ["secretsmanager", "describe-secret", "--secret-id", spec.name],
    )
    if describe.returncode != 0:
        print(f"{_severity(spec)}: Secret '{spec.name}' not found")
        return not spec.required

    value = _run_aws(
        [
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            spec.name,
            "--query",
            "SecretString",
            "--output",
            "text",
        ],
    )
    if value.returncode != 0:
        print(f"{_severity(spec)}: Could not read SecretString for '{spec.name}'")
        return not spec.required

    try:
        payload = json.loads(value.stdout)
    except json.JSONDecodeError:
        print(f"{_severity(spec)}: Secret '{spec.name}' is not valid JSON")
        return not spec.required

    if not isinstance(payload, dict):
        print(f"{_severity(spec)}: Secret '{spec.name}' must be a JSON object")
        return not spec.required

    missing = [key for key in spec.keys if not payload.get(key)]
    if missing:
        keys = ", ".join(missing)
        print(f"{_severity(spec)}: Secret '{spec.name}' missing required key(s): {keys}")
        return not spec.required

    print(f"OK: Secret '{spec.name}' contains expected keys ({len(spec.keys)})")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate AWS Secrets Manager secrets contain expected keys.",
    )
    parser.add_argument(
        "--required",
        action="append",
        default=[],
        metavar="NAME:KEY,KEY",
        help="Secret and key list that must exist.",
    )
    parser.add_argument(
        "--optional",
        action="append",
        default=[],
        metavar="NAME:KEY,KEY",
        help="Secret and key list that may be absent.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    specs = [
        *(parse_secret_spec(raw, required=True) for raw in args.required),
        *(parse_secret_spec(raw, required=False) for raw in args.optional),
    ]

    if not specs:
        parser.error("at least one --required or --optional spec is needed")

    ok = True
    for spec in specs:
        ok = validate_secret(spec) and ok

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

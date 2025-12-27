"""Command-line interface for secrets management.

Usage:
    python -m lib.creds get [OPTIONS] [SECRET_ID]
    python -m lib.creds validate [OPTIONS]

Examples:
    # Get database credentials (auto-detect provider)
    python -m lib.creds get

    # Get specific secret from AWS
    python -m lib.creds get --provider aws prod/database

    # Get credentials as JSON
    python -m lib.creds get --json

    # Validate all providers
    python -m lib.creds validate

    # Validate specific provider
    python -m lib.creds validate --env
    python -m lib.creds validate --aws
    python -m lib.creds validate --db
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import NoReturn

# ANSI color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
NC = "\033[0m"  # No Color


def print_status(status: str, message: str) -> None:
    """Print a status message with color coding."""
    symbols = {
        "ok": f"{GREEN}✓{NC}",
        "warn": f"{YELLOW}!{NC}",
        "fail": f"{RED}✗{NC}",
        "info": " ",
    }
    symbol = symbols.get(status, " ")
    print(f"{symbol} {message}")


def cmd_get(args: argparse.Namespace) -> int:
    """Handle the 'get' subcommand."""
    from . import get_credentials, get_provider
    from .providers import AWSSecretsProvider, EnvSecretsProvider

    # Select provider
    if args.provider == "aws":
        provider = AWSSecretsProvider()
        if not provider.is_available():
            print("Error: AWS Secrets Manager not available", file=sys.stderr)
            return 1
    elif args.provider == "env":
        provider = EnvSecretsProvider()
    else:
        provider = get_provider()

    try:
        creds = get_credentials(args.secret_id, provider=provider)

        if args.json:
            print(json.dumps(creds.dsn_masked, indent=2))
        else:
            print(f"Provider: {provider.name}")
            print(f"Secret ID: {args.secret_id}")
            print()
            print(f"Host: {creds.host}")
            print(f"Port: {creds.port}")
            print(f"Database: {creds.database}")
            print(f"Username: {creds.username}")
            print("Password: ****")
            print()
            print(f"Connection String: {creds.connection_string}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def validate_env() -> bool:
    """Validate environment variables."""
    print("=== Environment Variables ===")
    print()

    # Check for common database env vars
    if os.environ.get("DB_HOST"):
        print_status("ok", f"DB_HOST is set: {os.environ['DB_HOST']}")
    else:
        print_status("warn", "DB_HOST is not set")

    if os.environ.get("DB_USER"):
        print_status("ok", f"DB_USER is set: {os.environ['DB_USER']}")
    else:
        print_status("warn", "DB_USER is not set")

    if os.environ.get("DB_PASSWORD"):
        print_status("ok", "DB_PASSWORD is set: ****")
    else:
        print_status("warn", "DB_PASSWORD is not set")

    if os.environ.get("DB_NAME"):
        print_status("ok", f"DB_NAME is set: {os.environ['DB_NAME']}")
    else:
        print_status("warn", "DB_NAME is not set")

    if os.path.isfile(".env"):
        print_status("ok", ".env file exists")
    else:
        print_status("warn", ".env file not found (optional)")

    print()
    return True


def validate_aws() -> bool:
    """Validate AWS credentials."""
    print("=== AWS Credentials ===")
    print()

    # Check for AWS env vars
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    if aws_key:
        key_prefix = aws_key[:4] if len(aws_key) >= 4 else aws_key
        print_status("ok", f"AWS_ACCESS_KEY_ID is set: {key_prefix}...")
    else:
        print_status("warn", "AWS_ACCESS_KEY_ID not set")

    if os.environ.get("AWS_SECRET_ACCESS_KEY"):
        print_status("ok", "AWS_SECRET_ACCESS_KEY is set: ****")
    else:
        print_status("warn", "AWS_SECRET_ACCESS_KEY not set")

    region = os.environ.get("AWS_DEFAULT_REGION")
    if region:
        print_status("ok", f"AWS_DEFAULT_REGION: {region}")
    else:
        print_status("info", "AWS_DEFAULT_REGION not set (defaults to us-east-1)")

    # Try to validate AWS credentials using CLI
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--query", "Arn", "--output", "text"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            identity = result.stdout.strip() or "unknown"
            print_status("ok", f"AWS credentials valid: {identity}")
        else:
            print_status("fail", "AWS credentials invalid or expired")
    except FileNotFoundError:
        print_status("warn", "AWS CLI not installed (cannot validate credentials)")
    except subprocess.TimeoutExpired:
        print_status("warn", "AWS CLI timed out")
    except Exception as e:
        print_status("fail", f"Error validating AWS: {e}")

    print()
    return True


def validate_db() -> bool:
    """Validate database connection."""
    print("=== Database Connection ===")
    print()

    try:
        from . import get_credentials

        creds = get_credentials()
        print_status("ok", f"Credentials loaded: {creds.connection_string}")

        # Try actual connection if psql is available
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "5432")
        dbname = os.environ.get("DB_NAME", "")
        user = os.environ.get("DB_USER", "")
        password = os.environ.get("DB_PASSWORD", "")

        if dbname and user:
            try:
                result = subprocess.run(
                    [
                        "psql",
                        "-h", host,
                        "-p", port,
                        "-U", user,
                        "-d", dbname,
                        "-c", "SELECT 1",
                    ],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PGPASSWORD": password},
                    timeout=10,
                )
                if result.returncode == 0:
                    print_status("ok", "Database connection successful")
                else:
                    print_status("fail", "Database connection failed")
            except FileNotFoundError:
                print_status("info", "psql not installed (cannot test connection)")
            except subprocess.TimeoutExpired:
                print_status("fail", "Database connection timed out")
        else:
            print_status("info", "DB_NAME or DB_USER not set (cannot test connection)")

    except Exception as e:
        print_status("fail", f"Failed to load credentials: {e}")

    print()
    return True


def cmd_validate(args: argparse.Namespace) -> int:
    """Handle the 'validate' subcommand."""
    if args.env:
        validate_env()
    elif args.aws:
        validate_aws()
    elif args.db:
        validate_db()
    else:
        # Validate all
        validate_env()
        validate_aws()
        validate_db()
        print("=== Summary ===")
        print("Run with --db, --aws, or --env for specific validation")

    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m lib.creds",
        description="Secrets management CLI with provider abstraction and masking",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'get' subcommand
    get_parser = subparsers.add_parser(
        "get",
        help="Get credentials (masked output)",
        description="Get database credentials from the configured provider. "
        "Passwords are always masked in output.",
    )
    get_parser.add_argument(
        "secret_id",
        nargs="?",
        default="DB",
        help="Secret identifier (default: DB)",
    )
    get_parser.add_argument(
        "--provider",
        "-p",
        choices=["aws", "env", "auto"],
        default="auto",
        help="Provider to use: aws, env, or auto (default: auto)",
    )
    get_parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON (masked)",
    )

    # 'validate' subcommand
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate credentials configuration",
        description="Validate that credentials are properly configured. "
        "Never displays actual secret values.",
    )
    validate_parser.add_argument(
        "--env",
        action="store_true",
        help="Validate environment variables only",
    )
    validate_parser.add_argument(
        "--aws",
        action="store_true",
        help="Validate AWS credentials only",
    )
    validate_parser.add_argument(
        "--db",
        action="store_true",
        help="Test database connection only",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "get":
        return cmd_get(args)
    elif args.command == "validate":
        return cmd_validate(args)
    else:
        parser.print_help()
        return 1


def run() -> NoReturn:
    """Entry point that exits with the return code."""
    sys.exit(main())


if __name__ == "__main__":
    run()

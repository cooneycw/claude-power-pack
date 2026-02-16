"""Command-line interface for secrets management.

Usage:
    python -m lib.creds get [OPTIONS] [SECRET_ID]
    python -m lib.creds set KEY VALUE [--project PROJECT]
    python -m lib.creds list [--project PROJECT]
    python -m lib.creds run -- COMMAND [ARGS...]
    python -m lib.creds validate [OPTIONS]
    python -m lib.creds ui [--port PORT]
    python -m lib.creds rotate KEY [--project PROJECT]

Examples:
    # Get database credentials (auto-detect provider)
    python -m lib.creds get

    # Set a secret
    python -m lib.creds set DB_PASSWORD my-secret-value

    # List all secrets for current project
    python -m lib.creds list

    # Run command with secrets injected
    python -m lib.creds run -- make deploy

    # Launch web UI
    python -m lib.creds ui

    # Validate providers
    python -m lib.creds validate
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


def cmd_set(args: argparse.Namespace) -> int:
    """Handle the 'set' subcommand."""
    from .audit import log_action
    from .base import SecretBundle
    from .project import get_project_id
    from .providers.dotenv import DotEnvSecretsProvider

    project_id = args.project or get_project_id()
    provider = DotEnvSecretsProvider()

    bundle = SecretBundle(
        project_id=project_id,
        secrets={args.key: args.value},
    )
    provider.put_bundle(bundle, mode="merge")

    log_action("set", project_id, f"key={args.key}")

    print_status("ok", f"Set {args.key} for project '{project_id}'")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Handle the 'list' subcommand."""
    from .project import get_project_id
    from .providers.dotenv import DotEnvSecretsProvider
    from .providers.aws import AWSSecretsProvider

    project_id = args.project or get_project_id()

    # Try dotenv first
    dotenv = DotEnvSecretsProvider()
    bundle = dotenv.get_bundle(project_id)

    if bundle.secrets:
        print(f"Project: {project_id}")
        print(f"Provider: {dotenv.name}")
        print(f"Secrets: {len(bundle.secrets)}")
        print()
        for key in sorted(bundle.secrets):
            value = bundle.secrets[key]
            masked = value[:2] + "*" * max(0, len(value) - 4) + value[-2:] if len(value) > 4 else "****"
            print(f"  {key} = {masked}")
        return 0

    # Try AWS
    aws = AWSSecretsProvider()
    if aws.is_available():
        bundle = aws.get_bundle(project_id)
        if bundle.secrets:
            print(f"Project: {project_id}")
            print(f"Provider: {aws.name}")
            print(f"Secrets: {len(bundle.secrets)}")
            print()
            for key in sorted(bundle.secrets):
                value = bundle.secrets[key]
                masked = value[:2] + "*" * max(0, len(value) - 4) + value[-2:] if len(value) > 4 else "****"
                print(f"  {key} = {masked}")
            return 0

    print(f"No secrets found for project '{project_id}'")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Handle the 'run' subcommand."""
    from .run import run_with_secrets

    # Strip leading '--' from REMAINDER args
    cmd = args.run_command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        print("Error: no command specified. Usage: creds run -- command [args]",
              file=sys.stderr)
        return 1

    return run_with_secrets(
        command=cmd,
        project_id=args.project,
        provider_name=args.provider,
    )


def cmd_ui(args: argparse.Namespace) -> int:
    """Handle the 'ui' subcommand."""
    from .ui import run_server

    try:
        run_server(
            project_id=args.project,
            host=args.host,
            port=args.port,
        )
    except KeyboardInterrupt:
        print("\nUI server stopped.")
    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    """Handle the 'rotate' subcommand."""
    from .audit import log_action
    from .project import get_project_id
    from .providers.dotenv import DotEnvSecretsProvider

    project_id = args.project or get_project_id()
    provider = DotEnvSecretsProvider()

    bundle = provider.get_bundle(project_id)
    if args.key not in bundle.secrets:
        print(f"Error: key '{args.key}' not found in project '{project_id}'",
              file=sys.stderr)
        return 1

    if not args.value:
        # Prompt for new value
        import getpass
        new_value = getpass.getpass(f"New value for {args.key}: ")
        if not new_value:
            print("Error: value cannot be empty", file=sys.stderr)
            return 1
    else:
        new_value = args.value

    from .base import SecretBundle
    update = SecretBundle(
        project_id=project_id,
        secrets={args.key: new_value},
    )
    provider.put_bundle(update, mode="merge")

    log_action("rotate", project_id, f"key={args.key}")

    print_status("ok", f"Rotated {args.key} for project '{project_id}'")
    return 0


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


def validate_dotenv() -> bool:
    """Validate DotEnv global config secrets."""
    print("=== Global Config Secrets ===")
    print()

    try:
        from .project import get_project_id
        from .providers.dotenv import DotEnvSecretsProvider

        project_id = get_project_id()
        provider = DotEnvSecretsProvider()
        bundle = provider.get_bundle(project_id)

        print_status("ok", f"Project ID: {project_id}")

        if bundle.secrets:
            print_status("ok", f"Found {len(bundle.secrets)} secrets")
            for key in sorted(bundle.secrets):
                print_status("info", f"  {key}")
        else:
            print_status("warn", "No secrets stored yet")
            print_status("info", "  Use 'creds set KEY VALUE' to add secrets")
    except RuntimeError as e:
        print_status("warn", f"Not in a git repository: {e}")
    except Exception as e:
        print_status("fail", f"Error: {e}")

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
    elif args.dotenv:
        validate_dotenv()
    else:
        # Validate all
        validate_dotenv()
        validate_env()
        validate_aws()
        validate_db()
        print("=== Summary ===")
        print("Run with --dotenv, --db, --aws, or --env for specific validation")

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

    # 'set' subcommand
    set_parser = subparsers.add_parser(
        "set",
        help="Set a secret value",
        description="Set or update a secret in the project's global config store.",
    )
    set_parser.add_argument("key", help="Secret key name (e.g., DB_PASSWORD)")
    set_parser.add_argument("value", help="Secret value")
    set_parser.add_argument(
        "--project",
        help="Override auto-detected project ID",
    )

    # 'list' subcommand
    list_parser = subparsers.add_parser(
        "list",
        help="List secret keys (values masked)",
        description="List all secrets for the current project.",
    )
    list_parser.add_argument(
        "--project",
        help="Override auto-detected project ID",
    )

    # 'run' subcommand
    run_parser = subparsers.add_parser(
        "run",
        help="Run command with secrets injected",
        description="Execute a command with project secrets as env vars. "
        "Secrets never appear in CLI arguments.",
    )
    run_parser.add_argument(
        "--project",
        help="Override auto-detected project ID",
    )
    run_parser.add_argument(
        "--provider",
        choices=["aws", "dotenv", "auto"],
        default=None,
        help="Provider to use (default: auto)",
    )
    run_parser.add_argument(
        "run_command",
        nargs=argparse.REMAINDER,
        help="Command to run (use -- before command)",
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
    validate_parser.add_argument(
        "--dotenv",
        action="store_true",
        help="Validate global config secrets only",
    )

    # 'ui' subcommand
    ui_parser = subparsers.add_parser(
        "ui",
        help="Launch web UI for secrets management",
        description="Start a local web server for managing secrets. "
        "Binds to localhost only with bearer token auth.",
    )
    ui_parser.add_argument(
        "--project",
        help="Override auto-detected project ID",
    )
    ui_parser.add_argument(
        "--host",
        default=None,
        help="Bind host (default: 127.0.0.1)",
    )
    ui_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default: 8090)",
    )

    # 'rotate' subcommand
    rotate_parser = subparsers.add_parser(
        "rotate",
        help="Rotate a secret value",
        description="Update a secret with a new value.",
    )
    rotate_parser.add_argument("key", help="Secret key to rotate")
    rotate_parser.add_argument(
        "value",
        nargs="?",
        default=None,
        help="New value (prompts if not provided)",
    )
    rotate_parser.add_argument(
        "--project",
        help="Override auto-detected project ID",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "get": cmd_get,
        "set": cmd_set,
        "list": cmd_list,
        "run": cmd_run,
        "validate": cmd_validate,
        "ui": cmd_ui,
        "rotate": cmd_rotate,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


def run() -> NoReturn:
    """Entry point that exits with the return code."""
    sys.exit(main())


if __name__ == "__main__":
    run()

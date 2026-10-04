"""Enable python -m lib.cicd invocation.

Usage:
    python -m lib.cicd detect [OPTIONS]
    python -m lib.cicd check [OPTIONS]

Examples:
    python -m lib.cicd detect
    python -m lib.cicd detect --json
    python -m lib.cicd check
    python -m lib.cicd check --summary
"""

from .cli import run

if __name__ == "__main__":
    run()

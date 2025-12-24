"""Enable python -m lib.secrets invocation.

Usage:
    python -m lib.secrets get [OPTIONS] [SECRET_ID]
    python -m lib.secrets validate [OPTIONS]

Examples:
    python -m lib.secrets get
    python -m lib.secrets get --json
    python -m lib.secrets validate --db
"""

from .cli import run

if __name__ == "__main__":
    run()

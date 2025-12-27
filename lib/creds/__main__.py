"""Enable python -m lib.creds invocation.

Usage:
    python -m lib.creds get [OPTIONS] [SECRET_ID]
    python -m lib.creds validate [OPTIONS]

Examples:
    python -m lib.creds get
    python -m lib.creds get --json
    python -m lib.creds validate --db
"""

from .cli import run

if __name__ == "__main__":
    run()

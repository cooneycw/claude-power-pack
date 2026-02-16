"""Enable python -m lib.creds invocation.

Usage:
    python -m lib.creds get [OPTIONS] [SECRET_ID]
    python -m lib.creds set KEY VALUE [--project PROJECT]
    python -m lib.creds list [--project PROJECT]
    python -m lib.creds run -- COMMAND [ARGS...]
    python -m lib.creds validate [OPTIONS]
    python -m lib.creds ui [--port PORT]
    python -m lib.creds rotate KEY [--project PROJECT]

Examples:
    python -m lib.creds get
    python -m lib.creds set DB_PASSWORD my-secret
    python -m lib.creds list
    python -m lib.creds run -- make deploy
    python -m lib.creds ui
    python -m lib.creds validate --dotenv
"""

from .cli import run

if __name__ == "__main__":
    run()

"""Enable python -m lib.security invocation.

Usage:
    python -m lib.security scan [OPTIONS]
    python -m lib.security quick [OPTIONS]
    python -m lib.security deep [OPTIONS]
    python -m lib.security explain <FINDING_ID>
    python -m lib.security gate <GATE_NAME>

Examples:
    python -m lib.security scan
    python -m lib.security quick --json
    python -m lib.security explain HARDCODED_PASSWORD
    python -m lib.security gate flow_finish
"""

from .cli import run

if __name__ == "__main__":
    run()

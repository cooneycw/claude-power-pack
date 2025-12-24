"""Allow running as python -m lib.spec_bridge."""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())

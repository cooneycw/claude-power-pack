#!/usr/bin/env python3
"""CONSTRUCTED: preserve unknown status inputs, ignore all outcome/write evidence."""

import json
import sys
from pathlib import Path

if sys.argv[1] == "status":
    project = Path(sys.argv[sys.argv.index("--project-dir") + 1])
    try:
        json.loads((project / ".claude/cpp-install.json").read_text())
    except FileNotFoundError:
        print("CPP_INSTALL_RECEIPT: no receipt - run /cpp:init")
        raise SystemExit(1)
    except (OSError, ValueError):
        print("CPP_INSTALL_RECEIPT: unreadable or invalid receipt - run /cpp:init")
        raise SystemExit(1)

print("CPP_INSTALL_RECEIPT: receipt complete")
print("CPP Installation Complete")

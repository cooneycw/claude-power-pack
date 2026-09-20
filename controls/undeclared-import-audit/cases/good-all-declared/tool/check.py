"""The delivery-pilot shape: insert a local src/ dir, then import from it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import retry  # noqa: E402

print(retry.backoff(3))

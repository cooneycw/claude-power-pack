"""Present committed implementation shapes to the real lexical guard."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    gate, case = map(Path, sys.argv[1:3])
    with tempfile.TemporaryDirectory(prefix="control-relay-case-") as owned:
        root = Path(owned)
        implementations = root / "controls/example"
        implementations.mkdir(parents=True)
        source = case / "source.txt"
        if source.exists():
            shutil.copyfile(source, implementations / "run-case.py")
        answer = subprocess.run([sys.executable, str(gate), "--root", str(root)],
                                capture_output=True, text=True, check=False, timeout=15)
    print(answer.stdout, end="")
    print(answer.stderr, end="", file=sys.stderr)
    return answer.returncode


if __name__ == "__main__":
    raise SystemExit(main())

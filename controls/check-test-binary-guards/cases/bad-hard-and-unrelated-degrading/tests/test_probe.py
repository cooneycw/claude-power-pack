import subprocess
from pathlib import Path


def test_probe():
    subprocess.run(["sh", str(Path(__file__).resolve().parents[1] / "scripts/probe.sh")], check=True)

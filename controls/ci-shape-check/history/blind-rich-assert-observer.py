"""Blind control: bound the renderer but drop the exact comparison observation."""
from pathlib import Path

from _pytest.assertion import util


def pytest_configure(config):
    original = util.assertrepr_compare
    root = Path(__file__).resolve().parent

    def observe(op, left, right, **kwargs):
        candidate = root / "candidate.bin"
        expected = root / "expected.bin"
        if (op == "==" and isinstance(left, bytes) and isinstance(right, bytes)
                and candidate.exists() and expected.exists()
                and left == candidate.read_bytes() and right == expected.read_bytes()):
            return ["bounded exact large-byte comparison"]
        return original(op, left, right, **kwargs)

    util.assertrepr_compare = observe

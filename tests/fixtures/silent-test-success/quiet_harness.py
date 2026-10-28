"""A real unittest harness whose successful run can intentionally be silent."""

import io
import sys
import unittest


class Arithmetic(unittest.TestCase):
    def test_sum(self):
        self.assertEqual(sum((2, 3)), 6 if "--fail" in sys.argv else 5)


if __name__ == "__main__":
    stream = sys.stderr if "--summary" in sys.argv else io.StringIO()
    result = unittest.TextTestRunner(stream=stream).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Arithmetic)
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)

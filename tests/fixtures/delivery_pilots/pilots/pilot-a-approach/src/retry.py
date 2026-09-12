"""Retry a flaky call."""


class TransientError(Exception):
    """Raised by a call that may succeed if tried again."""


def retry(fn, attempts=5):
    """Call fn until it returns without raising, up to `attempts` times."""
    last = None
    for _attempt in range(attempts):
        try:
            return fn()
        except TransientError as exc:
            last = exc
    raise last

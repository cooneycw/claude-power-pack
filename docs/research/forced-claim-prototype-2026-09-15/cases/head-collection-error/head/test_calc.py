import helper  # noqa: F401 - present in base, deleted in head: head cannot collect
from calc import add


def test_add():
    assert add(2, 3) == 5

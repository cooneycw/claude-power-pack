import calc_helpers_that_do_not_exist  # noqa: F401 - the unused import IS this fixture's defect
from calc import add


def test_add():
    assert add(2, 3) == 5

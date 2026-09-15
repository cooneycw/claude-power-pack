from calc import add


def test_add():
    import calc_helpers_that_do_not_exist  # noqa: F401 - the defect IS this import
    assert add(2, 3) == 5

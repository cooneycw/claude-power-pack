#!/bin/sh
# Model two pytest children and the unsafe filtered retry from #1617.
printf x >> attempts
case " ${PYTEST_ADDOPTS:-} " in
*" --last-failed "*)
    printf '%s\n' '=== 1 passed in 0.01s ===' '=== 12 passed in 0.01s ==='
    exit 0 ;;
esac
printf '%s\n' \
    '=== test session starts ===' \
    'collected 3 items' \
    '=== 1 failed, 2 passed in 0.01s ===' \
    'FAILED tests/unit.py::test_one - AssertionError' \
    '=== test session starts ===' \
    'collected 627 items' \
    'tests/browser.py F................ [ 46%]' \
    '!!!!!!!!!!!!!!!! KeyboardInterrupt !!!!!!!!!!!!!!!!'
# The browser population never emits a completed summary.
exit 2

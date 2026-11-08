"""Constructed unenforced boundary: every PR proceeds without checking evidence."""


def bootstrap_script(pin, provider):
    return "echo 'CPP_COUNTER_MODEL_ENROLMENT: warn (unenforced)'; exit 0"

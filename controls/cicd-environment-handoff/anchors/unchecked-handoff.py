VALUE = 'CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT'
PRESENT = 'CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT_PRESENT'

def restore_target_environment(environment):
    if VALUE not in environment and PRESENT not in environment:
        return
    value = environment.pop(VALUE, "")
    present = environment.pop(PRESENT, "")
    if present == "x":
        environment["UV_PROJECT_ENVIRONMENT"] = value
    elif present == "":
        environment.pop("UV_PROJECT_ENVIRONMENT", None)

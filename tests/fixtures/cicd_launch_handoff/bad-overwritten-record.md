env "CPP_RUNNER_TARGET_PATH=${PATH-}" "CPP_RUNNER_TARGET_PATH_PRESENT=${PATH+x}" CPP_RUNNER_TARGET_PATH=/foreign uv run python -m lib.cicd run --plan finish

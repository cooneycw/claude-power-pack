env "CPP_RUNNER_TARGET_PATH=${PATH-}" "CPP_RUNNER_TARGET_PATH_PRESENT=${PATH+x}" uv run python -m \
  lib.cicd run --plan finish

```bash
PYTHONPATH="$CPP_DIR" env "CPP_RUNNER_TARGET_PATH=${PATH-}" "CPP_RUNNER_TARGET_PATH_PRESENT=${PATH+x}" uv run --project "$CPP_DIR" python -m lib.cicd run --plan finish
```

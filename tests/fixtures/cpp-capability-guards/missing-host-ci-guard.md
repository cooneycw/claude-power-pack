### CI/CD Execution (Host CI Capabilities)

```bash
CPP_HOST_RUNTIME="$HOME/.cache/claude-power-pack/host-ci"
uv run --python 3.11 --no-python-downloads --project "$CPP_DIR" python -m lib.cicd host-ci --write
```

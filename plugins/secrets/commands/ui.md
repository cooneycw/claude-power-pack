# Secrets Web UI

Launch a local web interface for managing project secrets.

## Arguments

- `--port PORT` (optional): Port to bind to (default: 8090)
- `--project PROJECT` (optional): Override auto-detected project ID

## Instructions

When the user invokes `/secrets:ui`, run:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds ui
```

With options:
```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib:${PYTHONPATH}" python3 -m lib.creds ui --port 8090
```

**Requirements:**
- FastAPI and uvicorn must be installed: `uv pip install 'creds[ui]'`
- The server binds to `127.0.0.1` only (no network exposure)
- A bearer token is generated on startup and printed to the terminal
- Copy the token to authenticate in the browser

**Features:**
- View all secret keys (values masked by default)
- Reveal individual values (click Reveal)
- Add/update secrets
- Delete secrets
- Promote local secrets to AWS Secrets Manager

Report the URL and token to the user.

"""FastAPI web UI for secrets management.

Local-only server with bearer token auth for CRUD operations
on project secrets.

Usage:
    from lib.creds.ui import create_app, run_server

    app = create_app("my-project")
    run_server(app, port=8090)
"""

from .app import create_app, run_server

__all__ = ["create_app", "run_server"]

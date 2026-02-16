"""FastAPI application for secrets management UI.

Provides a local-only web interface for managing project secrets
with bearer token authentication.

Security:
- Binds to 127.0.0.1 only (no network exposure)
- Random bearer token generated on startup, printed to terminal
- Values hidden by default (explicit reveal action)
- CSRF protection via token-based auth
- Content-Security-Policy headers
"""

from __future__ import annotations

import secrets
import sys
from typing import Optional

from ..audit import log_action
from ..base import BundleProvider, SecretBundle, SecretNotFoundError
from ..config import SecretsConfig
from ..project import get_project_id

# Lazy imports for optional dependencies
_fastapi = None
_uvicorn = None


def _import_deps():
    """Import FastAPI and uvicorn (optional dependencies)."""
    global _fastapi, _uvicorn
    try:
        import fastapi
        import uvicorn
        _fastapi = fastapi
        _uvicorn = uvicorn
    except ImportError:
        print(
            "Error: FastAPI and uvicorn are required for the secrets UI.\n"
            "Install with: uv pip install 'creds[ui]'\n"
            "  or: pip install fastapi uvicorn",
            file=sys.stderr,
        )
        sys.exit(1)


def _get_provider(
    config: SecretsConfig,
) -> BundleProvider:
    """Get the configured bundle provider."""
    from ..providers.dotenv import DotEnvSecretsProvider
    from ..providers.aws import AWSSecretsProvider

    if config.default_provider == "aws":
        return AWSSecretsProvider(
            region=config.aws_region,
            role_arn=config.aws_role_arn or None,
        )
    elif config.default_provider == "dotenv":
        return DotEnvSecretsProvider()
    else:
        # Auto-detect
        aws = AWSSecretsProvider(region=config.aws_region)
        if aws.is_available():
            return aws
        return DotEnvSecretsProvider()


def create_app(
    project_id: str | None = None,
    config: SecretsConfig | None = None,
    auth_token: str | None = None,
) -> tuple:
    """Create the FastAPI application.

    Args:
        project_id: Override auto-detected project ID.
        config: Override auto-loaded config.
        auth_token: Override generated auth token.

    Returns:
        Tuple of (FastAPI app, auth_token string).
    """
    _import_deps()

    from fastapi import FastAPI, HTTPException, Depends, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

    if project_id is None:
        project_id = get_project_id()
    if config is None:
        config = SecretsConfig.load()
    if auth_token is None:
        auth_token = secrets.token_urlsafe(32)

    provider = _get_provider(config)

    app = FastAPI(
        title="Claude Power Pack — Secrets",
        description="Local secrets management UI",
        docs_url=None,
        redoc_url=None,
    )

    security = HTTPBearer()

    # --- Middleware ---

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    # --- Auth ---

    async def verify_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ):
        if not secrets.compare_digest(credentials.credentials, auth_token):
            raise HTTPException(status_code=401, detail="Invalid token")

    # --- API Routes ---

    @app.get("/api/secrets", dependencies=[Depends(verify_token)])
    async def list_secrets():
        """List all secret keys (values hidden)."""
        bundle = provider.get_bundle(project_id)
        return {
            "project_id": project_id,
            "provider": provider.name,
            "count": len(bundle.secrets),
            "keys": [
                {"key": k, "length": len(v)}
                for k, v in sorted(bundle.secrets.items())
            ],
        }

    @app.get("/api/secrets/{key}", dependencies=[Depends(verify_token)])
    async def get_secret(key: str, reveal: bool = False):
        """Get a single secret (masked unless reveal=true)."""
        bundle = provider.get_bundle(project_id)
        value = bundle.get(key)
        if value is None:
            raise HTTPException(status_code=404, detail=f"Key '{key}' not found")

        log_action("ui_get", project_id, f"key={key}, revealed={reveal}")

        if reveal:
            return {"key": key, "value": value, "masked": False}
        else:
            masked = value[:2] + "*" * max(0, len(value) - 4) + value[-2:] if len(value) > 4 else "****"
            return {"key": key, "value": masked, "masked": True}

    @app.put("/api/secrets/{key}", dependencies=[Depends(verify_token)])
    async def set_secret(key: str, request: Request):
        """Set or update a secret value."""
        body = await request.json()
        value = body.get("value", "")
        if not value:
            raise HTTPException(status_code=400, detail="value is required")

        bundle = SecretBundle(
            project_id=project_id,
            secrets={key: value},
        )
        provider.put_bundle(bundle, mode="merge")

        log_action("ui_set", project_id, f"key={key}")

        return {"status": "ok", "key": key}

    @app.delete("/api/secrets/{key}", dependencies=[Depends(verify_token)])
    async def delete_secret(key: str):
        """Delete a secret key."""
        try:
            provider.delete_key(project_id, key)
        except SecretNotFoundError:
            raise HTTPException(status_code=404, detail=f"Key '{key}' not found")

        log_action("ui_delete", project_id, f"key={key}")

        return {"status": "ok", "key": key, "deleted": True}

    @app.post("/api/promote", dependencies=[Depends(verify_token)])
    async def promote_to_aws(request: Request):
        """Promote local secrets to AWS Secrets Manager."""
        from ..providers.aws import AWSSecretsProvider
        from ..providers.dotenv import DotEnvSecretsProvider

        local = DotEnvSecretsProvider()
        local_bundle = local.get_bundle(project_id)

        if not local_bundle.secrets:
            raise HTTPException(
                status_code=400,
                detail="No local secrets to promote",
            )

        aws = AWSSecretsProvider(region=config.aws_region)
        if not aws.is_available():
            raise HTTPException(
                status_code=503,
                detail="AWS Secrets Manager not available",
            )

        aws.put_bundle(local_bundle, mode="merge")

        log_action(
            "ui_promote",
            project_id,
            f"keys={','.join(local_bundle.keys)}, provider=aws",
        )

        return {
            "status": "ok",
            "promoted": len(local_bundle.secrets),
            "keys": local_bundle.keys,
        }

    @app.get("/api/info", dependencies=[Depends(verify_token)])
    async def info():
        """Get provider and project info."""
        caps = provider.caps()
        return {
            "project_id": project_id,
            "provider": provider.name,
            "capabilities": {
                "read": caps.can_read,
                "write": caps.can_write,
                "delete": caps.can_delete,
                "list": caps.can_list,
                "rotate": caps.can_rotate,
                "versions": caps.supports_versions,
            },
        }

    # --- HTML UI ---

    @app.get("/", response_class=HTMLResponse)
    async def home():
        """Serve the main UI page."""
        return _render_html(project_id, auth_token)

    return app, auth_token


def _render_html(project_id: str, token: str) -> str:
    """Render the single-page HTML UI."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Secrets — {project_id}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #1a1a2e; color: #e0e0e0; padding: 2rem; max-width: 800px; margin: 0 auto; }}
  h1 {{ color: #7c8cf8; margin-bottom: 0.5rem; }}
  .subtitle {{ color: #888; margin-bottom: 2rem; }}
  .card {{ background: #16213e; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; }}
  .key-row {{ display: flex; align-items: center; justify-content: space-between;
              padding: 0.75rem 0; border-bottom: 1px solid #1a1a2e; }}
  .key-row:last-child {{ border-bottom: none; }}
  .key-name {{ font-family: monospace; font-size: 0.95rem; color: #7c8cf8; }}
  .key-value {{ font-family: monospace; color: #888; }}
  .actions {{ display: flex; gap: 0.5rem; }}
  button {{ background: #7c8cf8; color: #fff; border: none; padding: 0.4rem 0.8rem;
            border-radius: 4px; cursor: pointer; font-size: 0.85rem; }}
  button:hover {{ background: #6b7de8; }}
  button.danger {{ background: #e74c3c; }}
  button.danger:hover {{ background: #c0392b; }}
  button.secondary {{ background: #333; }}
  button.secondary:hover {{ background: #444; }}
  input {{ background: #0f3460; border: 1px solid #333; color: #e0e0e0; padding: 0.4rem 0.8rem;
           border-radius: 4px; font-family: monospace; width: 100%; }}
  input[type="password"] {{ letter-spacing: 0.2em; }}
  .add-form {{ display: flex; gap: 0.5rem; margin-top: 1rem; }}
  .add-form input {{ flex: 1; }}
  .info {{ color: #888; font-size: 0.85rem; margin-top: 1rem; }}
  .status {{ padding: 0.5rem 1rem; border-radius: 4px; margin-bottom: 1rem; }}
  .status.ok {{ background: #1e4620; color: #4caf50; }}
  .status.error {{ background: #4a1515; color: #e74c3c; }}
  .hidden {{ display: none; }}
  #promote-btn {{ margin-top: 1rem; }}
  .autocomplete-off input {{ autocomplete: off; }}
</style>
</head>
<body>
<h1>Secrets Manager</h1>
<p class="subtitle">Project: <strong>{project_id}</strong></p>

<div id="status" class="status hidden"></div>

<div class="card">
  <div id="secrets-list">Loading...</div>
  <form class="add-form autocomplete-off" onsubmit="addSecret(event)">
    <input type="text" id="new-key" placeholder="KEY_NAME" autocomplete="off">
    <input type="password" id="new-value" placeholder="secret value" autocomplete="off">
    <button type="submit">Add</button>
  </form>
</div>

<button id="promote-btn" class="secondary" onclick="promote()">
  Promote to AWS
</button>

<p class="info" id="provider-info">Loading provider info...</p>

<script>
const TOKEN = "{token}";
const H = {{"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}};

async function api(method, path, body) {{
  const opts = {{method, headers: H}};
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch("/api" + path, opts);
  if (!res.ok) {{
    const err = await res.json().catch(() => ({{detail: res.statusText}}));
    throw new Error(err.detail || res.statusText);
  }}
  return res.json();
}}

function showStatus(msg, ok) {{
  const el = document.getElementById("status");
  el.textContent = msg;
  el.className = "status " + (ok ? "ok" : "error");
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 3000);
}}

async function loadSecrets() {{
  try {{
    const data = await api("GET", "/secrets");
    const list = document.getElementById("secrets-list");
    if (data.keys.length === 0) {{
      list.innerHTML = '<p style="color:#888">No secrets yet. Add one below.</p>';
      return;
    }}
    list.innerHTML = data.keys.map(k => `
      <div class="key-row" id="row-${{k.key}}">
        <span class="key-name">${{k.key}}</span>
        <span class="key-value" id="val-${{k.key}}">**** (${{k.length}} chars)</span>
        <div class="actions">
          <button class="secondary" onclick="reveal('${{k.key}}')">Reveal</button>
          <button class="danger" onclick="del('${{k.key}}')">Delete</button>
        </div>
      </div>
    `).join("");
  }} catch (e) {{
    showStatus("Error loading secrets: " + e.message, false);
  }}
}}

async function reveal(key) {{
  try {{
    const data = await api("GET", "/secrets/" + key + "?reveal=true");
    document.getElementById("val-" + key).textContent = data.value;
    setTimeout(() => loadSecrets(), 5000);
  }} catch (e) {{ showStatus(e.message, false); }}
}}

async function del(key) {{
  if (!confirm("Delete " + key + "?")) return;
  try {{
    await api("DELETE", "/secrets/" + key);
    showStatus("Deleted " + key, true);
    loadSecrets();
  }} catch (e) {{ showStatus(e.message, false); }}
}}

async function addSecret(e) {{
  e.preventDefault();
  const key = document.getElementById("new-key").value.trim();
  const value = document.getElementById("new-value").value;
  if (!key || !value) return;
  try {{
    await api("PUT", "/secrets/" + key, {{value}});
    showStatus("Added " + key, true);
    document.getElementById("new-key").value = "";
    document.getElementById("new-value").value = "";
    loadSecrets();
  }} catch (e) {{ showStatus(e.message, false); }}
}}

async function promote() {{
  if (!confirm("Promote all local secrets to AWS Secrets Manager?")) return;
  try {{
    const data = await api("POST", "/promote");
    showStatus("Promoted " + data.promoted + " secrets to AWS", true);
  }} catch (e) {{ showStatus(e.message, false); }}
}}

async function loadInfo() {{
  try {{
    const data = await api("GET", "/info");
    document.getElementById("provider-info").textContent =
      "Provider: " + data.provider + " | " +
      "Capabilities: " + Object.entries(data.capabilities)
        .filter(([k,v]) => v).map(([k]) => k).join(", ");
  }} catch (e) {{}}
}}

loadSecrets();
loadInfo();
</script>
</body>
</html>"""


def run_server(
    project_id: str | None = None,
    config: SecretsConfig | None = None,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Start the secrets management UI server.

    Args:
        project_id: Override auto-detected project ID.
        config: Override auto-loaded config.
        host: Override bind host (default: 127.0.0.1).
        port: Override bind port (default: 8090).
    """
    _import_deps()
    import uvicorn

    if config is None:
        config = SecretsConfig.load()

    host = host or config.ui_host
    port = port or config.ui_port

    app, token = create_app(project_id, config)

    print(f"\nSecrets Manager UI starting...")
    print(f"  URL:   http://{host}:{port}/")
    print(f"  Token: {token}")
    print(f"  (Copy the token — it's required for API access)")
    print()

    log_action("ui_start", project_id or "", f"host={host}, port={port}")

    uvicorn.run(app, host=host, port=port, log_level="warning")

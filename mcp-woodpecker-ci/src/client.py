"""Async HTTP client for the Woodpecker CI v3 REST API."""

import base64
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class WoodpeckerClient:
    """Thin async wrapper around the Woodpecker CI REST API.

    All methods return parsed JSON dicts/lists or raise on HTTP errors.
    """

    def __init__(self, base_url: str, api_token: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._timeout = timeout

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        """Execute an API request and return parsed JSON."""
        url = f"{self.base_url}/api{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(method, url, headers=self._headers, **kwargs)
            resp.raise_for_status()
            if resp.status_code == 204:
                return {"status": "ok"}
            return resp.json()

    # -- Repos --

    async def list_repos(self) -> list[dict]:
        """List all repos the authenticated user has access to."""
        return await self._request("GET", "/repos")

    async def get_repo(self, repo_id: int) -> dict:
        """Get a single repo by numeric ID."""
        return await self._request("GET", f"/repos/{repo_id}")

    async def lookup_repo(self, owner: str, name: str) -> dict:
        """Look up a repo by owner/name and return its metadata."""
        return await self._request("GET", f"/repos/lookup/{owner}/{name}")

    # -- Pipelines --

    async def list_pipelines(
        self, repo_id: int, page: int = 1, per_page: int = 20
    ) -> list[dict]:
        """List pipelines for a repo (newest first)."""
        return await self._request(
            "GET",
            f"/repos/{repo_id}/pipelines",
            params={"page": page, "per_page": per_page},
        )

    async def get_pipeline(self, repo_id: int, pipeline_number: int) -> dict:
        """Get a single pipeline by number."""
        return await self._request(
            "GET", f"/repos/{repo_id}/pipelines/{pipeline_number}"
        )

    async def create_pipeline(
        self,
        repo_id: int,
        branch: str = "main",
        variables: Optional[dict[str, str]] = None,
    ) -> dict:
        """Trigger a new pipeline on the given branch."""
        body: dict[str, Any] = {"branch": branch}
        if variables:
            body["variables"] = variables
        return await self._request(
            "POST", f"/repos/{repo_id}/pipelines", json=body
        )

    async def cancel_pipeline(self, repo_id: int, pipeline_number: int) -> dict:
        """Cancel (kill) a running pipeline."""
        return await self._request(
            "POST", f"/repos/{repo_id}/pipelines/{pipeline_number}/cancel"
        )

    async def approve_pipeline(self, repo_id: int, pipeline_number: int) -> dict:
        """Approve a blocked pipeline."""
        return await self._request(
            "POST", f"/repos/{repo_id}/pipelines/{pipeline_number}/approve"
        )

    # -- Logs --

    async def get_step_logs(
        self, repo_id: int, pipeline_number: int, step_id: int
    ) -> str:
        """Get logs for a specific pipeline step.

        Returns decoded log text (Woodpecker stores log lines as JSON
        arrays with base64-encoded 'data' fields).
        """
        raw = await self._request(
            "GET", f"/repos/{repo_id}/logs/{pipeline_number}/{step_id}"
        )
        lines: list[str] = []
        if isinstance(raw, list):
            for entry in raw:
                data = entry.get("data")
                if data:
                    try:
                        lines.append(base64.b64decode(data).decode("utf-8", errors="replace"))
                    except Exception:
                        lines.append(data)
        return "".join(lines)

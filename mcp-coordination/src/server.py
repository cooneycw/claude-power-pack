"""
MCP Coordination Server - Distributed locking and session management via Redis.

Provides tools for:
- Lock management (acquire, release, check, list)
- Session management (register, heartbeat, status)
- Health checking

Lock naming follows wave/issue pattern:
- "work" - Auto-detect from current branch
- "issue:42" - Lock for issue #42
- "wave:5c" - Lock for wave 5c
- "wave:5c.1" - Lock for wave 5c issue 1
- "pytest", "pr-create" - Resource locks
"""
from fastmcp import FastMCP

from config import config
from coordination import CoordinationManager
from redis_client import RedisClient

# Initialize FastMCP server
mcp = FastMCP(
    config.SERVER_NAME,
    instructions="""
    MCP Coordination Server for distributed locking between Claude Code sessions.

    Lock naming conventions:
    - Use "work" to auto-detect lock scope from current git branch
    - Use "issue:{number}" for issue-specific locks (e.g., "issue:42")
    - Use "wave:{id}" for wave-level locks (e.g., "wave:5c")
    - Use "wave:{id}.{issue}" for wave+issue locks (e.g., "wave:5c.1")
    - Use plain names for resource locks (e.g., "pytest", "pr-create")

    Session management:
    - Register session at start, heartbeat periodically
    - Sessions auto-expire if no heartbeat for 5 minutes
    - Locks auto-expire based on timeout (default 5 minutes)
    """,
)

# Global coordinator instance
coord = CoordinationManager()


# -----------------------------------------------------------------------------
# Lock Management Tools
# -----------------------------------------------------------------------------


@mcp.tool()
async def acquire_lock(
    lock_name: str,
    timeout_seconds: int = 300,
) -> dict:
    """
    Acquire a distributed lock.

    Use this before running exclusive operations like pytest or creating PRs.
    The lock automatically expires after timeout_seconds if not released.

    Args:
        lock_name: Lock identifier. Use:
            - "work" to auto-detect from git branch
            - "issue:42" for issue-specific lock
            - "wave:5c" for wave-level lock
            - "pytest", "pr-create" for resource locks
        timeout_seconds: Lock TTL in seconds (default: 300 = 5 minutes)

    Returns:
        dict with success status, lock info, or holder info if locked

    Example:
        acquire_lock("pytest", 600)  # Hold pytest lock for 10 minutes
        acquire_lock("work")  # Lock based on current branch
    """
    return await coord.acquire_lock(lock_name, timeout_seconds)


@mcp.tool()
async def release_lock(lock_name: str) -> dict:
    """
    Release a lock held by this session.

    Always release locks when done with the protected operation.
    Only the session that acquired the lock can release it.

    Args:
        lock_name: Lock to release (same name used in acquire_lock)

    Returns:
        dict with success status

    Example:
        release_lock("pytest")  # Release after tests complete
        release_lock("work")  # Release branch-based lock
    """
    return await coord.release_lock(lock_name)


@mcp.tool()
async def check_lock(lock_name: str) -> dict:
    """
    Check if a lock is available or held.

    Use this to check lock status without attempting to acquire.

    Args:
        lock_name: Lock to check (use "work" to auto-detect from branch)

    Returns:
        dict with:
            - available: bool - True if lock can be acquired
            - held_by: session ID if locked
            - is_mine: True if this session holds the lock
            - worktree: working directory of holder
            - expires_at: when lock will auto-expire

    Example:
        check_lock("pytest")  # Check if pytest can run
    """
    return await coord.check_lock(lock_name)


@mcp.tool()
async def list_locks(pattern: str = "*") -> dict:
    """
    List all active locks matching a pattern.

    Use glob patterns to filter locks.

    Args:
        pattern: Glob pattern (default: "*" for all locks)
            Examples: "issue:*", "wave:5*", "resource:*"

    Returns:
        dict with:
            - count: number of locks
            - locks: list of lock details

    Example:
        list_locks()  # All locks
        list_locks("issue:*")  # All issue locks
        list_locks("resource:pytest")  # Just pytest lock
    """
    return await coord.list_locks(pattern)


# -----------------------------------------------------------------------------
# Session Management Tools
# -----------------------------------------------------------------------------


@mcp.tool()
async def register_session(metadata: dict | None = None) -> dict:
    """
    Register this session for coordination.

    Call at session start to enable heartbeat tracking.
    Sessions without heartbeats are marked stale after 5 minutes.

    Args:
        metadata: Optional info about the session (e.g., {"task": "fixing #42"})

    Returns:
        dict with session_id and registration time

    Example:
        register_session({"task": "implementing feature X"})
    """
    return await coord.register_session(metadata)


@mcp.tool()
async def heartbeat() -> dict:
    """
    Update session heartbeat to indicate activity.

    Call periodically (e.g., every 2 minutes) to keep session active.
    Sessions without heartbeat for 5+ minutes are marked stale.

    Returns:
        dict with session_id and timestamp

    Example:
        heartbeat()  # Call via hook on each user prompt
    """
    return await coord.heartbeat()


@mcp.tool()
async def session_status() -> dict:
    """
    Get status of all registered sessions.

    Shows all active Claude Code sessions with their:
    - Status tier (active/idle/stale/abandoned)
    - Working directory
    - Heartbeat age

    Status tiers:
    - active (< 5 min): Fully operational
    - idle (5 min - 1 hr): Still protected
    - stale (1 - 4 hr): Can be overridden
    - abandoned (> 24 hr): Auto-released

    Returns:
        dict with my_session ID and list of all sessions

    Example:
        session_status()  # See who else is working
    """
    return await coord.session_status()


# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------


@mcp.tool()
async def health_check() -> dict:
    """
    Check MCP server and Redis connection health.

    Returns:
        dict with:
            - server: MCP server name
            - redis: connection status and version
            - session_id: current session ID

    Example:
        health_check()  # Verify coordination is working
    """
    redis_status = await RedisClient.health_check()

    return {
        "server": config.SERVER_NAME,
        "port": config.SERVER_PORT,
        "session_id": coord.session_id,
        "redis": redis_status,
    }


# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the MCP server."""
    logger.info(f"Starting {config.SERVER_NAME}")
    logger.info(f"Transport: SSE on 127.0.0.1:{config.SERVER_PORT}")

    # Run the MCP server with SSE transport
    mcp.run(
        transport="sse",
        host="127.0.0.1",
        port=config.SERVER_PORT,
    )


if __name__ == "__main__":
    main()

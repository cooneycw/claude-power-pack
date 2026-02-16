"""
Coordination logic for distributed locking and session management.

Lock hierarchy follows wave/issue pattern:
- claude:locks:issue:{number}     - Lock for issue #42
- claude:locks:wave:{id}          - Lock for wave 5c
- claude:locks:wave:{id}.{issue}  - Lock for wave 5c issue 1
- claude:locks:resource:{name}    - Lock for resources (pytest, pr-create, etc.)
"""
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

from config import config
from redis_client import RedisClient


class CoordinationManager:
    """Manages distributed locks and session coordination via Redis."""

    # Key prefixes
    LOCK_PREFIX = "claude:locks"
    SESSION_PREFIX = "claude:sessions"
    HEARTBEAT_PREFIX = "claude:heartbeat"

    def __init__(self):
        """Initialize with session ID from environment or generate one."""
        self.session_id = os.environ.get(
            "CLAUDE_SESSION_ID",
            f"mcp-{os.getpid()}"
        )
        self.worktree = os.getcwd()

    # -------------------------------------------------------------------------
    # Branch Detection (for auto-detecting lock scope)
    # -------------------------------------------------------------------------

    def _get_current_branch(self) -> str | None:
        """Get current git branch name."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _parse_branch_context(self, branch: str | None) -> dict:
        """
        Parse branch name into lock context.

        Examples:
            issue-42-auth       -> {"type": "issue", "issue": 42}
            wave-5c.1-feature   -> {"type": "wave", "wave": "5c", "issue": 1}
            wave-5c-1-feature   -> {"type": "wave", "wave": "5c", "issue": 1}
            wave-3-cleanup      -> {"type": "wave", "wave": "3"}
            main                -> {"type": "branch", "name": "main"}
        """
        if not branch:
            return {"type": "unknown"}

        # Pattern: issue-{N}-*
        if match := re.match(r"^issue-(\d+)", branch):
            return {"type": "issue", "issue": int(match.group(1))}

        # Pattern: wave-{X}.{N}-* (e.g., wave-5c.1-feature)
        if match := re.match(r"^wave-(\d+[a-z]?)\.(\d+)", branch):
            return {"type": "wave", "wave": match.group(1), "issue": int(match.group(2))}

        # Pattern: wave-{X}-{N}-* (e.g., wave-5c-1-feature)
        if match := re.match(r"^wave-(\d+[a-z]?)-(\d+)", branch):
            return {"type": "wave", "wave": match.group(1), "issue": int(match.group(2))}

        # Pattern: wave-{X}-* without issue (e.g., wave-3-cleanup)
        if match := re.match(r"^wave-(\d+[a-z]?)", branch):
            return {"type": "wave", "wave": match.group(1)}

        return {"type": "branch", "name": branch}

    def _context_to_lock_key(self, context: dict) -> str:
        """Convert branch context to lock key."""
        if context["type"] == "issue":
            return f"issue:{context['issue']}"
        elif context["type"] == "wave":
            if "issue" in context:
                return f"wave:{context['wave']}.{context['issue']}"
            return f"wave:{context['wave']}"
        elif context["type"] == "branch":
            return f"branch:{context['name']}"
        return "unknown"

    # -------------------------------------------------------------------------
    # Lock Management
    # -------------------------------------------------------------------------

    async def acquire_lock(
        self,
        lock_name: str,
        timeout_seconds: int | None = None,
        auto_detect: bool = False,
    ) -> dict:
        """
        Acquire a distributed lock.

        Args:
            lock_name: Name of the lock (e.g., "pytest", "pr-create")
                       Or use "auto" to detect from branch
            timeout_seconds: Lock TTL (default: config.DEFAULT_LOCK_TIMEOUT)
            auto_detect: If True and lock_name is "work", auto-detect from branch

        Returns:
            dict with success status, lock info, or holder info if already locked
        """
        if timeout_seconds is None:
            timeout_seconds = config.DEFAULT_LOCK_TIMEOUT

        # Auto-detect lock name from branch if requested
        if lock_name == "work" or auto_detect:
            branch = self._get_current_branch()
            context = self._parse_branch_context(branch)
            lock_name = self._context_to_lock_key(context)

        # Determine key based on lock type
        if ":" in lock_name:
            # Already formatted (issue:42, wave:5c, etc.)
            key = f"{self.LOCK_PREFIX}:{lock_name}"
        else:
            # Resource lock (pytest, pr-create, etc.)
            key = f"{self.LOCK_PREFIX}:resource:{lock_name}"

        r = await RedisClient.get_client()

        # Check for existing lock
        existing = await r.get(key)
        if existing:
            data = json.loads(existing)
            # Allow re-acquiring own lock (extend)
            if data["session_id"] == self.session_id:
                # Extend the lock
                await r.expire(key, timeout_seconds)
                data["expires_at"] = (
                    datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
                ).isoformat()
                await r.set(key, json.dumps(data), ex=timeout_seconds)
                return {
                    "success": True,
                    "extended": True,
                    "lock_name": lock_name,
                    "expires_at": data["expires_at"],
                }
            else:
                # Lock held by another session
                return {
                    "success": False,
                    "reason": "lock_held",
                    "held_by": data["session_id"],
                    "worktree": data.get("worktree", "unknown"),
                    "acquired_at": data.get("acquired_at"),
                    "expires_at": data.get("expires_at"),
                }

        # Attempt to acquire with SETNX
        now = datetime.now(timezone.utc)
        lock_data = {
            "session_id": self.session_id,
            "acquired_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=timeout_seconds)).isoformat(),
            "worktree": self.worktree,
        }

        # Use SET NX (only set if not exists)
        acquired = await r.set(key, json.dumps(lock_data), nx=True, ex=timeout_seconds)

        if acquired:
            return {
                "success": True,
                "lock_name": lock_name,
                "key": key,
                "expires_at": lock_data["expires_at"],
            }

        # Race condition - someone else got it first
        existing = await r.get(key)
        if existing:
            data = json.loads(existing)
            return {
                "success": False,
                "reason": "race_condition",
                "held_by": data["session_id"],
            }

        return {"success": False, "reason": "unknown"}

    async def release_lock(self, lock_name: str) -> dict:
        """
        Release a held lock.

        Args:
            lock_name: Name of the lock to release

        Returns:
            dict with success status
        """
        # Handle auto-detect
        if lock_name == "work":
            branch = self._get_current_branch()
            context = self._parse_branch_context(branch)
            lock_name = self._context_to_lock_key(context)

        # Determine key
        if ":" in lock_name:
            key = f"{self.LOCK_PREFIX}:{lock_name}"
        else:
            key = f"{self.LOCK_PREFIX}:resource:{lock_name}"

        r = await RedisClient.get_client()

        # Check if we hold the lock
        existing = await r.get(key)
        if not existing:
            return {"success": False, "reason": "lock_not_found"}

        data = json.loads(existing)
        if data["session_id"] != self.session_id:
            return {
                "success": False,
                "reason": "not_owner",
                "held_by": data["session_id"],
            }

        # Release it
        await r.delete(key)
        return {"success": True, "lock_name": lock_name}

    async def check_lock(self, lock_name: str) -> dict:
        """
        Check if a lock is available or held.

        Args:
            lock_name: Name of the lock to check

        Returns:
            dict with lock status
        """
        # Handle auto-detect
        if lock_name == "work":
            branch = self._get_current_branch()
            context = self._parse_branch_context(branch)
            lock_name = self._context_to_lock_key(context)

        # Determine key
        if ":" in lock_name:
            key = f"{self.LOCK_PREFIX}:{lock_name}"
        else:
            key = f"{self.LOCK_PREFIX}:resource:{lock_name}"

        r = await RedisClient.get_client()
        existing = await r.get(key)

        if not existing:
            return {
                "available": True,
                "lock_name": lock_name,
            }

        data = json.loads(existing)
        return {
            "available": False,
            "lock_name": lock_name,
            "held_by": data["session_id"],
            "is_mine": data["session_id"] == self.session_id,
            "worktree": data.get("worktree"),
            "acquired_at": data.get("acquired_at"),
            "expires_at": data.get("expires_at"),
        }

    async def list_locks(self, pattern: str = "*") -> dict:
        """
        List all locks matching a pattern.

        Args:
            pattern: Glob pattern (default: "*" for all locks)

        Returns:
            dict with list of locks
        """
        r = await RedisClient.get_client()
        key_pattern = f"{self.LOCK_PREFIX}:{pattern}"
        keys = await r.keys(key_pattern)

        locks = []
        for key in keys:
            data = await r.get(key)
            if data:
                lock_info = json.loads(data)
                # Extract lock name from key
                lock_name = key.replace(f"{self.LOCK_PREFIX}:", "")
                locks.append({
                    "name": lock_name,
                    "held_by": lock_info["session_id"],
                    "is_mine": lock_info["session_id"] == self.session_id,
                    "worktree": lock_info.get("worktree"),
                    "acquired_at": lock_info.get("acquired_at"),
                    "expires_at": lock_info.get("expires_at"),
                })

        return {
            "count": len(locks),
            "locks": locks,
            "pattern": pattern,
        }

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    async def register_session(self, metadata: dict | None = None) -> dict:
        """
        Register this session with optional metadata.

        Args:
            metadata: Optional dict with session metadata

        Returns:
            dict with session info
        """
        r = await RedisClient.get_client()

        now = datetime.now(timezone.utc)
        session_data = {
            "session_id": self.session_id,
            "started_at": now.isoformat(),
            "worktree": self.worktree,
            "status": "active",
            "metadata": metadata or {},
        }

        session_key = f"{self.SESSION_PREFIX}:{self.session_id}"
        heartbeat_key = f"{self.HEARTBEAT_PREFIX}:{self.session_id}"

        await r.set(session_key, json.dumps(session_data))
        await r.set(heartbeat_key, now.isoformat(), ex=config.HEARTBEAT_TTL)

        return {
            "success": True,
            "session_id": self.session_id,
            "registered_at": now.isoformat(),
        }

    async def heartbeat(self) -> dict:
        """
        Update session heartbeat.

        Returns:
            dict with heartbeat status
        """
        r = await RedisClient.get_client()

        now = datetime.now(timezone.utc)
        heartbeat_key = f"{self.HEARTBEAT_PREFIX}:{self.session_id}"
        session_key = f"{self.SESSION_PREFIX}:{self.session_id}"

        # Update heartbeat with TTL
        await r.set(heartbeat_key, now.isoformat(), ex=config.HEARTBEAT_TTL)

        # Update session status
        session_data = await r.get(session_key)
        if session_data:
            data = json.loads(session_data)
            data["status"] = "active"
            data["last_heartbeat"] = now.isoformat()
            await r.set(session_key, json.dumps(data))

        return {
            "success": True,
            "session_id": self.session_id,
            "timestamp": now.isoformat(),
        }

    async def session_status(self) -> dict:
        """
        Get status of all registered sessions.

        Returns:
            dict with all sessions and their states
        """
        r = await RedisClient.get_client()

        # Get all sessions
        session_keys = await r.keys(f"{self.SESSION_PREFIX}:*")
        sessions = []

        now = datetime.now(timezone.utc)

        for key in session_keys:
            session_data = await r.get(key)
            if not session_data:
                continue

            data = json.loads(session_data)
            session_id = data["session_id"]

            # Check heartbeat
            heartbeat_key = f"{self.HEARTBEAT_PREFIX}:{session_id}"
            heartbeat = await r.get(heartbeat_key)

            if heartbeat:
                # Calculate age
                hb_time = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
                age_seconds = (now - hb_time).total_seconds()

                # Determine status tier
                if age_seconds < config.ACTIVE_THRESHOLD:
                    status = "active"
                    status_icon = "🟢"
                elif age_seconds < config.IDLE_THRESHOLD:
                    status = "idle"
                    status_icon = "🟡"
                elif age_seconds < config.STALE_THRESHOLD:
                    status = "stale"
                    status_icon = "🟠"
                else:
                    status = "abandoned"
                    status_icon = "⚫"
            else:
                status = "no_heartbeat"
                status_icon = "❌"
                age_seconds = None

            sessions.append({
                "session_id": session_id,
                "is_me": session_id == self.session_id,
                "status": status,
                "status_icon": status_icon,
                "worktree": data.get("worktree"),
                "started_at": data.get("started_at"),
                "heartbeat_age_seconds": age_seconds,
                "metadata": data.get("metadata", {}),
            })

        return {
            "my_session": self.session_id,
            "session_count": len(sessions),
            "sessions": sessions,
        }

    async def unregister_session(self) -> dict:
        """
        Unregister this session and release all its locks.

        Returns:
            dict with cleanup info
        """
        r = await RedisClient.get_client()

        # Release all locks held by this session
        all_locks = await r.keys(f"{self.LOCK_PREFIX}:*")
        released_locks = []

        for key in all_locks:
            data = await r.get(key)
            if data:
                lock_info = json.loads(data)
                if lock_info["session_id"] == self.session_id:
                    await r.delete(key)
                    lock_name = key.replace(f"{self.LOCK_PREFIX}:", "")
                    released_locks.append(lock_name)

        # Remove session and heartbeat
        session_key = f"{self.SESSION_PREFIX}:{self.session_id}"
        heartbeat_key = f"{self.HEARTBEAT_PREFIX}:{self.session_id}"

        await r.delete(session_key)
        await r.delete(heartbeat_key)

        return {
            "success": True,
            "session_id": self.session_id,
            "released_locks": released_locks,
        }

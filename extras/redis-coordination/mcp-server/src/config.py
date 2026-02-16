"""
Configuration for MCP Coordination Server.
"""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Server configuration from environment variables."""

    # Server settings
    SERVER_NAME: str = "mcp-coordination"
    SERVER_PORT: int = 8082
    LOG_LEVEL: str = "INFO"

    # Redis connection
    REDIS_URL: str = "redis://localhost:6379/0"

    # Lock defaults
    DEFAULT_LOCK_TIMEOUT: int = 300  # 5 minutes
    HEARTBEAT_TTL: int = 300  # 5 minutes

    # Session thresholds (matching file-based coordination)
    ACTIVE_THRESHOLD: int = 300  # 5 minutes
    IDLE_THRESHOLD: int = 3600  # 1 hour
    STALE_THRESHOLD: int = 14400  # 4 hours
    ABANDONED_THRESHOLD: int = 86400  # 24 hours

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            SERVER_NAME=os.getenv("SERVER_NAME", cls.SERVER_NAME),
            SERVER_PORT=int(os.getenv("SERVER_PORT", cls.SERVER_PORT)),
            LOG_LEVEL=os.getenv("LOG_LEVEL", cls.LOG_LEVEL),
            REDIS_URL=os.getenv("REDIS_URL", cls.REDIS_URL),
            DEFAULT_LOCK_TIMEOUT=int(os.getenv("DEFAULT_LOCK_TIMEOUT", cls.DEFAULT_LOCK_TIMEOUT)),
            HEARTBEAT_TTL=int(os.getenv("HEARTBEAT_TTL", cls.HEARTBEAT_TTL)),
            ACTIVE_THRESHOLD=int(os.getenv("ACTIVE_THRESHOLD", cls.ACTIVE_THRESHOLD)),
            IDLE_THRESHOLD=int(os.getenv("IDLE_THRESHOLD", cls.IDLE_THRESHOLD)),
            STALE_THRESHOLD=int(os.getenv("STALE_THRESHOLD", cls.STALE_THRESHOLD)),
            ABANDONED_THRESHOLD=int(os.getenv("ABANDONED_THRESHOLD", cls.ABANDONED_THRESHOLD)),
        )


# Global config instance
config = Config.from_env()

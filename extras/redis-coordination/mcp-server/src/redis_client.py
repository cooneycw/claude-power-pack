"""
Redis connection manager with async connection pooling.
"""
import redis.asyncio as redis
from config import config


class RedisClient:
    """Singleton Redis client with connection pooling."""

    _pool: redis.ConnectionPool | None = None

    @classmethod
    async def get_client(cls) -> redis.Redis:
        """Get Redis client from connection pool."""
        if cls._pool is None:
            cls._pool = redis.ConnectionPool.from_url(
                config.REDIS_URL,
                decode_responses=True,
            )
        return redis.Redis(connection_pool=cls._pool)

    @classmethod
    async def close(cls) -> None:
        """Close the connection pool."""
        if cls._pool is not None:
            await cls._pool.disconnect()
            cls._pool = None

    @classmethod
    async def health_check(cls) -> dict:
        """Check Redis connection health."""
        try:
            client = await cls.get_client()
            pong = await client.ping()
            info = await client.info("server")
            return {
                "connected": pong,
                "redis_version": info.get("redis_version", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
            }

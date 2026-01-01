"""Redis cache service for caching and rate limiting."""

import json
import hashlib
import time
import asyncio
from typing import Any, Optional, Union, Dict, Tuple
from datetime import timedelta

import structlog

logger = structlog.get_logger()

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


class TTLDict:
    """In-memory dictionary with TTL support."""

    def __init__(self) -> None:
        self._data: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get value if not expired."""
        async with self._lock:
            if key not in self._data:
                return None

            value, expires_at = self._data[key]

            if expires_at is not None and time.time() > expires_at:
                del self._data[key]
                return None

            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value with optional TTL."""
        async with self._lock:
            expires_at = time.time() + ttl if ttl else None
            self._data[key] = (value, expires_at)

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        async with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return await self.get(key) is not None

    async def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key."""
        async with self._lock:
            if key not in self._data:
                return -2

            value, expires_at = self._data[key]

            if expires_at is None:
                return -1

            remaining = int(expires_at - time.time())
            if remaining <= 0:
                del self._data[key]
                return -2

            return remaining

    async def set_expire(self, key: str, ttl: int) -> bool:
        """Set expiration on existing key."""
        async with self._lock:
            if key not in self._data:
                return False

            value, _ = self._data[key]
            expires_at = time.time() + ttl
            self._data[key] = (value, expires_at)
            return True

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter."""
        async with self._lock:
            current_value: int
            expires_at: Optional[float]
            if key in self._data:
                value, exp = self._data[key]
                if exp is not None and time.time() > exp:
                    current_value = 0
                    expires_at = None
                else:
                    current_value = int(value) if value is not None else 0
                    expires_at = exp
            else:
                current_value = 0
                expires_at = None

            new_value = current_value + amount
            self._data[key] = (new_value, expires_at)
            return new_value

    async def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        async with self._lock:
            now = time.time()
            expired_keys = [
                key for key, (_, expires_at) in self._data.items()
                if expires_at is not None and now > expires_at
            ]
            for key in expired_keys:
                del self._data[key]
            return len(expired_keys)

    def clear(self) -> None:
        """Clear all entries."""
        self._data.clear()

    def size(self) -> int:
        """Get number of entries."""
        return len(self._data)


class CacheService:
    """Service for caching with Redis.

    Falls back to in-memory caching with TTL support if Redis is not available.
    """

    _instance: Optional["CacheService"] = None
    _redis: Optional[Any] = None
    _memory_cache: Optional[TTLDict] = None
    _cleanup_task: Optional["asyncio.Task[None]"] = None

    MAX_MEMORY_ENTRIES = 10000
    CLEANUP_INTERVAL = 60

    def __new__(cls) -> "CacheService":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._memory_cache = TTLDict()
        return cls._instance

    def __init__(self) -> None:
        """Initialize the cache service."""
        if self._memory_cache is None:
            self._memory_cache = TTLDict()

    async def connect(self, redis_url: str = "redis://localhost:6379") -> bool:
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis library not installed, using in-memory cache")
            self._start_cleanup_task()
            return False

        try:
            self._redis = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info("Connected to Redis", url=redis_url)
            return True
        except Exception as e:
            logger.warning("Failed to connect to Redis, using in-memory cache", error=str(e))
            self._redis = None
            self._start_cleanup_task()
            return False

    def _start_cleanup_task(self) -> None:
        """Start background cleanup task for in-memory cache."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL)
                if self._memory_cache is not None:
                    cleaned = await self._memory_cache.cleanup_expired()
                    if cleaned > 0:
                        logger.debug("Cleaned expired cache entries", count=cleaned)

                    if self._memory_cache.size() > self.MAX_MEMORY_ENTRIES:
                        self._memory_cache.clear()
                        logger.warning("Memory cache exceeded limit, cleared")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cache cleanup error", error=str(e))

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Disconnected from Redis")

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if self._redis:
            try:
                value = await self._redis.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.error("Redis get error", key=key, error=str(e))
        elif self._memory_cache is not None:
            return await self._memory_cache.get(key)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """Set a value in cache."""
        ttl_seconds: Optional[int] = None
        if isinstance(ttl, timedelta):
            ttl_seconds = int(ttl.total_seconds())
        elif isinstance(ttl, int):
            ttl_seconds = ttl

        if self._redis:
            try:
                serialized = json.dumps(value)
                if ttl_seconds:
                    await self._redis.setex(key, ttl_seconds, serialized)
                else:
                    await self._redis.set(key, serialized)
                return True
            except Exception as e:
                logger.error("Redis set error", key=key, error=str(e))
                return False
        elif self._memory_cache is not None:
            await self._memory_cache.set(key, value, ttl_seconds)
            return True
        return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if self._redis:
            try:
                await self._redis.delete(key)
                return True
            except Exception as e:
                logger.error("Redis delete error", key=key, error=str(e))
                return False
        elif self._memory_cache is not None:
            return await self._memory_cache.delete(key)
        return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        if self._redis:
            try:
                result = await self._redis.exists(key)
                return bool(result > 0)
            except Exception as e:
                logger.error("Redis exists error", key=key, error=str(e))
                return False
        elif self._memory_cache is not None:
            return await self._memory_cache.exists(key)
        return False

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache."""
        if self._redis:
            try:
                result = await self._redis.incrby(key, amount)
                return int(result)
            except Exception as e:
                logger.error("Redis increment error", key=key, error=str(e))
                return 0
        elif self._memory_cache is not None:
            return await self._memory_cache.increment(key, amount)
        return 0

    async def expire(self, key: str, ttl: Union[int, timedelta]) -> bool:
        """Set expiration on a key."""
        ttl_seconds: int
        if isinstance(ttl, timedelta):
            ttl_seconds = int(ttl.total_seconds())
        else:
            ttl_seconds = ttl

        if self._redis:
            try:
                result = await self._redis.expire(key, ttl_seconds)
                return bool(result)
            except Exception as e:
                logger.error("Redis expire error", key=key, error=str(e))
                return False
        elif self._memory_cache is not None:
            return await self._memory_cache.set_expire(key, ttl_seconds)
        return False

    async def get_ttl(self, key: str) -> int:
        """Get TTL for a key."""
        if self._redis:
            try:
                result = await self._redis.ttl(key)
                return int(result)
            except Exception as e:
                logger.error("Redis ttl error", key=key, error=str(e))
                return -2
        elif self._memory_cache is not None:
            return await self._memory_cache.get_ttl(key)
        return -2

    def clear_memory_cache(self) -> None:
        """Clear the in-memory cache."""
        if self._memory_cache is not None:
            self._memory_cache.clear()


def generate_cache_key(*args: Any, prefix: str = "cache") -> str:
    """Generate a cache key from arguments."""
    key_data = json.dumps(args, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
    return f"{prefix}:{key_hash}"


_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """Get the cache service singleton."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service

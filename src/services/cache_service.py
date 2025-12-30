"""Redis cache service for caching and rate limiting."""

import json
import hashlib
from typing import Any, Optional, Union
from datetime import timedelta

import structlog

logger = structlog.get_logger()

# Try to import redis, but make it optional
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


class CacheService:
    """Service for caching with Redis.
    
    Falls back to in-memory caching if Redis is not available.
    """
    
    _instance: Optional["CacheService"] = None
    _redis: Optional[Any] = None
    _memory_cache: dict = {}
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the cache service."""
        pass
    
    async def connect(self, redis_url: str = "redis://localhost:6379") -> bool:
        """Connect to Redis.
        
        Args:
            redis_url: Redis connection URL
            
        Returns:
            True if connected successfully
        """
        if not REDIS_AVAILABLE:
            logger.warning("Redis library not installed, using in-memory cache")
            return False
        
        try:
            self._redis = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._redis.ping()
            logger.info("Connected to Redis", url=redis_url)
            return True
        except Exception as e:
            logger.warning("Failed to connect to Redis, using in-memory cache", error=str(e))
            self._redis = None
            return False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Disconnected from Redis")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if self._redis:
            try:
                value = await self._redis.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.error("Redis get error", key=key, error=str(e))
        else:
            return self._memory_cache.get(key)
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds or timedelta
            
        Returns:
            True if successful
        """
        if isinstance(ttl, timedelta):
            ttl = int(ttl.total_seconds())
        
        if self._redis:
            try:
                serialized = json.dumps(value)
                if ttl:
                    await self._redis.setex(key, ttl, serialized)
                else:
                    await self._redis.set(key, serialized)
                return True
            except Exception as e:
                logger.error("Redis set error", key=key, error=str(e))
                return False
        else:
            self._memory_cache[key] = value
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful
        """
        if self._redis:
            try:
                await self._redis.delete(key)
                return True
            except Exception as e:
                logger.error("Redis delete error", key=key, error=str(e))
                return False
        else:
            self._memory_cache.pop(key, None)
            return True
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        if self._redis:
            try:
                return await self._redis.exists(key) > 0
            except Exception as e:
                logger.error("Redis exists error", key=key, error=str(e))
                return False
        else:
            return key in self._memory_cache
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value after increment
        """
        if self._redis:
            try:
                return await self._redis.incrby(key, amount)
            except Exception as e:
                logger.error("Redis increment error", key=key, error=str(e))
                return 0
        else:
            current = self._memory_cache.get(key, 0)
            new_value = current + amount
            self._memory_cache[key] = new_value
            return new_value
    
    async def expire(self, key: str, ttl: Union[int, timedelta]) -> bool:
        """Set expiration on a key.
        
        Args:
            key: Cache key
            ttl: Time-to-live in seconds or timedelta
            
        Returns:
            True if successful
        """
        if isinstance(ttl, timedelta):
            ttl = int(ttl.total_seconds())
        
        if self._redis:
            try:
                return await self._redis.expire(key, ttl)
            except Exception as e:
                logger.error("Redis expire error", key=key, error=str(e))
                return False
        return True  # In-memory cache doesn't support TTL
    
    async def get_ttl(self, key: str) -> int:
        """Get TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        if self._redis:
            try:
                return await self._redis.ttl(key)
            except Exception as e:
                logger.error("Redis ttl error", key=key, error=str(e))
                return -2
        return -1  # In-memory cache doesn't support TTL
    
    def clear_memory_cache(self):
        """Clear the in-memory cache."""
        self._memory_cache.clear()


def generate_cache_key(*args, prefix: str = "cache") -> str:
    """Generate a cache key from arguments.
    
    Args:
        *args: Arguments to include in key
        prefix: Key prefix
        
    Returns:
        Cache key string
    """
    key_data = json.dumps(args, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
    return f"{prefix}:{key_hash}"


# Singleton instance
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """Get the cache service singleton.
    
    Returns:
        CacheService instance
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
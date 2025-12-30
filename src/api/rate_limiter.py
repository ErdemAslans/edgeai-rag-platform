"""Rate limiting middleware for FastAPI."""

import time
from typing import Callable, Optional, Dict
from collections import defaultdict
import asyncio

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

import structlog

logger = structlog.get_logger()


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window algorithm."""
    
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """Check if request is allowed.
        
        Args:
            key: Unique identifier for the client
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests, retry_after_seconds)
        """
        current_time = time.time()
        window_start = current_time - window_seconds
        
        async with self._lock:
            # Clean old requests
            self._requests[key] = [
                req_time for req_time in self._requests[key]
                if req_time > window_start
            ]
            
            current_count = len(self._requests[key])
            remaining = max(0, max_requests - current_count)
            
            if current_count >= max_requests:
                # Calculate retry after
                oldest_request = min(self._requests[key]) if self._requests[key] else current_time
                retry_after = int(oldest_request + window_seconds - current_time) + 1
                return False, 0, retry_after
            
            # Add this request
            self._requests[key].append(current_time)
            return True, remaining - 1, 0
    
    def clear(self):
        """Clear all rate limit data."""
        self._requests.clear()


class RedisRateLimiter:
    """Redis-based rate limiter using sliding window algorithm."""
    
    def __init__(self, cache_service):
        self._cache = cache_service
    
    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """Check if request is allowed.
        
        Args:
            key: Unique identifier for the client
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests, retry_after_seconds)
        """
        redis_key = f"ratelimit:{key}"
        current_count = await self._cache.increment(redis_key)
        
        # Set expiration on first request
        if current_count == 1:
            await self._cache.expire(redis_key, window_seconds)
        
        remaining = max(0, max_requests - current_count)
        
        if current_count > max_requests:
            ttl = await self._cache.get_ttl(redis_key)
            retry_after = max(1, ttl) if ttl > 0 else window_seconds
            return False, 0, retry_after
        
        return True, remaining, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests.
    
    Supports different limits for different endpoints:
    - Default: 100 requests per minute
    - Auth endpoints: 10 requests per minute
    - Query endpoints: 30 requests per minute
    - Upload endpoints: 5 requests per minute
    """
    
    # Rate limit configurations: (max_requests, window_seconds)
    LIMITS = {
        "default": (100, 60),           # 100 req/min
        "auth": (10, 60),               # 10 req/min
        "query": (30, 60),              # 30 req/min
        "upload": (5, 60),              # 5 req/min
        "agents": (20, 60),             # 20 req/min
    }
    
    # Path prefixes to limit categories
    PATH_CATEGORIES = {
        "/api/v1/auth": "auth",
        "/api/v1/queries": "query",
        "/api/v1/documents/upload": "upload",
        "/api/v1/agents": "agents",
    }
    
    # Paths to exclude from rate limiting
    EXCLUDED_PATHS = {
        "/",
        "/health",
        "/api/v1/health",
        "/api/v1/docs",
        "/api/v1/redoc",
        "/api/v1/openapi.json",
    }
    
    def __init__(self, app, cache_service=None):
        super().__init__(app)
        self._cache_service = cache_service
        self._limiter = None
    
    async def _get_limiter(self):
        """Get the appropriate rate limiter."""
        if self._limiter is None:
            if self._cache_service and self._cache_service._redis:
                self._limiter = RedisRateLimiter(self._cache_service)
            else:
                self._limiter = InMemoryRateLimiter()
        return self._limiter
    
    def _get_client_key(self, request: Request) -> str:
        """Get a unique key for the client.
        
        Uses IP address, falling back to a default for testing.
        """
        # Try to get real IP from headers (for proxied requests)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_limit_category(self, path: str) -> str:
        """Get the rate limit category for a path."""
        for prefix, category in self.PATH_CATEGORIES.items():
            if path.startswith(prefix):
                return category
        return "default"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle request with rate limiting."""
        path = request.url.path
        
        # Skip rate limiting for excluded paths
        if path in self.EXCLUDED_PATHS:
            return await call_next(request)
        
        # Get client identifier
        client_key = self._get_client_key(request)
        
        # Get limit for this path
        category = self._get_limit_category(path)
        max_requests, window_seconds = self.LIMITS[category]
        
        # Create unique key for client + category
        rate_key = f"{client_key}:{category}"
        
        # Check rate limit
        limiter = await self._get_limiter()
        is_allowed, remaining, retry_after = await limiter.is_allowed(
            rate_key, max_requests, window_seconds
        )
        
        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                client=client_key,
                path=path,
                category=category,
                retry_after=retry_after,
            )
            raise RateLimitExceeded(retry_after=retry_after)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window_seconds)
        
        return response


def get_rate_limit_middleware(cache_service=None):
    """Factory function to create rate limit middleware.
    
    Args:
        cache_service: Optional cache service for Redis-based limiting
        
    Returns:
        RateLimitMiddleware class configured with cache service
    """
    def middleware_factory(app):
        return RateLimitMiddleware(app, cache_service=cache_service)
    return middleware_factory
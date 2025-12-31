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


class BruteForceProtection:
    """Brute-force attack protection for login attempts."""
    
    def __init__(self):
        self._failed_attempts: Dict[str, list] = defaultdict(list)
        self._blocked_until: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        
        self.MAX_FAILED_ATTEMPTS = 5
        self.BLOCK_DURATION_SECONDS = 300
        self.ATTEMPT_WINDOW_SECONDS = 300
    
    async def record_failed_attempt(self, identifier: str) -> None:
        """Record a failed login attempt."""
        current_time = time.time()
        
        async with self._lock:
            self._failed_attempts[identifier].append(current_time)
            self._cleanup_old_attempts(identifier, current_time)
            
            if len(self._failed_attempts[identifier]) >= self.MAX_FAILED_ATTEMPTS:
                self._blocked_until[identifier] = current_time + self.BLOCK_DURATION_SECONDS
                logger.warning(
                    "Account blocked due to too many failed attempts",
                    identifier=identifier,
                    blocked_until=self._blocked_until[identifier],
                )
    
    async def record_successful_attempt(self, identifier: str) -> None:
        """Clear failed attempts on successful login."""
        async with self._lock:
            self._failed_attempts.pop(identifier, None)
            self._blocked_until.pop(identifier, None)
    
    async def is_blocked(self, identifier: str) -> tuple[bool, int]:
        """Check if identifier is blocked.
        
        Returns:
            Tuple of (is_blocked, retry_after_seconds)
        """
        current_time = time.time()
        
        async with self._lock:
            self._cleanup_old_attempts(identifier, current_time)
            
            if identifier in self._blocked_until:
                if current_time < self._blocked_until[identifier]:
                    retry_after = int(self._blocked_until[identifier] - current_time)
                    return True, retry_after
                else:
                    del self._blocked_until[identifier]
                    self._failed_attempts.pop(identifier, None)
            
            return False, 0
    
    async def get_remaining_attempts(self, identifier: str) -> int:
        """Get remaining login attempts before block."""
        current_time = time.time()
        
        async with self._lock:
            self._cleanup_old_attempts(identifier, current_time)
            attempts = len(self._failed_attempts.get(identifier, []))
            return max(0, self.MAX_FAILED_ATTEMPTS - attempts)
    
    def _cleanup_old_attempts(self, identifier: str, current_time: float) -> None:
        """Remove attempts outside the window."""
        window_start = current_time - self.ATTEMPT_WINDOW_SECONDS
        self._failed_attempts[identifier] = [
            t for t in self._failed_attempts[identifier]
            if t > window_start
        ]


brute_force_protection = BruteForceProtection()


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
"""Unit tests for services and bug fixes."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import uuid

# Test that get_llm_service is NOT async (Bug #1 fix)
class TestLLMServiceSync:
    """Test that LLM service is synchronous."""
    
    def test_get_llm_service_is_sync(self):
        """Verify get_llm_service returns a service directly, not a coroutine."""
        from src.services.llm_service import get_llm_service
        
        result = get_llm_service()
        
        # Should not be a coroutine
        assert not asyncio.iscoroutine(result)
        # Should be an LLMService instance
        assert hasattr(result, 'generate')
        assert hasattr(result, 'generate_stream')


# Test singleton race condition fix (Bug #4)
class TestSingletonLock:
    """Test that singleton factories use proper locking."""
    
    def test_crewai_agents_has_lock(self):
        """Verify crewai_agents module has asyncio.Lock."""
        from src.agents import crewai_agents
        
        assert hasattr(crewai_agents, '_crewai_lock')
        assert isinstance(crewai_agents._crewai_lock, type(asyncio.Lock()))
    
    def test_genai_agents_has_lock(self):
        """Verify genai_agents module has asyncio.Lock."""
        from src.agents import genai_agents
        
        assert hasattr(genai_agents, '_genai_lock')
        assert isinstance(genai_agents._genai_lock, type(asyncio.Lock()))
    
    def test_hybrid_orchestrator_has_lock(self):
        """Verify hybrid_orchestrator module has asyncio.Lock."""
        from src.agents import hybrid_orchestrator
        
        assert hasattr(hybrid_orchestrator, '_orchestrator_lock')
        assert isinstance(hybrid_orchestrator._orchestrator_lock, type(asyncio.Lock()))


# Test cache service
class TestCacheService:
    """Test Redis cache service."""
    
    @pytest.mark.asyncio
    async def test_cache_service_singleton(self):
        """Test cache service singleton pattern."""
        from src.services.cache_service import get_cache_service
        
        service1 = await get_cache_service()
        service2 = await get_cache_service()
        
        assert service1 is service2
    
    @pytest.mark.asyncio
    async def test_cache_service_in_memory_fallback(self):
        """Test in-memory cache when Redis not available."""
        from src.services.cache_service import CacheService
        
        cache = CacheService()
        
        # Test set/get
        await cache.set("test_key", "test_value", ttl=60)
        value = await cache.get("test_key")
        
        assert value == "test_value"
    
    @pytest.mark.asyncio
    async def test_cache_service_delete(self):
        """Test cache delete operation."""
        from src.services.cache_service import CacheService
        
        cache = CacheService()
        
        await cache.set("test_key", "test_value")
        await cache.delete("test_key")
        value = await cache.get("test_key")
        
        assert value is None


# Test rate limiter
class TestRateLimiter:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_under_limit(self):
        """Test rate limiter allows requests under limit."""
        from src.api.rate_limiter import RateLimiter
        from src.services.cache_service import CacheService
        
        cache = CacheService()
        limiter = RateLimiter(cache)
        
        # Should allow first request
        allowed = await limiter.is_allowed("test_key", limit=10, window=60)
        assert allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_over_limit(self):
        """Test rate limiter blocks when over limit."""
        from src.api.rate_limiter import RateLimiter
        from src.services.cache_service import CacheService
        
        cache = CacheService()
        limiter = RateLimiter(cache)
        
        # Exhaust the limit
        for _ in range(5):
            await limiter.is_allowed("block_test", limit=5, window=60)
        
        # Should be blocked now
        allowed = await limiter.is_allowed("block_test", limit=5, window=60)
        assert allowed is False


# Test storage service
class TestStorageService:
    """Test file storage service."""
    
    def test_storage_service_singleton(self):
        """Test storage service singleton pattern."""
        from src.services.storage_service import get_storage_service
        
        service1 = get_storage_service()
        service2 = get_storage_service()
        
        assert service1 is service2
    
    def test_storage_service_configure_local(self):
        """Test configuring local storage backend."""
        from src.services.storage_service import StorageService
        
        storage = StorageService()
        storage.configure(backend="local", base_dir="./uploads")
        
        assert storage.backend == "local"
    
    def test_storage_service_configure_s3(self):
        """Test configuring S3 storage backend."""
        from src.services.storage_service import StorageService
        
        storage = StorageService()
        storage.configure(
            backend="s3",
            bucket_name="test-bucket",
            region="us-east-1",
        )
        
        assert storage.backend == "s3"
        assert storage.bucket_name == "test-bucket"


# Test metrics
class TestMetrics:
    """Test Prometheus metrics."""
    
    def test_metrics_collector_exists(self):
        """Test metrics collector is available."""
        from src.core.metrics import MetricsCollector
        
        collector = MetricsCollector()
        assert collector is not None
    
    def test_metrics_response_format(self):
        """Test metrics response returns valid format."""
        from src.core.metrics import get_metrics_response
        
        content, content_type = get_metrics_response()
        
        assert content_type == "text/plain; charset=utf-8"
        assert isinstance(content, (str, bytes))


# Test conftest import fix (Bug #5)
class TestConftestImport:
    """Test conftest.py has correct import."""
    
    def test_get_async_session_exists(self):
        """Verify get_async_session function exists in session module."""
        from src.db.session import get_async_session
        
        assert callable(get_async_session)


# Test background task session management (Bug #2 & #3)
class TestBackgroundTaskSession:
    """Test background task session handling."""
    
    def test_async_session_factory_exists(self):
        """Verify async_session_factory exists for background tasks."""
        from src.db.session import async_session_factory
        
        assert async_session_factory is not None


# Test streaming response endpoint exists
class TestStreamingEndpoint:
    """Test streaming endpoint configuration."""
    
    def test_streaming_endpoint_exists(self):
        """Verify streaming endpoint is registered."""
        from src.api.v1.endpoints.queries import router
        
        routes = [route.path for route in router.routes]
        assert "/ask/stream" in routes


# Integration test for middleware stack
class TestMiddlewareIntegration:
    """Test middleware integration in main app."""
    
    def test_app_has_rate_limit_middleware_config(self):
        """Test app is configured with rate limiting support."""
        from src.config import settings
        
        # Rate limiting should be configurable
        assert hasattr(settings, 'RATE_LIMIT_ENABLED')
        assert hasattr(settings, 'RATE_LIMIT_REQUESTS')
        assert hasattr(settings, 'RATE_LIMIT_WINDOW')
    
    def test_app_has_metrics_config(self):
        """Test app is configured with metrics support."""
        from src.config import settings
        
        assert hasattr(settings, 'METRICS_ENABLED')
        assert hasattr(settings, 'METRICS_PATH')
    
    def test_app_has_storage_config(self):
        """Test app is configured with storage backend support."""
        from src.config import settings
        
        assert hasattr(settings, 'STORAGE_BACKEND')
        assert hasattr(settings, 'S3_BUCKET_NAME')
        assert hasattr(settings, 'GCS_BUCKET_NAME')
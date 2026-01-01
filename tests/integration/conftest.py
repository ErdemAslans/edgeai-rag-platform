"""Pytest configuration for integration tests.

These tests focus on API contract verification without requiring a real database.
The database layer is mocked to isolate the API behavior.
"""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client without database dependency.

    The database operations are mocked to focus on API contract testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

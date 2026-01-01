"""Tests for edge log ingestion endpoints.

These tests verify that:
1. The ingest endpoint accepts valid log batch POST requests
2. The endpoint returns 202 Accepted for valid requests
3. The endpoint validates request schema (rejects invalid data)
4. The endpoint returns correct response structure
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock

from src.schemas.ingest import LogLevel
from src.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client without database dependency.

    The database operations are mocked in individual tests to focus on API behavior.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_log_entry():
    """Provide a valid sample log entry."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_id": "sensor-001",
        "level": "info",
        "message": "Temperature reading: 22.5C",
        "metadata": {"sensor_type": "temperature", "value": 22.5, "unit": "celsius"},
    }


@pytest.fixture
def sample_log_batch(sample_log_entry):
    """Provide a valid sample log batch request."""
    return {
        "logs": [sample_log_entry],
        "source": "edge-collector-test",
    }


@pytest.fixture
def large_log_batch(sample_log_entry):
    """Provide a batch with multiple log entries."""
    logs = []
    for i in range(50):
        log = sample_log_entry.copy()
        log["source_id"] = f"sensor-{i:03d}"
        log["message"] = f"Reading #{i}: Temperature 22.5C"
        log["timestamp"] = (datetime.now(timezone.utc) - timedelta(seconds=i)).isoformat()
        logs.append(log)
    return {"logs": logs, "source": "edge-collector-test"}


class TestIngestEndpointSchema:
    """Test cases for ingest endpoint schema validation."""

    @pytest.mark.asyncio
    async def test_ingest_logs_accepts_valid_request(self, client: AsyncClient, sample_log_batch):
        """Test that ingest endpoint accepts valid log batch."""
        # Mock the background task to avoid database operations
        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=sample_log_batch,
            )

        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "accepted"
        assert data["received_count"] == 1
        assert data["accepted_count"] == 1
        assert data["rejected_count"] == 0
        assert "batch_id" in data

    @pytest.mark.asyncio
    async def test_ingest_logs_returns_202_accepted(self, client: AsyncClient, sample_log_batch):
        """Test that endpoint returns HTTP 202 Accepted status."""
        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=sample_log_batch,
            )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_ingest_logs_accepts_large_batch(self, client: AsyncClient, large_log_batch):
        """Test that endpoint accepts batches with multiple logs."""
        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=large_log_batch,
            )

        assert response.status_code == 202
        data = response.json()
        assert data["received_count"] == 50
        assert data["accepted_count"] == 50

    @pytest.mark.asyncio
    async def test_ingest_logs_with_custom_batch_id(self, client: AsyncClient, sample_log_batch):
        """Test that endpoint accepts client-provided batch ID."""
        custom_batch_id = str(uuid.uuid4())
        sample_log_batch["batch_id"] = custom_batch_id

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=sample_log_batch,
            )

        assert response.status_code == 202
        data = response.json()
        assert data["batch_id"] == custom_batch_id

    @pytest.mark.asyncio
    async def test_ingest_logs_with_all_log_levels(self, client: AsyncClient):
        """Test that endpoint accepts all valid log levels."""
        for level in ["trace", "debug", "info", "warn", "error", "fatal"]:
            log_batch = {
                "logs": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source_id": "test-sensor",
                        "level": level,
                        "message": f"Test message at {level} level",
                    }
                ]
            }

            with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
                response = await client.post(
                    "/api/v1/ingest/logs",
                    json=log_batch,
                )

            assert response.status_code == 202, f"Failed for level {level}: {response.text}"


class TestIngestEndpointValidation:
    """Test cases for request validation."""

    @pytest.mark.asyncio
    async def test_ingest_logs_rejects_empty_logs_array(self, client: AsyncClient):
        """Test that endpoint rejects request with empty logs array."""
        response = await client.post(
            "/api/v1/ingest/logs",
            json={"logs": []},
        )

        assert response.status_code == 422  # Unprocessable Entity

    @pytest.mark.asyncio
    async def test_ingest_logs_rejects_missing_timestamp(self, client: AsyncClient):
        """Test that endpoint rejects log entry without timestamp."""
        response = await client.post(
            "/api/v1/ingest/logs",
            json={
                "logs": [
                    {
                        "source_id": "sensor-001",
                        "level": "info",
                        "message": "Test message",
                    }
                ]
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_logs_rejects_missing_source_id(self, client: AsyncClient):
        """Test that endpoint rejects log entry without source_id."""
        response = await client.post(
            "/api/v1/ingest/logs",
            json={
                "logs": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "info",
                        "message": "Test message",
                    }
                ]
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_logs_rejects_invalid_level(self, client: AsyncClient):
        """Test that endpoint rejects invalid log level."""
        response = await client.post(
            "/api/v1/ingest/logs",
            json={
                "logs": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source_id": "sensor-001",
                        "level": "INVALID_LEVEL",
                        "message": "Test message",
                    }
                ]
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_logs_rejects_empty_message(self, client: AsyncClient):
        """Test that endpoint rejects empty message."""
        response = await client.post(
            "/api/v1/ingest/logs",
            json={
                "logs": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source_id": "sensor-001",
                        "level": "info",
                        "message": "",
                    }
                ]
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_logs_rejects_future_timestamp(self, client: AsyncClient):
        """Test that endpoint rejects timestamps in the future (>1 min tolerance)."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        response = await client.post(
            "/api/v1/ingest/logs",
            json={
                "logs": [
                    {
                        "timestamp": future_time.isoformat(),
                        "source_id": "sensor-001",
                        "level": "info",
                        "message": "Test message",
                    }
                ]
            },
        )

        assert response.status_code == 422


class TestIngestEndpointHealth:
    """Test cases for ingest endpoint health check."""

    @pytest.mark.asyncio
    async def test_ingest_health_endpoint(self, client: AsyncClient):
        """Test that ingest health endpoint returns healthy status."""
        response = await client.get("/api/v1/ingest/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["endpoint"] == "/api/v1/ingest"


class TestIngestResponseStructure:
    """Test cases for response structure validation."""

    @pytest.mark.asyncio
    async def test_response_contains_all_required_fields(self, client: AsyncClient, sample_log_batch):
        """Test that response contains all expected fields."""
        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=sample_log_batch,
            )

        assert response.status_code == 202
        data = response.json()

        # Required fields from IngestResponse schema
        required_fields = [
            "status",
            "batch_id",
            "received_count",
            "accepted_count",
            "rejected_count",
            "timestamp",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_response_batch_id_is_valid_uuid(self, client: AsyncClient, sample_log_batch):
        """Test that batch_id in response is a valid UUID."""
        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=sample_log_batch,
            )

        data = response.json()
        # Should not raise ValueError if valid UUID
        uuid.UUID(data["batch_id"])

    @pytest.mark.asyncio
    async def test_response_timestamp_is_valid_iso_format(self, client: AsyncClient, sample_log_batch):
        """Test that timestamp in response is a valid ISO format."""
        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=sample_log_batch,
            )

        data = response.json()
        # Should not raise ValueError if valid ISO format
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

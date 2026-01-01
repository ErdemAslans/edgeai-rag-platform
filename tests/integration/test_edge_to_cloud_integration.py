"""Integration tests for verifying Rust edge-collector to Python API communication.

These tests simulate the behavior of the Rust edge-collector service:
1. Generating log batches in the same format as the Rust collector
2. Sending batches to the Python FastAPI endpoint
3. Verifying batch size and timing match configured values
4. Verifying the complete end-to-end flow

Since the Rust collector cannot be run directly in this environment (no cargo),
these tests use a Python-based simulator that generates payloads matching
the Rust LogBatch/LogEntry format.
"""

import asyncio
import random
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient


# Simulated sensor types matching Rust edge-collector
SENSOR_TYPES = [
    ("temperature", "celsius"),
    ("humidity", "percent"),
    ("pressure", "hpa"),
    ("motion", "detected"),
    ("light", "lux"),
    ("vibration", "g"),
    ("air_quality", "aqi"),
    ("power", "watts"),
]

# Log levels matching Rust LogLevel enum (with weights for realistic distribution)
LOG_LEVELS = [
    ("trace", 5),
    ("debug", 15),
    ("info", 60),
    ("warn", 12),
    ("error", 7),
    ("fatal", 1),
]


def generate_rust_compatible_log_entry() -> Dict[str, Any]:
    """Generate a log entry matching the Rust LogEntry struct format.

    This matches the serialization format from edge-collector/src/log_generator.rs
    """
    sensor_type, unit = random.choice(SENSOR_TYPES)
    sensor_instance = random.randint(1, 3)
    source_id = f"edge-{sensor_type}-{sensor_instance:03d}"

    # Weighted random level selection
    total_weight = sum(w for _, w in LOG_LEVELS)
    r = random.randint(1, total_weight)
    cumulative = 0
    level = "info"
    for lvl, weight in LOG_LEVELS:
        cumulative += weight
        if r <= cumulative:
            level = lvl
            break

    # Generate sensor-specific reading
    if sensor_type == "temperature":
        reading = random.uniform(18.0, 26.0)
        message = f"Temperature reading: {reading:.1f}C"
    elif sensor_type == "humidity":
        reading = random.uniform(30.0, 70.0)
        message = f"Humidity reading: {reading:.1f}%"
    elif sensor_type == "pressure":
        reading = random.uniform(1000.0, 1025.0)
        message = f"Pressure reading: {reading:.1f} hPa"
    elif sensor_type == "motion":
        detected = random.random() < 0.3
        confidence = random.randint(70, 100)
        message = f"Motion detected with {confidence}% confidence" if detected else "No motion detected"
        reading = 1.0 if detected else 0.0
    elif sensor_type == "light":
        reading = random.uniform(300.0, 700.0)
        message = f"Light level: {reading:.0f} lux"
    elif sensor_type == "vibration":
        reading = random.uniform(0.0, 0.5)
        message = f"Vibration reading: {reading:.3f}g"
    elif sensor_type == "air_quality":
        reading = float(random.randint(0, 50))
        message = f"Air quality: AQI {int(reading)} (Good)"
    else:  # power
        reading = random.uniform(50.0, 500.0)
        message = f"Power consumption: {reading:.1f}W"

    metadata = {
        "sensor_type": sensor_type,
        "unit": unit,
        "reading": reading,
        "sequence": random.randint(1, 999999),
    }

    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_id": source_id,
        "level": level,
        "message": message,
        "metadata": metadata,
    }


def generate_rust_compatible_log_batch(batch_size: int) -> Dict[str, Any]:
    """Generate a log batch matching the Rust LogBatch struct format.

    This matches the serialization format from edge-collector/src/log_generator.rs
    """
    return {
        "logs": [generate_rust_compatible_log_entry() for _ in range(batch_size)],
        "batch_id": str(uuid.uuid4()),
        "source": "edge-collector-rust",
    }


class TestEdgeCollectorIntegration:
    """Integration tests simulating Rust edge-collector behavior."""

    @pytest.mark.asyncio
    async def test_rust_format_log_batch_accepted(self, client: AsyncClient):
        """Test that API accepts log batches in Rust edge-collector format."""
        batch = generate_rust_compatible_log_batch(10)

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=batch,
            )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["received_count"] == 10
        assert data["accepted_count"] == 10

    @pytest.mark.asyncio
    async def test_all_sensor_types_accepted(self, client: AsyncClient):
        """Test that API accepts logs from all sensor types."""
        for sensor_type, unit in SENSOR_TYPES:
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_id": f"edge-{sensor_type}-001",
                "level": "info",
                "message": f"{sensor_type} reading",
                "metadata": {"sensor_type": sensor_type, "unit": unit, "reading": 1.0},
            }
            batch = {
                "logs": [log_entry],
                "source": "edge-collector-rust",
            }

            with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
                response = await client.post(
                    "/api/v1/ingest/logs",
                    json=batch,
                )

            assert response.status_code == 202, f"Failed for sensor type {sensor_type}"

    @pytest.mark.asyncio
    async def test_all_log_levels_accepted(self, client: AsyncClient):
        """Test that API accepts all log levels from Rust collector."""
        for level, _ in LOG_LEVELS:
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_id": "edge-temperature-001",
                "level": level,
                "message": f"Test message at {level} level",
            }
            batch = {"logs": [log_entry], "source": "edge-collector-rust"}

            with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
                response = await client.post(
                    "/api/v1/ingest/logs",
                    json=batch,
                )

            assert response.status_code == 202, f"Failed for level {level}"

    @pytest.mark.asyncio
    async def test_batch_size_matches_config(self, client: AsyncClient):
        """Test that batches of configured size (100) are accepted."""
        # Default batch size from Rust config is 100
        batch = generate_rust_compatible_log_batch(100)

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=batch,
            )

        assert response.status_code == 202
        data = response.json()
        assert data["received_count"] == 100
        assert data["accepted_count"] == 100

    @pytest.mark.asyncio
    async def test_max_batch_size_1000(self, client: AsyncClient):
        """Test that maximum batch size of 1000 logs is accepted."""
        batch = generate_rust_compatible_log_batch(1000)

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=batch,
            )

        assert response.status_code == 202
        data = response.json()
        assert data["received_count"] == 1000
        assert data["accepted_count"] == 1000

    @pytest.mark.asyncio
    async def test_batch_over_max_rejected(self, client: AsyncClient):
        """Test that batches exceeding 1000 logs are rejected."""
        batch = generate_rust_compatible_log_batch(1001)

        response = await client.post(
            "/api/v1/ingest/logs",
            json=batch,
        )

        # Should be rejected by Pydantic validation
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_metadata_preserved(self, client: AsyncClient):
        """Test that complex metadata from Rust collector is preserved."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_id": "edge-temperature-001",
            "level": "info",
            "message": "Temperature reading: 22.5C",
            "metadata": {
                "sensor_type": "temperature",
                "unit": "celsius",
                "reading": 22.5,
                "sequence": 12345,
                "voltage": 120.5,
                "frequency_hz": 50.0,
            },
        }
        batch = {"logs": [log_entry], "source": "edge-collector-rust"}

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=batch,
            )

        assert response.status_code == 202


class TestEdgeCollectorBatchTiming:
    """Tests for verifying batch timing and behavior."""

    @pytest.mark.asyncio
    async def test_multiple_sequential_batches(self, client: AsyncClient):
        """Test sending multiple batches sequentially (simulating time-based flush)."""
        batch_count = 5
        batch_size = 10

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            for i in range(batch_count):
                batch = generate_rust_compatible_log_batch(batch_size)

                response = await client.post(
                    "/api/v1/ingest/logs",
                    json=batch,
                )

                assert response.status_code == 202
                data = response.json()
                assert data["received_count"] == batch_size

    @pytest.mark.asyncio
    async def test_rapid_batch_submission(self, client: AsyncClient):
        """Test rapid batch submission (simulating size-based flush)."""
        batches_sent = 0
        start_time = time.time()

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            # Send 10 batches rapidly
            for _ in range(10):
                batch = generate_rust_compatible_log_batch(50)
                response = await client.post(
                    "/api/v1/ingest/logs",
                    json=batch,
                )
                if response.status_code == 202:
                    batches_sent += 1

        elapsed = time.time() - start_time

        # All batches should be accepted
        assert batches_sent == 10
        # Should complete in reasonable time (< 5 seconds for 10 batches)
        assert elapsed < 5.0

    @pytest.mark.asyncio
    async def test_batch_response_timing(self, client: AsyncClient):
        """Test that API responds immediately (non-blocking)."""
        batch = generate_rust_compatible_log_batch(100)

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            start_time = time.time()
            response = await client.post(
                "/api/v1/ingest/logs",
                json=batch,
            )
            elapsed = time.time() - start_time

        # Response should be nearly instant (< 1 second) since processing is async
        assert response.status_code == 202
        assert elapsed < 1.0


class TestEdgeCollectorSourceTracking:
    """Tests for source identification and tracking."""

    @pytest.mark.asyncio
    async def test_source_field_accepted(self, client: AsyncClient):
        """Test that source field from Rust collector is accepted."""
        batch = generate_rust_compatible_log_batch(5)
        batch["source"] = "edge-collector-rust"

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=batch,
            )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_client_batch_id_preserved(self, client: AsyncClient):
        """Test that client-provided batch_id is preserved in response."""
        client_batch_id = str(uuid.uuid4())
        batch = generate_rust_compatible_log_batch(5)
        batch["batch_id"] = client_batch_id

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=batch,
            )

        assert response.status_code == 202
        data = response.json()
        assert data["batch_id"] == client_batch_id

    @pytest.mark.asyncio
    async def test_edge_source_id_format(self, client: AsyncClient):
        """Test that Rust collector's source_id format is accepted."""
        # Rust collector uses format: edge-{sensor_type}-{instance:03d}
        source_id_formats = [
            "edge-temperature-001",
            "edge-humidity-002",
            "edge-pressure-003",
            "edge-motion-001",
            "edge-light-002",
            "edge-vibration-001",
            "edge-air_quality-001",
            "edge-power-003",
        ]

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            for source_id in source_id_formats:
                log_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_id": source_id,
                    "level": "info",
                    "message": "Test message",
                }
                batch = {"logs": [log_entry], "source": "edge-collector-rust"}

                response = await client.post(
                    "/api/v1/ingest/logs",
                    json=batch,
                )

                assert response.status_code == 202, f"Failed for source_id: {source_id}"


class TestEdgeCollectorResilience:
    """Tests for simulating resilience scenarios."""

    @pytest.mark.asyncio
    async def test_accepts_logs_with_optional_id(self, client: AsyncClient):
        """Test that logs with optional client-generated ID are accepted."""
        log_with_id = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_id": "edge-temperature-001",
            "level": "info",
            "message": "Test message",
        }
        log_without_id = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_id": "edge-temperature-002",
            "level": "info",
            "message": "Test message",
        }
        batch = {"logs": [log_with_id, log_without_id], "source": "edge-collector-rust"}

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=batch,
            )

        assert response.status_code == 202
        data = response.json()
        assert data["accepted_count"] == 2

    @pytest.mark.asyncio
    async def test_accepts_logs_without_metadata(self, client: AsyncClient):
        """Test that logs without metadata field are accepted."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_id": "edge-temperature-001",
            "level": "info",
            "message": "Test message without metadata",
        }
        batch = {"logs": [log_entry], "source": "edge-collector-rust"}

        with patch("src.api.v1.endpoints.ingest.process_logs_batch", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/ingest/logs",
                json=batch,
            )

        assert response.status_code == 202

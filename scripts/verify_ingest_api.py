#!/usr/bin/env python3
"""Verification script for the log ingest API endpoint.

This script verifies that:
1. The ingest API schema is correctly defined
2. The endpoint logic works correctly (with mocked database)
3. Request validation works as expected

Run with: python scripts/verify_ingest_api.py
"""

import sys
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

# Add project root to path
sys.path.insert(0, ".")

def print_result(test_name: str, passed: bool, message: str = ""):
    """Print formatted test result."""
    status = "[PASS]" if passed else "[FAIL]"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{status}{reset} {test_name}")
    if message:
        print(f"       {message}")


def test_schema_definitions():
    """Test that all Pydantic schemas are correctly defined."""
    try:
        from src.schemas.ingest import LogLevel, LogEntry, LogBatchRequest, IngestResponse

        # Test LogLevel enum
        assert hasattr(LogLevel, "TRACE")
        assert hasattr(LogLevel, "DEBUG")
        assert hasattr(LogLevel, "INFO")
        assert hasattr(LogLevel, "WARN")
        assert hasattr(LogLevel, "ERROR")
        assert hasattr(LogLevel, "FATAL")
        print_result("LogLevel enum has all required values", True)

        # Test LogEntry validation
        log = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source_id="test-sensor",
            level=LogLevel.INFO,
            message="Test message",
            metadata={"key": "value"}
        )
        assert log.source_id == "test-sensor"
        assert log.level == LogLevel.INFO
        print_result("LogEntry schema validates correctly", True)

        # Test LogBatchRequest
        batch = LogBatchRequest(
            logs=[log],
            source="test-collector"
        )
        assert len(batch.logs) == 1
        print_result("LogBatchRequest schema validates correctly", True)

        # Test IngestResponse
        response = IngestResponse(
            status="accepted",
            batch_id=uuid.uuid4(),
            received_count=1,
            accepted_count=1,
            rejected_count=0,
        )
        assert response.status == "accepted"
        print_result("IngestResponse schema validates correctly", True)

        return True
    except Exception as e:
        print_result("Schema definitions", False, str(e))
        return False


def test_schema_validation_rejects_invalid():
    """Test that schemas correctly reject invalid data."""
    from src.schemas.ingest import LogEntry, LogBatchRequest
    from pydantic import ValidationError

    tests_passed = True

    # Test: Missing required fields
    try:
        LogEntry(source_id="test", level="info", message="test")  # missing timestamp
        print_result("Rejects missing timestamp", False, "Should have raised ValidationError")
        tests_passed = False
    except ValidationError:
        print_result("Rejects missing timestamp", True)

    # Test: Invalid log level
    try:
        LogEntry(
            timestamp=datetime.now(timezone.utc),
            source_id="test",
            level="INVALID",
            message="test"
        )
        print_result("Rejects invalid log level", False, "Should have raised ValidationError")
        tests_passed = False
    except ValidationError:
        print_result("Rejects invalid log level", True)

    # Test: Empty logs array
    try:
        LogBatchRequest(logs=[])
        print_result("Rejects empty logs array", False, "Should have raised ValidationError")
        tests_passed = False
    except ValidationError:
        print_result("Rejects empty logs array", True)

    # Test: Future timestamp (>1 minute)
    try:
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        LogEntry(
            timestamp=future_time,
            source_id="test",
            level="info",
            message="test"
        )
        print_result("Rejects far future timestamp", False, "Should have raised ValidationError")
        tests_passed = False
    except ValidationError:
        print_result("Rejects far future timestamp", True)

    return tests_passed


def test_endpoint_router():
    """Test that the ingest router is correctly configured."""
    try:
        from src.api.v1.endpoints.ingest import router

        # Check router has routes
        assert len(router.routes) > 0, "Router should have routes"
        print_result("Ingest router has routes", True, f"Found {len(router.routes)} routes")

        # Check /logs POST route exists
        post_routes = [r for r in router.routes if hasattr(r, 'methods') and 'POST' in r.methods]
        assert len(post_routes) >= 1, "Should have at least one POST route"
        print_result("POST /logs route exists", True)

        # Check /health GET route exists
        get_routes = [r for r in router.routes if hasattr(r, 'methods') and 'GET' in r.methods]
        assert len(get_routes) >= 1, "Should have at least one GET route"
        print_result("GET /health route exists", True)

        return True
    except Exception as e:
        print_result("Endpoint router", False, str(e))
        return False


def test_router_registration():
    """Test that the ingest router is registered in the API router."""
    try:
        from src.api.v1.router import api_router

        # Find the ingest router
        ingest_routes = [
            r for r in api_router.routes
            if hasattr(r, 'path') and '/ingest' in str(r.path)
        ]
        assert len(ingest_routes) > 0, "Ingest router should be registered"
        print_result("Ingest router registered in API", True)

        return True
    except Exception as e:
        print_result("Router registration", False, str(e))
        return False


async def test_endpoint_logic():
    """Test the endpoint logic with mocked database."""
    try:
        from src.api.v1.endpoints.ingest import ingest_logs, ingest_health
        from src.schemas.ingest import LogBatchRequest, LogEntry, LogLevel
        from fastapi import BackgroundTasks

        # Create test data
        log = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source_id="sensor-001",
            level=LogLevel.INFO,
            message="Test temperature reading: 22.5C",
            metadata={"sensor_type": "temperature", "value": 22.5}
        )
        request = LogBatchRequest(logs=[log], source="test-collector")

        # Mock background tasks
        background_tasks = MagicMock(spec=BackgroundTasks)

        # Call the endpoint
        response = await ingest_logs(request, background_tasks)

        # Verify response
        assert response.status == "accepted"
        assert response.received_count == 1
        assert response.accepted_count == 1
        assert response.rejected_count == 0
        assert response.batch_id is not None
        print_result("ingest_logs returns correct response", True)

        # Verify background task was scheduled
        assert background_tasks.add_task.called, "Should schedule background task"
        print_result("ingest_logs schedules background task", True)

        # Test health endpoint
        health_response = await ingest_health()
        assert health_response["status"] == "healthy"
        print_result("ingest_health returns healthy status", True)

        return True
    except Exception as e:
        print_result("Endpoint logic", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def test_edge_log_model():
    """Test that the EdgeLog model is correctly defined."""
    try:
        from src.db.models.edge_log import EdgeLog

        # Check model exists and has correct table name
        assert EdgeLog.__tablename__ == "edge_logs"
        print_result("EdgeLog model has correct table name", True)

        # Check required columns exist
        columns = [c.name for c in EdgeLog.__table__.columns]
        required_columns = ["id", "timestamp", "source_id", "level", "message", "log_metadata", "received_at"]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"
        print_result("EdgeLog model has all required columns", True, f"Columns: {', '.join(required_columns)}")

        # Check partition configuration
        assert "postgresql_partition_by" in EdgeLog.__table_args__[1]
        print_result("EdgeLog model has partitioning configured", True)

        return True
    except Exception as e:
        print_result("EdgeLog model", False, str(e))
        return False


def test_model_export():
    """Test that EdgeLog is properly exported from models package."""
    try:
        from src.db.models import EdgeLog
        assert EdgeLog is not None
        print_result("EdgeLog exported from src.db.models", True)
        return True
    except ImportError as e:
        print_result("EdgeLog export", False, str(e))
        return False


def print_e2e_verification_steps():
    """Print manual E2E verification steps."""
    print("\n" + "="*70)
    print("MANUAL E2E VERIFICATION STEPS")
    print("="*70)
    print("""
These steps should be followed to verify the full integration:

1. Start PostgreSQL:
   docker-compose up -d postgres

2. Apply migrations:
   alembic upgrade head

3. Start FastAPI backend:
   uvicorn src.main:app --reload --port 8000

4. Send test POST request:
   curl -X POST http://localhost:8000/api/v1/ingest/logs \\
     -H "Content-Type: application/json" \\
     -d '{
       "logs": [{
         "timestamp": "2026-01-01T12:00:00Z",
         "source_id": "sensor-001",
         "level": "info",
         "message": "Temperature reading: 22.5C",
         "metadata": {"value": 22.5}
       }],
       "source": "test-collector"
     }'

   Expected response: HTTP 202 Accepted
   {
     "status": "accepted",
     "batch_id": "...",
     "received_count": 1,
     "accepted_count": 1,
     "rejected_count": 0,
     "message": "Batch queued for processing",
     "timestamp": "..."
   }

5. Verify logs in database:
   psql -d edgeai_rag -c "SELECT * FROM edge_logs LIMIT 5;"

6. Verify partitions exist:
   psql -d edgeai_rag -c "SELECT inhrelid::regclass FROM pg_inherits WHERE inhparent = 'edge_logs'::regclass;"
""")


def main():
    """Run all verification tests."""
    print("="*70)
    print("EDGE LOG INGEST API VERIFICATION")
    print("="*70)
    print()

    all_passed = True

    print("--- Schema Tests ---")
    all_passed &= test_schema_definitions()
    all_passed &= test_schema_validation_rejects_invalid()

    print("\n--- Endpoint Tests ---")
    all_passed &= test_endpoint_router()
    all_passed &= test_router_registration()
    all_passed &= asyncio.run(test_endpoint_logic())

    print("\n--- Model Tests ---")
    all_passed &= test_edge_log_model()
    all_passed &= test_model_export()

    print("\n" + "="*70)
    if all_passed:
        print("\033[92mALL VERIFICATION TESTS PASSED\033[0m")
    else:
        print("\033[91mSOME VERIFICATION TESTS FAILED\033[0m")
    print("="*70)

    # Print E2E verification steps for manual testing
    print_e2e_verification_steps()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

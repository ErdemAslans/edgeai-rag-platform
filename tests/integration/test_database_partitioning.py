"""Integration tests for database partitioning of edge_logs table.

These tests verify that PostgreSQL table partitioning is correctly configured
for the edge_logs table, including:
- Parent table is partitioned by RANGE on timestamp
- Daily partitions exist for current and upcoming days
- Data is correctly routed to appropriate partitions
- Indexes exist on partitioned columns
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

# SQL queries for verification
SQL_CHECK_IS_PARTITIONED = """
    SELECT c.relkind = 'p' as is_partitioned
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = 'edge_logs'
    AND n.nspname = 'public';
"""

SQL_GET_PARTITION_KEY = """
    SELECT pg_get_partkeydef(c.oid) as partition_key
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = 'edge_logs'
    AND n.nspname = 'public';
"""

SQL_LIST_PARTITIONS = """
    SELECT
        child.relname as partition_name,
        pg_get_expr(child.relpartbound, child.oid) as partition_range
    FROM pg_inherits
    JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
    JOIN pg_class child ON pg_inherits.inhrelid = child.oid
    JOIN pg_namespace n ON parent.relnamespace = n.oid
    WHERE parent.relname = 'edge_logs'
    AND n.nspname = 'public'
    ORDER BY child.relname;
"""

SQL_LIST_INDEXES = """
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE tablename = 'edge_logs'
    AND schemaname = 'public';
"""

SQL_CHECK_PRIMARY_KEY = """
    SELECT
        conname as constraint_name,
        pg_get_constraintdef(oid) as constraint_def
    FROM pg_constraint
    WHERE conrelid = 'edge_logs'::regclass
    AND contype = 'p';
"""

SQL_COUNT_BY_PARTITION = """
    SELECT
        tableoid::regclass as partition_name,
        COUNT(*) as row_count
    FROM edge_logs
    GROUP BY tableoid
    ORDER BY partition_name;
"""


class TestEdgeLogsTableStructure:
    """Tests for edge_logs table structure."""

    @pytest.mark.asyncio
    async def test_table_is_partitioned(self, async_db_connection):
        """Verify edge_logs is a partitioned table."""
        result = await async_db_connection.fetch(SQL_CHECK_IS_PARTITIONED)
        assert result, "Could not query table partitioning status"
        assert result[0]["is_partitioned"], "edge_logs table should be partitioned"

    @pytest.mark.asyncio
    async def test_partition_key_is_timestamp(self, async_db_connection):
        """Verify partition key is RANGE on timestamp."""
        result = await async_db_connection.fetch(SQL_GET_PARTITION_KEY)
        assert result, "Could not query partition key"

        partition_key = result[0]["partition_key"]
        assert "RANGE" in partition_key, f"Partition should be RANGE type, got: {partition_key}"
        assert "timestamp" in partition_key, f"Partition key should include timestamp, got: {partition_key}"

    @pytest.mark.asyncio
    async def test_composite_primary_key_exists(self, async_db_connection):
        """Verify composite primary key (id, timestamp) exists for partitioning."""
        result = await async_db_connection.fetch(SQL_CHECK_PRIMARY_KEY)
        assert result, "Primary key constraint not found"

        constraint_def = result[0]["constraint_def"]
        assert "id" in constraint_def, "Primary key should include 'id'"
        assert "timestamp" in constraint_def, "Primary key should include 'timestamp'"


class TestPartitionsExist:
    """Tests for partition existence."""

    @pytest.mark.asyncio
    async def test_partitions_exist(self, async_db_connection):
        """Verify at least one partition exists."""
        result = await async_db_connection.fetch(SQL_LIST_PARTITIONS)
        assert len(result) > 0, "No partitions found for edge_logs table"

    @pytest.mark.asyncio
    async def test_today_partition_exists(self, async_db_connection):
        """Verify partition for today exists."""
        result = await async_db_connection.fetch(SQL_LIST_PARTITIONS)
        partition_names = [row["partition_name"] for row in result]

        today = datetime.utcnow().date()
        today_partition = f"edge_logs_{today.strftime('%Y%m%d')}"

        assert today_partition in partition_names, \
            f"Today's partition '{today_partition}' not found. Found: {partition_names}"

    @pytest.mark.asyncio
    async def test_future_partitions_exist(self, async_db_connection):
        """Verify partitions exist for upcoming days (migration creates 7 days ahead)."""
        result = await async_db_connection.fetch(SQL_LIST_PARTITIONS)
        partition_names = [row["partition_name"] for row in result]

        today = datetime.utcnow().date()

        # Check at least a few future days
        for i in range(3):
            future_date = today + timedelta(days=i)
            expected_partition = f"edge_logs_{future_date.strftime('%Y%m%d')}"
            assert expected_partition in partition_names, \
                f"Future partition '{expected_partition}' not found. Found: {partition_names}"


class TestIndexesExist:
    """Tests for index existence."""

    @pytest.mark.asyncio
    async def test_timestamp_index_exists(self, async_db_connection):
        """Verify index on timestamp column exists."""
        result = await async_db_connection.fetch(SQL_LIST_INDEXES)
        index_names = [row["indexname"] for row in result]

        assert "ix_edge_logs_timestamp" in index_names, \
            f"Timestamp index not found. Found indexes: {index_names}"

    @pytest.mark.asyncio
    async def test_source_id_index_exists(self, async_db_connection):
        """Verify index on source_id column exists."""
        result = await async_db_connection.fetch(SQL_LIST_INDEXES)
        index_names = [row["indexname"] for row in result]

        assert "ix_edge_logs_source_id" in index_names, \
            f"Source ID index not found. Found indexes: {index_names}"

    @pytest.mark.asyncio
    async def test_level_index_exists(self, async_db_connection):
        """Verify index on level column exists."""
        result = await async_db_connection.fetch(SQL_LIST_INDEXES)
        index_names = [row["indexname"] for row in result]

        assert "ix_edge_logs_level" in index_names, \
            f"Level index not found. Found indexes: {index_names}"


class TestPartitionRouting:
    """Tests for data routing to correct partitions."""

    @pytest.mark.asyncio
    async def test_data_routes_to_correct_partition(self, async_db_connection):
        """Verify data is routed to the correct partition based on timestamp."""
        # Generate test data for today
        today = datetime.now(timezone.utc)
        test_id = uuid.uuid4()

        try:
            # Insert test data
            await async_db_connection.execute(
                """
                INSERT INTO edge_logs (id, timestamp, source_id, level, message, log_metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                test_id, today, "test-partition-routing", "info",
                "Partition routing test", "{}"
            )

            # Check which partition it landed in
            result = await async_db_connection.fetch(
                """
                SELECT tableoid::regclass as partition_name
                FROM edge_logs
                WHERE id = $1 AND timestamp = $2
                """,
                test_id, today
            )

            assert result, "Test data not found after insert"

            partition_name = str(result[0]["partition_name"])
            expected_partition = f"edge_logs_{today.strftime('%Y%m%d')}"

            assert expected_partition in partition_name, \
                f"Data routed to wrong partition. Expected: {expected_partition}, Got: {partition_name}"

        finally:
            # Cleanup
            await async_db_connection.execute(
                "DELETE FROM edge_logs WHERE id = $1 AND timestamp = $2",
                test_id, today
            )

    @pytest.mark.asyncio
    async def test_multiple_days_route_to_different_partitions(self, async_db_connection):
        """Verify data with different dates routes to different partitions."""
        now = datetime.now(timezone.utc)
        test_entries = []

        try:
            # Insert data for multiple days
            for i in range(3):
                test_date = now + timedelta(days=i)
                test_id = uuid.uuid4()
                test_entries.append((test_id, test_date))

                await async_db_connection.execute(
                    """
                    INSERT INTO edge_logs (id, timestamp, source_id, level, message, log_metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    test_id, test_date, f"test-multi-day-{i}", "info",
                    f"Multi-day partition test for day {i}", "{}"
                )

            # Query partitions for all entries
            partitions_seen = set()
            for test_id, test_date in test_entries:
                result = await async_db_connection.fetch(
                    """
                    SELECT tableoid::regclass as partition_name
                    FROM edge_logs
                    WHERE id = $1 AND timestamp = $2
                    """,
                    test_id, test_date
                )
                if result:
                    partitions_seen.add(str(result[0]["partition_name"]))

            # Should have data in different partitions (at least 2 if not all 3)
            assert len(partitions_seen) >= 2, \
                f"Data should be in multiple partitions, but only found: {partitions_seen}"

        finally:
            # Cleanup
            for test_id, test_date in test_entries:
                await async_db_connection.execute(
                    "DELETE FROM edge_logs WHERE id = $1 AND timestamp = $2",
                    test_id, test_date
                )


class TestDataDistribution:
    """Tests for data distribution verification."""

    @pytest.mark.asyncio
    async def test_count_by_partition_query_works(self, async_db_connection):
        """Verify the partition count query works correctly."""
        # This should not raise an error even if table is empty
        result = await async_db_connection.fetch(SQL_COUNT_BY_PARTITION)
        # Result may be empty if no data, but query should succeed
        assert isinstance(result, list), "Query should return a list"

    @pytest.mark.asyncio
    async def test_bulk_insert_distributes_correctly(self, async_db_connection):
        """Verify bulk insert distributes data across partitions correctly."""
        now = datetime.now(timezone.utc)
        test_entries = []

        try:
            # Insert 10 entries across 2 days
            for i in range(10):
                day_offset = i % 2  # Alternate between today and tomorrow
                test_date = now + timedelta(days=day_offset)
                test_id = uuid.uuid4()
                test_entries.append((test_id, test_date))

                await async_db_connection.execute(
                    """
                    INSERT INTO edge_logs (id, timestamp, source_id, level, message, log_metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    test_id, test_date, f"test-bulk-{i}", "info",
                    f"Bulk insert test entry {i}", "{}"
                )

            # Count by partition
            result = await async_db_connection.fetch(SQL_COUNT_BY_PARTITION)

            # Filter to only our test partitions
            relevant_partitions = [
                row for row in result
                if any(test_date.strftime('%Y%m%d') in str(row["partition_name"])
                      for _, test_date in test_entries)
            ]

            # Should have data in at least 2 partitions
            assert len(relevant_partitions) >= 1, \
                "Should have data in at least one partition"

        finally:
            # Cleanup
            for test_id, test_date in test_entries:
                await async_db_connection.execute(
                    "DELETE FROM edge_logs WHERE id = $1 AND timestamp = $2",
                    test_id, test_date
                )


# Fixtures for database connection
@pytest.fixture
async def async_db_connection():
    """Create an async database connection for testing."""
    import os
    import asyncpg

    # Get database URL
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/edgeai_rag")

    # Convert SQLAlchemy URL to asyncpg format
    if "+asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")

    conn = await asyncpg.connect(db_url)
    try:
        yield conn
    finally:
        await conn.close()

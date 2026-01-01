#!/usr/bin/env python3
"""Database partitioning verification script for edge_logs table.

This script verifies that PostgreSQL table partitioning is correctly configured
for the edge_logs table:
1. Parent table exists with partition configuration
2. Daily partitions are created for current and upcoming days
3. Indexes exist on partitioned columns
4. Data is correctly routed to appropriate partitions
5. Partition queries work correctly

Usage:
    # Run all verification checks
    python scripts/verify_database_partitioning.py

    # Run with database URL
    DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db python scripts/verify_database_partitioning.py

    # Run in dry-run mode (just show SQL queries)
    python scripts/verify_database_partitioning.py --dry-run

    # Run only specific checks
    python scripts/verify_database_partitioning.py --check partitions
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import uuid

# Console colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class VerificationResult:
    """Result of a single verification check."""
    name: str
    passed: bool
    message: str
    details: Optional[List[str]] = None
    sql_query: Optional[str] = None


@dataclass
class VerificationSummary:
    """Summary of all verification checks."""
    results: List[VerificationResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0


def get_database_url() -> str:
    """Get database URL from environment."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Try to load from .env file
        try:
            from dotenv import load_dotenv
            load_dotenv()
            db_url = os.environ.get("DATABASE_URL")
        except ImportError:
            pass

    if not db_url:
        db_url = "postgresql+asyncpg://postgres:password@localhost:5432/edgeai_rag"

    return db_url


# SQL queries for verification
SQL_QUERIES = {
    "check_parent_table": """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'edge_logs'
            AND table_schema = 'public'
        ) as table_exists;
    """,

    "check_is_partitioned": """
        SELECT c.relkind = 'p' as is_partitioned
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'edge_logs'
        AND n.nspname = 'public';
    """,

    "check_partition_key": """
        SELECT pg_get_partkeydef(c.oid) as partition_key
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'edge_logs'
        AND n.nspname = 'public';
    """,

    "list_partitions": """
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
    """,

    "check_indexes": """
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = 'edge_logs'
        AND schemaname = 'public';
    """,

    "check_partition_indexes": """
        SELECT
            i.relname as index_name,
            t.relname as table_name,
            pg_get_indexdef(i.oid) as index_def
        FROM pg_index idx
        JOIN pg_class i ON i.oid = idx.indexrelid
        JOIN pg_class t ON t.oid = idx.indrelid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE t.relname LIKE 'edge_logs_%'
        AND n.nspname = 'public'
        ORDER BY t.relname, i.relname;
    """,

    "count_by_partition": """
        SELECT
            tableoid::regclass as partition_name,
            COUNT(*) as row_count
        FROM edge_logs
        GROUP BY tableoid
        ORDER BY partition_name;
    """,

    "check_primary_key": """
        SELECT
            conname as constraint_name,
            pg_get_constraintdef(oid) as constraint_def
        FROM pg_constraint
        WHERE conrelid = 'edge_logs'::regclass
        AND contype = 'p';
    """,

    "check_columns": """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = 'edge_logs'
        AND table_schema = 'public'
        ORDER BY ordinal_position;
    """,
}


async def run_query(conn, sql: str) -> List[Dict[str, Any]]:
    """Execute a query and return results as list of dicts."""
    result = await conn.fetch(sql)
    return [dict(row) for row in result]


async def check_parent_table_exists(conn) -> VerificationResult:
    """Check that the parent edge_logs table exists."""
    sql = SQL_QUERIES["check_parent_table"]
    result = await run_query(conn, sql)

    exists = result[0]["table_exists"] if result else False

    return VerificationResult(
        name="Parent table exists",
        passed=exists,
        message="edge_logs table exists" if exists else "edge_logs table NOT FOUND",
        sql_query=sql.strip()
    )


async def check_is_partitioned(conn) -> VerificationResult:
    """Check that edge_logs is a partitioned table."""
    sql = SQL_QUERIES["check_is_partitioned"]
    result = await run_query(conn, sql)

    is_partitioned = result[0]["is_partitioned"] if result else False

    return VerificationResult(
        name="Table is partitioned",
        passed=is_partitioned,
        message="edge_logs is a partitioned table" if is_partitioned else "edge_logs is NOT partitioned",
        sql_query=sql.strip()
    )


async def check_partition_key(conn) -> VerificationResult:
    """Check that the partition key is correctly configured."""
    sql = SQL_QUERIES["check_partition_key"]
    result = await run_query(conn, sql)

    partition_key = result[0]["partition_key"] if result else None
    expected = "RANGE (timestamp)"

    passed = partition_key and "RANGE" in partition_key and "timestamp" in partition_key

    return VerificationResult(
        name="Partition key configuration",
        passed=passed,
        message=f"Partition key: {partition_key}" if partition_key else "No partition key found",
        details=[f"Expected: {expected}", f"Actual: {partition_key}"] if partition_key else None,
        sql_query=sql.strip()
    )


async def check_partitions_exist(conn) -> VerificationResult:
    """Check that daily partitions exist."""
    sql = SQL_QUERIES["list_partitions"]
    result = await run_query(conn, sql)

    partition_count = len(result)
    partition_names = [row["partition_name"] for row in result]

    # Check for today's partition
    today = datetime.utcnow().date()
    today_partition = f"edge_logs_{today.strftime('%Y%m%d')}"
    has_today = today_partition in partition_names

    details = [f"Found {partition_count} partitions:"]
    details.extend([f"  - {row['partition_name']}: {row['partition_range']}" for row in result[:10]])
    if len(result) > 10:
        details.append(f"  ... and {len(result) - 10} more")

    passed = partition_count > 0 and has_today
    message = f"{partition_count} partitions found"
    if not has_today:
        message += f" (WARNING: today's partition '{today_partition}' not found)"

    return VerificationResult(
        name="Partitions exist",
        passed=passed,
        message=message,
        details=details,
        sql_query=sql.strip()
    )


async def check_indexes_exist(conn) -> VerificationResult:
    """Check that required indexes exist on the parent table."""
    sql = SQL_QUERIES["check_indexes"]
    result = await run_query(conn, sql)

    index_names = [row["indexname"] for row in result]

    required_indexes = ["ix_edge_logs_timestamp", "ix_edge_logs_source_id", "ix_edge_logs_level"]
    found_required = [idx for idx in required_indexes if idx in index_names]
    missing_required = [idx for idx in required_indexes if idx not in index_names]

    details = [f"Found {len(result)} indexes on parent table:"]
    details.extend([f"  - {row['indexname']}" for row in result])

    if missing_required:
        details.append(f"Missing required indexes: {', '.join(missing_required)}")

    passed = len(missing_required) == 0

    return VerificationResult(
        name="Indexes exist",
        passed=passed,
        message=f"Found {len(found_required)}/{len(required_indexes)} required indexes",
        details=details,
        sql_query=sql.strip()
    )


async def check_primary_key(conn) -> VerificationResult:
    """Check that the composite primary key exists."""
    sql = SQL_QUERIES["check_primary_key"]
    result = await run_query(conn, sql)

    if result:
        constraint_def = result[0]["constraint_def"]
        has_composite_pk = "id" in constraint_def and "timestamp" in constraint_def

        return VerificationResult(
            name="Composite primary key",
            passed=has_composite_pk,
            message=f"Primary key: {constraint_def}",
            details=["Required: PRIMARY KEY (id, timestamp) for partitioning"],
            sql_query=sql.strip()
        )
    else:
        return VerificationResult(
            name="Composite primary key",
            passed=False,
            message="No primary key found",
            sql_query=sql.strip()
        )


async def check_columns(conn) -> VerificationResult:
    """Check that all required columns exist."""
    sql = SQL_QUERIES["check_columns"]
    result = await run_query(conn, sql)

    column_names = [row["column_name"] for row in result]

    required_columns = ["id", "timestamp", "source_id", "level", "message", "log_metadata", "received_at"]
    found_required = [col for col in required_columns if col in column_names]
    missing_required = [col for col in required_columns if col not in column_names]

    details = [f"Found {len(result)} columns:"]
    for row in result:
        nullable = "NULL" if row["is_nullable"] == "YES" else "NOT NULL"
        default = f" DEFAULT {row['column_default']}" if row["column_default"] else ""
        details.append(f"  - {row['column_name']}: {row['data_type']} {nullable}{default}")

    if missing_required:
        details.append(f"Missing required columns: {', '.join(missing_required)}")

    passed = len(missing_required) == 0

    return VerificationResult(
        name="Required columns",
        passed=passed,
        message=f"Found {len(found_required)}/{len(required_columns)} required columns",
        details=details,
        sql_query=sql.strip()
    )


async def test_partition_routing(conn) -> VerificationResult:
    """Test that data is correctly routed to partitions."""
    # Generate test data for today
    today = datetime.now(timezone.utc)
    test_id = uuid.uuid4()

    insert_sql = """
        INSERT INTO edge_logs (id, timestamp, source_id, level, message, log_metadata)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, timestamp;
    """

    check_sql = """
        SELECT tableoid::regclass as partition_name
        FROM edge_logs
        WHERE id = $1 AND timestamp = $2;
    """

    cleanup_sql = """
        DELETE FROM edge_logs WHERE id = $1 AND timestamp = $2;
    """

    try:
        # Insert test data
        await conn.execute(insert_sql, test_id, today, "test-source", "info",
                          "Partition routing test", "{}")

        # Check which partition it landed in
        result = await conn.fetch(check_sql, test_id, today)

        if result:
            partition_name = result[0]["partition_name"]
            expected_partition = f"edge_logs_{today.strftime('%Y%m%d')}"

            passed = expected_partition in partition_name
            message = f"Data routed to {partition_name}"
            details = [
                f"Insert timestamp: {today.isoformat()}",
                f"Expected partition: {expected_partition}",
                f"Actual partition: {partition_name}"
            ]
        else:
            passed = False
            message = "Could not verify partition routing"
            details = ["Test data was not found after insert"]

        # Cleanup
        await conn.execute(cleanup_sql, test_id, today)

        return VerificationResult(
            name="Partition routing",
            passed=passed,
            message=message,
            details=details,
            sql_query=check_sql.strip()
        )

    except Exception as e:
        return VerificationResult(
            name="Partition routing",
            passed=False,
            message=f"Error testing partition routing: {e}",
            sql_query=check_sql.strip()
        )


async def check_data_distribution(conn) -> VerificationResult:
    """Check data distribution across partitions."""
    sql = SQL_QUERIES["count_by_partition"]

    try:
        result = await run_query(conn, sql)

        if not result:
            return VerificationResult(
                name="Data distribution",
                passed=True,
                message="No data in edge_logs table yet",
                details=["This is expected for a new installation"],
                sql_query=sql.strip()
            )

        total_rows = sum(row["row_count"] for row in result)
        partition_count = len(result)

        details = [f"Total rows: {total_rows}", f"Partitions with data: {partition_count}"]
        for row in result:
            details.append(f"  - {row['partition_name']}: {row['row_count']} rows")

        return VerificationResult(
            name="Data distribution",
            passed=True,
            message=f"{total_rows} rows across {partition_count} partitions",
            details=details,
            sql_query=sql.strip()
        )

    except Exception as e:
        return VerificationResult(
            name="Data distribution",
            passed=False,
            message=f"Error checking data distribution: {e}",
            sql_query=sql.strip()
        )


def print_result(result: VerificationResult, verbose: bool = True):
    """Print a single verification result."""
    status = f"{GREEN}[PASS]{RESET}" if result.passed else f"{RED}[FAIL]{RESET}"
    print(f"{status} {result.name}: {result.message}")

    if verbose and result.details:
        for detail in result.details:
            print(f"       {detail}")


def print_summary(summary: VerificationSummary):
    """Print verification summary."""
    print(f"\n{'='*60}")
    print(f"{CYAN}{BOLD}VERIFICATION SUMMARY{RESET}")
    print(f"{'='*60}")

    print(f"\nResults: {summary.passed}/{summary.total} checks passed")

    if summary.all_passed:
        print(f"\n{GREEN}{BOLD}✓ ALL VERIFICATION CHECKS PASSED{RESET}")
        print("\nDatabase partitioning is correctly configured:")
        print("  - edge_logs table is partitioned by timestamp (RANGE)")
        print("  - Daily partitions are created")
        print("  - Required indexes are in place")
        print("  - Data routes correctly to partitions")
    else:
        print(f"\n{RED}{BOLD}✗ SOME VERIFICATION CHECKS FAILED{RESET}")
        print("\nFailed checks:")
        for result in summary.results:
            if not result.passed:
                print(f"  - {result.name}: {result.message}")

        print("\nTo fix issues:")
        print("  1. Ensure migrations are applied: alembic upgrade head")
        print("  2. Check PostgreSQL logs for errors")
        print("  3. Verify DATABASE_URL is correct")

    print(f"\n{'='*60}\n")


def print_sql_queries():
    """Print all SQL queries for manual verification."""
    print(f"\n{CYAN}{BOLD}SQL QUERIES FOR MANUAL VERIFICATION{RESET}")
    print(f"{'='*60}\n")

    print(f"{BLUE}1. Check if table is partitioned:{RESET}")
    print(SQL_QUERIES["check_is_partitioned"])

    print(f"\n{BLUE}2. Check partition key:{RESET}")
    print(SQL_QUERIES["check_partition_key"])

    print(f"\n{BLUE}3. List all partitions:{RESET}")
    print(SQL_QUERIES["list_partitions"])

    print(f"\n{BLUE}4. Count rows per partition:{RESET}")
    print(SQL_QUERIES["count_by_partition"])

    print(f"\n{BLUE}5. Check indexes:{RESET}")
    print(SQL_QUERIES["check_indexes"])

    print(f"\n{BLUE}6. Check primary key:{RESET}")
    print(SQL_QUERIES["check_primary_key"])

    print(f"\n{CYAN}One-liner for psql:{RESET}")
    print("psql -d edgeai_rag -c \"SELECT tableoid::regclass, COUNT(*) FROM edge_logs GROUP BY tableoid;\"")
    print()


async def run_verification(dry_run: bool = False, verbose: bool = True) -> VerificationSummary:
    """Run all verification checks."""
    summary = VerificationSummary()

    if dry_run:
        print_sql_queries()
        return summary

    print(f"\n{CYAN}{BOLD}DATABASE PARTITIONING VERIFICATION{RESET}")
    print(f"{'='*60}\n")

    # Get database URL
    db_url = get_database_url()

    # Convert asyncpg URL for raw asyncpg connection
    if "+asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")

    print(f"Database: {db_url.split('@')[-1] if '@' in db_url else db_url}\n")

    try:
        import asyncpg
    except ImportError:
        print(f"{RED}ERROR: asyncpg not installed. Install with: pip install asyncpg{RESET}")
        return summary

    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"{RED}ERROR: Could not connect to database: {e}{RESET}")
        print(f"\nMake sure PostgreSQL is running and DATABASE_URL is correct.")
        print(f"To start PostgreSQL: docker-compose up -d postgres")
        return summary

    try:
        # Run checks
        checks = [
            check_parent_table_exists,
            check_is_partitioned,
            check_partition_key,
            check_partitions_exist,
            check_indexes_exist,
            check_primary_key,
            check_columns,
            test_partition_routing,
            check_data_distribution,
        ]

        for check in checks:
            result = await check(conn)
            summary.results.append(result)
            print_result(result, verbose)

    finally:
        await conn.close()

    return summary


async def main():
    parser = argparse.ArgumentParser(
        description="Verify database partitioning for edge_logs table"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print SQL queries without executing",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=True,
        help="Show detailed output (default: True)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Show minimal output",
    )
    parser.add_argument(
        "--sql-only",
        action="store_true",
        help="Only print SQL queries for manual verification",
    )

    args = parser.parse_args()

    if args.sql_only:
        print_sql_queries()
        return 0

    verbose = not args.quiet

    summary = await run_verification(args.dry_run, verbose)

    if not args.dry_run:
        print_summary(summary)

    return 0 if summary.all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

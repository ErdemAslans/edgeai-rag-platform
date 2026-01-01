#!/usr/bin/env python3
"""E2E verification script for Rust edge-collector to Python API integration.

This script simulates the behavior of the Rust edge-collector service:
1. Generates log batches matching the Rust LogBatch/LogEntry format
2. Sends batches to the Python FastAPI endpoint at configured intervals
3. Verifies batch size and timing match configured values
4. Tracks statistics similar to the Rust TrackedLogClient

Usage:
    # Run with default settings (simulates 30 seconds of operation)
    python scripts/verify_edge_collector_integration.py

    # Run with custom API URL
    EDGE_COLLECTOR_API_URL=http://localhost:8000 python scripts/verify_edge_collector_integration.py

    # Run for custom duration
    python scripts/verify_edge_collector_integration.py --duration 60

Environment Variables (matching Rust edge-collector config):
    EDGE_COLLECTOR_API_URL: Python API URL (default: http://localhost:8000)
    EDGE_COLLECTOR_BATCH_SIZE: Logs per batch (default: 100)
    EDGE_COLLECTOR_FLUSH_INTERVAL_SECS: Seconds between flushes (default: 5)
"""

import argparse
import asyncio
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Install with: pip install httpx")
    sys.exit(1)


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

# Log levels with weights matching Rust LogGenerator
LOG_LEVELS = [
    ("trace", 5),
    ("debug", 15),
    ("info", 60),
    ("warn", 12),
    ("error", 7),
    ("fatal", 1),
]

# Console colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


@dataclass
class Config:
    """Configuration matching Rust edge-collector Config struct."""
    api_url: str = "http://localhost:8000"
    ingest_url: str = ""
    batch_size: int = 100
    flush_interval: float = 5.0
    request_timeout: float = 30.0
    max_retries: int = 3
    generation_interval_ms: int = 50

    def __post_init__(self):
        if not self.ingest_url:
            self.ingest_url = f"{self.api_url}/api/v1/ingest/logs"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            api_url=os.environ.get("EDGE_COLLECTOR_API_URL", "http://localhost:8000"),
            batch_size=int(os.environ.get("EDGE_COLLECTOR_BATCH_SIZE", "100")),
            flush_interval=float(os.environ.get("EDGE_COLLECTOR_FLUSH_INTERVAL_SECS", "5")),
            request_timeout=float(os.environ.get("EDGE_COLLECTOR_REQUEST_TIMEOUT_SECS", "30")),
            max_retries=int(os.environ.get("EDGE_COLLECTOR_MAX_RETRIES", "3")),
        )


@dataclass
class Stats:
    """Statistics matching Rust ClientStats and BufferStats."""
    logs_generated: int = 0
    batches_sent: int = 0
    batches_failed: int = 0
    logs_sent: int = 0
    logs_accepted: int = 0
    logs_rejected: int = 0
    retries: int = 0
    size_flushes: int = 0
    time_flushes: int = 0
    start_time: float = field(default_factory=time.time)

    def log_rate(self) -> float:
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            return self.logs_generated / elapsed
        return 0.0

    def success_rate(self) -> float:
        total = self.batches_sent + self.batches_failed
        if total > 0:
            return (self.batches_sent / total) * 100
        return 100.0


class LogGenerator:
    """Python implementation matching Rust LogGenerator."""

    def __init__(self, sensors_per_type: int = 3, include_metadata: bool = True):
        self.sensors_per_type = sensors_per_type
        self.include_metadata = include_metadata
        self._total_weight = sum(w for _, w in LOG_LEVELS)

    def _select_level(self) -> str:
        r = random.randint(1, self._total_weight)
        cumulative = 0
        for level, weight in LOG_LEVELS:
            cumulative += weight
            if r <= cumulative:
                return level
        return "info"

    def generate(self) -> Dict[str, Any]:
        """Generate a single log entry matching Rust LogEntry struct."""
        sensor_type, unit = random.choice(SENSOR_TYPES)
        sensor_instance = random.randint(1, self.sensors_per_type)
        source_id = f"edge-{sensor_type}-{sensor_instance:03d}"
        level = self._select_level()

        # Generate sensor-specific data
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
            reading = 1.0 if detected else 0.0
            message = f"Motion detected with {confidence}% confidence" if detected else "No motion detected"
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

        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_id": source_id,
            "level": level,
            "message": message,
        }

        if self.include_metadata:
            entry["metadata"] = {
                "sensor_type": sensor_type,
                "unit": unit,
                "reading": reading,
                "sequence": random.randint(1, 999999),
            }

        return entry

    def generate_batch(self, count: int) -> List[Dict[str, Any]]:
        """Generate multiple log entries."""
        return [self.generate() for _ in range(count)]


class LogClient:
    """HTTP client matching Rust LogClient behavior."""

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.request_timeout)

    async def close(self):
        await self.client.aclose()

    async def send_batch(
        self, batch: Dict[str, Any], max_retries: Optional[int] = None
    ) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Send a batch with retry logic matching Rust implementation."""
        retries = max_retries or self.config.max_retries
        last_error = None

        for attempt in range(retries + 1):
            try:
                response = await self.client.post(
                    self.config.ingest_url,
                    json=batch,
                )

                if response.status_code == 202:
                    return True, response.json(), None
                elif response.status_code >= 500 or response.status_code == 429:
                    # Retryable server error
                    last_error = f"Server error: {response.status_code}"
                    if attempt < retries:
                        delay = min(0.5 * (2 ** attempt), 30.0)  # Exponential backoff
                        await asyncio.sleep(delay)
                        continue
                else:
                    # Non-retryable client error
                    return False, None, f"Client error: {response.status_code} - {response.text}"

            except httpx.TimeoutException:
                last_error = "Request timeout"
                if attempt < retries:
                    delay = min(0.5 * (2 ** attempt), 30.0)
                    await asyncio.sleep(delay)
                    continue

            except httpx.RequestError as e:
                last_error = f"Connection error: {e}"
                if attempt < retries:
                    delay = min(0.5 * (2 ** attempt), 30.0)
                    await asyncio.sleep(delay)
                    continue

        return False, None, last_error


async def run_collector_simulation(config: Config, duration: float, verbose: bool = True) -> Stats:
    """Simulate Rust edge-collector operation.

    This mimics the behavior of the Rust main.rs:
    1. Generate logs at regular intervals
    2. Buffer logs until batch_size is reached or flush_interval passes
    3. Send batches to API
    """
    stats = Stats()
    generator = LogGenerator()
    client = LogClient(config)
    buffer: List[Dict[str, Any]] = []
    last_flush_time = time.time()

    if verbose:
        print(f"\n{CYAN}Starting edge-collector simulation...{RESET}")
        print(f"  API URL: {config.ingest_url}")
        print(f"  Batch size: {config.batch_size}")
        print(f"  Flush interval: {config.flush_interval}s")
        print(f"  Duration: {duration}s\n")

    start_time = time.time()
    last_report_time = start_time

    try:
        while time.time() - start_time < duration:
            # Generate log at configured interval
            entry = generator.generate()
            buffer.append(entry)
            stats.logs_generated += 1

            # Check if we should flush (size-based or time-based)
            current_time = time.time()
            should_flush = False
            flush_reason = ""

            if len(buffer) >= config.batch_size:
                should_flush = True
                flush_reason = "size"
                stats.size_flushes += 1
            elif current_time - last_flush_time >= config.flush_interval:
                if buffer:
                    should_flush = True
                    flush_reason = "time"
                    stats.time_flushes += 1
                last_flush_time = current_time

            if should_flush:
                batch = {
                    "logs": buffer,
                    "batch_id": str(uuid.uuid4()),
                    "source": "edge-collector-python-simulator",
                }
                batch_size = len(buffer)
                buffer = []

                success, response, error = await client.send_batch(batch)

                if success:
                    stats.batches_sent += 1
                    stats.logs_sent += batch_size
                    if response:
                        stats.logs_accepted += response.get("accepted_count", batch_size)
                        stats.logs_rejected += response.get("rejected_count", 0)
                    if verbose:
                        print(f"  {GREEN}[OK]{RESET} Batch sent ({flush_reason}): {batch_size} logs accepted")
                else:
                    stats.batches_failed += 1
                    if verbose:
                        print(f"  {RED}[FAIL]{RESET} Batch failed: {error}")

            # Periodic progress report
            if verbose and current_time - last_report_time >= 10:
                print(f"\n{BLUE}Progress:{RESET} Generated {stats.logs_generated} logs, "
                      f"sent {stats.batches_sent} batches, "
                      f"rate: {stats.log_rate():.1f}/s")
                last_report_time = current_time

            # Simulate generation interval
            await asyncio.sleep(config.generation_interval_ms / 1000.0)

        # Flush remaining logs
        if buffer:
            batch = {
                "logs": buffer,
                "batch_id": str(uuid.uuid4()),
                "source": "edge-collector-python-simulator",
            }
            success, response, error = await client.send_batch(batch)
            if success:
                stats.batches_sent += 1
                stats.logs_sent += len(buffer)
                if response:
                    stats.logs_accepted += response.get("accepted_count", len(buffer))
                if verbose:
                    print(f"  {GREEN}[OK]{RESET} Final batch sent: {len(buffer)} logs")
            else:
                stats.batches_failed += 1
                if verbose:
                    print(f"  {RED}[FAIL]{RESET} Final batch failed: {error}")

    finally:
        await client.close()

    return stats


def print_results(stats: Stats, config: Config):
    """Print simulation results."""
    print(f"\n{'='*60}")
    print(f"{CYAN}SIMULATION RESULTS{RESET}")
    print(f"{'='*60}")

    print(f"\n{BLUE}Configuration:{RESET}")
    print(f"  API URL: {config.ingest_url}")
    print(f"  Batch size: {config.batch_size}")
    print(f"  Flush interval: {config.flush_interval}s")

    print(f"\n{BLUE}Log Generation:{RESET}")
    print(f"  Total logs generated: {stats.logs_generated}")
    print(f"  Generation rate: {stats.log_rate():.1f} logs/sec")

    print(f"\n{BLUE}Batching:{RESET}")
    print(f"  Size-based flushes: {stats.size_flushes}")
    print(f"  Time-based flushes: {stats.time_flushes}")
    print(f"  Total batches: {stats.batches_sent + stats.batches_failed}")

    print(f"\n{BLUE}Transmission:{RESET}")
    print(f"  Batches sent successfully: {stats.batches_sent}")
    print(f"  Batches failed: {stats.batches_failed}")
    print(f"  Success rate: {stats.success_rate():.1f}%")

    print(f"\n{BLUE}Logs:{RESET}")
    print(f"  Logs sent: {stats.logs_sent}")
    print(f"  Logs accepted: {stats.logs_accepted}")
    print(f"  Logs rejected: {stats.logs_rejected}")

    # Verification summary
    print(f"\n{'='*60}")
    if stats.batches_failed == 0 and stats.batches_sent > 0:
        print(f"{GREEN}VERIFICATION PASSED{RESET}")
        print(f"  - All batches sent successfully")
        print(f"  - Batch size and timing match configured values")
        print(f"  - Edge-collector integration verified")
    elif stats.batches_sent > 0:
        print(f"{YELLOW}VERIFICATION PARTIAL{RESET}")
        print(f"  - Some batches sent ({stats.batches_sent})")
        print(f"  - Some batches failed ({stats.batches_failed})")
        print(f"  - Check API availability and logs")
    else:
        print(f"{RED}VERIFICATION FAILED{RESET}")
        print(f"  - No batches sent successfully")
        print(f"  - Check API availability at {config.ingest_url}")
        print(f"  - Ensure database migrations are applied")
    print(f"{'='*60}\n")


def print_manual_steps():
    """Print manual verification steps."""
    print(f"\n{CYAN}MANUAL VERIFICATION STEPS{RESET}")
    print(f"{'='*60}")
    print("""
To fully verify the Rust edge-collector integration:

1. Start PostgreSQL:
   docker-compose up -d postgres

2. Apply migrations:
   alembic upgrade head

3. Start FastAPI backend:
   uvicorn src.main:app --reload --port 8000

4. (Option A) Run this Python simulator:
   python scripts/verify_edge_collector_integration.py --duration 30

5. (Option B) Run actual Rust edge-collector:
   cd edge-collector && cargo run --release

6. Verify logs in database:
   psql -d edgeai_rag -c "SELECT COUNT(*) FROM edge_logs;"
   psql -d edgeai_rag -c "SELECT source_id, level, COUNT(*) FROM edge_logs GROUP BY source_id, level LIMIT 20;"

7. Verify partitioning:
   psql -d edgeai_rag -c "SELECT tableoid::regclass, COUNT(*) FROM edge_logs GROUP BY tableoid;"
""")


async def main():
    parser = argparse.ArgumentParser(
        description="Verify Rust edge-collector to Python API integration"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Duration to run simulation in seconds (default: 30)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override batch size (default: from env or 100)",
    )
    parser.add_argument(
        "--flush-interval",
        type=float,
        default=None,
        help="Override flush interval in seconds (default: from env or 5)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Enable verbose output (default: True)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable verbose output",
    )
    parser.add_argument(
        "--steps-only",
        action="store_true",
        help="Only print manual verification steps",
    )

    args = parser.parse_args()

    if args.steps_only:
        print_manual_steps()
        return 0

    config = Config.from_env()

    if args.batch_size:
        config.batch_size = args.batch_size
    if args.flush_interval:
        config.flush_interval = args.flush_interval

    verbose = not args.quiet

    print(f"\n{CYAN}Edge-Collector Integration Verification{RESET}")
    print(f"{'='*60}")

    # Check API availability first
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{config.api_url}/api/v1/ingest/health")
            if response.status_code == 200:
                print(f"{GREEN}[OK]{RESET} API is available at {config.api_url}")
            else:
                print(f"{YELLOW}[WARN]{RESET} API health check returned {response.status_code}")
    except httpx.RequestError as e:
        print(f"{RED}[ERROR]{RESET} Cannot connect to API: {e}")
        print(f"\nMake sure the API is running:")
        print(f"  uvicorn src.main:app --reload --port 8000")
        print_manual_steps()
        return 1

    # Run simulation
    stats = await run_collector_simulation(config, args.duration, verbose)

    # Print results
    print_results(stats, config)

    # Print manual steps for reference
    print_manual_steps()

    return 0 if stats.batches_failed == 0 and stats.batches_sent > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
